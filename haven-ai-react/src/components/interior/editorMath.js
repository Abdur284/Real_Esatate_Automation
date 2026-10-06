// Pure geometry for the interior editor: what was clicked, where a dragged
// object would go, and how handles change its size. Everything is in the
// scene's normalised coordinates (0-1 of the image width/height), the same
// as the backend's scene JSON. The backend re-checks and has the final word
// (it keeps furniture on the floor, etc.); these only drive the live preview.

export const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));

export function pointInPolygon([x, y], poly) {
    let inside = false;
    for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
        const [xi, yi] = poly[i];
        const [xj, yj] = poly[j];
        if ((yi > y) !== (yj > y) && x < ((xj - xi) * (y - yi)) / (yj - yi || 1e-9) + xi) inside = !inside;
    }
    return inside;
}

function inBox(b, x, y) {
    return b && x >= b.x && x <= b.x + b.w && y >= b.y && y <= b.y + b.h;
}

/** Row (0-1) of the wall/floor seam at column x (0-1). */
export function seamAt(scene, x) {
    const { columns, floor_y: fy } = scene.layout;
    if (x <= columns[0]) return fy[0];
    for (let i = 1; i < columns.length; i++) {
        if (x <= columns[i]) {
            const t = (x - columns[i - 1]) / (columns[i] - columns[i - 1] || 1);
            return fy[i - 1] + t * (fy[i] - fy[i - 1]);
        }
    }
    return fy[fy.length - 1];
}

/** The element under a point: the nearest object whose outline contains it,
 *  else the wall/floor/ceiling there. */
export function hitTest(scene, x, y) {
    const objects = [...scene.objects].sort((a, b) => (a.depth ?? 0) - (b.depth ?? 0));   // nearest first
    for (const o of objects) {
        if (inBox(o.bounds, x, y) && (o.outline?.length > 2 ? pointInPolygon([x, y], o.outline) : true)) {
            return { kind: 'object', id: o.id };
        }
    }
    for (const s of scene.surfaces) {
        if (inBox(s.bbox, x, y) && s.outline?.length > 2 && pointInPolygon([x, y], s.outline)) {
            return { kind: 'surface', id: s.id };
        }
    }
    // hidden behind furniture: the surface that is behind it
    const type = y >= seamAt(scene, x) ? 'floor' : 'wall';
    const candidates = scene.surfaces.filter((s) => s.type === type);
    const s = candidates.find((c) => x >= c.bbox.x && x <= c.bbox.x + c.bbox.w) || candidates[0];
    return s ? { kind: 'surface', id: s.id } : null;
}

/** How much bigger a floor object looks at row `y` than at its current row
 *  (things nearer the camera look bigger). Rugs also stretch in depth. */
export function perspectiveFactor(scene, obj, y) {
    if (obj.placement !== 'floor' && obj.placement !== 'floor_flat') return { kx: 1, ky: 1 };
    const hz = scene.camera.horizon;
    const from = obj.transform.position.y - hz;
    const to = y - hz;
    if (from <= 0.001 || to <= 0.001) return { kx: 1, ky: 1 };
    const k = to / from;
    return obj.placement === 'floor_flat' ? { kx: k, ky: k * k } : { kx: k, ky: k };
}

/** Where the backend will (roughly) allow the object: floor pieces on the
 *  floor, wall pieces on the wall, ceiling pieces slide sideways only. */
export function constrainPosition(scene, obj, x, y) {
    let nx = clamp(x, 0, 1);
    let ny = clamp(y, 0, 1);
    if (obj.placement === 'floor' || obj.placement === 'floor_flat') {
        const rows = scene.floor_rows || [];
        const minY = Math.max(scene.camera.horizon + 0.02, rows.length ? rows[0][0] : 0);
        ny = Math.max(ny, minY);
        if (rows.length) {
            const band = rows.reduce((best, r) => (Math.abs(r[0] - ny) < Math.abs(best[0] - ny) ? r : best), rows[0]);
            nx = clamp(nx, band[1], band[2]);
        }
    } else if (obj.placement === 'wall') {
        const halfH = (obj.bounds?.h || 0) / 2;
        ny = Math.min(ny, seamAt(scene, nx) - halfH);
    } else if (obj.placement === 'ceiling') {
        ny = obj.transform.position.y;
    }
    return { x: nx, y: ny };
}

/** The object's box after moving its anchor to `pos` and scaling by
 *  `mul` = {x, y} about the anchor (with perspective). */
export function previewBox(scene, obj, pos, mul = { x: 1, y: 1 }) {
    const b = obj.bounds;
    const a = obj.transform.position;
    const { kx, ky } = perspectiveFactor(scene, obj, pos.y);
    const sx = kx * mul.x;
    const sy = ky * mul.y;
    return {
        x: pos.x + (b.x - a.x) * sx,
        y: pos.y + (b.y - a.y) * sy,
        w: b.w * sx,
        h: b.h * sy,
    };
}

/** Scale multipliers from dragging a handle by (dx, dy) (normalised).
 *  Objects grow about their anchor: floor pieces keep their feet in place
 *  (bottom-centre), others grow about their centre. Corner handles keep the
 *  proportions unless `keepAspect` is off. */
export function resizeFromHandle(handle, obj, dx, dy, keepAspect = true) {
    const b = obj.bounds;
    const feet = obj.placement === 'floor' || obj.placement === 'floor_flat';
    let mx = 1;
    let my = 1;
    if (handle.includes('e')) mx = (b.w + 2 * dx) / b.w;
    if (handle.includes('w')) mx = (b.w - 2 * dx) / b.w;
    if (handle.includes('n')) my = (b.h - (feet ? 1 : 2) * dy) / b.h;
    if (handle.includes('s')) my = (b.h + (feet ? 1 : 2) * dy) / b.h;
    if (keepAspect && handle.length === 2) {
        const m = Math.abs(mx - 1) >= Math.abs(my - 1) ? mx : my;
        mx = m;
        my = m;
    }
    return { x: Math.max(0.05, mx), y: Math.max(0.05, my) };
}

/** Which resize handles an object gets: floor pieces cannot move their feet. */
export function handlesFor(obj) {
    const feet = obj.placement === 'floor' || obj.placement === 'floor_flat';
    return feet ? ['nw', 'n', 'ne', 'e', 'w'] : ['nw', 'n', 'ne', 'e', 'se', 's', 'sw', 'w'];
}

/** Degrees from the object's centre to a point (0 = up, clockwise). */
export function angleTo(center, point, aspect = 1) {
    const dx = point.x - center.x;
    const dy = (point.y - center.y) / aspect;
    return (Math.atan2(dx, -dy) * 180) / Math.PI;
}

export const pct = (v) => `${Math.round(v * 100)}%`;
export const metres = (v) => (v == null ? '—' : `${v.toFixed(2)} m`);

/** Human label for a material key. */
export function materialLabel(catalog, key) {
    if (!key || key === 'original') return 'As in photo';
    return catalog?.materials?.[key]?.label || key.replace(/_/g, ' ');
}
