"""Layer 1: floor-plan image -> structured plan, checked against ground truth."""
import json

import cv2
import numpy as np
import pytest

from app.services.plan_vision.image_io import ImageRejected
from app.services.plan_vision.service import analyze_floor_plan
from app.services.design3d.from_plan2d import generate_3d_from_plan2d
from tests import planfactory as pf

TOL_FT = 0.35  # measured edges vs. drawn truth (drawing is 20 px/ft)


def items(plan):
    floor = plan["design"]["ground_floor"]
    return [it for sec in ("rooms", "circulation", "open_spaces") for it in floor[sec]]


def rect(it):
    return (it["x"], it["y"], it["width"], it["length"])


def match(found, truth):
    """Each truth rectangle has a found rectangle within TOL_FT on every edge."""
    unmatched = []
    for t in truth:
        if not any(all(abs(a - b) <= TOL_FT for a, b in zip(rect(f), t)) for f in found):
            unmatched.append(t)
    return unmatched


@pytest.fixture(scope="module")
def simple():
    layout = pf.simple_house()
    return layout, pf.png_bytes(pf.draw(layout))


def test_valid_floor_plan_rooms_and_dimensions(simple):
    layout, data = simple
    res = analyze_floor_plan(data, width_ft=25, depth_ft=40)
    assert res["status"] == "ANALYZED", res.get("message")
    plan = res["plan"]
    assert plan["plot"] == {"width_ft": 25, "length_ft": 40, "area_sqft": 1000}
    found = items(plan)
    assert len(found) == 6
    truth = [t for rects in pf.truth_rects(layout).values() for t in rects]
    assert match(found, truth) == []
    # Walls measured from the drawing.
    assert plan["structure"]["exterior_wall_thickness_ft"] == pytest.approx(0.75, abs=0.15)
    assert plan["structure"]["interior_wall_thickness_ft"] == pytest.approx(0.375, abs=0.15)
    assert len(plan["walls"]) >= 8


def test_doors_and_windows_detected(simple):
    _, data = simple
    plan = analyze_floor_plan(data, width_ft=25, depth_ft=40)["plan"]
    doors = [d for it in items(plan) for d in it["doors"]]
    windows = [w for it in items(plan) for w in it["windows"]]
    assert len(doors) == 6
    assert len(windows) == 3
    assert sum(1 for d in doors if d["to"] == "Outside") == 1
    for d in doors:
        assert d["width_ft"] == pytest.approx(3.0, abs=0.6) or d["width_ft"] == pytest.approx(3.5, abs=0.6)
    main = next(d for it in items(plan) for d in it["doors"] if d["to"] == "Outside")
    host = next(it for it in items(plan) if main in it["doors"])
    assert main["wall"] == "south"
    assert host["x"] + main["offset_ft"] == pytest.approx(5, abs=TOL_FT)


def test_confidence_and_provenance(simple):
    _, data = simple
    res = analyze_floor_plan(data, width_ft=25, depth_ft=40)
    a = res["analysis"]
    assert a["method"] == "computer_vision"
    assert set(a["confidence"]) == {"walls", "rooms", "openings", "dimensions", "room_types", "overall"}
    assert a["confidence"]["walls"] >= 0.8 and a["confidence"]["rooms"] >= 0.8
    assert a["confidence"]["dimensions"] == 1.0
    # The printed labels name every room, so nothing is left for the user to type.
    assert a["counts"]["named_rooms"] == 6
    assert all(it["detection"]["type_source"] == "read_from_label" for it in items(res["plan"]))


def test_without_text_recognition_rooms_stay_unnamed(simple, monkeypatch):
    from app.services.plan_vision import text as plan_text
    monkeypatch.setattr(plan_text, "read_text", lambda bgr: None)
    _, data = simple
    res = analyze_floor_plan(data, width_ft=25, depth_ft=40)
    a = res["analysis"]
    assert a["review_required"] is True
    assert any("not installed" in m for m in a["missing"])
    assert all(it["type"] == "other" and it["detection"]["type_source"] == "unknown" for it in items(res["plan"]))


def test_missing_dimensions_asks_instead_of_guessing(simple):
    _, data = simple
    res = analyze_floor_plan(data)
    assert res["status"] == "NEEDS_DIMENSIONS"
    assert "plan" not in res
    assert res["analysis"]["counts"]["rooms"] == 6
    assert res["analysis"]["layout_aspect_ratio"] == pytest.approx(25 / 40, abs=0.02)


def test_single_dimension_derives_the_other(simple):
    _, data = simple
    res = analyze_floor_plan(data, width_ft=25)
    assert res["status"] == "ANALYZED"
    assert res["plan"]["plot"]["length_ft"] == pytest.approx(40, abs=0.5)
    assert any("derived" in w for w in res["analysis"]["warnings"])


def test_dimension_mismatch_is_blocked(simple):
    _, data = simple
    assert analyze_floor_plan(data, width_ft=25, depth_ft=25)["status"] == "DIMENSION_MISMATCH"


def test_front_side_rotation(simple):
    layout, _ = simple
    rotated = cv2.rotate(pf.draw(layout), cv2.ROTATE_90_CLOCKWISE)  # road now on the left
    res = analyze_floor_plan(pf.png_bytes(rotated), width_ft=25, depth_ft=40, front="left")
    assert res["status"] == "ANALYZED"
    truth = [t for rects in pf.truth_rects(layout).values() for t in rects]
    assert match(items(res["plan"]), truth) == []


def test_jpeg_input(simple):
    layout, _ = simple
    ok, buf = cv2.imencode(".jpg", pf.draw(layout), [cv2.IMWRITE_JPEG_QUALITY, 85])
    res = analyze_floor_plan(buf.tobytes(), width_ft=25, depth_ft=40)
    assert res["status"] == "ANALYZED"
    assert len(items(res["plan"])) == 6


def test_l_shaped_room_becomes_one_grouped_room():
    layout = pf.l_shaped_house()
    res = analyze_floor_plan(pf.png_bytes(pf.draw(layout)), width_ft=30, depth_ft=30)
    assert res["status"] == "ANALYZED"
    found = items(res["plan"])
    groups = {it.get("group") for it in found if it.get("group")}
    assert len(groups) == 1
    lounge = [it for it in found if it.get("group")]
    area = sum(it["width"] * it["length"] for it in lounge)
    truth_area = sum(w * h for _, _, w, h in pf.truth_rects(layout)["LOUNGE"])
    assert area == pytest.approx(truth_area, rel=0.05)
    # And it builds in 3D without a wall through the middle of the lounge.
    model = generate_3d_from_plan2d(res["plan"])
    assert model["status"] == "FEASIBLE"


def test_colour_legend_and_stairs_are_inferred():
    h = pf.EXT_T / 2
    layout = pf.Layout(24, 30, [
        pf.Room("BED", h, h, 12, 15, fill=(0xbb, 0xf7, 0xd0)),
        pf.Room("KITCHEN", 12, h, 24 - h, 15, fill=(0xbf, 0xdb, 0xfe)),
        pf.Room("STAIR", h, 15, 8, 30 - h, stairs=True),
        pf.Room("BATH", 8, 15, 24 - h, 30 - h, fill=(0xdd, 0xd6, 0xfe)),
    ], [pf.Opening("door", True, h, 3, 6), pf.Opening("door", False, 12, 5, 8)])
    res = analyze_floor_plan(pf.png_bytes(pf.draw(layout, text=False)), width_ft=24, depth_ft=30)
    assert res["status"] == "ANALYZED"
    types = sorted(it["type"] for it in items(res["plan"]))
    assert types == ["bathroom", "bedroom", "kitchen", "staircase"]


def test_embedded_haven_plan_is_used_exactly(simple):
    from tests.test_layer2_geometry import plan_one_floor
    plan = plan_one_floor()
    _, data = simple
    res = analyze_floor_plan(pf.with_itxt(data, "haven-plan2d", json.dumps(plan)))
    assert res["status"] == "ANALYZED"
    assert res["analysis"]["method"] == "embedded_plan"
    assert items(res["plan"])[0]["width"] == 12


def test_tampered_embedded_plan_falls_back_to_vision(simple):
    from tests.test_layer2_geometry import plan_one_floor
    plan = plan_one_floor()
    plan["design"]["ground_floor"]["rooms"][1]["x"] = 3  # overlapping rooms
    _, data = simple
    res = analyze_floor_plan(pf.with_itxt(data, "haven-plan2d", json.dumps(plan)), width_ft=25, depth_ft=40)
    assert res["analysis"]["method"] == "computer_vision"


@pytest.mark.parametrize("data,message", [
    (b"", "empty"),
    (b"hello world", "PNG, JPEG or WebP"),
    (b"\x89PNG\r\n\x1a\n" + b"\x00" * 64, "could not be read"),
    (b"GIF89a" + b"\x00" * 64, "PNG, JPEG or WebP"),
])
def test_invalid_images_are_rejected(data, message):
    with pytest.raises(ImageRejected, match=message):
        analyze_floor_plan(data, width_ft=25, depth_ft=40)


def test_low_resolution_image():
    small = cv2.resize(pf.draw(pf.simple_house()), (120, 180), interpolation=cv2.INTER_AREA)
    assert analyze_floor_plan(pf.png_bytes(small), width_ft=25, depth_ft=40)["status"] == "LOW_RESOLUTION"


@pytest.mark.parametrize("img", [
    np.full((600, 800, 3), 255, np.uint8),                                              # blank page
    np.random.default_rng(1).integers(0, 255, (600, 800, 3), dtype=np.uint8),           # noise
    np.dstack([np.tile(np.linspace(0, 255, 800, dtype=np.uint8), (600, 1))] * 3),       # photo-like gradient
])
def test_non_floor_plan_images(img):
    res = analyze_floor_plan(pf.png_bytes(img), width_ft=25, depth_ft=40)
    assert res["status"] == "NOT_A_FLOOR_PLAN"


def test_full_pipeline_image_to_glb(simple):
    from app.services.design3d.gltf_export import export_glb, read_glb
    _, data = simple
    plan = analyze_floor_plan(data, width_ft=25, depth_ft=40)["plan"]
    result = generate_3d_from_plan2d(plan)
    assert result["status"] == "FEASIBLE"
    model = result["model"]
    assert model["source"] == "image_analysis"
    doors = [o for w in model["storeys"][0]["walls"] for o in w["openings"] if o["type"] == "door"]
    assert len(doors) == 6
    js, _ = read_glb(export_glb(model)[0])
    rooms = [n for n in js["nodes"] if n.get("extras", {}).get("kind") == "room"]
    assert len(rooms) == 6


def haven_style_png():
    """A 2D plan drawn the way HAVEN's 2D viewer draws it (legend fills, thin
    dark strokes, blue windows, white door gaps), at its export scale."""
    import pathlib
    plan = json.loads((pathlib.Path(__file__).parent / "haven_plan_two_floor.json").read_text())
    ppf, pad = 16, 4
    W, L = plan["plot"]["width_ft"], plan["plot"]["length_ft"]
    img = np.full((int((L + 2 * pad) * ppf), int((W + 2 * pad) * ppf), 3), 255, np.uint8)
    X = lambda x: int(round((x + pad) * ppf))           # noqa: E731
    Y = lambda y: int(round((L - y + pad) * ppf))       # noqa: E731
    colors = dict(pf_legend())
    floor = plan["design"]["ground_floor"]
    items = floor["open_spaces"] + floor["rooms"]
    for it in items:
        rgb = colors.get(it["type"], (229, 231, 235))
        cv2.rectangle(img, (X(it["x"]), Y(it["y"] + it["length"])), (X(it["x"] + it["width"]), Y(it["y"])), rgb[::-1], -1)
    for it in floor["rooms"]:
        cv2.rectangle(img, (X(it["x"]), Y(it["y"] + it["length"])), (X(it["x"] + it["width"]), Y(it["y"])), (59, 41, 30), 6)
    for it in floor["rooms"]:
        for kind in ("doors", "windows"):
            for op in it.get(kind, []):
                x0, y0, w, l = it["x"], it["y"], it["width"], it["length"]
                o, ow = op["offset_ft"], op["width_ft"]
                seg = {"south": ((x0 + o, y0), (x0 + o + ow, y0)), "north": ((x0 + o, y0 + l), (x0 + o + ow, y0 + l)),
                       "west": ((x0, y0 + o), (x0, y0 + o + ow)), "east": ((x0 + w, y0 + o), (x0 + w, y0 + o + ow))}[op["wall"]]
                p0, p1 = (X(seg[0][0]), Y(seg[0][1])), (X(seg[1][0]), Y(seg[1][1]))
                if kind == "windows":
                    cv2.line(img, p0, p1, (233, 165, 14), 9)
                    cv2.line(img, p0, p1, (255, 255, 255), 3)
                else:
                    cv2.line(img, p0, p1, (255, 255, 255), 8)
                    cv2.line(img, p0, p1, (6, 119, 217), 3)
    return pf.png_bytes(img), plan


def pf_legend():
    from app.services.plan_vision.structure import HAVEN_LEGEND
    return [(t, tuple(int(c.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))) for t, c in HAVEN_LEGEND]


def test_haven_style_image_reads_every_room_and_type():
    data, plan = haven_style_png()
    # The form asks for the outside-to-outside width: HAVEN centres its 6 px
    # (0.375 ft) wall strokes on the 25 ft plot line.
    res = analyze_floor_plan(data, width_ft=25 + 6 / 16)
    assert res["status"] == "ANALYZED"
    found = items(res["plan"])
    want = {it["type"] for it in plan["design"]["ground_floor"]["rooms"]}
    assert {it["type"] for it in found} == want
    # Each room is within ~one wall stroke (0.6 ft at 16 px/ft) of the plan it was drawn from.
    for truth in plan["design"]["ground_floor"]["rooms"]:
        got = next(it for it in found if it["type"] == truth["type"])
        for k in ("x", "y", "width", "length"):
            assert got[k] == pytest.approx(truth[k] + (6 / 32 if k in ("x", "y") else 0), abs=0.6), (truth["name"], k)


@pytest.mark.parametrize("name", ["render_like"])
def test_filled_render_like_image_is_not_a_floor_plan(name):
    img = np.full((700, 900, 3), 232, np.uint8)
    cv2.rectangle(img, (100, 420), (820, 640), (105, 85, 71), -1)          # a road slab
    cv2.rectangle(img, (300, 150), (600, 420), (245, 245, 245), -1)        # a lit facade
    cv2.rectangle(img, (340, 250), (390, 420), (52, 94, 139), -1)          # a door
    assert analyze_floor_plan(pf.png_bytes(img), width_ft=25)["status"] == "NOT_A_FLOOR_PLAN"
