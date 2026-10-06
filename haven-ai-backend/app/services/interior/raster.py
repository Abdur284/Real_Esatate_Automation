"""
A small vectorised triangle rasteriser (numpy) with a depth buffer.

Used for the real 3D models: the camera view (perspective-correct
barycentrics per pixel, for texturing and shading) and the light's view
(shadow maps). Scan-line based and fully vectorised: every (triangle, row)
pair gets its exact span of covered pixels, so the work is proportional to
the pixels actually covered, whatever the size of the triangles.
"""
from typing import Callable, Optional, Tuple

import numpy as np

_BUDGET = 3_000_000          # covered pixels per numpy batch


def _ranges(counts: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """For counts [2, 3] -> owner [0, 0, 1, 1, 1], offset [0, 1, 0, 1, 2]."""
    owner = np.repeat(np.arange(len(counts)), counts)
    starts = np.cumsum(counts) - counts
    offset = np.arange(int(counts.sum())) - np.repeat(starts, counts)
    return owner, offset


def rasterize(xy: np.ndarray, depth: np.ndarray, tris: np.ndarray, W: int, H: int,
              inv_w: Optional[np.ndarray] = None,
              keep: Optional[Callable[[np.ndarray, np.ndarray], np.ndarray]] = None
              ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Nearest triangle per pixel.

    xy     (V, 2) vertex positions in pixels (pixel (i, j) covers x in [i, i+1))
    depth  (V,)   value to z-test; the smallest wins
    tris   (T, 3) vertex indices
    inv_w  (V,)   1 / camera distance for perspective-correct barycentrics
                  (None: affine, e.g. an orthographic shadow map)
    keep   optional test(tri_ids, barycentrics) -> bool, e.g. an alpha cut-out

    Returns tri (H, W) int32 (-1 = empty), bary (H, W, 3) float32 and
    z (H, W) float32 (inf = empty)."""
    tri_out = np.full(H * W, -1, np.int32)
    bary_out = np.zeros((H * W, 3), np.float32)
    z_out = np.full(H * W, np.inf, np.float32)

    def done():
        return tri_out.reshape(H, W), bary_out.reshape(H, W, 3), z_out.reshape(H, W)
    if len(tris) == 0:
        return done()
    P = xy[tris].astype(np.float64)                     # (T, 3, 2)
    y0 = np.maximum(np.ceil(P[..., 1].min(1) - 0.5), 0).astype(np.int64)
    y1 = np.minimum(np.floor(P[..., 1].max(1) - 0.5), H - 1).astype(np.int64)
    xmn, xmx = P[..., 0].min(1), P[..., 0].max(1)
    area = ((P[:, 1, 0] - P[:, 0, 0]) * (P[:, 2, 1] - P[:, 0, 1])
            - (P[:, 1, 1] - P[:, 0, 1]) * (P[:, 2, 0] - P[:, 0, 0]))
    ok = (y1 >= y0) & (xmx >= 0.5 - 1) & (xmn <= W) & (np.abs(area) > 1e-12) & np.isfinite(area)
    ids = np.nonzero(ok)[0]
    if not len(ids):
        return done()
    est = (y1[ids] - y0[ids] + 1) * (np.ceil(xmx[ids] - xmn[ids]) + 1)
    cand_t, cand_p, cand_z, cand_b = [], [], [], []
    bounds = np.searchsorted(np.cumsum(est), np.arange(_BUDGET, est.sum() + _BUDGET, _BUDGET))
    start = 0
    for stop in list(bounds) + [len(ids)]:
        stop = max(stop, start + 1)
        g = ids[start:stop]
        start = stop
        if not len(g):
            continue
        # (triangle, row) pairs and each row's covered span
        owner, off = _ranges(y1[g] - y0[g] + 1)
        t = g[owner]
        py = (y0[t] + off) + 0.5
        p = P[t]
        xl = np.full(len(t), np.inf)
        xr = np.full(len(t), -np.inf)
        for a, b in ((0, 1), (1, 2), (2, 0)):
            ya, yb = p[:, a, 1], p[:, b, 1]
            xa, xb = p[:, a, 0], p[:, b, 0]
            lo, hi = np.minimum(ya, yb), np.maximum(ya, yb)
            cross = (py >= lo) & (py <= hi) & (hi > lo)
            x = xa + (py - ya) * (xb - xa) / np.where(hi > lo, yb - ya, 1.0)
            xl = np.where(cross, np.minimum(xl, x), xl)
            xr = np.where(cross, np.maximum(xr, x), xr)
        c0 = np.maximum(np.ceil(xl - 0.5), 0)
        c1 = np.minimum(np.floor(xr - 0.5), W - 1)
        n = np.where(np.isfinite(c0) & np.isfinite(c1), c1 - c0 + 1, 0).clip(0).astype(np.int64)
        if not n.sum():
            continue
        row_of, col_off = _ranges(n)
        tt = t[row_of]
        px = c0[row_of] + col_off + 0.5
        pyy = py[row_of]
        q = P[tt]
        a = area[tt]
        l0 = ((q[:, 1, 0] - px) * (q[:, 2, 1] - pyy) - (q[:, 1, 1] - pyy) * (q[:, 2, 0] - px)) / a
        l1 = ((q[:, 2, 0] - px) * (q[:, 0, 1] - pyy) - (q[:, 2, 1] - pyy) * (q[:, 0, 0] - px)) / a
        L = np.clip(np.stack([l0, l1, 1.0 - l0 - l1], 1), 0.0, 1.0)
        L /= np.maximum(L.sum(1, keepdims=True), 1e-12)
        vi = tris[tt]
        if inv_w is not None:
            qq = L * inv_w[vi]
            L = qq / np.maximum(qq.sum(1, keepdims=True), 1e-12)
        z = (L * depth[vi]).sum(1)
        pix = (pyy - 0.5).astype(np.int64) * W + (px - 0.5).astype(np.int64)
        if keep is not None:
            m = keep(tt, L)
            tt, L, z, pix = tt[m], L[m], z[m], pix[m]
        # z-buffer: keep only candidates that are the nearest so far
        np.minimum.at(z_out, pix, z.astype(np.float32))
        win = z.astype(np.float32) <= z_out[pix]
        cand_t.append(tt[win].astype(np.int32))
        cand_p.append(pix[win])
        cand_z.append(z[win].astype(np.float32))
        cand_b.append(L[win].astype(np.float32))
    if not cand_t:
        return done()
    t = np.concatenate(cand_t)
    pix = np.concatenate(cand_p)
    z = np.concatenate(cand_z)
    b = np.concatenate(cand_b)
    win = z <= z_out[pix]
    tri_out[pix[win]] = t[win]
    bary_out[pix[win]] = b[win]
    return done()
