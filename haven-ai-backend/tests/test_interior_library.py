"""The interior object library: catalogue integrity, search, filters, facets,
natural-language requests, previews, the API, 2D image assets and adding
items through data only."""
import json
import os
import shutil

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.interior import library as libmod
from app.services.interior import meshes
from app.services.interior.furniture3d import GENERATORS, WALL_GENERATORS
from app.services.interior.library import Library, LibraryError, get_library
from app.services.interior.thumbnails import render_preview

client = TestClient(app)


@pytest.fixture(scope="module")
def lib():
    return get_library()


# ---- catalogue ------------------------------------------------------------------------

def test_catalogue_is_substantial_and_valid(lib):
    assert len(lib.items) >= 150
    assert len(lib.categories) >= 35
    for cat in lib.categories.values():
        assert lib.by_category.get(cat.id), f"{cat.id} has no items"
    for it in lib.items.values():
        assert it.model["kind"] in ("parametric", "mesh")
        if it.model["kind"] == "parametric":
            assert it.model["generator"] in GENERATORS or it.model["generator"] in WALL_GENERATORS
            assert it.dimensions_source == "nominal"
        else:
            # a real 3D model: measured from the model, free licence, files installed
            assert it.dimensions_source == "measured" and it.model["license"] == "CC0"
            assert meshes.available(it.model["asset"])
        assert it.unit == "cm"
        assert it.colors, it.id


def test_the_sofa_range(lib):
    sofas = {it.subcategory for it in lib.by_category["sofa"]}
    assert {"2-seater", "3-seater", "4-seater", "L-shaped", "U-shaped", "recliner"} <= sofas
    styles = {it.style for it in lib.by_category["sofa"]}
    assert {"modern", "minimalist", "traditional", "luxury", "contemporary"} <= styles
    assert {"fabric", "leather", "velvet", "linen"} <= {it.material for it in lib.by_category["sofa"]}


def test_variants_are_genuinely_different(lib):
    """No two items share the same model, size and material (no padding)."""
    seen = set()
    for it in lib.items.values():
        key = (json.dumps(it.model, sort_keys=True), tuple(it.dimensions.values()), it.material, it.color)
        assert key not in seen, it.id
        seen.add(key)


def test_one_preview_per_category_renders(lib):
    for cat in lib.categories.values():
        img = render_preview(lib, lib.default_item(cat.id))
        assert img.shape == (240, 320, 3)
        background = np.array([236, 236, 240])
        assert (np.abs(img.astype(int) - background).sum(2) > 40).mean() > 0.02, cat.id    # something is drawn


# ---- search -----------------------------------------------------------------------------

@pytest.mark.parametrize("query,expect", [
    ("modern gray sofa", {"category": "sofa", "style": "modern", "color": "gray"}),
    ("black leather sofa", {"category": "sofa", "material": "leather", "color": "black"}),
    ("wooden coffee table", {"category": "coffee_table", "material": "wood"}),
    ("Give me a minimalist black chair.", {"category": "dining_chair", "style": "minimalist", "color": "black"}),
    ("Show luxury bedroom furniture.", {"group": "bedroom", "style": "luxury"}),
    ("small plant", {"category": "plant", "size": "small"}),
])
def test_natural_language_becomes_filters(lib, query, expect):
    r = lib.search(query)
    for k, v in expect.items():
        assert r["filters"].get(k) == v, (query, r["filters"])
    assert r["total"] > 0
    for it in r["items"]:
        full = lib.get(it["id"])
        if "category" in expect:
            assert full.category == expect["category"]
        if "material" in expect:
            assert full.material_family == expect["material"]
        if "color" in expect:
            assert expect["color"] in {c["name"] for c in full.colors}


def test_keywords_narrow_results(lib):
    r = lib.search("king size bed")
    assert r["items"] and all("king" in i["name"].lower() or "king" in i["subcategory"] for i in r["items"])
    r = lib.search("l-shaped sofa")
    assert {i["subcategory"] for i in r["items"]} == {"L-shaped"}


def test_never_invents_items(lib):
    r = lib.search("purple unicorn hovercraft")
    assert all(i["id"] in lib.items for i in r["items"])
    r = lib.search("olive sofa")         # no olive sofa exists: the colour is relaxed and reported
    assert "color" in r["relaxed"] and all(i["category"] == "sofa" for i in r["items"])


def test_explicit_filters_and_dynamic_facets(lib):
    r = lib.search(category="sofa", material="leather")
    assert r["total"] > 0 and all(lib.get(i["id"]).material_family == "leather" for i in r["items"])
    sofa_styles = {f["value"] for f in r["facets"]["style"]}
    lamps = lib.search(category="pendant_light")
    assert {f["value"] for f in lamps["facets"]["material"]} != {f["value"] for f in r["facets"]["material"]}
    # a facet ignores its own filter so other choices stay visible
    assert len(sofa_styles) > 1
    sizes = {f["value"] for f in lib.search(category="bed")["facets"]["size"]}
    assert sizes <= {"small", "medium", "large"} and len(sizes) >= 2


def test_sorting_and_pagination(lib):
    first = lib.search(category="sofa", sort="width_asc", page_size=5)
    widths = [i["dimensions"]["width"] for i in first["items"]]
    assert widths == sorted(widths)
    assert first["pages"] == -(-first["total"] // 5)
    second = lib.search(category="sofa", sort="width_asc", page_size=5, page=2)
    assert not {i["id"] for i in first["items"]} & {i["id"] for i in second["items"]}
    assert lib.search(page_size=500)["page_size"] == libmod.MAX_PAGE_SIZE


def test_context_categories(lib):
    assert lib.category_for_type("sofa") == "sofa"
    assert lib.category_for_type("chest_of_drawers") == "dresser"
    assert lib.category_for_type("lamp", "floor") == "floor_lamp"
    assert lib.category_for_type("lamp", "surface") == "table_lamp"
    assert lib.category_for_type("curtain") == "curtains"
    assert lib.category_for_type("window") is None


# ---- API ------------------------------------------------------------------------------------

def test_library_api():
    cats = client.get("/api/interior/library/categories").json()
    assert cats["total"] >= 150 and any(g["id"] == "lighting" for g in cats["groups"])
    r = client.get("/api/interior/library/search", params={"q": "velvet sofa", "page_size": 6}).json()
    assert r["items"] and r["filters"] == {"category": "sofa", "material": "velvet"}
    it = r["items"][0]
    for key in ("id", "name", "category", "style", "material", "colors", "dimensions", "thumbnail_url"):
        assert key in it
    detail = client.get(f"/api/interior/library/items/{it['id']}").json()
    assert detail["model"]["kind"] == "parametric" and detail["materials_allowed"]
    png = client.get(it["thumbnail_url"])
    assert png.status_code == 200 and png.headers["content-type"] == "image/png" and "etag" in png.headers
    assert cv2.imdecode(np.frombuffer(png.content, np.uint8), cv2.IMREAD_COLOR).shape == (240, 320, 3)
    assert client.get("/api/interior/library/items/nope").status_code == 404
    assert client.get("/api/interior/library/search", params={"category": "nope"}).status_code == 422
    sw = client.get("/api/interior/library/materials/herringbone/swatch.png")
    assert sw.status_code == 200 and sw.headers["content-type"] == "image/png"


# ---- extending the library through data ---------------------------------------------------

@pytest.fixture
def custom_library(tmp_path):
    src = os.path.dirname(libmod.__file__) + "/library_data"
    dst = tmp_path / "library_data"
    shutil.copytree(src, dst)
    return dst


def test_new_items_and_categories_need_only_data(custom_library):
    meta = json.loads((custom_library / "categories.json").read_text(encoding="utf-8"))
    meta["categories"].append({"id": "daybed", "label": "Daybeds", "group": "seating", "placement": "floor",
                               "generator": "sofa", "size_breaks_cm": [150, 200], "materials": ["fabric", "velvet"],
                               "synonyms": ["daybed", "day bed"]})
    (custom_library / "categories.json").write_text(json.dumps(meta), encoding="utf-8")
    (custom_library / "items" / "extra.json").write_text(json.dumps([{
        "id": "daybed-linen-daybed", "name": "Linen Daybed", "category": "daybed", "subcategory": "daybed",
        "style": "scandinavian", "material": "linen", "color": "cream", "colors": ["cream", "gray"],
        "dimensions": {"width": 190, "depth": 85, "height": 70}, "unit": "cm", "dimensions_source": "nominal",
        "tags": [], "model": {"kind": "parametric", "generator": "sofa", "params": {"seats": 1, "arm": "slim"}}}]),
        encoding="utf-8")
    lib = Library(str(custom_library))
    r = lib.search("scandinavian daybed")
    assert [i["id"] for i in r["items"]] == ["daybed-linen-daybed"]
    assert render_preview(lib, lib.get("daybed-linen-daybed")).shape == (240, 320, 3)


def test_bad_data_is_rejected(custom_library):
    (custom_library / "items" / "bad.json").write_text(json.dumps([{
        "id": "x", "name": "X", "category": "sofa", "material": "unobtainium",
        "dimensions": {"width": 1, "depth": 1, "height": 1}, "model": {"kind": "parametric", "generator": "sofa"}}]),
        encoding="utf-8")
    with pytest.raises(LibraryError):
        Library(str(custom_library))


def test_future_3d_files_are_skipped_not_fatal(custom_library):
    (custom_library / "items" / "gltf.json").write_text(json.dumps([{
        "id": "sofa-scanned", "name": "Scanned Sofa", "category": "sofa", "material": "fabric",
        "dimensions": {"width": 200, "depth": 90, "height": 80}, "model": {"kind": "gltf", "file": "x.glb"}}]),
        encoding="utf-8")
    lib = Library(str(custom_library))
    assert "sofa-scanned" not in lib.items and len(lib.items) >= 150


def test_2d_image_assets_render_in_a_room(custom_library, monkeypatch):
    """A cut-out picture item stands on the floor at its real size."""
    from app.services.interior import renderer
    from tests import roomfactory as rf
    from tests.test_interior_render import apply, draw
    from app.services.interior import operations
    from app.services.interior.renderer import Assets
    from app.services.interior.scene_builder import build_scene
    os.makedirs(custom_library / "assets", exist_ok=True)
    pic = np.zeros((200, 100, 4), np.uint8)
    pic[20:200, 20:80] = (30, 30, 200, 255)                    # a red stand-up, transparent around it
    cv2.imwrite(str(custom_library / "assets" / "red_lamp.png"), pic)
    (custom_library / "items" / "img.json").write_text(json.dumps([{
        "id": "floor_lamp-red-cutout", "name": "Red Cut-out Lamp", "category": "floor_lamp", "material": "painted",
        "color": "#aa2222", "dimensions": {"width": 40, "depth": 40, "height": 160},
        "model": {"kind": "image", "file": "assets/red_lamp.png"}}]), encoding="utf-8")
    lib = Library(str(custom_library))
    monkeypatch.setattr(libmod, "_library", lib)
    monkeypatch.setattr(libmod, "DATA_DIR", str(custom_library))
    renderer._images.clear()
    img = rf.room_image()
    cls, conf = rf.FakeSegmenter().segment(img)
    det, instances, alphas = build_scene(img, cls, conf, rf.LABELS)
    info = {"width": rf.W, "height": rf.H, "original_width": rf.W, "original_height": rf.H, "quality": {}, "warnings": []}
    scene = operations.initial_scene("t" * 32, det, info)
    crops = {}
    for idx, a in alphas.items():
        ys, xs = np.where(a > 0)
        crops[idx] = (int(ys.min()), int(xs.min()), a[ys.min():ys.max() + 1, xs.min():xs.max() + 1])
    assets = Assets(original=img, instances=instances, alphas=crops)
    s = apply(scene, det, {"operation": "add_object", "object": {"library_item": "floor_lamp-red-cutout",
                                                               "position": {"x": 0.12, "y": 0.9}}})
    o = next(o for o in s["objects"] if (o.get("library_item") or {}).get("id") == "floor_lamp-red-cutout")
    out = draw(s, det, assets)
    b = o["bounds"]
    box = (int((b["x"] + b["w"] * 0.4) * rf.W), int((b["y"] + b["h"] * 0.4) * rf.H),
           int((b["x"] + b["w"] * 0.6) * rf.W), int((b["y"] + b["h"] * 0.7) * rf.H))
    bgr = rf.mean_color(out, box)
    assert bgr[2] > bgr[0] + 60                                  # the red picture is there
    assert b["y"] + b["h"] == pytest.approx(0.9, abs=0.02)      # standing on the floor point
