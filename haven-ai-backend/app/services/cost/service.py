"""
Entry point for the construction cost estimation module.

Wraps the trained hybrid estimator defined in
    ml_models/construction_cost_estimation.py
and exposes a single estimate_cost(text) used by the REST endpoint and the
centralized chatbot.

The heavy ML stack (xgboost / scikit-learn) and the trained model file are
OPTIONAL at runtime: if either is missing, callers get CostModelUnavailable and
fall back to the built-in typical-rate estimate, exactly like the other
modules degrade when their service is unreachable. The trained model is loaded
once, lazily, on the first estimate (not at import), so a server without the
model still starts and serves every other endpoint.

Drop the model file trained in Colab at:
    haven-ai-backend/ml_models/xgb_cost_model.pkl
or point COST_MODEL_PATH at it.
"""
import importlib.util
import logging
import os
import threading
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# .../haven-ai-backend/app/services/cost/service.py -> parents[3] == haven-ai-backend
_BACKEND_ROOT = Path(__file__).resolve().parents[3]
_MODEL_SCRIPT = _BACKEND_ROOT / "ml_models" / "construction_cost_estimation.py"
_MODEL_PATH = os.getenv("COST_MODEL_PATH",
                        str(_BACKEND_ROOT / "ml_models" / "xgb_cost_model.pkl"))

_lock = threading.Lock()
_system = None                       # cached ConstructionCostSystem instance
_load_error: Optional[str] = None    # remembered so we don't retry a hopeless load every call

# Internal breakdown keys -> human labels for the API/chat response.
_CSI_LABELS = {
    'excavation':    'Earthwork',
    'concrete_rcc':  'Concrete & RCC',
    'formwork':      'Formwork',
    'rebar':         'Reinforcement',
    'masonry':       'Masonry',
    'woodwork':      'Woodwork',
    'roofing':       'Roofing',
    'doors_windows': 'Doors & Windows',
    'finishes':      'Finishes',
    'plumbing':      'Plumbing',
    'electrical':    'Electrical',
}


class CostModelUnavailable(RuntimeError):
    """Raised when the ML stack or the trained model file is not present."""


def is_available() -> bool:
    """True if a real estimate can be produced (model present + loadable)."""
    try:
        _load_system()
        return True
    except CostModelUnavailable:
        return False


def _load_system():
    """Load (once) the ConstructionCostSystem and its trained .pkl."""
    global _system, _load_error
    if _system is not None:
        return _system
    with _lock:
        if _system is not None:
            return _system
        if _load_error is not None:
            raise CostModelUnavailable(_load_error)
        try:
            if not _MODEL_SCRIPT.exists():
                raise CostModelUnavailable(f"model script not found at {_MODEL_SCRIPT}")
            if not os.path.exists(_MODEL_PATH):
                raise CostModelUnavailable(
                    f"trained model not found at {_MODEL_PATH} -- train it in Colab "
                    f"and place xgb_cost_model.pkl in haven-ai-backend/ml_models/")
            spec = importlib.util.spec_from_file_location(
                "construction_cost_estimation", _MODEL_SCRIPT)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)  # imports xgboost/sklearn here
            system = module.ConstructionCostSystem(model_path=_MODEL_PATH)
            system.load()
            _system = system
            logger.info("Cost model loaded from %s", _MODEL_PATH)
            return _system
        except CostModelUnavailable as exc:
            _load_error = str(exc)
            logger.warning("Cost model unavailable: %s", _load_error)
            raise
        except Exception as exc:  # missing xgboost/sklearn, corrupt pkl, version skew
            _load_error = f"{type(exc).__name__}: {exc}"
            logger.exception("Cost model failed to load")
            raise CostModelUnavailable(_load_error)


def estimate_cost(text: str) -> Dict:
    """Natural-language brief -> structured cost estimate (JSON-serialisable).

    Raises CostModelUnavailable if the model/ML stack is not installed; the
    caller is expected to fall back to a typical-rate estimate.
    """
    if not text or not text.strip():
        raise ValueError("text must not be empty")
    system = _load_system()
    return _to_payload(system.estimate(text.strip()))


def _pkr(n) -> str:
    return f"PKR {int(round(float(n))):,}"


def _recommendations(features: Dict, rule: Dict) -> List[str]:
    tips: List[str] = []
    bd = rule.get("breakdown", {})
    direct = rule.get("direct_cost", 0) or 1
    if bd.get("finishes", 0) / direct > 0.20:
        tips.append("Finishes are a large share of the cost -- choosing mid-range tile "
                    "and paint over premium can save 8-12%.")
    if bd.get("rebar", 0) / direct > 0.20:
        tips.append("Steel is a major driver -- buying rebar in bulk and locking the rate "
                    "early protects against price swings.")
    if float(features.get("floors", 1)) >= 2:
        tips.append("A multi-storey layout shares foundation and roof cost across floors, "
                    "lowering the per-sqft rate versus a single storey.")
    tips.append("Build during the off-season (Oct-Feb) for lower labour rates.")
    return tips[:4]


def _to_payload(result: Dict) -> Dict:
    """Shape the raw system.estimate() output into the response used by the REST
    endpoint and the chatbot template (which reads total_cost / breakdown /
    cost_per_sqft / recommendations)."""
    h = result["hybrid_result"]
    r = result["rule_result"]
    f = result["features"]
    s = result["source"]

    breakdown = {
        _CSI_LABELS.get(k, k.replace("_", " ").title()): _pkr(v)
        for k, v in r["breakdown"].items()
    }

    return {
        "status": "OK",
        "input": result.get("input"),
        "total_cost": _pkr(h["final_cost"]),
        "total_cost_value": h["final_cost"],
        "cost_range": {
            "low": h["low_estimate"],
            "high": h["high_estimate"],
            "display": f"{_pkr(h['low_estimate'])} - {_pkr(h['high_estimate'])}",
        },
        "cost_per_sqft": _pkr(r["per_sqft"]),
        "total_built_sqft": r["total_built_sqft"],
        "breakdown": breakdown,
        "features": {k: f.get(k) for k in (
            "area_sqft", "floors", "bedrooms", "bathrooms", "kitchens",
            "other_rooms", "city", "house_style", "tile_type", "door_material")},
        "feature_sources": s,
        "method": {
            "rule_weight": h["alpha_rule"],
            "ml_weight": h["alpha_ml"],
            "rule_estimate": h["base_cost"],
            "ml_estimate": result["ml_prediction"],
            "disagreement_pct": h["disagreement_pct"],
        },
        "warning": h.get("warning"),
        "recommendations": _recommendations(f, r),
        "disclaimer": "Estimate for new construction (grey structure + finishing), "
                      "excluding land. Verify with local contractors.",
    }
