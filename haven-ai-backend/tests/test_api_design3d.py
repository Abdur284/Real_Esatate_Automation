"""REST layer: analyze -> from-2d -> GLB download, plus regressions."""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from tests import planfactory as pf
from tests.test_layer2_geometry import plan_one_floor

client = TestClient(app)


@pytest.fixture(scope="module")
def plan_png():
    return pf.png_bytes(pf.draw(pf.simple_house()))


def test_analyze_then_build_then_download(plan_png):
    r = client.post("/api/design/3d/analyze", files={"image": ("plan.png", plan_png, "image/png")},
                    data={"width_ft": "25", "depth_ft": "40", "front": "bottom"})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ANALYZED"

    r = client.post("/api/design/3d/from-2d", json={"plan": body["plan"]})
    assert r.status_code == 200
    built = r.json()
    assert built["status"] == "FEASIBLE"
    glb = built["glb"]
    assert glb["format"] == "glb" and glb["model_url"].startswith("/api/design/3d/models/")
    assert glb["metadata"]["units"] == "m" and glb["metadata"]["rooms"] == 6

    r = client.get(glb["model_url"])
    assert r.status_code == 200
    assert r.headers["content-type"] == "model/gltf-binary"
    assert r.content[:4] == b"glTF"


def test_filename_and_mime_are_not_trusted():
    r = client.post("/api/design/3d/analyze", files={"image": ("plan.png", b"not an image", "image/png")},
                    data={"width_ft": "25"})
    assert r.status_code == 415


def test_analyze_validates_form_fields(plan_png):
    r = client.post("/api/design/3d/analyze", files={"image": ("p.png", plan_png, "image/png")},
                    data={"front": "diagonal"})
    assert r.status_code == 422
    r = client.post("/api/design/3d/analyze", files={"image": ("p.png", plan_png, "image/png")},
                    data={"width_ft": "5000"})
    assert r.status_code == 422
    r = client.post("/api/design/3d/analyze", data={"width_ft": "25"})
    assert r.status_code == 422  # no file


def test_oversized_upload_rejected():
    big = b"\x89PNG\r\n\x1a\n" + b"\x00" * (8 * 1024 * 1024 + 10)
    r = client.post("/api/design/3d/analyze", files={"image": ("big.png", big, "image/png")})
    assert r.status_code == 415
    assert "8 MB" in r.json()["detail"]


def test_unknown_or_malformed_model_id():
    assert client.get("/api/design/3d/models/" + "a" * 32 + ".glb").status_code == 404
    assert client.get("/api/design/3d/models/..%2F..%2Fsecret.glb").status_code == 404


def test_from_2d_plan_and_invalid_plan():
    r = client.post("/api/design/3d/from-2d", json={"plan": plan_one_floor()})
    assert r.json()["status"] == "FEASIBLE" and "glb" in r.json()
    bad = plan_one_floor()
    bad["design"]["ground_floor"]["rooms"][1]["x"] = 5
    r = client.post("/api/design/3d/from-2d", json={"plan": bad})
    assert r.json()["status"] == "NOT_FEASIBLE" and "glb" not in r.json()


def test_text_generation_still_works_and_gains_glb():
    r = client.post("/api/design/3d/generate", json={"prompt": "25 x 50 ft plot, 3 bedrooms, 2 bathrooms, kitchen, TV lounge, double storey"})
    body = r.json()
    assert body["status"] == "FEASIBLE"
    assert client.get(body["glb"]["model_url"]).status_code == 200
    r = client.post("/api/design/3d/generate", json={"prompt": "3 bedrooms"})
    assert r.json()["status"] == "MISSING_DIMENSIONS"
    assert client.post("/api/design/3d/generate", json={"prompt": "  "}).status_code == 422


def test_other_routes_still_registered():
    paths = {r.path for r in app.routes}
    assert {"/api/chat/send", "/api/design/2d/generate", "/api/design/3d/generate-from-image"} <= paths
    assert client.get("/").json()["status"] == "running"
