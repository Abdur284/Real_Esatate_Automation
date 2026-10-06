"""
Photographic rendering of real 3D models into the room photo.

For a library piece backed by a glTF asset (meshes.py) this renders, through
the photo's own camera:

  * geometry: every triangle of the scanned model, z-buffered, supersampled
    (anti-aliased edges), alpha-tested leaves, see-through glass;
  * materials: the asset's PBR textures -- colour, normal map (stitching,
    grain, folds), roughness, metalness, baked ambient occlusion -- with mip
    mapping; a new colour tints the upholstery texture keeping its detail; a
    new material is a photographed PBR texture of that material at real
    scale (tri-planar, in the object's own metres) on the upholstery parts;
  * light: the room's estimated key light, ambient bounce and exposure
    (lighting.py), GGX specular, reflections of the room itself on glossy
    and metal surfaces, and the model's shadow on itself (shadow map);
  * contact with the room: a shadow cast by the key light onto the floor and
    walls behind it (the same shadow map, softened by the light's size) and
    contact occlusion where it stands on the floor, so it does not float.

The result is cached per object state, so an unchanged piece is not
re-rendered when something else in the room changes.
"""
import hashlib
import json
import math
from collections import OrderedDict
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

from . import geometry, meshes, pbr
from .camera import Camera
from .catalog import MATERIALS
from .lighting import RoomLight, linear_to_srgb, lum, srgb_to_linear
from .materials import hex_to_bgr
from .raster import rasterize

EMISSIVE_WORDS = ("bulb", "flame", "lamp_light", "_light", "lamps_")
GLASS_WORDS = ("glass", "globe")


# ---- texture helpers -------------------------------------------------------------

_pyr_cache: "OrderedDict[tuple, List[np.ndarray]]" = OrderedDict()


def _tinted(key: tuple, img: np.ndarray, color_bgr: np.ndarray) -> np.ndarray:
    """The upholstery texture recoloured: target colour, original detail."""
    rgb = img[..., :3]
    lab = cv2.cvtColor(rgb.astype(np.float32), cv2.COLOR_RGB2LAB)
    t = cv2.cvtColor((color_bgr[::-1][None, None, :] / 255.0).astype(np.float32), cv2.COLOR_RGB2LAB)[0, 0]
    L = lab[..., 0]
    med = float(np.median(L))
    out = np.empty_like(lab)
    out[..., 0] = np.clip(t[0] + (L - med) * 0.85, 0, 100)
    out[..., 1] = t[1] + (lab[..., 1] - float(np.median(lab[..., 1]))) * 0.25
    out[..., 2] = t[2] + (lab[..., 2] - float(np.median(lab[..., 2]))) * 0.25
    res = np.clip(cv2.cvtColor(out, cv2.COLOR_LAB2RGB), 0, 1)
    if img.shape[2] == 4:
        res = np.dstack([res, img[..., 3]])
    return res.astype(np.float32)


def _mask_weight(rgb: np.ndarray, mask: Optional[Dict]) -> np.ndarray:
    """How much of each texel is upholstery (0..1): texels close in colour
    (CIELAB distance) to the item's upholstery colour, soft at the edge."""
    if not mask:
        return np.ones(rgb.shape[:2], np.float32)
    lab = cv2.cvtColor(np.clip(rgb, 0, 1).astype(np.float32), cv2.COLOR_RGB2LAB)
    ref = hex_to_bgr(mask["color"])[::-1] / 255.0
    t = cv2.cvtColor(ref[None, None, :].astype(np.float32), cv2.COLOR_RGB2LAB)[0, 0]
    dist = np.sqrt(((lab - t) ** 2).sum(2))
    tol = float(mask.get("tolerance", 20))
    w = np.clip((1.6 * tol - dist) / (0.6 * tol), 0, 1)
    w = cv2.GaussianBlur(w, (0, 0), 1.2)
    return (w * w * (3 - 2 * w)).astype(np.float32)


def _stack(mesh: meshes.Mesh, k: int, tint: Optional[np.ndarray], mask: Optional[Dict] = None,
           slot: bool = False) -> List[np.ndarray]:
    """All texture maps of material k in one 11-channel image (so one lookup
    serves them all), as a mip pyramid:
      0-2 colour (sRGB RGB), 3 alpha, 4-6 normal (tangent space),
      7 roughness, 8 metalness, 9 ambient occlusion,
      10 how much a new colour/material applies here (upholstery weight)."""
    key = (mesh.asset, mesh.quality, k, None if tint is None else tuple(int(c) for c in tint),
           json.dumps(mask, sort_keys=True) if mask else None, slot)
    if key in _pyr_cache:
        _pyr_cache.move_to_end(key)
        return _pyr_cache[key]
    mt = mesh.materials[k]
    maps = [x for x in (mt.base, mt.normal, mt.mr, mt.occlusion) if x is not None]
    h, w = maps[0].shape[:2] if maps else (4, 4)

    def fit(img):
        return img if img.shape[:2] == (h, w) else cv2.resize(img, (w, h), interpolation=cv2.INTER_AREA)
    out = np.zeros((h, w, 11), np.float32)
    out[..., 0:3] = 1.0
    out[..., 3] = 1.0
    out[..., 6] = 1.0
    out[..., 7] = 1.0
    out[..., 8] = 1.0
    out[..., 9] = 1.0
    if mt.base is not None:
        base = fit(mt.base)
        weight = _mask_weight(base[..., :3], mask) if slot else np.zeros((h, w), np.float32)
        out[..., 10] = weight
        if tint is not None and slot:
            tinted = _tinted((mesh.asset, mesh.quality, k), base, tint)
            base = base * (1 - weight[..., None]) + tinted * weight[..., None]
        out[..., 0:3] = base[..., :3]
        if base.shape[2] == 4:
            out[..., 3] = base[..., 3]
    else:
        out[..., 10] = 1.0 if slot else 0.0
    if mt.normal is not None:
        out[..., 4:7] = fit(mt.normal)
    if mt.mr is not None:
        mr = fit(mt.mr)
        out[..., 7] = mr[..., 1]
        out[..., 8] = mr[..., 2]
    if mt.occlusion is not None:
        out[..., 9] = fit(mt.occlusion)[..., 0]
    levels = [out]
    while min(levels[-1].shape[:2]) > 8 and len(levels) < 10:
        levels.append(cv2.pyrDown(levels[-1]))
    _pyr_cache[key] = levels
    while len(_pyr_cache) > 40:
        _pyr_cache.popitem(last=False)
    return levels


def _triplanar(material: str, color_bgr: Optional[np.ndarray], P: np.ndarray, N: np.ndarray, quality: str,
               mpp: float) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
    """Linear BGR albedo and roughness of a library material at real scale on
    arbitrary geometry (object-space metres, blended by the normal)."""
    ts = pbr.texture_set(material, quality)
    w = np.abs(N) ** 4
    w = w / np.maximum(w.sum(1, keepdims=True), 1e-6)
    if ts is None:
        spec = MATERIALS.get(material, {"color": "#808080", "tintable": True})
        base = color_bgr if (color_bgr is not None and spec.get("tintable")) else hex_to_bgr(spec["color"])
        return np.broadcast_to(srgb_to_linear(base / 255.0), (len(P), 3)).astype(np.float32), None
    tint = color_bgr if pbr.PROPS[material].get("tint") else None
    levels = pbr.albedo_levels(material, tint, quality)
    lvl = pbr.pick_level(levels, ts.size_m, mpp)
    img = levels[lvl]
    col = np.zeros((len(P), 3), np.float32)
    rough = np.zeros(len(P), np.float32) if ts.rough is not None else None
    s = ts.size_m
    for axis, (a, b) in enumerate(((2, 1), (0, 2), (0, 1))):
        sel = w[:, axis] > 0.01
        if not sel.any():
            continue
        fu, fv = P[sel, a] / s, -P[sel, b] / s
        col[sel] += pbr.sample(img, fu, fv) * w[sel, axis, None]
        if rough is not None:
            rough[sel] += pbr.sample(ts.rough, fu, fv) * w[sel, axis]
    if color_bgr is not None and not pbr.PROPS[material].get("tint"):
        t = color_bgr / np.maximum(hex_to_bgr(MATERIALS[material]["color"]), 1)
        col = col * (0.3 + 0.7 * t)
    return srgb_to_linear(np.clip(col / 255.0, 0, 1)), rough


# ---- shading ------------------------------------------------------------------

def _dot(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return a[:, 0] * b[:, 0] + a[:, 1] * b[:, 1] + a[:, 2] * b[:, 2]


def _unit(a: np.ndarray) -> np.ndarray:
    return a / np.maximum(np.sqrt(_dot(a, a)), 1e-9)[:, None]


def _shadow_basis(d: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    up = np.array([0.0, 1.0, 0.0]) if abs(d[1]) < 0.95 else np.array([1.0, 0.0, 0.0])
    u = np.cross(up, d)
    u /= np.linalg.norm(u)
    return u.astype(np.float32), np.cross(d, u).astype(np.float32)


class ShadowMap:
    """Depth of the model seen from the key light (orthographic)."""

    def __init__(self, P: np.ndarray, tris: np.ndarray, d: np.ndarray, radius: float, keep=None):
        self.d = d.astype(np.float32)
        self.u, self.v = _shadow_basis(self.d)
        a, b = P @ self.u, P @ self.v
        span = max(float(np.ptp(a)), float(np.ptp(b)), 0.05)
        self.texel = max(span / 420.0, 0.005)
        self.a0, self.b0 = float(a.min()) - 8 * self.texel, float(b.min()) - 8 * self.texel
        w = int((np.ptp(a)) / self.texel) + 17
        h = int((np.ptp(b)) / self.texel) + 17
        xy = np.stack([(a - self.a0) / self.texel, (b - self.b0) / self.texel], 1)
        _, _, z = rasterize(xy, -(P @ self.d), tris, w, h, keep=keep)
        self.z = z
        self.soft = 0.012 + 0.25 * radius          # penumbra width (m) grows with the light's size
        ang = np.linspace(0, 2 * np.pi, 12, endpoint=False)
        rr = np.sqrt((np.arange(12) + 0.5) / 12)
        self.offsets = np.stack([np.cos(ang * 2.39996) * rr, np.sin(ang * 2.39996) * rr], 1)

    def occlusion(self, Q: np.ndarray, bias: float = 0.02, soft: Optional[float] = None) -> np.ndarray:
        """0 (lit) .. 1 (fully shadowed) for world points Q (N, 3)."""
        if not len(Q):
            return np.zeros(0, np.float32)
        a = (Q @ self.u - self.a0) / self.texel
        b = (Q @ self.v - self.b0) / self.texel
        depth = -(Q @ self.d)
        h, w = self.z.shape
        r = (soft if soft is not None else self.soft) / self.texel
        occ = np.zeros(len(Q), np.float32)
        for ox, oy in self.offsets:
            x = np.clip(np.round(a + ox * r).astype(np.int64), 0, w - 1)
            y = np.clip(np.round(b + oy * r).astype(np.int64), 0, h - 1)
            occ += (self.z[y, x] < depth - bias)
        return occ / len(self.offsets)


def _env_lookup(light: RoomLight, cam: Camera, P: np.ndarray, R: np.ndarray, rough: np.ndarray) -> np.ndarray:
    """Radiance reflected from the room: where the reflected ray meets a
    surface ~2.5 m away, looked up in the photo; the sky/ground ambient
    where that point is outside the picture."""
    Q = P + R * 2.5
    ok = Q[:, 2] > 0.2
    z = np.maximum(Q[:, 2], 0.2)
    x = (cam.vx + cam.f * Q[:, 0] / z) / light.env_scale
    y = (cam.horizon + cam.f * (cam.eye_height_m - Q[:, 1]) / z) / light.env_scale
    h, w = light.env.shape[:2]
    ok &= (x >= 0) & (x < w) & (y >= 0) & (y < h)
    fx, fy = (np.clip(x, 0, w - 1) + 0.5) / w, (np.clip(y, 0, h - 1) + 0.5) / h
    sharp = pbr.sample(light.env, fx, fy)
    blur = pbr.sample(light.env_blur, fx, fy)
    t = np.clip(rough * 2.0, 0, 1)[:, None]
    photo = sharp * (1 - t) + blur * t
    hemi = light.ground + (light.sky - light.ground) * np.clip(0.5 + 0.5 * R[:, 1:2], 0, 1)
    return np.where(ok[:, None], photo, hemi).astype(np.float32)


def _material_role(mat: meshes.MeshMaterial) -> str:
    """surface | glass (see-through, glossy) | blend (texture transparency,
    e.g. fringes) | emissive (bulbs, flames)."""
    n = mat.name.lower()
    if ("flame" in n or "bulb" in n or n.endswith("_lamp")
            or (mat.base is None and any(w in n for w in EMISSIVE_WORDS))):
        return "emissive"
    if any(w in n for w in GLASS_WORDS):
        return "glass"
    if mat.alpha_mode == "BLEND":
        return "blend"
    return "surface"


def _mip_level(tex_w: int, uv_tri: np.ndarray, xy_tri: np.ndarray) -> int:
    """Mip level from texels per screen pixel (median over the triangles)."""
    def area2(p):
        a, b = p[:, 1] - p[:, 0], p[:, 2] - p[:, 0]
        return np.abs(a[:, 0] * b[:, 1] - a[:, 1] * b[:, 0])
    duv = area2(uv_tri) * tex_w * tex_w
    dxy = area2(xy_tri)
    good = dxy > 0.05
    if not good.any():
        return 0
    ratio = np.median(np.sqrt(duv[good] / dxy[good]))
    return int(np.clip(np.floor(np.log2(max(ratio, 1e-6))), 0, 8))


def render_layer(obj: Dict, cam: Camera, W: int, H: int, light: RoomLight, quality: str = "1k",
                 S: int = 2) -> Optional[Dict]:
    """The model alone: BGR colour, coverage, its position in the image, and
    what is needed to cast its shadow onto the room."""
    m = obj["model"]
    mesh = meshes.load(m["asset"], quality, m.get("yaw", 0.0))
    P, N = geometry.mesh_world(obj, mesh, cam, W, H)
    front = P[:, 2] > 0.05
    tris = mesh.tris[front[mesh.tris].all(1)]
    tmat = mesh.tri_mat[front[mesh.tris].all(1)]
    if not len(tris):
        return None
    xy = geometry.project_points(P, cam)
    used = np.unique(tris)
    x0, y0 = np.floor(xy[used].min(0)).astype(int) - 2
    x1, y1 = np.ceil(xy[used].max(0)).astype(int) + 2
    x0c, y0c, x1c, y1c = max(0, x0), max(0, y0), min(W, x1), min(H, y1)
    if x0c >= x1c or y0c >= y1c:
        return None
    ww, hh = (x1c - x0c) * S, (y1c - y0c) * S
    sxy = ((xy - [x0c, y0c]) * S).astype(np.float64)
    roles = [_material_role(mt) for mt in mesh.materials]
    glass_t = np.array([roles[k] in ("glass", "blend") for k in tmat], bool)

    def alpha_keep(t: np.ndarray, L: np.ndarray, source=tris, mats=tmat) -> np.ndarray:
        keep = np.ones(len(t), bool)
        for k, mt in enumerate(mesh.materials):
            if mt.alpha_mode != "MASK" or mt.base is None or mt.base.shape[2] < 4:
                continue
            sel = mats[t] == k
            if not sel.any():
                continue
            uv = (L[sel, :, None] * mesh.uvs[source[t[sel]]]).sum(1)
            a = pbr.sample(mt.base[..., 3], uv[:, 0], uv[:, 1]) * mt.base_factor[3]
            keep[np.nonzero(sel)[0][a < mt.alpha_cutoff]] = False
        return keep

    inv_w = 1.0 / np.maximum(P[:, 2], 1e-3)
    opaque = tris[~glass_t]
    op_mat = tmat[~glass_t]
    tri_o, bary_o, z_o = rasterize(sxy, P[:, 2], opaque, ww, hh, inv_w,
                                   keep=lambda t, L: alpha_keep(t, L, opaque, op_mat))
    glass = tris[glass_t]
    gl_mat = tmat[glass_t]
    if len(glass):
        tri_g, bary_g, z_g = rasterize(sxy, P[:, 2], glass, ww, hh, inv_w)
        tri_g[z_g >= z_o] = -1
    else:
        tri_g = None

    # the key light, as seen from this object, and its shadow map (opaque parts only)
    centre = P[used].mean(0)
    d = light.key_pos - centre
    d = (d / max(np.linalg.norm(d), 1e-6)).astype(np.float32)
    smap = ShadowMap(P, opaque, d, light.radius, keep=lambda t, L: alpha_keep(t, L, opaque, op_mat))

    ap = obj.get("appearance") or {}
    native = (obj.get("library_item") or {}).get("material") or m.get("material")
    slots = set(m.get("recolor") or [])
    mask = m.get("recolor_mask")
    new_mat = ap.get("material") if ap.get("material") not in (None, "original", native) else None
    color = ap.get("color")
    native_color = (m.get("native_color") or "").lower()
    color_bgr = hex_to_bgr(color) if color and color.lower() != native_color else None
    mpp = float(np.median(P[used][:, 2])) / cam.f / S
    tangent_cache: Dict[int, Tuple[np.ndarray, np.ndarray]] = {}

    def _tangents(source: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        if id(source) not in tangent_cache:
            p0, p1, p2 = P[source[:, 0]], P[source[:, 1]], P[source[:, 2]]
            u0, u1, u2 = mesh.uvs[source[:, 0]], mesh.uvs[source[:, 1]], mesh.uvs[source[:, 2]]
            d1, d2 = u1 - u0, u2 - u0
            det = d1[:, 0] * d2[:, 1] - d2[:, 0] * d1[:, 1]
            ok = np.abs(det) > 1e-12
            r = np.where(ok, 1.0 / np.where(ok, det, 1.0), 0.0)[:, None]
            tangent_cache[id(source)] = (((p1 - p0) * d2[:, 1:2] - (p2 - p0) * d1[:, 1:2]) * r).astype(np.float32), \
                np.where(det < 0, -1.0, 1.0).astype(np.float32)
        return tangent_cache[id(source)]

    def shade(tri_map, bary_map, source, mats) -> Tuple[np.ndarray, np.ndarray]:
        pix = np.nonzero(tri_map.reshape(-1) >= 0)[0]
        out = np.zeros((hh * ww, 3), np.float32)
        cover = np.zeros(hh * ww, np.float32)
        if not len(pix):
            return out.reshape(hh, ww, 3), cover.reshape(hh, ww)
        t = tri_map.reshape(-1)[pix]
        B = bary_map.reshape(-1, 3)[pix]
        vi = source[t]
        Pp = np.einsum("nk,nkj->nj", B, P[vi])
        Nn = _unit(np.einsum("nk,nkj->nj", B, N[vi]))
        UV = np.einsum("nk,nkj->nj", B, mesh.uvs[vi])
        V = _unit(np.array([0.0, cam.eye_height_m, 0.0], np.float32) - Pp)
        Nn[_dot(Nn, V) < 0] *= -1
        # tangent frame (per triangle, from positions and texture coordinates)
        tan, sgn = _tangents(source)
        T = tan[t]
        T = _unit(T - Nn * _dot(T, Nn)[:, None])
        Bt = np.cross(Nn, T) * sgn[t][:, None]
        mat_of = mats[t]
        albedo = np.ones((len(pix), 3), np.float32) * 0.5      # linear BGR
        alpha = np.ones(len(pix), np.float32)
        rough = np.full(len(pix), 0.7, np.float32)
        metal = np.zeros(len(pix), np.float32)
        ao = np.ones(len(pix), np.float32)
        emit = np.zeros(len(pix), bool)
        for k, mt in enumerate(mesh.materials):
            sel = mat_of == k
            if not sel.any():
                continue
            idx = np.nonzero(sel)[0]
            uv = UV[idx]
            tsel = np.unique(t[idx])
            role = roles[k]
            # which parts take a new colour/material: named upholstery
            # materials, or the upholstery-coloured texels (recolor_mask)
            recolour = mt.name in slots if slots else bool(mask)
            lv = _stack(mesh, k, color_bgr if recolour else None, None if slots else mask, recolour)
            lvl = min(len(lv) - 1, _mip_level(lv[0].shape[1], mesh.uvs[source[tsel]], sxy[source[tsel]]))
            tx = pbr.sample(lv[lvl], uv[:, 0], uv[:, 1])          # (n, 11): see _stack
            albedo[idx] = srgb_to_linear(tx[:, 2::-1]) * mt.base_factor[2::-1]
            if mt.base is None and color_bgr is not None and recolour:
                albedo[idx] = srgb_to_linear(color_bgr / 255.0)
            alpha[idx] = 1.0 if mt.alpha_mode == "MASK" else tx[:, 3] * mt.base_factor[3]
            rough[idx] = np.clip(tx[:, 7] * mt.rough, 0.03, 1)
            metal[idx] = np.clip(tx[:, 8] * mt.metal, 0, 1)
            ao[idx] = np.clip(tx[:, 9], 0, 1)
            if mt.normal is not None:
                Nn[idx] = _unit(T[idx] * tx[:, 4:5] + Bt[idx] * tx[:, 5:6] + Nn[idx] * tx[:, 6:7])
            if new_mat and recolour and role == "surface":
                wgt = np.clip(tx[:, 10:11], 0, 1)
                obj_local = Pp[idx] - centre
                rgb, rmap = _triplanar(new_mat, color_bgr if color else None, obj_local, Nn[idx], quality, mpp)
                # keep the original's shading detail (folds, tufting) under the new material
                detail = np.clip(lum(albedo[idx]) / max(float(np.median(lum(albedo[idx]))), 1e-4), 0.4, 1.8)
                albedo[idx] = albedo[idx] * (1 - wgt) + rgb * detail[:, None] ** 0.5 * wgt
                pp = pbr.props(new_mat)
                r_new = rmap * 0.6 + pp["rough"] * 0.4 if rmap is not None else pp["rough"]
                rough[idx] = rough[idx] * (1 - wgt[:, 0]) + r_new * wgt[:, 0]
                metal[idx] = metal[idx] * (1 - wgt[:, 0]) + pp["metal"] * wgt[:, 0]
            if role == "emissive":
                emit[idx] = True
            if role == "glass":
                rough[idx] = np.minimum(rough[idx], 0.15)
                alpha[idx] = np.clip(np.where(alpha[idx] >= 0.99, 0.3, alpha[idx]), 0.12, 0.85)
        # lighting (linear)
        Lv = _unit(light.key_pos - Pp)
        NdL = np.clip(_dot(Nn, Lv), 0, 1)
        NdV = np.clip(_dot(Nn, V), 1e-3, 1)
        Hv = _unit(Lv + V)
        NdH = np.clip(_dot(Nn, Hv), 0, 1)
        VdH = np.clip(_dot(V, Hv), 0, 1)
        vis = 1.0 - smap.occlusion(Pp, bias=0.015 + 2 * smap.texel, soft=smap.soft * 0.5)
        a2 = np.maximum(rough, 0.04) ** 4
        D = a2 / (np.pi * (NdH ** 2 * (a2 - 1) + 1) ** 2)
        kk = (rough + 1) ** 2 / 8
        G = NdL / (NdL * (1 - kk) + kk) * NdV / (NdV * (1 - kk) + kk)
        F0 = 0.04 * (1 - metal[:, None]) + albedo * metal[:, None]
        F = F0 + (1 - F0) * ((1 - VdH) ** 5)[:, None]
        spec = (D * G / np.maximum(4 * NdL * NdV, 1e-4))[:, None] * F * np.pi
        kd = (1 - F) * (1 - metal[:, None])
        key = light.key[None, :] * (NdL * vis)[:, None]
        hemi = light.ground + (light.sky - light.ground) * np.clip(0.5 + 0.5 * Nn[:, 1:2], 0, 1)
        R = 2 * _dot(Nn, V)[:, None] * Nn - V
        Fe = F0 + (np.maximum(1 - rough[:, None], F0) - F0) * ((1 - NdV) ** 5)[:, None]
        env = _env_lookup(light, cam, Pp, R, rough) * Fe * ao[:, None] * (1 - 0.6 * rough[:, None])
        col_bgr = (kd * albedo + spec) * key + kd * albedo * hemi * ao[:, None] + env
        if emit.any():
            col_bgr[emit] = np.array([0.82, 0.95, 1.0], np.float32) * max(1.0, float(lum(light.sky + light.key)) * 1.4)
        out[pix] = linear_to_srgb(col_bgr) * 255.0
        cover[pix] = alpha
        return out.reshape(hh, ww, 3), cover.reshape(hh, ww)

    col, cov = shade(tri_o, bary_o, opaque, op_mat)
    if tri_g is not None and (tri_g >= 0).any():
        gcol, gcov = shade(tri_g, bary_g, glass, gl_mat)
        g = gcov[..., None]
        col = gcol * g + col * cov[..., None] * (1 - g)
        cov = gcov + cov * (1 - gcov)
        col = np.where(cov[..., None] > 1e-4, col / np.maximum(cov[..., None], 1e-4), 0)
    pre = cv2.resize(col * cov[..., None], (x1c - x0c, y1c - y0c), interpolation=cv2.INTER_AREA)
    a = cv2.resize(cov, (x1c - x0c, y1c - y0c), interpolation=cv2.INTER_AREA)
    rgb = np.where(a[..., None] > 1e-4, pre / np.maximum(a[..., None], 1e-4), 0)
    return {"rgb": rgb.astype(np.float32), "alpha": np.clip(a, 0, 1).astype(np.float32), "x0": x0c, "y0": y0c,
            "P": P, "tris": opaque, "smap": smap, "used": used, "d": d}


# ---- the model's effect on the room ---------------------------------------------

def room_shadow(layer: Dict, obj: Dict, scene: Dict, cam: Camera, light: RoomLight, behind: np.ndarray,
                receivers: np.ndarray, W: int, H: int) -> Optional[Tuple[np.ndarray, int, int]]:
    """Multiplicative darkening (h, w) of the floor and walls around the
    model: its cast shadow from the key light plus contact occlusion under
    it. `receivers` marks pixels that are bare floor/wall."""
    P = layer["P"][layer["used"]]
    d = layer["d"]
    lo, hi = P.min(0), P.max(0)
    corners = np.array([[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])],
                       np.float32)
    pts = [corners]
    if d[1] > 0.08:        # where the corners' shadows land on the floor
        pts.append(corners - d[None, :] * (corners[:, 1:2] / d[1]))
    allp = np.vstack(pts)
    allp = allp[allp[:, 2] > 0.1]
    if not len(allp):
        return None
    xy = geometry.project_points(allp, cam)
    pad = 0.15 * max(np.ptp(xy[:, 0]), np.ptp(xy[:, 1]), 20)
    x0, y0 = np.floor(xy.min(0) - pad).astype(int)
    x1, y1 = np.ceil(xy.max(0) + pad).astype(int)
    x0, y0, x1, y1 = max(0, x0), max(int(cam.horizon) - 5 if obj["placement"] == "floor" and d[1] > 0.5 else 0, y0), \
        min(W, x1), min(H, y1)
    x0, y0 = max(0, x0), max(0, y0)
    if x0 >= x1 or y0 >= y1:
        return None
    ys, xs = np.mgrid[y0:y1, x0:x1]
    beh = behind[y0:y1, x0:x1]
    rec = receivers[y0:y1, x0:x1]
    Q = np.zeros(ys.shape + (3,), np.float32)
    on_floor = (beh == 1) & rec & (ys > cam.horizon + 1)
    zf = cam.f * cam.eye_height_m / np.maximum(ys + 0.5 - cam.horizon, 1e-3)
    Q[..., 0] = np.where(on_floor, (xs + 0.5 - cam.vx) * zf / cam.f, 0)
    Q[..., 2] = np.where(on_floor, zf, 0)
    on_wall = (beh == 0) & rec
    if on_wall.any():
        cols = np.arange(x0, x1)
        zw = np.array([geometry.wall_depth(scene, cam, float(c)) for c in cols[:: max(1, len(cols) // 64)]])
        zw = np.interp(cols, cols[:: max(1, len(cols) // 64)], zw)[None, :].repeat(y1 - y0, 0)
        Q[..., 0] = np.where(on_wall, (xs + 0.5 - cam.vx) * zw / cam.f, Q[..., 0])
        Q[..., 1] = np.where(on_wall, cam.eye_height_m + (cam.horizon - ys - 0.5) * zw / cam.f, Q[..., 1])
        Q[..., 2] = np.where(on_wall, zw, Q[..., 2])
    valid = on_floor | on_wall
    dark = np.ones(ys.shape, np.float32)
    if not valid.any():
        return None
    q = Q[valid]
    smap = layer["smap"]
    occ = smap.occlusion(q, bias=0.02, soft=smap.soft * 0.6)
    # how much of the receiver's light is the key light
    Lv = light.key_pos - q
    Lv /= np.maximum(np.linalg.norm(Lv, axis=1, keepdims=True), 1e-9)
    n_floor = np.array([0, 1, 0], np.float32)
    n_wall = np.array([0, 0, -1], np.float32)
    nrm = np.where(on_floor[valid][:, None], n_floor, n_wall)
    ndl = np.clip((Lv * nrm).sum(1), 0, 1)
    k = float(lum(light.key))
    amb = float(lum(light.sky)) * 0.8 + float(lum(light.ground)) * 0.2
    share = k * ndl / np.maximum(k * ndl + amb, 1e-6)
    dark[valid] = 1 - 0.92 * share * occ
    if obj["placement"] == "floor" and on_floor.any():
        # contact occlusion: the floor under and right around the piece sees
        # less of the room (a height map of the model seen from above)
        ao = _floor_occlusion(layer, Q[on_floor])
        amb_share = amb / max(amb + k * 0.5, 1e-6)
        dark[on_floor] *= 1 - 0.85 * amb_share * ao
    # soften to the penumbra's size on screen (the samples above are sparse)
    zmed = float(np.median(q[:, 2]))
    dark = cv2.GaussianBlur(dark, (0, 0), float(np.clip(0.45 * smap.soft * cam.f / max(zmed, 0.3), 1.0, 12.0)))
    return dark, x0, y0


def _floor_occlusion(layer: Dict, q: np.ndarray, reach: float = 0.9) -> np.ndarray:
    """0..1 occlusion of floor points q by the model: high under low parts
    (a sofa's base), fading with height and with distance from the piece."""
    P, tris = layer["P"], layer["tris"]
    low = P[:, 1] < reach
    tri_low = tris[low[tris].any(1)]
    if not len(tri_low):
        return np.zeros(len(q), np.float32)
    cell = 0.02
    lo = P[low][:, [0, 2]].min(0) - 0.3
    hi = P[low][:, [0, 2]].max(0) + 0.3
    gw, gh = int((hi[0] - lo[0]) / cell) + 1, int((hi[1] - lo[1]) / cell) + 1
    xy = np.stack([(P[:, 0] - lo[0]) / cell, (P[:, 2] - lo[1]) / cell], 1)
    _, _, hmap = rasterize(xy, P[:, 1], tri_low, gw, gh)
    # a seat 40 cm up still shades the floor under it; a leg touching it, more
    occ = np.where(np.isfinite(hmap), np.exp(-np.clip(hmap, 0, None) / 0.3), 0).astype(np.float32)
    occ = cv2.GaussianBlur(occ, (0, 0), 0.07 / cell)
    occ = np.clip(occ * 1.3, 0, 1)
    gx = ((q[:, 0] - lo[0]) / cell).astype(int)
    gz = ((q[:, 2] - lo[1]) / cell).astype(int)
    inside = (gx >= 0) & (gx < gw) & (gz >= 0) & (gz < gh)
    out = np.zeros(len(q), np.float32)
    out[inside] = occ[gz[inside], gx[inside]]
    return out


def state_key(obj: Dict, quality: str, S: int, light: RoomLight) -> str:
    keep = {k: obj.get(k) for k in ("model", "transform", "appearance", "placement")}
    raw = json.dumps([keep, quality, S, [round(float(v), 3) for v in light.key_pos]], sort_keys=True, default=str)
    return hashlib.sha1(raw.encode()).hexdigest()
