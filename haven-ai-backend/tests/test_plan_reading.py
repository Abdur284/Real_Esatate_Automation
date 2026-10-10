"""The uploaded plan is the source of truth: its printed names and sizes are
read, outlined walls are understood, the 3D model is checked against the
plan, and a floor plan is never used as a facade photo."""
import pathlib

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.design3d.fidelity import check_reconstruction
from app.services.design3d.from_plan2d import _enclosed, build_model_from_plan2d, generate_3d_from_plan2d
from app.services.plan_vision import text as plan_text
from app.services.plan_vision.service import analyze_floor_plan, looks_like_floor_plan
from tests import planfactory as pf
from tests.test_layer1_vision import items, match

client = TestClient(app)
NAMES = {"LIVING": "living_room", "KITCHEN": "kitchen", "BATH": "bathroom",
         "BED 1": "bedroom", "BED 2": "bedroom", "STORE": "store"}


@pytest.fixture(scope="module")
def layout():
    return pf.simple_house()


@pytest.mark.parametrize("text, want", [
    ("12' x 14'", (12.0, 14.0)), ("12'-6\" x 10'", (12.5, 10.0)), ("14'x9'", (14.0, 9.0)),
    ("26'�12", (26.0, 12.0)), ("12 X 14", (12.0, 14.0)), ("3.6m x 4.2m", (11.81, 13.78)),
])
def test_dimension_strings(text, want):
    assert plan_text.parse_pair(text)[:2] == pytest.approx(want, abs=0.01)


@pytest.mark.parametrize("text", ["BED 2", "D1", "12 14", "GROUND FLOOR PLAN", ".6x,9"])
def test_non_dimension_strings(text):
    assert plan_text.parse_pair(text) is None


@pytest.mark.parametrize("text, rtype", [
    ("LIVINGROOM", "living_room"), ("Master Bed", "master_bedroom"), ("W.C.", "bathroom"),
    ("TV LOUNGE", "tv_lounge"), ("Car Porch", "parking"), ("DRAWING ROOM", "drawing_room"),
    ("Hallway", "corridor"), ("STAIRS", "staircase"), ("GROUND FLOOR PLAN", None), ("W1", None),
])
def test_room_words(text, rtype):
    assert plan_text.room_type_for(text) == rtype


def test_room_names_are_read_from_the_drawing(layout):
    res = analyze_floor_plan(pf.png_bytes(pf.draw(layout)), width_ft=25, depth_ft=40)
    found = {it["name"].upper(): it for it in items(res["plan"])}
    assert set(found) == set(NAMES)
    for name, rtype in NAMES.items():
        assert found[name]["type"] == rtype
    # Each name is on the room it was printed in.
    living = found["LIVING"]
    assert (living["x"], living["y"]) == pytest.approx((0.375, 0.375), abs=0.35)
    assert any("read from the labels" in e for e in res["analysis"]["explicit"])


def test_printed_room_sizes_set_the_scale(layout):
    """No size typed: the printed room sizes give the scale instead of a guess."""
    res = analyze_floor_plan(pf.png_bytes(pf.draw(layout, sizes=True)))
    assert res["status"] == "ANALYZED", res.get("message")
    plot = res["plan"]["plot"]
    # The drawing is 25.75 x 40.75 ft outside to outside; printed sizes are
    # centre-line sizes, read to within a few percent.
    assert plot["width_ft"] == pytest.approx(25.75, rel=0.05)
    assert plot["length_ft"] == pytest.approx(40.75, rel=0.05)
    assert any("printed" in e for e in res["analysis"]["explicit"])
    assert res["analysis"]["counts"]["distinct_rooms"] == 6


def test_printed_overall_dimension_is_preferred(layout):
    res = analyze_floor_plan(pf.png_bytes(pf.draw(layout, sizes=True, overall=True)))
    assert res["status"] == "ANALYZED"
    assert res["plan"]["plot"]["width_ft"] == pytest.approx(25.0, abs=0.3)
    assert "overall dimensions" in " ".join(res["analysis"]["explicit"])


def test_typed_size_wins_but_is_cross_checked(layout):
    res = analyze_floor_plan(pf.png_bytes(pf.draw(layout, sizes=True)), width_ft=35)
    assert res["plan"]["plot"]["width_ft"] == 35
    assert any("printed on the drawing suggest" in w for w in res["analysis"]["warnings"])


def test_outlined_walls_are_read_like_solid_ones(layout):
    """Walls drawn as two parallel lines (common in CAD exports)."""
    res = analyze_floor_plan(pf.png_bytes(pf.draw(layout, hollow=True)), width_ft=25, depth_ft=40)
    assert res["status"] == "ANALYZED", res.get("message")
    found = items(res["plan"])
    assert len(found) == 6
    truth = [t for rects in pf.truth_rects(layout).values() for t in rects]
    assert match(found, truth) == []
    doors = sum(len(it["doors"]) for it in found)
    windows = sum(len(it["windows"]) for it in found)
    assert (doors, windows) == (6, 3)


def test_reconstruction_check_passes_and_catches_a_moved_room(layout):
    plan = analyze_floor_plan(pf.png_bytes(pf.draw(layout)), width_ft=25, depth_ft=40)["plan"]
    built = generate_3d_from_plan2d(plan)
    assert built["status"] == "FEASIBLE"
    v = built["validation"]
    assert v["passed"] and {c["name"] for c in v["checks"]} >= {"rooms", "adjacency", "geometry", "walls", "openings"}

    result = build_model_from_plan2d(plan)
    room = result["model"]["storeys"][0]["rooms"][0]
    room["x"] += 2.0
    v = check_reconstruction(result["items"], result["model"], 0, _enclosed)
    assert not v["passed"]
    assert not next(c for c in v["checks"] if c["name"] == "rooms")["ok"]


def test_image_to_glb_keeps_the_same_house(layout):
    """Image -> plan -> 3D: same rooms with the same names in the same places."""
    data = pf.png_bytes(pf.draw(layout, sizes=True, overall=True))
    body = client.post("/api/design/3d/analyze", files={"image": ("plan.png", data, "image/png")}).json()
    assert body["status"] == "ANALYZED"
    built = client.post("/api/design/3d/from-2d", json={"plan": body["plan"]}).json()
    assert built["status"] == "FEASIBLE" and built["validation"]["passed"]
    assert next(c for c in built["validation"]["checks"] if c["name"] == "glb")["ok"]
    rooms = {r["label"].upper(): r for r in built["model"]["storeys"][0]["rooms"]}
    assert set(rooms) == set(NAMES)
    # Relative layout: living at the front left, kitchen to its right, the
    # bedrooms behind it, the store at the back right.
    assert rooms["KITCHEN"]["x"] > rooms["LIVING"]["x"]
    assert rooms["BED 1"]["y"] > rooms["LIVING"]["y"]
    assert rooms["STORE"]["y"] > rooms["BED 2"]["y"] and rooms["STORE"]["x"] > rooms["BED 1"]["x"]


def test_floor_plan_is_not_used_as_a_property_photo(layout):
    data = pf.png_bytes(pf.draw(layout))
    r = client.post("/api/design/3d/generate-from-image",
                    files={"image": ("plan.png", data, "image/png")},
                    data={"prompt": "3 bedrooms", "plot_width_ft": "25", "plot_length_ft": "40", "storeys": "1"})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "FLOOR_PLAN_DETECTED"
    assert "model" not in body


def test_photos_are_not_mistaken_for_floor_plans():
    for path in (pathlib.Path(__file__).parent / "fixtures" / "rooms").glob("*.jpg"):
        assert looks_like_floor_plan(path.read_bytes()) is False, path.name


@pytest.mark.parametrize("text, want", [
    ("110×166", (11.0, 16.5)), ("160×110", (16.0, 11.0)), ("100'x50", (10.0, 5.0)),
    ("50×11'6", (5.0, 11.5)), ("30' x 60'", (30.0, 60.0)), ("30x60", (30.0, 60.0)),
])
def test_feet_inch_marks_lost_by_ocr(text, want):
    """11'0" x 16'6" often comes back from OCR as "110x166"."""
    assert plan_text.parse_pair(text)[:2] == pytest.approx(want, abs=0.01)


def test_labels_that_contradict_the_walls_stop_the_analysis(layout):
    """Room names printed where the traced walls have no separate room mean
    the walls were misread: no layout is returned rather than a wrong one."""
    import cv2
    img = pf.draw(layout)
    # Three more names inside LIVING (0..14 x 0..16 ft, 20 px/ft, 60 px margin).
    for i, name in enumerate(("KITCHEN", "DINING", "STUDY")):
        cv2.putText(img, name, (90, 60 + int((40 - 4 - 3 * i) * 20)), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                    (20, 20, 20), 1, cv2.LINE_AA)
    res = analyze_floor_plan(pf.png_bytes(img), width_ft=25, depth_ft=40)
    assert res["status"] == "UNCERTAIN_LAYOUT"
    assert "plan" not in res
    assert "ran together" in res["message"]
