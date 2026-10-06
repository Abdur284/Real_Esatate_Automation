"""Interior Design REST API: upload validation, edit operations, history,
saving/reloading and access control. The ML model is replaced by
FakeSegmenter (known class map); tests with the real model are in
test_interior_model.py."""
import copy

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.core.auth import optional_user, require_user
from app.main import app
from app.services.interior import service
from app.services.interior.designs import MemoryDesigns, get_repository
from app.services.interior.store import store
from tests import roomfactory as rf

client = TestClient(app)


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    """Own storage folder, the fake model, a signed-in user 'alice' and an
    in-memory design repository for every test."""
    monkeypatch.setattr(store, "root", str(tmp_path))
    store._assets.clear()
    service._renders.clear()
    monkeypatch.setattr(service, "get_segmenter", lambda: rf.FakeSegmenter())
    repo = MemoryDesigns()
    user = {"uid": "alice"}
    app.dependency_overrides[optional_user] = lambda: user["uid"]
    app.dependency_overrides[require_user] = lambda: user["uid"] or pytest.fail("not signed in")
    app.dependency_overrides[get_repository] = lambda: repo
    yield {"repo": repo, "user": user}
    app.dependency_overrides.clear()


def upload(data=None, name="room.png", mime="image/png"):
    return client.post("/api/interior/scenes",
                       files={"image": (name, rf.png_bytes() if data is None else data, mime)})


def new_scene():
    r = upload()
    assert r.status_code == 200, r.text
    return r.json()


def op(scene, operation, base=True):
    body = {"operation": operation}
    if base:
        body["base_version"] = scene["version"]
    return client.post(f"/api/interior/scenes/{scene['scene_id']}/operations", json=body)


def obj(scene, oid):
    return next(o for o in scene["objects"] if o["id"] == oid)


# ---- upload -------------------------------------------------------------------

def test_valid_upload_returns_structured_scene():
    body = new_scene()
    scene = body["scene"]
    assert body["can_undo"] is False and body["can_redo"] is False
    assert body["render_url"].startswith(f"/api/interior/scenes/{scene['scene_id']}/render")
    ids = {o["id"] for o in scene["objects"]}
    assert ids == {"sofa_001", "table_001", "vase_001", "painting_001"}
    assert {s["id"] for s in scene["surfaces"]} == {"wall_001", "floor_001"}
    sofa = obj(scene, "sofa_001")
    for key in ("id", "category", "type", "bounds", "outline", "transform", "appearance", "confidence",
                "editable", "original", "capabilities", "dimensions_m"):
        assert key in sofa
    # normalised, resolution-independent coordinates
    b = sofa["bounds"]
    assert b == pytest.approx(sofa["original"]["bbox"], abs=0.01)
    assert b == pytest.approx({"x": 150 / 640, "y": 215 / 480, "w": 300 / 640, "h": 115 / 480}, abs=0.02)
    assert sofa["transform"]["position"] == pytest.approx({"x": 300 / 640, "y": 330 / 480}, abs=0.02)
    assert sofa["capabilities"]["move"] and sofa["capabilities"]["rotate"] == "mirror"
    assert obj(scene, "vase_001")["parent"] == "table_001"


@pytest.mark.parametrize("data,name,mime,status", [
    (b"GIF89a" + b"\x00" * 100, "room.gif", "image/gif", 415),
    (b"not an image at all", "room.png", "image/png", 415),         # declared type is not trusted
    (b"", "room.jpg", "image/jpeg", 415),
    (b"\xff\xd8\xff" + b"\x00" * 50, "room.jpg", "image/jpeg", 415),  # JPEG header, broken body
])
def test_invalid_files_are_rejected(data, name, mime, status):
    r = upload(data, name, mime)
    assert r.status_code == status
    assert "Traceback" not in r.text


def test_filename_is_not_trusted():
    """A real PNG called .gif is accepted: the content decides."""
    assert upload(rf.png_bytes(), "photo.gif", "image/gif").status_code == 200


def test_large_file_rejected():
    big = b"\xff\xd8\xff" + b"\x00" * (10 * 1024 * 1024 + 10)
    r = upload(big, "big.jpg", "image/jpeg")
    assert r.status_code == 413


def test_tiny_image_rejected():
    ok, buf = cv2.imencode(".png", np.full((120, 160, 3), 128, np.uint8))
    r = upload(buf.tobytes())
    assert r.status_code == 422 and "too small" in r.json()["detail"]


def test_dark_image_rejected():
    dark = (rf.room_image().astype(np.float32) * 0.08).astype(np.uint8)
    r = upload(rf.png_bytes(dark))
    assert r.status_code == 422 and "dark" in r.json()["detail"]


def test_blurry_image_rejected():
    blurry = cv2.GaussianBlur(rf.room_image(), (0, 0), 12)
    r = upload(rf.png_bytes(blurry))
    assert r.status_code == 422 and "blurry" in r.json()["detail"]


def test_model_unavailable_is_503(monkeypatch):
    from app.services.interior.segmentation import SegmentationUnavailable

    def missing():
        raise SegmentationUnavailable("no model")
    monkeypatch.setattr(service, "get_segmenter", missing)
    r = upload()
    assert r.status_code == 503 and "not available" in r.json()["detail"]


# ---- operations -----------------------------------------------------------------

def test_recolor_changes_only_the_target():
    scene = new_scene()["scene"]
    r = op(scene, {"operation": "update_object", "object_id": "sofa_001", "changes": {"color": "#222222"}})
    assert r.status_code == 200, r.text
    new = r.json()["scene"]
    assert obj(new, "sofa_001")["appearance"]["color"] == "#222222"
    for o in scene["objects"]:
        if o["id"] != "sofa_001":
            assert obj(new, o["id"]) == o
    assert new["surfaces"] == scene["surfaces"]
    assert new["version"] > scene["version"]


def test_move_updates_position_and_carries_things_on_top():
    scene = new_scene()["scene"]
    table, vase = obj(scene, "table_001"), obj(scene, "vase_001")
    target = {"x": table["transform"]["position"]["x"] - 0.1, "y": table["transform"]["position"]["y"] + 0.05}
    r = op(scene, {"operation": "transform_object", "object_id": "table_001", "changes": {"position": target}})
    assert r.status_code == 200, r.text
    new = r.json()["scene"]
    assert obj(new, "table_001")["transform"]["position"] == pytest.approx(target, abs=1e-3)
    moved_vase = obj(new, "vase_001")["transform"]["position"]
    assert moved_vase["x"] == pytest.approx(vase["transform"]["position"]["x"] - 0.1, abs=1e-3)
    assert obj(new, "sofa_001") == obj(scene, "sofa_001")
    # nearer the camera -> drawn bigger (perspective)
    assert obj(new, "table_001")["bounds"]["w"] > table["bounds"]["w"]


def test_floor_furniture_stays_on_the_floor():
    scene = new_scene()["scene"]
    r = op(scene, {"operation": "transform_object", "object_id": "sofa_001",
                   "changes": {"position": {"x": 0.5, "y": 0.1}}})
    body = r.json()
    assert r.status_code == 200
    assert obj(body["scene"], "sofa_001")["transform"]["position"]["y"] >= rf.SEAM_Y / rf.H - 0.02
    assert any("floor" in n for n in body["notes"])


def test_wall_items_stay_on_the_wall():
    scene = new_scene()["scene"]
    r = op(scene, {"operation": "transform_object", "object_id": "painting_001",
                   "changes": {"position": {"x": 0.5, "y": 0.95}}})
    p = obj(r.json()["scene"], "painting_001")
    assert p["bounds"]["y"] + p["bounds"]["h"] <= rf.SEAM_Y / rf.H + 0.01


def test_resize_limits_and_warnings():
    scene = new_scene()["scene"]
    r = op(scene, {"operation": "transform_object", "object_id": "sofa_001", "changes": {"scale": {"x": 5}}})
    assert r.status_code == 422 and "between" in r.json()["detail"]
    r = op(scene, {"operation": "transform_object", "object_id": "sofa_001", "changes": {"scale": {"x": 1.5}}})
    assert r.status_code == 200
    s = r.json()["scene"]
    assert obj(s, "sofa_001")["transform"]["scale"] == {"x": 1.5, "y": 1.0}
    assert r.json()["notes"] and "unusual" in r.json()["notes"][0]      # a 4+ m sofa
    r = op(s, {"operation": "transform_object", "object_id": "sofa_001", "changes": {"scale": {"z": 2}}})
    assert r.status_code == 422                                         # photo objects have no depth


def test_rotation_rules():
    scene = new_scene()["scene"]
    r = op(scene, {"operation": "transform_object", "object_id": "sofa_001", "changes": {"rotation": 30}})
    assert r.status_code == 422 and "mirrored" in r.json()["detail"]
    r = op(scene, {"operation": "transform_object", "object_id": "sofa_001", "changes": {"flip": True}})
    assert r.status_code == 200 and obj(r.json()["scene"], "sofa_001")["transform"]["flip"] is True
    s = r.json()["scene"]
    r = op(s, {"operation": "transform_object", "object_id": "painting_001", "changes": {"rotation": 10}})
    assert r.status_code == 200 and obj(r.json()["scene"], "painting_001")["transform"]["rotation"] == 10
    s = r.json()["scene"]
    r = op(s, {"operation": "transform_object", "object_id": "painting_001", "changes": {"rotation": 80}})
    assert r.status_code == 422


def test_material_validation():
    scene = new_scene()["scene"]
    r = op(scene, {"operation": "update_object", "object_id": "sofa_001", "changes": {"material": "marble_white"}})
    assert r.status_code == 422
    r = op(scene, {"operation": "update_object", "object_id": "sofa_001", "changes": {"material": "leather"}})
    assert r.status_code == 200
    s = r.json()["scene"]
    r = op(s, {"operation": "update_surface", "surface_id": "floor_001", "changes": {"material": "herringbone"}})
    assert r.status_code == 200
    r = op(r.json()["scene"], {"operation": "update_surface", "surface_id": "wall_001",
                               "changes": {"material": "herringbone"}})
    assert r.status_code == 422
    r = op(scene, {"operation": "update_object", "object_id": "sofa_001", "changes": {"color": "red"}},
           base=False)
    assert r.status_code == 422


def test_unknown_things_are_rejected():
    scene = new_scene()["scene"]
    assert op(scene, {"operation": "remove_object", "object_id": "piano_001"}).status_code == 422
    assert op(scene, {"operation": "explode", "object_id": "sofa_001"}).status_code == 422
    r = op(scene, {"operation": "update_object", "object_id": "sofa_001", "changes": {"price": 3}})
    assert r.status_code == 422


def test_replace_from_library_keeps_place_and_gets_new_id():
    scene = new_scene()["scene"]
    sofa = obj(scene, "sofa_001")
    r = op(scene, {"operation": "replace_object", "object_id": "sofa_001",
                   "changes": {"library_item": "sofa-l-shaped-sectional-sofa", "color": "#3f5e5a"}})
    assert r.status_code == 200, r.text
    body = r.json()
    s = body["scene"]
    new_id = s["last_operation"]["assigned_id"]
    assert new_id == "sofa_002"                                    # a new, unique id
    new = obj(s, new_id)
    assert new["source"] == "model" and new["library_item"]["id"] == "sofa-l-shaped-sectional-sofa"
    assert new["replaces"]["id"] == "sofa_001" and new["appearance"]["color"] == "#3f5e5a"
    # it fills the old sofa's place in the picture, not its own catalogue size (2.8 m)
    ob, nb = sofa["bounds"], new["bounds"]
    assert nb["x"] + nb["w"] / 2 == pytest.approx(ob["x"] + ob["w"] / 2, abs=0.01)
    assert nb["w"] == pytest.approx(ob["w"], rel=0.03)
    # a deep sectional cannot go through the wall: it comes forward, never back
    assert nb["y"] + nb["h"] >= ob["y"] + ob["h"] - 0.01
    assert new["fit"]["mode"] == "match" and new["fit"]["uniform"]
    sc = new["transform"]["scale"]
    assert sc["x"] == sc["y"] and new["dimensions_m"]["width"] != pytest.approx(2.8)
    assert new["capabilities"]["rotate"] == "yaw"
    assert "sofa_001" not in {o["id"] for o in s["objects"]}
    assert {x["id"] for x in s["removed"]} == {"sofa_001"}
    assert "typical size" in body["notes"][0] and "Sized to fill the space of the original sofa" in body["notes"][0]
    for o in scene["objects"]:
        if o["id"] != "sofa_001":
            assert obj(s, o["id"]) == o                               # nothing else changed

    # turn it, then swap it again: the turn is kept
    s = op(s, {"operation": "transform_object", "object_id": new_id, "changes": {"rotation": 30}}).json()["scene"]
    s2 = op(s, {"operation": "replace_object", "object_id": new_id,
                "changes": {"library_item": "sofa-modern-3-seater-sofa"}}).json()["scene"]
    third = obj(s2, s2["last_operation"]["assigned_id"])
    assert third["transform"]["rotation"] == 30

    # undo the second swap, then reset brings back what was replaced first
    s = client.post(f"/api/interior/scenes/{scene['scene_id']}/undo").json()["scene"]
    back = op(s, {"operation": "reset_object", "object_id": new_id}).json()["scene"]
    assert obj(back, "sofa_001") == sofa
    assert new_id not in {o["id"] for o in back["objects"]}


def test_replace_rules():
    scene = new_scene()["scene"]
    r = op(scene, {"operation": "replace_object", "object_id": "sofa_001", "changes": {"library_item": "nope"}})
    assert r.status_code == 422 and "object library" in r.json()["detail"]
    # older clients may still name a type
    r = op(scene, {"operation": "replace_object", "object_id": "sofa_001", "changes": {"type": "sectional_sofa"}})
    assert r.status_code == 200
    assert obj(r.json()["scene"], "sofa_002")["library_item"]["id"] == "sofa-l-shaped-sectional-sofa"
    # a wall picture swapped for a mirror stays on the wall
    s = r.json()["scene"]
    r = op(s, {"operation": "replace_object", "object_id": "painting_001",
               "changes": {"library_item": "mirror-round-brass-mirror"}})
    m = obj(r.json()["scene"], "mirror_001")
    assert m["placement"] == "wall" and m["bounds"]["y"] + m["bounds"]["h"] < rf.SEAM_Y / rf.H + 0.01


def test_undo_redo_replacement():
    scene = new_scene()["scene"]
    sid = scene["scene_id"]
    op(scene, {"operation": "replace_object", "object_id": "sofa_001",
               "changes": {"library_item": "sofa-chesterfield-sofa"}})
    u = client.post(f"/api/interior/scenes/{sid}/undo").json()
    assert u["scene"]["objects"] == scene["objects"]
    r = client.post(f"/api/interior/scenes/{sid}/redo").json()
    assert obj(r["scene"], "sofa_002")["library_item"]["id"] == "sofa-chesterfield-sofa"


def test_add_remove_restore():
    scene = new_scene()["scene"]
    r = op(scene, {"operation": "add_object", "object": {"type": "armchair", "color": "#3f5e5a"}})
    assert r.status_code == 200, r.text
    s = r.json()["scene"]
    added = obj(s, "armchair_001")
    assert added["source"] == "model" and added["appearance"]["color"] == "#3f5e5a"
    assert added["transform"]["position"]["y"] > rf.SEAM_Y / rf.H
    r = op(s, {"operation": "add_object", "object": {"type": "armchair"}})
    s = r.json()["scene"]
    assert {o["id"] for o in s["objects"]} >= {"armchair_001", "armchair_002"}
    r = op(s, {"operation": "remove_object", "object_id": "table_001"})
    s = r.json()["scene"]
    ids = {o["id"] for o in s["objects"]}
    assert "table_001" not in ids and "vase_001" not in ids            # the vase went with its table
    assert {x["id"] for x in s["removed"]} == {"table_001", "vase_001"}
    r = op(s, {"operation": "restore_object", "object_id": "table_001"})
    assert "table_001" in {o["id"] for o in r.json()["scene"]["objects"]}
    assert op(scene, {"operation": "add_object", "object": {"type": "spaceship"}}, base=False).status_code == 422


def test_reset_object():
    scene = new_scene()["scene"]
    s = op(scene, {"operation": "transform_object", "object_id": "sofa_001",
                   "changes": {"position": {"x": 0.4, "y": 0.8}, "scale": {"x": 1.2, "y": 1.2}}}).json()["scene"]
    s = op(s, {"operation": "reset_object", "object_id": "sofa_001"}).json()["scene"]
    assert obj(s, "sofa_001")["transform"] == obj(scene, "sofa_001")["transform"]


def test_architecture_is_not_movable_or_removable():
    from app.services.interior.operations import capabilities
    door = capabilities({"type": "door", "placement": "fixed", "source": "detected"})
    assert door["remove"] is False and door["move"] is False and door["resize"] is False
    assert "wood_oak" in door["materials"]                      # but it can be refinished
    window = capabilities({"type": "window", "placement": "fixed", "source": "detected"})
    assert window["color"] is False and window["materials"] == []


# ---- history ----------------------------------------------------------------------

def test_undo_redo_reset():
    first = new_scene()
    scene = first["scene"]
    sid = scene["scene_id"]
    s1 = op(scene, {"operation": "transform_object", "object_id": "sofa_001",
                    "changes": {"position": {"x": 0.45, "y": 0.75}}}).json()["scene"]
    s2 = op(s1, {"operation": "update_object", "object_id": "sofa_001", "changes": {"color": "#222222"}}).json()
    assert s2["can_undo"] and not s2["can_redo"]
    u = client.post(f"/api/interior/scenes/{sid}/undo").json()
    assert u["scene"] == s1 and u["can_redo"]                        # only the colour was undone
    u = client.post(f"/api/interior/scenes/{sid}/undo").json()
    assert u["scene"]["objects"] == scene["objects"]
    assert client.post(f"/api/interior/scenes/{sid}/undo").status_code == 409
    r = client.post(f"/api/interior/scenes/{sid}/redo").json()
    assert r["scene"] == s1
    r = client.post(f"/api/interior/scenes/{sid}/redo").json()
    assert obj(r["scene"], "sofa_001")["appearance"]["color"] == "#222222"
    assert client.post(f"/api/interior/scenes/{sid}/redo").status_code == 409
    reset = client.post(f"/api/interior/scenes/{sid}/reset").json()
    assert reset["scene"]["objects"] == scene["objects"] and reset["scene"]["surfaces"] == scene["surfaces"]
    assert reset["can_undo"]                                          # reset itself can be undone
    back = client.post(f"/api/interior/scenes/{sid}/undo").json()
    assert obj(back["scene"], "sofa_001")["appearance"]["color"] == "#222222"


def test_new_edit_clears_redo():
    scene = new_scene()["scene"]
    sid = scene["scene_id"]
    s1 = op(scene, {"operation": "update_object", "object_id": "sofa_001", "changes": {"color": "#111111"}}).json()
    client.post(f"/api/interior/scenes/{sid}/undo")
    s = client.get(f"/api/interior/scenes/{sid}").json()["scene"]
    r = op(s, {"operation": "update_object", "object_id": "sofa_001", "changes": {"color": "#999999"}}).json()
    assert r["can_redo"] is False and s1["scene"]["version"] != r["scene"]["version"]


def test_stale_edit_conflicts():
    scene = new_scene()["scene"]
    op(scene, {"operation": "update_object", "object_id": "sofa_001", "changes": {"color": "#111111"}})
    r = op(scene, {"operation": "update_object", "object_id": "sofa_001", "changes": {"color": "#999999"}})
    assert r.status_code == 409


# ---- rendering endpoints ------------------------------------------------------------

def test_render_original_sprite_final():
    body = new_scene()
    scene = body["scene"]
    sid = scene["scene_id"]
    r = client.get(body["render_url"])
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg"
    assert client.get(body["original_url"]).status_code == 200
    r = client.get(f"/api/interior/scenes/{sid}/objects/sofa_001/sprite")
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"
    bx, by, bw, bh = map(float, r.headers["x-bounds"].split(","))
    assert bw == pytest.approx(300 / 640, abs=0.03)
    assert client.get(f"/api/interior/scenes/{sid}/objects/nope/sprite").status_code == 404
    r = client.post(f"/api/interior/scenes/{sid}/final", json={})
    assert r.status_code == 200
    body = r.json()
    assert body["format"] == "jpg" and body["quality"] == "high" and body["filename"].endswith(".jpg")
    got = client.get(body["url"] + "?download=true")
    assert got.status_code == 200 and got.headers["content-type"] == "image/jpeg"
    assert got.headers["content-disposition"].startswith("attachment")
    img = cv2.imdecode(np.frombuffer(got.content, np.uint8), cv2.IMREAD_COLOR)
    assert img.shape[1] == body["width"] and img.shape[0] == body["height"]


def test_final_image_as_png_or_smaller_jpeg_and_original_untouched():
    scene = new_scene()["scene"]
    sid = scene["scene_id"]
    before = client.get(f"/api/interior/scenes/{sid}/original").content
    s = op(scene, {"operation": "update_object", "object_id": "sofa_001", "changes": {"color": "#202020"}}).json()["scene"]
    png = client.post(f"/api/interior/scenes/{sid}/final", json={"format": "png"}).json()
    assert png["format"] == "png" and png["quality"] == "lossless" and png["version"] == s["version"]
    r = client.get(png["url"])
    assert r.headers["content-type"] == "image/png" and r.content[1:4] == b"PNG"
    high = client.post(f"/api/interior/scenes/{sid}/final", json={"format": "jpg", "quality": "high"}).json()
    std = client.post(f"/api/interior/scenes/{sid}/final", json={"format": "jpg", "quality": "standard"}).json()
    assert std["bytes"] < high["bytes"] < png["bytes"]
    # the lossless file is the same picture as the JPEG, and the photo itself never changes
    a = cv2.imdecode(np.frombuffer(r.content, np.uint8), cv2.IMREAD_COLOR).astype(int)
    b = cv2.imdecode(np.frombuffer(client.get(high["url"]).content, np.uint8), cv2.IMREAD_COLOR).astype(int)
    assert np.abs(a - b).mean() < 3
    assert client.get(f"/api/interior/scenes/{sid}/original").content == before
    assert client.post(f"/api/interior/scenes/{sid}/final", json={"format": "gif"}).status_code == 422
    assert client.post(f"/api/interior/scenes/{sid}/final", json={"photoreal": True}).status_code == 422


def test_unknown_scene_404():
    assert client.get("/api/interior/scenes/" + "0" * 32).status_code == 404
    assert client.get("/api/interior/scenes/../../etc").status_code == 404


# ---- saving, loading, ownership -----------------------------------------------------

def test_save_reload_list_delete(isolated):
    scene = new_scene()["scene"]
    sid = scene["scene_id"]
    s1 = op(scene, {"operation": "update_surface", "surface_id": "wall_001",
                    "changes": {"color": "#5b7fa6"}}).json()["scene"]
    r = client.post("/api/interior/designs", json={"scene_id": sid, "name": "Blue lounge"})
    assert r.status_code == 200, r.text
    design = r.json()
    assert design["name"] == "Blue lounge" and design["scene_id"] == sid
    record = isolated["repo"].get(design["design_id"])
    assert record["user_id"] == "alice" and "scene_json" in record and record["created_at"]

    # keep editing after saving, then reopen: the saved state comes back
    op(s1, {"operation": "remove_object", "object_id": "sofa_001"})
    opened = client.get(f"/api/interior/designs/{design['design_id']}").json()
    assert "sofa_001" in {o["id"] for o in opened["scene"]["objects"]}
    wall = next(s for s in opened["scene"]["surfaces"] if s["id"] == "wall_001")
    assert wall["appearance"]["color"] == "#5b7fa6"
    assert opened["can_undo"]

    listed = client.get("/api/interior/designs").json()["designs"]
    assert [d["design_id"] for d in listed] == [design["design_id"]]

    # saving the same room again updates the same design
    again = client.post("/api/interior/designs", json={"scene_id": sid, "name": "Blue lounge v2"}).json()
    assert again["design_id"] == design["design_id"]
    assert client.put(f"/api/interior/designs/{design['design_id']}", json={"name": "Renamed"}).json()["name"] == "Renamed"

    assert client.delete(f"/api/interior/designs/{design['design_id']}").status_code == 200
    assert client.get("/api/interior/designs").json()["designs"] == []
    assert client.get(f"/api/interior/scenes/{sid}").status_code == 404


def test_other_users_cannot_access(isolated):
    scene = new_scene()["scene"]
    sid = scene["scene_id"]
    design = client.post("/api/interior/designs", json={"scene_id": sid, "name": "Mine"}).json()
    isolated["user"]["uid"] = "mallory"
    assert client.get(f"/api/interior/scenes/{sid}").status_code == 403
    assert op(scene, {"operation": "remove_object", "object_id": "sofa_001"}).status_code == 403
    assert client.get(f"/api/interior/scenes/{sid}/render").status_code == 403
    assert client.get(f"/api/interior/designs/{design['design_id']}").status_code == 404
    assert client.delete(f"/api/interior/designs/{design['design_id']}").status_code == 404
    assert client.get("/api/interior/designs").json()["designs"] == []


def test_saving_requires_sign_in(isolated):
    app.dependency_overrides.pop(require_user)
    app.dependency_overrides[optional_user] = lambda: None
    sid = new_scene()["scene"]["scene_id"]
    r = client.post("/api/interior/designs", json={"scene_id": sid, "name": "x"})
    assert r.status_code == 401


def test_catalog_matches_validation():
    cat = client.get("/api/interior/catalog").json()
    assert "sofa" in [a["type"] for a in cat["addable"]]
    assert "herringbone" in cat["surface_materials"]["floor"]
    assert cat["materials"]["leather"]["tintable"] is True


def test_snapshot_is_not_shared_between_versions():
    """History snapshots are independent copies (editing one never changes another)."""
    scene = new_scene()["scene"]
    before = copy.deepcopy(scene)
    op(scene, {"operation": "update_object", "object_id": "sofa_001", "changes": {"color": "#111111"}})
    sid = scene["scene_id"]
    back = client.post(f"/api/interior/scenes/{sid}/undo").json()["scene"]
    assert back["objects"] == before["objects"]
