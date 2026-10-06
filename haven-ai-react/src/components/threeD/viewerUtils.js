// Pure helpers for the 3D viewer: indexing the loaded GLB by the node names
// and extras the backend writes, layer visibility, and camera views.
//
// GLB space (see the backend's arch_defaults.py): metres, +X = plan x (left to
// right seen from the road), +Y = up, +Z = towards the road (z = -plan y).
import * as THREE from 'three';

export const FT_TO_M = 0.3048;
const LOOK_AHEAD_M = 0.6;

/** Collects the named parts of a HAVEN house scene from node extras (userData). */
export function indexScene(root) {
    const index = { meta: null, site: null, storeys: new Map(), layers: new Map(), roofs: new Map(), rooms: [] };
    root.traverse((obj) => {
        const u = obj.userData || {};
        if (u.haven) index.meta = u.haven;
        switch (u.kind) {
            case 'site': index.site = obj; break;
            case 'storey': index.storeys.set(u.level, obj); break;
            case 'layer': index.layers.set(`${u.level}:${u.layer}`, obj); break;
            case 'roof': index.roofs.set(u.level, obj); break;
            case 'room': index.rooms.push(obj); break;
            default: break;
        }
    });
    return index;
}

const LAYER_OPTION = { walls: 'showWalls', doors: 'showDoors', windows: 'showWindows', furniture: 'showFurniture' };

/** Shows/hides storeys, layers and roof pieces. The roof is shown only when
 *  every storey is, so isolating any single floor opens it up for inspection. */
export function applyVisibility(index, options) {
    const levels = options.visibleLevels ?? [...index.storeys.keys()];
    const allShown = [...index.storeys.keys()].every((l) => levels.includes(l));
    index.storeys.forEach((obj, level) => { obj.visible = levels.includes(level); });
    index.layers.forEach((obj, key) => {
        const layer = key.split(':')[1];
        const opt = LAYER_OPTION[layer];
        obj.visible = opt ? options[opt] !== false : true;
    });
    index.roofs.forEach((obj) => {
        obj.visible = options.showRoof !== false && allShown;
    });
}

/** Swaps the wall materials for see-through copies (and back). */
export function setWallsTransparent(index, transparent) {
    index.layers.forEach((obj, key) => {
        if (!key.endsWith(':walls')) return;
        obj.traverse((m) => {
            if (!m.isMesh) return;
            if (!m.userData.opaqueMaterial) m.userData.opaqueMaterial = m.material;
            if (transparent) {
                if (!m.userData.clearMaterial) {
                    const clear = m.userData.opaqueMaterial.clone();
                    clear.transparent = true;
                    clear.opacity = 0.28;
                    clear.depthWrite = false;
                    m.userData.clearMaterial = clear;
                }
                m.material = m.userData.clearMaterial;
                m.castShadow = false;
            } else {
                m.material = m.userData.opaqueMaterial;
                m.castShadow = true;
            }
        });
    });
}

/** True if the object and all its ancestors are visible. */
export function isShown(obj) {
    for (let o = obj; o; o = o.parent) if (!o.visible) return false;
    return true;
}

/** First visible room floor along a pointer ray (clicks pass through walls
 *  and the roof, so any room can be picked from outside). */
export function pickRoom(intersections) {
    const hit = intersections.find((i) => i.object.userData?.kind === 'room' && isShown(i.object));
    return hit ? hit.object.userData : null;
}

export function roomKey(room) {
    return room ? `${room.level}:${room.id}` : null;
}

function levelInfo(meta, level) {
    const l = meta?.levels?.find((x) => x.level === level);
    return { elevation: l?.elevation_ft ?? 0, wallHeight: l?.wall_height_ft ?? 10 };
}

/** A room's box in GLB metres, from its extras (feet). */
export function roomBounds(room, meta) {
    const { elevation, wallHeight } = levelInfo(meta, room.level);
    return {
        min: [room.x_ft * FT_TO_M, elevation * FT_TO_M, -(room.y_ft + room.depth_ft) * FT_TO_M],
        max: [(room.x_ft + room.width_ft) * FT_TO_M, (elevation + wallHeight) * FT_TO_M, -room.y_ft * FT_TO_M],
    };
}

/** The building's bounds in metres: plot area up to the roof. */
export function modelBounds(meta) {
    const w = meta.plot.width_ft * FT_TO_M;
    const l = meta.plot.length_ft * FT_TO_M;
    const h = (meta.totals?.building_height_ft ?? 12) * FT_TO_M;
    return { min: [0, 0, -l], max: [w, h, 0] };
}

const VIEW_DIRECTIONS = {
    exterior: [0.62, 0.55, 1],
    front: [0, 0.14, 1],
    side: [1, 0.14, 0],
    back: [0, 0.14, -1],
    top: [0, 1, 0.0005], // a hair off vertical keeps OrbitControls well-defined
};

/**
 * Camera pose for a named view: { position, target } in metres.
 *   exterior | front | side | back | top  frame the whole model
 *   fit                                    keeps `currentDirection`, reframes
 *   interior                               eye height inside `room` (or the largest room)
 */
export function computeView(name, { meta, fov = 45, aspect = 1.6, room = null, rooms = [], currentDirection = null }) {
    if (name === 'interior') {
        const target = room ?? [...rooms].filter((r) => r.enclosed !== false)
            .sort((a, b) => b.area_sqft - a.area_sqft)[0];
        if (target) {
            const b = roomBounds(target, meta);
            const floorY = b.min[1];
            const cx = (b.min[0] + b.max[0]) / 2;
            const inset = Math.min(0.6, (b.max[2] - b.min[2]) * 0.2);
            const eye = floorY + 5.3 * FT_TO_M;
            // The orbit target sits just ahead of the eye, so dragging turns
            // the view in place (look around) instead of swinging the camera
            // through the walls.
            return {
                position: [cx, eye, b.max[2] - inset],
                target: [cx, eye - 0.05, b.max[2] - inset - LOOK_AHEAD_M],
                room: target,
            };
        }
        name = 'exterior';
    }
    const bounds = room ? roomBounds(room, meta) : modelBounds(meta);
    const center = bounds.min.map((v, i) => (v + bounds.max[i]) / 2);
    const size = bounds.max.map((v, i) => v - bounds.min[i]);
    const radius = Math.hypot(...size) / 2;
    const vfov = THREE.MathUtils.degToRad(fov);
    const hfov = 2 * Math.atan(Math.tan(vfov / 2) * aspect);
    const distance = (radius / Math.sin(Math.min(vfov, hfov) / 2)) * 1.05;
    const dir = new THREE.Vector3(...(name === 'fit' && currentDirection ? currentDirection
        : VIEW_DIRECTIONS[name] ?? VIEW_DIRECTIONS.exterior)).normalize();
    return {
        position: center.map((c, i) => c + dir.getComponent(i) * distance),
        target: center,
    };
}
