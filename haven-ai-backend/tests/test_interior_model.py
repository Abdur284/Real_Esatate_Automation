"""Layer 1 with the real segmentation model on real room photos
(tests/fixtures/rooms). Skipped when the model files are not installed."""
import os

import pytest
from fastapi.testclient import TestClient

from app.core.auth import optional_user
from app.core.config import settings
from app.main import app
from app.services.interior import service
from app.services.interior.store import store

MODEL = os.path.join(settings.INTERIOR_SEG_MODEL_DIR, "model.onnx")
FIX = os.path.join(os.path.dirname(__file__), "fixtures", "rooms")
pytestmark = pytest.mark.skipif(not os.path.isfile(MODEL), reason="segmentation model not installed")

client = TestClient(app)


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "root", str(tmp_path))
    store._assets.clear()
    service._renders.clear()
    app.dependency_overrides[optional_user] = lambda: None
    yield
    app.dependency_overrides.clear()


def analyse(name):
    with open(os.path.join(FIX, name), "rb") as f:
        r = client.post("/api/interior/scenes", files={"image": (name, f.read(), "image/jpeg")})
    assert r.status_code == 200, r.text
    return r.json()["scene"]


def by_type(scene):
    out = {}
    for o in scene["objects"]:
        out.setdefault(o["type"], []).append(o)
    return out


def test_living_room_sofa_wall_floor():
    scene = analyse("living_sofa.jpg")
    types = by_type(scene)
    assert len(types["sofa"]) == 1
    sofa = types["sofa"][0]
    assert sofa["confidence"] > 0.8 and sofa["placement"] == "floor"
    b = sofa["bounds"]
    assert b["x"] == pytest.approx(0.11, abs=0.04) and b["w"] == pytest.approx(0.79, abs=0.05)
    assert b["y"] + b["h"] == pytest.approx(0.76, abs=0.04)            # sofa stands where its legs are
    assert 1.4 < sofa["dimensions_m"]["width"] < 3.2
    assert {s["type"] for s in scene["surfaces"]} >= {"wall", "floor"}


def test_corner_with_armchair_paintings_rug():
    types = by_type(analyse("armchair_corner.jpg"))
    assert "armchair" in types and types["armchair"][0]["placement"] == "floor"
    assert len(types.get("painting", [])) >= 2
    assert all(p["placement"] == "wall" for p in types["painting"])
    assert "rug" in types
    assert "door" in types and types["door"][0]["capabilities"]["remove"] is False


def test_kitchen_fixtures_and_wall_cabinets():
    scene = analyse("kitchen.jpg")
    types = by_type(scene)
    assert "refrigerator" in types and types["refrigerator"][0]["capabilities"]["move"] is False
    assert len(types.get("stool", [])) >= 2
    assert any(c["placement"] == "wall" for c in types.get("cabinet", []))   # the upper cabinets
    assert "ceiling" in {s["type"] for s in scene["surfaces"]}
    assert len([s for s in scene["surfaces"] if s["type"] == "wall"]) >= 2      # walls split at corners


def test_edit_real_photo_end_to_end():
    scene = analyse("living_sofa.jpg")
    sid = scene["scene_id"]
    r = client.post(f"/api/interior/scenes/{sid}/operations", json={"operation": {
        "operation": "transform_object", "object_id": "sofa_001",
        "changes": {"position": {"x": 0.4, "y": 0.85}}}})
    assert r.status_code == 200
    img = client.get(r.json()["render_url"])
    assert img.status_code == 200 and len(img.content) > 10_000
