"""Layer 2: structured plan -> 3D geometry -> GLB."""
import copy
import struct

import pytest

from app.services.design3d import model_store
from app.services.design3d.arch_defaults import (
    EXT_WALL_THICKNESS_FT, FT_TO_M, INT_WALL_THICKNESS_FT, STOREY_PITCH_FT, WALL_HEIGHT_FT,
)
from app.services.design3d.from_plan2d import generate_3d_from_plan2d
from app.services.design3d.furniture import furnish_room
from app.services.design3d.gltf_export import export_glb, read_glb
from app.services.design3d.service import generate_3d_model


def plan_one_floor():
    """20 x 30 ft: a bedroom and a lounge side by side at the front, a
    kitchen across the back. Coordinates are wall centrelines."""
    return {
        "status": "FEASIBLE",
        "plot": {"width_ft": 20, "length_ft": 30, "area_sqft": 600},
        "design": {
            "floors": 1,
            "ground_floor": {
                "rooms": [
                    {"id": "a", "name": "Lounge", "type": "tv_lounge", "x": 0, "y": 0, "width": 12, "length": 18,
                     "doors": [{"wall": "south", "offset_ft": 4, "width_ft": 3.5, "to": "Outside"}],
                     "windows": [{"wall": "west", "offset_ft": 6, "width_ft": 4}]},
                    {"id": "b", "name": "Bedroom", "type": "bedroom", "x": 12, "y": 0, "width": 8, "length": 18,
                     "doors": [{"wall": "west", "offset_ft": 12, "width_ft": 3}], "windows": []},
                    {"id": "c", "name": "Kitchen", "type": "kitchen", "x": 0, "y": 18, "width": 20, "length": 12,
                     "doors": [{"wall": "south", "offset_ft": 2, "width_ft": 3}], "windows": []},
                ],
                "circulation": [], "open_spaces": [],
            },
            "first_floor": {"rooms": [], "circulation": [], "open_spaces": []},
        },
    }


def accessor_bounds(js, node_name):
    node = next(n for n in js["nodes"] if n["name"] == node_name)
    mesh = js["meshes"][node["mesh"]]
    mins, maxs = [], []
    for p in mesh["primitives"]:
        acc = js["accessors"][p["attributes"]["POSITION"]]
        mins.append(acc["min"])
        maxs.append(acc["max"])
    return [min(m[i] for m in mins) for i in range(3)], [max(m[i] for m in maxs) for i in range(3)]


def test_walls_rooms_and_openings_from_plan():
    result = generate_3d_from_plan2d(plan_one_floor())
    assert result["status"] == "FEASIBLE"
    storey = result["model"]["storeys"][0]
    walls = storey["walls"]
    # Exterior: 4 sides (the south side is split where the partition meets it).
    exterior = [w for w in walls if w["exterior"]]
    interior = [w for w in walls if not w["exterior"]]
    assert all(w["thickness"] == EXT_WALL_THICKNESS_FT for w in exterior)
    assert all(w["thickness"] == INT_WALL_THICKNESS_FT for w in interior)
    assert sum(w["length"] for w in exterior) == pytest.approx(2 * (20 + 30))
    # One partition between lounge/bedroom (18 ft) and one across the back (20 ft).
    assert sum(w["length"] for w in interior) == pytest.approx(18 + 20)
    # Room sizes preserved exactly.
    sizes = {r["label"]: (r["width"], r["depth"]) for r in storey["rooms"]}
    assert sizes == {"Lounge": (12, 18), "Bedroom": (8, 18), "Kitchen": (20, 12)}
    openings = [o for w in walls for o in w["openings"]]
    assert sorted(o["type"] for o in openings) == ["door", "door", "door", "window"]
    front_door = next(o for w in walls if w["exterior"] and w["y1"] == 0 for o in w["openings"])
    assert front_door["width"] == 3.5 and front_door["center"] == pytest.approx(4 + 1.75)


def test_multi_rectangle_room_has_no_internal_wall():
    plan = plan_one_floor()
    rooms = plan["design"]["ground_floor"]["rooms"]
    rooms[0]["group"] = rooms[2]["group"] = "g1"  # lounge + kitchen become one L-shaped room
    storey = generate_3d_from_plan2d(plan)["model"]["storeys"][0]
    # The seam y=18 between x=0..12 must carry no wall; x=12..20 still does (bedroom).
    seam = [w for w in storey["walls"] if w["y1"] == w["y2"] == 18]
    assert all(min(w["x1"], w["x2"]) >= 12 - 1e-6 for w in seam)


def test_measured_wall_thickness_is_used_only_when_plausible():
    plan = plan_one_floor()
    plan["source"] = "image_analysis"
    plan["structure"] = {"exterior_wall_thickness_ft": 1.0, "interior_wall_thickness_ft": 0.5}
    model = generate_3d_from_plan2d(plan)["model"]
    assert model["wall_thickness_ft"] == {"exterior": 1.0, "interior": 0.5}
    plan["structure"] = {"exterior_wall_thickness_ft": 9, "interior_wall_thickness_ft": -1}
    model = generate_3d_from_plan2d(plan)["model"]
    assert model["wall_thickness_ft"] == {"exterior": EXT_WALL_THICKNESS_FT, "interior": INT_WALL_THICKNESS_FT}


@pytest.mark.parametrize("mutate", [
    lambda p: p["design"]["ground_floor"]["rooms"][1].update(x=6),         # overlaps the lounge
    lambda p: p["design"]["ground_floor"]["rooms"][2].update(width=40),    # outside the plot
    lambda p: p["design"]["ground_floor"]["rooms"][0].update(width="big"), # not numeric
    lambda p: p.update(status="NOT_FEASIBLE"),
])
def test_invalid_geometry_is_rejected(mutate):
    plan = plan_one_floor()
    mutate(plan)
    assert generate_3d_from_plan2d(plan)["status"] == "NOT_FEASIBLE"


def test_glb_structure_units_and_dimensions():
    model = generate_3d_from_plan2d(plan_one_floor())["model"]
    data, meta = export_glb(model)
    assert data[:4] == b"glTF" and struct.unpack_from("<I", data, 8)[0] == len(data)
    js, binary = read_glb(data)
    assert js["asset"]["version"] == "2.0"
    assert len(binary) == js["buffers"][0]["byteLength"]
    names = {n["name"] for n in js["nodes"]}
    assert {"house", "site", "storey_1", "L1_walls", "L1_doors", "L1_windows", "L1_floors", "roof_1"} <= names

    # Unit conversion: walls run the full 20 x 30 ft (+ half an exterior wall
    # each side) and stand exactly WALL_HEIGHT_FT tall, in metres.
    lo, hi = accessor_bounds(js, "L1_walls")
    half = EXT_WALL_THICKNESS_FT / 2
    assert lo[0] == pytest.approx(-half * FT_TO_M, abs=1e-4)
    assert hi[0] == pytest.approx((20 + half) * FT_TO_M, abs=1e-4)
    assert hi[1] == pytest.approx(WALL_HEIGHT_FT * FT_TO_M, abs=1e-4)
    # Plan depth maps to -Z: the back wall is at z = -(30 + half) ft.
    assert lo[2] == pytest.approx(-(30 + half) * FT_TO_M, abs=1e-4)
    assert hi[2] == pytest.approx(half * FT_TO_M, abs=1e-4)

    # Every room is its own pickable node carrying its real dimensions.
    rooms = [n for n in js["nodes"] if n.get("extras", {}).get("kind") == "room"]
    assert {r["extras"]["label"]: (r["extras"]["width_ft"], r["extras"]["depth_ft"]) for r in rooms} == \
        {"Lounge": (12, 18), "Bedroom": (8, 18), "Kitchen": (20, 12)}
    kitchen = next(r for r in rooms if r["extras"]["label"] == "Kitchen")
    klo, khi = accessor_bounds(js, kitchen["name"])
    assert khi[0] - klo[0] == pytest.approx((20 - 0.2) * FT_TO_M, abs=1e-4)  # 0.1 ft inset each side

    glass = next(m for m in js["materials"] if m["name"] == "glass")
    assert glass["alphaMode"] == "BLEND"
    root = next(n for n in js["nodes"] if n["name"] == "house")
    assert root["extras"]["haven"]["units"] == "m"
    assert meta["rooms"] == 3 and meta["triangles"] > 0


def test_glb_for_generated_two_storey_model():
    result = generate_3d_model("25 x 50 ft plot, 3 bedrooms, 2 bathrooms, kitchen, TV lounge, parking, double storey")
    assert result["status"] == "FEASIBLE"
    js, _ = read_glb(export_glb(result["model"])[0])
    names = {n["name"] for n in js["nodes"]}
    assert {"storey_1", "storey_2", "L1_stairs"} <= names
    lo, hi = accessor_bounds(js, "L2_walls")
    assert lo[1] == pytest.approx(STOREY_PITCH_FT * FT_TO_M, abs=1e-4)


def test_door_and_window_counts_in_glb():
    plan = plan_one_floor()
    js, _ = read_glb(export_glb(generate_3d_from_plan2d(plan)["model"], furniture=False)[0])
    lo, hi = accessor_bounds(js, "L1_windows")
    # The single window sits in the west wall between 6 and 10 ft of depth.
    assert -hi[2] / FT_TO_M == pytest.approx(6, abs=0.01)
    assert -lo[2] / FT_TO_M == pytest.approx(10, abs=0.01)
    assert "L1_furniture" not in {n["name"] for n in js["nodes"]}


def test_furniture_fits_and_avoids_doors():
    room = {"x": 0, "y": 0, "width": 12, "depth": 14, "type": "bedroom", "enclosed": True}
    door = {"x1": 0, "y1": 0, "x2": 12, "y2": 0, "length": 12, "thickness": 0.375, "height": 10,
            "exterior": False, "parapet": False, "openings": [{"type": "door", "center": 6, "width": 3, "height": 7, "sill": 0}]}
    walls = [door,
             {"x1": 0, "y1": 14, "x2": 12, "y2": 14, "length": 12, "thickness": 0.375, "height": 10, "exterior": True, "parapet": False, "openings": []},
             {"x1": 0, "y1": 0, "x2": 0, "y2": 14, "length": 14, "thickness": 0.375, "height": 10, "exterior": True, "parapet": False, "openings": []},
             {"x1": 12, "y1": 0, "x2": 12, "y2": 14, "length": 14, "thickness": 0.375, "height": 10, "exterior": True, "parapet": False, "openings": []}]
    items = furnish_room(room, walls, 0.0)
    assert any(name == "bed_base" for name, _, _ in items)
    for _, _, (x0, y0, h0, x1, y1, h1) in items:
        assert 0 < x0 < x1 < 12 and 0 < y0 < y1 < 14
        assert not (x0 < 9.5 and x1 > 2.5 and y0 < 3.5), "furniture blocks the door"
    tiny = dict(room, width=5, depth=5)
    assert furnish_room(tiny, walls, 0.0) == []


def test_model_store_round_trip_and_id_validation():
    model_id = model_store.put(b"glTF-bytes")
    assert model_store.get(model_id) == b"glTF-bytes"
    assert model_store.get("../../etc/passwd") is None
    assert model_store.get("0" * 32) is None


def test_plan_is_not_mutated():
    plan = plan_one_floor()
    before = copy.deepcopy(plan)
    generate_3d_from_plan2d(plan)
    assert plan == before


@pytest.mark.parametrize("prompt", [
    "25 x 50 ft plot, 3 bedrooms, 2 bathrooms, kitchen, drawing room, TV lounge, car parking, double storey",
    "10 marla plot, 4 bedrooms, 3 bathrooms, kitchen, TV lounge, parking, double storey",
    "1 kanal, 5 bedrooms, 5 bathrooms, kitchen, drawing room, dining, TV lounge, 2 car parking, double storey",
])
def test_generated_models_have_no_overlapping_collinear_walls(prompt):
    """Regression: a solid wall overlapping a collinear one used to hide its door."""
    model = generate_3d_model(prompt)["model"]
    for storey in model["storeys"]:
        spans = {}
        for w in storey["walls"]:
            horiz = w["y1"] == w["y2"]
            key = (horiz, w["y1"] if horiz else w["x1"])
            s = min(w["x1"], w["x2"]) if horiz else min(w["y1"], w["y2"])
            spans.setdefault(key, []).append((s, s + w["length"]))
        for segs in spans.values():
            segs.sort()
            assert all(b[0] >= a[1] - 1e-6 for a, b in zip(segs, segs[1:]))
