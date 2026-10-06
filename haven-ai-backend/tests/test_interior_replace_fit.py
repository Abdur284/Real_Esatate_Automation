"""
Replacement keeps the replaced object's place, turn and size: the library
piece is scaled from its catalogue size to fill the old one's space
(uniformly for real furniture), and the user can still resize it or go back
to the catalogue size.
"""
import pytest

from app.services.interior import fit, geometry
from app.services.interior.library import get_library
from tests.test_interior_api import client, isolated, new_scene, obj, op  # noqa: F401  (fixture)


def _replace(scene, oid, item, **extra):
    r = op(scene, {"operation": "replace_object", "object_id": oid, "changes": {"library_item": item, **extra}})
    assert r.status_code == 200, r.text
    body = r.json()
    return body, obj(body["scene"], body["scene"]["last_operation"]["assigned_id"])


def _centre_x(b):
    return b["x"] + b["w"] / 2


def test_photo_sofa_is_replaced_at_its_size_not_the_catalogue_size():
    scene = new_scene()["scene"]
    sofa = obj(scene, "sofa_001")
    for item in ("sofa-chesterfield-sofa", "sofa-modern-3-seater-sofa"):
        body, new = _replace(scene, "sofa_001", item)
        lib = get_library().get(item).dimensions
        ob, nb = sofa["bounds"], new["bounds"]
        assert nb["w"] == pytest.approx(ob["w"], rel=0.03)                     # same width in the picture
        assert _centre_x(nb) == pytest.approx(_centre_x(ob), abs=0.01)           # same place
        assert nb["y"] + nb["h"] == pytest.approx(ob["y"] + ob["h"], abs=0.04)  # same floor line
        s = new["transform"]["scale"]
        assert s["x"] == s["y"]                                                 # real proportions kept
        assert new["dimensions_m"]["width"] != pytest.approx(lib["width"] / 100, abs=0.02)
        assert new["fit"]["basis"] == "width" and new["fit"]["library_size_m"]["width"] == lib["width"] / 100
        assert "Sized to fill the space of the original sofa" in body["notes"][0]
        client.post(f"/api/interior/scenes/{scene['scene_id']}/undo")


def test_catalogue_size_on_request_and_switching_back_and_forth():
    scene = new_scene()["scene"]
    body, new = _replace(scene, "sofa_001", "sofa-chesterfield-sofa", fit="catalogue")
    assert new["dimensions_m"]["width"] == pytest.approx(2.2) and new["fit"]["mode"] == "library"
    s = body["scene"]
    r = op(s, {"operation": "fit_object", "object_id": new["id"], "changes": {"size": "original"}})
    assert r.status_code == 422                                   # it was never fitted

    body, fitted = _replace(new_scene()["scene"], "sofa_001", "sofa-chesterfield-sofa")
    sid, s = fitted["id"], body["scene"]
    matched = dict(fitted["transform"]["scale"])
    r = op(s, {"operation": "fit_object", "object_id": sid, "changes": {"size": "catalogue"}})
    assert r.status_code == 200, r.text
    s = r.json()["scene"]
    assert obj(s, sid)["dimensions_m"]["width"] == pytest.approx(2.2)
    assert "catalogue size" in r.json()["notes"][0]
    r = op(s, {"operation": "fit_object", "object_id": sid, "changes": {"size": "original"}})
    assert obj(r.json()["scene"], sid)["transform"]["scale"] == matched
    # the user can still resize it by hand
    r = op(r.json()["scene"], {"operation": "transform_object", "object_id": sid,
                               "changes": {"scale": {"x": 1.3, "y": 1.3, "z": 1.3}}})
    assert r.status_code == 200 and obj(r.json()["scene"], sid)["transform"]["scale"]["x"] == 1.3
    assert op(s, {"operation": "fit_object", "object_id": sid, "changes": {"size": "huge"}}).status_code == 422


def test_model_replaced_by_model_keeps_turn_and_real_size_of_the_first():
    scene = new_scene()["scene"]
    body, first = _replace(scene, "sofa_001", "sofa-modern-3-seater-sofa", fit="catalogue")
    s = body["scene"]
    s = op(s, {"operation": "transform_object", "object_id": first["id"], "changes": {"rotation": 15}}).json()["scene"]
    _, second = _replace(s, first["id"], "sofa-chesterfield-sofa")
    assert second["transform"]["rotation"] == 15
    W1, D1, H1 = (first["dimensions_m"][k] for k in ("width", "depth", "height"))
    assert second["dimensions_m"]["width"] == pytest.approx(W1, abs=0.02)      # dominant dimension matched
    sc = second["transform"]["scale"]
    assert sc["x"] == pytest.approx(sc["y"], rel=fit.STRETCH - 1 + 0.01)        # at most a 15% nudge
    assert second["fit"]["target_m"]["width"] == pytest.approx(W1, abs=0.01)


def test_wall_picture_becomes_a_mirror_of_the_same_size_without_distortion():
    scene = new_scene()["scene"]
    pic = obj(scene, "painting_001")
    _, m = _replace(scene, "painting_001", "mirror-round-brass-mirror")
    s = m["transform"]["scale"]
    assert s["x"] == s["y"]                                         # a round mirror stays round
    assert m["placement"] == "wall"
    nb, ob = m["bounds"], pic["bounds"]
    assert _centre_x(nb) == pytest.approx(_centre_x(ob), abs=0.01)
    assert nb["y"] + nb["h"] / 2 == pytest.approx(ob["y"] + ob["h"] / 2, abs=0.02)
    assert nb["w"] == pytest.approx(ob["w"], rel=0.03) or nb["h"] == pytest.approx(ob["h"], rel=0.03)


def test_rug_fits_length_and_width_independently():
    scene = new_scene()["scene"]
    r = op(scene, {"operation": "add_object", "object": {"library_item": "rug-plain-area-rug"}})
    s = r.json()["scene"]
    rug = obj(s, s["last_operation"]["assigned_id"])
    s = op(s, {"operation": "transform_object", "object_id": rug["id"],
               "changes": {"scale": {"x": 1.4, "z": 0.7}}}).json()["scene"]
    _, new = _replace(s, rug["id"], "rug-striped-rug")
    old_dims = obj(s, rug["id"])["dimensions_m"]
    assert new["dimensions_m"]["width"] == pytest.approx(old_dims["width"], abs=0.02)
    assert new["dimensions_m"]["depth"] == pytest.approx(old_dims["depth"], abs=0.02)
    assert new["fit"]["basis"] == "free"


def test_cut_off_original_falls_back_to_catalogue_and_size_stays_realistic():
    scene = new_scene()["scene"]
    lib = get_library()
    new = lib.scene_object(lib.get("sofa-chesterfield-sofa"), "sofa_009")
    new["transform"]["position"] = {"x": 0.5, "y": 0.8}
    old = {"source": "detected", "label": "Sofa", "bounds": {"x": 0.0, "y": 0.3, "w": 1.0, "h": 0.7}}
    rec = fit.match(new, old, scene)
    assert rec["mode"] == "library" and new["transform"]["scale"] == {"x": 1.0, "y": 1.0, "z": 1.0}
    assert "cut off by the edge of the photo" in fit.describe(rec, new)
    # a tiny (wrongly detected) original does not shrink a sofa to a toy
    old = {"source": "detected", "label": "Sofa", "bounds": {"x": 0.45, "y": 0.75, "w": 0.02, "h": 0.02}}
    rec = fit.match(new, old, scene)
    assert min(new["transform"]["scale"].values()) >= fit.REAL_MIN - 1e-6 and rec["clamped"]
    assert geometry.model_dims(new)[0] >= 2.2 * fit.REAL_MIN - 1e-6
