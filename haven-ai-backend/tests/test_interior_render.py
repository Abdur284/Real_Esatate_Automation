"""Layers 1-3 without the ML model: scene extraction from a known class map,
camera estimation, and whether renders put the right colour, material, size
and position in the right place -- and nowhere else."""
import numpy as np
import pytest

from app.services.interior import catalog, geometry, operations
from app.services.interior.renderer import Assets, render
from app.services.interior.scene_builder import build_scene
from tests import roomfactory as rf


@pytest.fixture(scope="module")
def built():
    img = rf.room_image()
    cls, conf = rf.FakeSegmenter().segment(img)
    det, instances, alphas = build_scene(img, cls, conf, rf.LABELS)
    info = {"width": rf.W, "height": rf.H, "original_width": rf.W, "original_height": rf.H,
            "quality": {}, "warnings": []}
    scene = operations.initial_scene("t" * 32, det, info)
    crops = {}
    for idx, a in alphas.items():
        ys, xs = np.where(a > 0)
        crops[idx] = (int(ys.min()), int(xs.min()), a[ys.min():ys.max() + 1, xs.min():xs.max() + 1])
    return img, det, scene, Assets(original=img, instances=instances, alphas=crops)


def draw(scene, det, assets):
    s = dict(scene, _detections=det["objects"])
    return render(s, assets)


def apply(scene, det, operation):
    new, notes = operations.apply_operation(dict(scene, _detections=det["objects"]), operation)
    new.pop("_detections", None)
    return new


def region(box, pad=0):
    x0, y0, x1, y1 = box
    return x0 + pad, y0 + pad, x1 - pad, y1 - pad


# ---- Layer 1/2: extraction -----------------------------------------------------------

def test_vanishing_point_measured(built):
    _, det, scene, _ = built
    cam = geometry.camera(scene)
    assert cam.source.startswith("estimated")
    assert cam.horizon == pytest.approx(rf.VP[1], abs=6)
    assert cam.vx == pytest.approx(rf.VP[0], abs=6)


def test_objects_and_surfaces_found_with_ids(built):
    _, det, scene, _ = built
    types = {o["id"]: o["type"] for o in det["objects"]}
    assert types == {"sofa_001": "sofa", "table_001": "table", "vase_001": "vase", "painting_001": "painting"}
    placements = {o["id"]: o["placement"] for o in det["objects"]}
    assert placements["sofa_001"] == "floor" and placements["painting_001"] == "wall"
    assert placements["vase_001"] == "surface"
    rels = {(r["type"], r["subject"], r["object"]) for r in det["relationships"]}
    assert ("on", "vase_001", "table_001") in rels and ("hangs_on", "painting_001", "wall_001") in rels
    seam = np.array(det["layout"]["floor_y"]) * rf.H
    assert np.median(seam) == pytest.approx(rf.SEAM_Y, abs=4)


def test_nothing_is_invented(built):
    """Only classes present in the map become objects."""
    img = rf.room_image()
    cls = np.full(cls_shape := (rf.H, rf.W), rf.WALL, np.int16)
    cls[rf.SEAM_Y:] = rf.FLOOR
    det, _, _ = build_scene(img, cls, np.full(cls_shape, 0.9, np.float32), rf.LABELS)
    assert det["objects"] == []
    assert {s["type"] for s in det["surfaces"]} == {"wall", "floor"}


def test_sizes_are_consistent(built):
    _, det, scene, _ = built
    sofa = next(o for o in scene["objects"] if o["id"] == "sofa_001")
    # scale is calibrated from typical furniture: a sofa and table in view
    assert 1.5 < sofa["dimensions_m"]["width"] < 3.2


# ---- Layer 3: rendering ------------------------------------------------------------

def test_untouched_scene_renders_the_photo(built):
    img, det, scene, assets = built
    out = draw(scene, det, assets)
    assert np.abs(out.astype(int) - img.astype(int)).mean() < 1.0


def test_wall_colour_is_localised(built):
    img, det, scene, assets = built
    s = apply(scene, det, {"operation": "update_surface", "surface_id": "wall_001",
                           "changes": {"color": "#3355aa"}})
    out = draw(s, det, assets)
    wall = (20, 20, 140, 120)
    assert rf.color_distance(rf.mean_color(out, wall), rf.mean_color(img, wall)) > 60
    b, g, r = rf.mean_color(out, wall)
    assert b > r + 40                                                  # it is blue now
    # the painting, sofa and floor are untouched
    for box in (region(rf.PAINTING_BOX, 4), region(rf.SOFA_BOX, 4), (20, 420, 200, 470)):
        assert rf.color_distance(rf.mean_color(out, box), rf.mean_color(img, box)) < 4
    # shading is kept: the wall is still lit from the left
    left, right = rf.mean_color(out, (20, 20, 60, 120)), rf.mean_color(out, (560, 170, 620, 200))
    assert left.mean() > right.mean()


def test_floor_material_follows_floor_only(built):
    img, det, scene, assets = built
    s = apply(scene, det, {"operation": "update_surface", "surface_id": "floor_001",
                           "changes": {"material": "marble_white"}})
    out = draw(s, det, assets)
    floor = (20, 400, 140, 470)
    assert rf.mean_color(out, floor).mean() > rf.mean_color(img, floor).mean() + 40
    assert rf.color_distance(rf.mean_color(out, (20, 20, 140, 120)), rf.mean_color(img, (20, 20, 140, 120))) < 4
    assert rf.color_distance(rf.mean_color(out, region(rf.SOFA_BOX, 4)),
                             rf.mean_color(img, region(rf.SOFA_BOX, 4))) < 4


def test_object_colour_and_material(built):
    img, det, scene, assets = built
    s = apply(scene, det, {"operation": "update_object", "object_id": "sofa_001",
                           "changes": {"color": "#aa2222"}})
    out = draw(s, det, assets)
    b, g, r = rf.mean_color(out, region(rf.SOFA_BOX, 6))
    assert r > g + 50 and r > b + 50
    assert rf.color_distance(rf.mean_color(out, region(rf.TABLE_BOX, 4)),
                             rf.mean_color(img, region(rf.TABLE_BOX, 4))) < 4
    s = apply(scene, det, {"operation": "update_object", "object_id": "table_001",
                           "changes": {"material": "marble_white"}})
    out = draw(s, det, assets)
    assert rf.mean_color(out, region(rf.TABLE_BOX, 6)).mean() > rf.mean_color(img, region(rf.TABLE_BOX, 6)).mean() + 60


def test_move_puts_the_object_at_its_new_place(built):
    img, det, scene, assets = built
    # move the table left and forward
    s = apply(scene, det, {"operation": "transform_object", "object_id": "table_001",
                           "changes": {"position": {"x": 0.25, "y": 0.9}}})
    t = next(o for o in s["objects"] if o["id"] == "table_001")
    out = draw(s, det, assets)
    b = t["bounds"]
    new_box = (int((b["x"] + 0.2 * b["w"]) * rf.W), int((b["y"] + 0.3 * b["h"]) * rf.H),
               int((b["x"] + 0.8 * b["w"]) * rf.W), int((b["y"] + 0.8 * b["h"]) * rf.H))
    assert rf.color_distance(rf.mean_color(out, new_box), rf.TABLE_BGR) < 45
    # the old place now shows floor, not the table
    old = region(rf.TABLE_BOX, 12)
    old = (old[0], max(old[1], rf.SEAM_Y + 30), old[2], old[3])
    assert rf.color_distance(rf.mean_color(out, old), rf.mean_color(img, (40, 330, 120, 380))) < 45
    assert rf.color_distance(rf.mean_color(out, old), rf.TABLE_BGR) > 40
    # perspective: nearer the camera, it is drawn bigger
    assert b["w"] * rf.W > (rf.TABLE_BOX[2] - rf.TABLE_BOX[0]) * 1.1


def test_resize_changes_drawn_size(built):
    img, det, scene, assets = built
    s = apply(scene, det, {"operation": "transform_object", "object_id": "sofa_001",
                           "changes": {"scale": {"x": 0.6, "y": 0.6}}})
    out = draw(s, det, assets)
    green = (np.abs(out.astype(int) - np.array(rf.SOFA_BGR)).sum(2) < 60)
    cols = np.where(green[240:320].any(0))[0]
    width = cols.max() - cols.min()
    assert width == pytest.approx(0.6 * (rf.SOFA_BOX[2] - rf.SOFA_BOX[0]), rel=0.12)


def test_remove_fills_with_background(built):
    img, det, scene, assets = built
    s = apply(scene, det, {"operation": "remove_object", "object_id": "painting_001"})
    out = draw(s, det, assets)
    box = region(rf.PAINTING_BOX, 8)
    wall_near = (400, 60, 460, 150)
    assert rf.color_distance(rf.mean_color(out, box), rf.mean_color(img, wall_near)) < 20


def test_added_model_is_drawn_on_the_floor(built):
    img, det, scene, assets = built
    s = apply(scene, det, {"operation": "add_object", "object": {"type": "rug", "position": {"x": 0.3, "y": 0.9}}})
    rug = next(o for o in s["objects"] if o["type"] == "rug")
    out = draw(s, det, assets)
    b = rug["bounds"]
    assert b["y"] > rf.SEAM_Y / rf.H
    changed = np.abs(out.astype(int) - img.astype(int)).sum(2) > 30
    ys, xs = np.where(changed)
    assert ys.min() >= rf.SEAM_Y - 5                                   # only floor pixels changed


def test_render_is_deterministic(built):
    img, det, scene, assets = built
    s = apply(scene, det, {"operation": "update_surface", "surface_id": "floor_001",
                           "changes": {"material": "herringbone"}})
    s = apply(s, det, {"operation": "add_object", "object": {"type": "plant"}})
    a, b = draw(s, det, assets), draw(s, det, assets)
    assert np.array_equal(a, b)


def test_every_library_category_places_and_renders(built):
    """One piece from every category of the object library goes into the room
    in a sensible place and changes the picture."""
    from app.services.interior.library import get_library
    img, det, scene, assets = built
    lib = get_library()
    seam = rf.SEAM_Y / rf.H
    for cat in lib.categories.values():
        item = lib.default_item(cat.id)
        s = apply(scene, det, {"operation": "add_object", "object": {"library_item": item.id}})
        o = next(o for o in s["objects"] if o["id"] == s["last_operation"]["assigned_id"])
        b = o["bounds"]
        assert 0 < b["w"] <= 1.5 and o["outline"], item.id
        if cat.placement in ("floor", "floor_flat"):
            assert o["transform"]["position"]["y"] >= seam - 0.02, item.id          # on the floor
        elif cat.placement == "wall":
            assert b["y"] + b["h"] <= seam + 0.02, item.id                          # on the wall
        elif cat.placement == "ceiling":
            assert o["transform"]["position"]["y"] < geometry.camera(s).horizon / rf.H, item.id
        out = draw(s, det, assets)
        assert np.abs(out.astype(int) - img.astype(int)).sum() > 0, item.id
