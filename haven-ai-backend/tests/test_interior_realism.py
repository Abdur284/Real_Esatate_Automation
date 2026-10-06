"""Photographic rendering: real 3D models (glTF + PBR textures), the
rasteriser, photographed materials, the room's light, shadows, recolouring
of upholstery only, real-size replacement and the clean floor under removed
furniture. Tests that need the downloaded CC0 assets are skipped when
scripts/fetch_interior_assets.py has not been run."""
import base64
import json
import struct

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.core.auth import optional_user, require_user
from app.main import app
from app.services.interior import geometry, lighting, mesh_render, meshes, pbr, renderer, service
from app.services.interior.camera import Camera
from app.services.interior.library import get_library
from app.services.interior.raster import rasterize
from app.services.interior.store import store
from tests import roomfactory as rf

client = TestClient(app)
installed = pytest.mark.skipif(not (meshes.available("sofa_02") and meshes.available("Sofa_01")),
                               reason="real 3D assets not downloaded")


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "root", str(tmp_path))
    store._assets.clear()
    service._renders.clear()
    monkeypatch.setattr(service, "get_segmenter", lambda: rf.FakeSegmenter())
    app.dependency_overrides[optional_user] = lambda: "alice"
    app.dependency_overrides[require_user] = lambda: "alice"
    yield
    app.dependency_overrides.clear()


def _scene():
    r = client.post("/api/interior/scenes", files={"image": ("room.png", rf.png_bytes(), "image/png")})
    assert r.status_code == 200, r.text
    return r.json()["scene"]


def _op(scene, operation):
    r = client.post(f"/api/interior/scenes/{scene['scene_id']}/operations",
                    json={"operation": operation, "base_version": scene["version"]})
    return r


def _render(scene):
    r = client.get(f"/api/interior/scenes/{scene['scene_id']}/render?v={scene['version']}")
    assert r.status_code == 200
    return cv2.imdecode(np.frombuffer(r.content, np.uint8), cv2.IMREAD_COLOR)


# ---- rasteriser --------------------------------------------------------------------

def test_rasterizer_covers_triangles_and_keeps_the_nearest():
    xy = np.array([[2, 2], [30, 2], [2, 30], [0, 0], [40, 0], [0, 40]], np.float64)
    depth = np.array([1, 1, 1, 2, 2, 2], np.float64)
    tris = np.array([[3, 4, 5], [0, 1, 2]])            # far one first
    tri, bary, z = rasterize(xy, depth, tris, 48, 48)
    assert tri[10, 10] == 1 and z[10, 10] == pytest.approx(1)      # the near triangle wins
    assert tri[3, 33] == 0                                           # only the far one covers this
    assert tri[45, 45] == -1 and np.isinf(z[45, 45])
    assert np.allclose(bary[tri >= 0].sum(1), 1, atol=1e-5)
    # coverage ~ area of the big triangle (40 x 40 / 2)
    assert abs((tri >= 0).sum() - 800) < 60


# ---- glTF loading ------------------------------------------------------------------

def _tiny_gltf(folder):
    """A 1.0 x 0.5 x 0.4 m box (w x h x d) with a textured material."""
    x, y, z = 0.5, 0.5, 0.2
    pos = np.array([[-x, 0, -z], [x, 0, -z], [x, y, -z], [-x, y, -z],
                    [-x, 0, z], [x, 0, z], [x, y, z], [-x, y, z]], np.float32)
    uv = np.array([[0, 0], [1, 0], [1, 1], [0, 1]] * 2, np.float32)
    idx = np.array([0, 2, 1, 0, 3, 2, 4, 5, 6, 4, 6, 7, 0, 1, 5, 0, 5, 4,
                    3, 7, 6, 3, 6, 2, 0, 4, 7, 0, 7, 3, 1, 2, 6, 1, 6, 5], np.uint16)
    blob = pos.tobytes() + uv.tobytes() + idx.tobytes()
    cv2.imwrite(str(folder / "tex.png"), np.full((8, 8, 3), (40, 90, 200), np.uint8))
    doc = {
        "asset": {"version": "2.0"}, "scene": 0, "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0, "scale": [1, 1, 1]}],
        "meshes": [{"primitives": [{"attributes": {"POSITION": 0, "TEXCOORD_0": 1}, "indices": 2, "material": 0}]}],
        "materials": [{"name": "box", "pbrMetallicRoughness": {"baseColorTexture": {"index": 0},
                                                              "roughnessFactor": 0.6, "metallicFactor": 0.0}}],
        "textures": [{"source": 0}], "images": [{"uri": "tex.png"}],
        "buffers": [{"uri": "box.bin", "byteLength": len(blob)}],
        "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": 96},
                        {"buffer": 0, "byteOffset": 96, "byteLength": 64},
                        {"buffer": 0, "byteOffset": 160, "byteLength": 72}],
        "accessors": [{"bufferView": 0, "componentType": 5126, "count": 8, "type": "VEC3"},
                      {"bufferView": 1, "componentType": 5126, "count": 8, "type": "VEC2"},
                      {"bufferView": 2, "componentType": 5123, "count": 36, "type": "SCALAR"}],
    }
    (folder / "box.bin").write_bytes(blob)
    (folder / "box.gltf").write_text(json.dumps(doc))
    return folder / "box.gltf"


def test_gltf_loads_to_real_size_facing_the_camera(tmp_path):
    mesh = meshes.load_gltf(str(_tiny_gltf(tmp_path)), "box")
    w, d, h = mesh.dims
    assert (round(w, 3), round(d, 3), round(h, 3)) == (1.0, 0.4, 0.5)
    assert mesh.positions[:, 1].min() == pytest.approx(0)          # stands on y = 0
    assert len(mesh.tris) == 12 and mesh.materials[0].rough == pytest.approx(0.6)
    rgb = mesh.materials[0].base[0, 0]
    assert rgb[2] < rgb[0]                                            # BGR file read as RGB
    turned = meshes.load_gltf(str(_tiny_gltf(tmp_path)), "box", yaw_deg=90)
    assert turned.dims[0] == pytest.approx(0.4, abs=1e-3)            # the yaw fix turns it


def test_asset_files_cannot_escape_their_folder(tmp_path):
    path = _tiny_gltf(tmp_path)
    doc = json.loads(path.read_text())
    doc["buffers"][0]["uri"] = "../../secret.bin"
    path.write_text(json.dumps(doc))
    with pytest.raises(ValueError):
        meshes.load_gltf(str(path), "box")
    assert meshes.gltf_path("../x") is None and meshes.gltf_path("a/b") is None


@installed
def test_real_models_have_their_published_size():
    for asset in ("sofa_02", "Sofa_01", "steel_frame_shelves_01"):
        info = json.load(open(f"{meshes.asset_root()}/models/{asset}/info.json"))
        w, d, h = meshes.load(asset, textures=False).dims
        assert max(w, d, h) == pytest.approx(max(info["dimensions_mm"]) / 1000, rel=0.03), asset


# ---- materials ----------------------------------------------------------------------

@pytest.mark.skipif(not pbr.available("wood_oak"), reason="PBR textures not downloaded")
def test_photographed_textures_at_real_scale_and_tint_keeps_detail():
    u, v = np.meshgrid(np.linspace(0, 2, 200), np.linspace(0, 1, 100))
    wood = pbr.photo_albedo("wood_oak", u, v, None)
    assert wood.shape == (100, 200, 3) and wood.std() > 3              # real grain, not flat
    navy = pbr.photo_albedo("fabric", u, v, np.array([87, 62, 44], np.float32))
    plain = pbr.photo_albedo("fabric", u, v, None)
    assert navy.mean(axis=(0, 1))[0] > navy.mean(axis=(0, 1))[2]      # blue-ish now
    assert navy[..., 1].std() > 0.3 * plain[..., 1].std()             # weave still there


# ---- the library ----------------------------------------------------------------------

@installed
def test_library_prefers_real_models_and_understands_realistic():
    lib = get_library()
    r = lib.search("black leather sofa")
    assert r["items"][0]["realism"] == "real" and r["items"][0]["id"] == "ph-sofa-02"
    r = lib.search("realistic wooden coffee table")
    assert r["filters"]["realism"] == "real" and r["total"] > 0
    assert all(i["realism"] == "real" for i in r["items"])
    assert lib.search(realism="procedural", category="sofa")["items"][0]["realism"] == "procedural"
    it = lib.get("ph-chinese-sofa")
    assert lib.materials_for(it) == ["wood_walnut"] and len(it.colors) == 1     # keeps its real finish
    assert len(lib.materials_for(lib.get("ph-sofa-01"))) > 1                   # upholstery can change


# ---- in the room ---------------------------------------------------------------------

@installed
def test_replace_with_real_model_keeps_place_and_uses_measured_size(api):
    s0 = _scene()
    sofa = next(o for o in s0["objects"] if o["type"] == "sofa")
    r = _op(s0, {"operation": "replace_object", "object_id": sofa["id"], "changes": {"library_item": "ph-sofa-02"}})
    assert r.status_code == 200, r.text
    body = r.json()
    new = next(o for o in body["scene"]["objects"] if o.get("replaces"))
    assert new["model"]["kind"] == "mesh" and new["library_item"]["realism"] == "real"
    # measured real size is the basis; it is scaled (uniformly) to fill the old sofa's place
    assert new["fit"]["library_size_m"]["width"] == pytest.approx(1.81, abs=0.01)
    assert new["library_item"]["dimensions"]["width"] == pytest.approx(181, abs=1)
    assert "measured from the 3D model" in body["notes"][0]
    sc = new["transform"]["scale"]
    assert sc["x"] == sc["y"]
    ob, nb = sofa["bounds"], new["bounds"]
    assert nb["w"] == pytest.approx(ob["w"], rel=0.03)
    assert nb["x"] + nb["w"] / 2 == pytest.approx(ob["x"] + ob["w"] / 2, abs=0.01)
    img = _render(body["scene"])
    b = new["bounds"]
    H, W = img.shape[:2]
    crop = img[int(b["y"] * H):int((b["y"] + b["h"]) * H), int(b["x"] * W):int((b["x"] + b["w"]) * W)]
    assert crop.mean() < 110                     # the black leather sofa is there
    # its outline follows the model (convex hull of the real geometry), inside its bounds
    pts = np.array(new["outline"])
    assert len(pts) > 6 and pts[:, 0].min() >= b["x"] - 1e-3


@installed
def test_colour_changes_the_upholstery_not_the_wooden_frame(api):
    s0 = _scene()
    r = _op(s0, {"operation": "add_object", "object": {"library_item": "ph-sofa-01"}})
    assert r.status_code == 200, r.text
    s1 = r.json()["scene"]
    sofa = next(o for o in s1["objects"] if (o.get("model") or {}).get("asset") == "Sofa_01")
    assert sofa["capabilities"]["color"] and "velvet" in sofa["capabilities"]["materials"]
    mesh = meshes.load("Sofa_01")
    lv = mesh_render._stack(mesh, 0, np.array([87, 62, 44], np.float32), sofa["model"]["recolor_mask"], True)
    weight = lv[0][..., 10]
    base = mesh.materials[0].base[..., :3]
    dark = base.mean(2) < 0.12                   # the carved dark wood
    light = base.mean(2) > 0.45                  # the pale fabric
    assert weight[dark].mean() < 0.1 and weight[light].mean() > 0.8
    r = _op(s1, {"operation": "update_object", "object_id": sofa["id"], "changes": {"color": "#2c3e57"}})
    assert r.status_code == 200
    # a real piece without recolourable upholstery keeps its finish
    s2 = r.json()["scene"]
    r = _op(s2, {"operation": "add_object", "object": {"library_item": "ph-chinese-sofa"}})
    wooden = next(o for o in r.json()["scene"]["objects"] if o.get("model") and o["model"].get("asset") == "chinese_sofa")
    assert wooden["capabilities"]["color"] is False
    r = _op(r.json()["scene"], {"operation": "update_object", "object_id": wooden["id"], "changes": {"color": "#ff0000"}})
    assert r.status_code == 422


@installed
def test_model_casts_a_shadow_on_the_floor(api):
    s0 = _scene()
    r = _op(s0, {"operation": "add_object", "object": {"library_item": "ph-side-table-01", "position": {"x": 0.3, "y": 0.85}}})
    assert r.status_code == 200, r.text
    scene = service._with_detections(r.json()["scene"])
    assets = store.assets(scene["scene_id"])
    cam = geometry.camera(scene)
    W, H = geometry.size(scene)
    ctx = renderer.mesh_context(scene, assets, cam, renderer.erased_instances(scene))
    table = next(o for o in scene["objects"] if o["source"] == "model")
    layer = mesh_render.render_layer(table, cam, W, H, ctx["light"])
    assert layer["alpha"].max() > 0.99
    dark, x0, y0 = mesh_render.room_shadow(layer, table, scene, cam, ctx["light"], ctx["behind"],
                                           ctx["receivers"], W, H)
    assert dark.min() < 0.8                   # a real shadow / contact darkening ...
    assert dark.max() == pytest.approx(1.0, abs=0.02)      # ... and lit floor around it


def test_room_light_finds_a_window_and_falls_back_to_overhead():
    scene = {"layout": {"columns": [0, 1], "floor_y": [300 / 480] * 2, "ceiling_y": [-1, -1]},
             "image": {"width": 640, "height": 480}}
    cam = Camera(640, 480, horizon=150, vx=320, fov_deg=65, eye_height_m=1.4)
    img = rf.room_image()
    none = np.zeros(img.shape[:2], bool)
    plain = lighting.estimate(scene, img, none, cam)
    assert plain.source == "overhead" and plain.key_pos[1] > 2.0
    assert plain.key_pos[0] < 0             # the synthetic room is lit from the left
    win = img.copy()
    win[40:200, 60:180] = 255               # a bright window on the left of the wall
    lit = lighting.estimate(scene, win, none, cam)
    assert lit.source == "window" and lit.key_pos[0] < 0 and lit.key_pos[1] >= 1.3
    assert lit.radius > 0.05


@installed
def test_final_render_uses_the_high_quality_assets(api, monkeypatch):
    s0 = _scene()
    r = _op(s0, {"operation": "add_object", "object": {"library_item": "ph-ceramic-vase-01"}})
    seen = []
    real = meshes.load

    def spy(asset, quality="1k", *a, **k):
        seen.append(quality)
        return real(asset, quality, *a, **k)
    monkeypatch.setattr(meshes, "load", spy)
    service.render_scene(r.json()["scene"], 0, "2k")
    assert "2k" in seen


def test_removed_furniture_leaves_clean_straight_floor(api):
    s0 = _scene()
    sofa = next(o for o in s0["objects"] if o["type"] == "sofa")
    r = _op(s0, {"operation": "remove_object", "object_id": sofa["id"]})
    img = _render(r.json()["scene"])
    x0, y0, x1, y1 = rf.SOFA_BOX
    patch = img[rf.SEAM_Y + 4:y1 + 8, x0 + 10:x1 - 10]
    # no green sofa left, and the fill is floor-coloured
    assert rf.color_distance(patch.reshape(-1, 3).mean(0), rf.FLOOR_BGR) < 45
    assert (patch[..., 1].astype(int) - patch[..., 2].astype(int) > 40).mean() < 0.02
