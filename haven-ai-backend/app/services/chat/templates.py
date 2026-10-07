"""
Deterministic, non-LLM chatbot replies built from module data: used when
Gemini is unreachable, unconfigured or rate-limited, and always for 3D.
"""
from typing import Dict, Optional


def template_response(module: str, module_data: Optional[Dict]) -> str:
    """Deterministic, non-LLM response used when Gemini is unreachable, unconfigured,
    or rate-limited, so the chatbot still answers using the module data already fetched."""
    if module == "general_chat" or not module_data:
        return ("Hello! I am ArchiBot. I can help you with cost estimation, property search, "
                "2D/3D design, and interior design. What would you like to do?")

    if module == "cost_estimation":
        if module_data.get("error") == "CONNECTION_FAILED":
            fallback = module_data.get("fallback_data", {})
            total = fallback.get("total_cost", "N/A")
            return (f"### ⚠️ Live Cost Model Unavailable\n\n"
                    f"The cost estimation service is temporarily unavailable, so here is an "
                    f"estimate based on typical rates instead:\n\n"
                    f"**Estimated total cost: {total}**")

        total = module_data.get("total_cost", "N/A")
        breakdown = module_data.get("breakdown", {})
        breakdown_text = "\n".join([f"- **{k.title()}**: {v}" for k, v in breakdown.items()]) if breakdown else ""
        return (f"### 🏗️ Construction Cost Estimate\n\n"
                f"Estimated total construction cost: **{total}**.\n\n"
                f"{breakdown_text}")

    elif module == "property_rec":
        props = module_data.get("properties", [])
        if not props:
            return "I couldn't find any properties matching that description in our database right now."
        response = "I found these properties in our database for you:\n\n"
        for p in props:
            price = p.get('price', 'N/A')
            if isinstance(price, (int, float)):
                price = f"₹ {price:,}"
            response += f"### {p.get('title')}\n"
            response += f"- **Price**: {price}\n"
            response += f"- **Location**: {p.get('location')}\n"
            response += f"- **Details**: [View Listing](/property/{p.get('id')})\n\n"
        return response

    elif module == "design_2d":
        status = module_data.get("status")
        analysis = module_data.get("analysis") or {}
        if status not in ("FEASIBLE", "FEASIBLE_WITH_TWO_FLOORS"):
            text = f"### 📐 2D Floor Plan: {(status or 'ERROR').replace('_', ' ')}\n\n"
            text += analysis.get("reason") or module_data.get("message", "The floor plan could not be generated.")
            for item in analysis.get("missing_information") or []:
                text += f"\n- Please provide: {item}"
            for item in analysis.get("suggestions") or []:
                text += f"\n- {item}"
            return text

        plot = module_data.get("plot", {})
        design = module_data.get("design", {})
        lines = [
            "### 📐 2D Floor Plan Generated\n",
            f"- **Plot**: {plot.get('width_ft')} x {plot.get('length_ft')} ft ({plot.get('area_sqft')} sqft)",
            f"- **Floors**: {design.get('floors')}\n",
        ]
        for key, label in (("ground_floor", "Ground Floor"), ("first_floor", "First Floor")):
            rooms = (design.get(key) or {}).get("rooms") or []
            if not rooms:
                continue
            lines.append(f"**{label}**")
            for room in rooms:
                lines.append(f"- {room.get('name')} — {room.get('width')}x{room.get('length')} ft")
            lines.append("")
        if not (module_data.get("validation") or {}).get("passed", True):
            lines.append("⚠️ _The layout failed some automatic checks; see the 2D Design page for details._")
        lines.append("_Open the 2D Design page to view the drawn floor plan._")
        return "\n".join(lines)

    elif module == "design_3d":
        status = module_data.get("status")
        if status != "FEASIBLE":
            text = f"### 🏛️ 3D Model: {(status or 'NOT_FEASIBLE').replace('_', ' ')}\n\n"
            text += module_data.get("message", "The requested 3D model could not be generated.")
            if module_data.get("suggestion"):
                text += f"\n\n**Suggestion:** {module_data['suggestion']}"
            return text

        model = module_data.get("model", {})
        totals = model.get("totals", {})
        lines = [
            f"### 🏛️ 3D Model Generated\n",
            f"- **Storeys**: {totals.get('storeys')}",
            f"- **Covered area**: {totals.get('covered_area_sqft')} sqft",
            f"- **Building height**: {totals.get('building_height_ft')} ft\n",
        ]
        for storey in model.get("storeys", []):
            lines.append(f"**{storey['label']}** ({storey['covered_area_sqft']:g} sqft)")
            for room in storey["rooms"]:
                lines.append(f"- {room['label']} — {room['width']:g}x{room['depth']:g} ft")
            lines.append("")
        lines.append("_Open the 3D Design page to explore the model interactively._")
        return "\n".join(lines)

    elif module == "interior_design":
        furniture_list = "\n".join([f"- {f}" for f in module_data.get("furniture_recommendations", [])])
        return (f"Here is your interior design styling:\n"
                f"- **Theme**: {module_data.get('theme')}\n"
                f"- **Colors**: {', '.join(module_data.get('color_palette', []))}\n\n"
                f"### Furniture Recommendations:\n{furniture_list}")

    return "I processed your request, but couldn't format the response correctly."
