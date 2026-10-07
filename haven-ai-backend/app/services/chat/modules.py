"""
The 5 specialist modules the chatbot routes to. design_2d and design_3d run
in-process; the others call the URL configured in .env, or answer with
sample data when it is MOCK or unreachable.
"""
import asyncio
import logging
import os
from typing import Dict

import httpx

from app.core.firebase import FirebaseUnavailable, get_db, is_configured
from app.services.design2d.service import generate_2d_plan
from app.services.design3d.service import generate_3d_model

logger = logging.getLogger(__name__)

COST_ESTIMATION_API = os.getenv("COST_ESTIMATION_API_URL", "MOCK")
PROPERTY_REC_API     = os.getenv("PROPERTY_REC_API_URL", "MOCK")
DESIGN_2D_API        = os.getenv("DESIGN_2D_API_URL", "MOCK")
DESIGN_3D_API        = os.getenv("DESIGN_3D_API_URL", "MOCK")
INTERIOR_DESIGN_API  = os.getenv("INTERIOR_DESIGN_API_URL", "MOCK")

API_RETRY_ATTEMPTS = 2
API_TIMEOUT_SECONDS = 15.0


async def call_module_api(module: str, params: Dict, user_message: str) -> Dict:
    if module == "design_2d":
        # Gemini-backed planner in this same backend, validated deterministically.
        try:
            return await generate_2d_plan(user_message)
        except Exception as e:
            logger.error(f"design_2d module call failed: {e}")
            return {"status": "ERROR", "message": "The 2D design service could not create a plan right now. "
                                                  "Please try again in a minute."}

    if module == "design_3d":
        # Real deterministic module living in this same backend, so it is called
        # in-process rather than through the HTTP/MOCK dispatch below. Run in a
        # thread because the generator is synchronous CPU work.
        try:
            return await asyncio.to_thread(generate_3d_model, user_message)
        except Exception as e:
            logger.exception("design_3d module call failed")
            return {"status": "ERROR", "message": "The 3D design service could not create a model right now. "
                                                  "Please try again in a minute."}

    api_map = {
        "cost_estimation": COST_ESTIMATION_API,
        "property_rec":    PROPERTY_REC_API,
        "design_2d":       DESIGN_2D_API,
        "design_3d":       DESIGN_3D_API,
        "interior_design": INTERIOR_DESIGN_API,
    }
    url = api_map.get(module)
    if not url:
        return {"error": "UNKNOWN_MODULE"}

    if url == "MOCK":
        logger.info(f"[{module}] Using mock data (MOCK URL configured)")
        return await _mock_module_response(module, params)

    payload = {"text": user_message, "params": params} if module == "cost_estimation" else {"query": user_message, "params": params}

    last_error = None
    for attempt in range(1, API_RETRY_ATTEMPTS + 1):
        try:
            async with httpx.AsyncClient(timeout=API_TIMEOUT_SECONDS) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                return response.json()
        except Exception as e:
            last_error = e
            logger.warning(f"Module API call attempt {attempt} failed [{module}]: {e}")
            if attempt < API_RETRY_ATTEMPTS:
                await asyncio.sleep(0.5 * attempt)

    logger.error(f"Module API call exhausted retries [{module}]: {last_error}")
    return {
        # The URL and the exception stay in the server log: this dict is shown to
        # Gemini and the user, who only need to know the live service is down.
        "error": "CONNECTION_FAILED",
        "fallback_data": await _mock_module_response(module, params)
    }


def _fetch_real_properties_sync(query_params: Dict) -> list:
    """Blocking Firestore call — always run via a thread, never awaited directly."""
    try:
        db = get_db()
        location_q = (query_params.get("location") or "").lower().strip()
        type_q = (query_params.get("property_type") or "").lower().strip()

        # NOTE: not using .where("type", "==", type_q) here — Firestore `type` values
        # aren't guaranteed to be normalized to our lowercase keyword list (e.g. "Villa",
        # "Residential Villa"), so an exact-match filter would silently drop matches.
        # Substring filtering client-side avoids that regression; .limit() keeps the scan
        # bounded rather than reading the whole collection. Revisit with a normalized
        # `type_slug` field + .where() once data is cleaned up, for real scale.
        docs = db.collection("properties").limit(200).stream()

        results = []
        for doc in docs:
            p = doc.to_dict()
            p['id'] = doc.id

            loc = (p.get('location') or '').lower()
            title = (p.get('title') or '').lower()
            ptype = (p.get('type') or '').lower()

            if location_q and location_q not in loc and location_q not in title:
                continue
            if type_q and type_q not in ptype:
                continue

            results.append(p)
            if len(results) >= 3:
                break

        return results
    except FirebaseUnavailable:
        return []
    except Exception as e:
        logger.error(f"Firestore fetch error: {e}")
        return []


async def _fetch_real_properties(query_params: Dict) -> list:
    if not is_configured():
        return []
    return await asyncio.to_thread(_fetch_real_properties_sync, query_params)


async def _mock_module_response(module: str, params: Dict) -> Dict:
    """Fallback logic when external APIs are not reachable."""
    if module == "cost_estimation":
        return {
            "total_cost": "PKR 18,00,000 - 22,00,000",
            "breakdown": {
                "foundation": "PKR 2,50,000",
                "structure": "PKR 6,50,000",
                "roofing": "PKR 1,75,000",
                "finishing": "PKR 5,00,000",
                "labor": "PKR 5,25,000"
            },
            "cost_per_sqft": "PKR 1,800 - 2,200",
            "recommendations": [
                "Use fly ash bricks to save 8-10% on materials",
                "Consider ready-mix concrete for better quality",
                "Plan during off-season (Oct-Feb) for lower labor costs"
            ]
        }
    elif module == "property_rec":
        real_props = await _fetch_real_properties(params)
        if real_props:
            return {"properties": real_props}

        return {
            "properties": [
                {"id": "p1", "title": "3BHK Villa in Whitefield", "price": 8500000,
                 "location": "Whitefield, Bangalore", "area": "1800 sqft",
                 "features": ["Garden", "Parking", "Gated Community"]},
                {"id": "p2", "title": "Modern Apartment in Hinjewadi", "price": 5500000,
                 "location": "Hinjewadi, Pune", "area": "1200 sqft",
                 "features": ["Pool", "Gym", "Security"]},
                {"id": "p3", "title": "2BHK Flat in Andheri", "price": 9500000,
                 "location": "Andheri West, Mumbai", "area": "950 sqft",
                 "features": ["Metro nearby", "Sea facing"]}
            ]
        }

    mocks = {
        "design_2d": {
            "floor_plan_url": "https://via.placeholder.com/800x600.png?text=2D+Floor+Plan",
            "rooms": ["Living Room (18x20)", "Master Bedroom (14x16)", "Bedroom 2 (12x14)",
                      "Kitchen (12x15)", "Bathrooms x2", "Garage (20x22)"],
            "total_area": "2,200 sqft",
            "style": "Open-concept modern"
        },
        "design_3d": {
            "render_url": "https://via.placeholder.com/800x600.png?text=3D+Render",
            "style": "Contemporary",
            "materials": ["Brick facade", "Glass panels", "Metal accents"],
            "views_available": ["Front", "Rear", "Aerial", "Interior"]
        },
        "interior_design": {
            "theme": "Modern Minimalist",
            "color_palette": ["#F5F0EB", "#2C3E50", "#E8D5B7", "#27AE60"],
            "furniture_recommendations": [
                "Scandinavian sofa set - IKEA KIVIK series",
                "Walnut coffee table with storage",
                "Statement pendant light above dining table"
            ],
            "estimated_budget": "PKR 80,000 - 1,50,000"
        }
    }
    return mocks.get(module, {"message": "Module processed successfully."})
