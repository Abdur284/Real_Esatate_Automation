// Helpers for reviewing a plan read from an image before it is built in 3D.
// The user may only rename rooms and set their type; geometry is never edited
// here, so what reaches the 3D engine is exactly what the analysis measured.

export const SECTIONS = ['rooms', 'circulation', 'open_spaces'];
const OPEN_AIR = new Set(['courtyard', 'lawn', 'terrace', 'balcony', 'setback']);
const CIRCULATION = new Set(['corridor', 'lobby', 'entrance']);

export const ROOM_TYPES = [
    'other', 'bedroom', 'master_bedroom', 'guest_room', 'bathroom', 'kitchen', 'dining_room',
    'living_room', 'tv_lounge', 'drawing_room', 'study', 'prayer_room', 'store', 'laundry',
    'servant_room', 'staircase', 'corridor', 'lobby', 'entrance', 'parking', 'garage',
    'courtyard', 'lawn', 'terrace', 'balcony',
];

export const typeLabel = (t) => (t === 'other' ? 'Unknown' : t.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()));

function sectionFor(type) {
    return OPEN_AIR.has(type) ? 'open_spaces' : CIRCULATION.has(type) ? 'circulation' : 'rooms';
}

const baseName = (name) => String(name || '').replace(/\s\([A-Z]\)$/, '');

export const FLOORS = [['ground_floor', 'Ground'], ['first_floor', 'First']];

const floorKeys = (plan) => FLOORS.slice(0, plan?.design?.floors === 2 ? 2 : 1).map(([k]) => k);

/** Plans from the 2D module carry no room ids; give every item a stable one
 *  so the review can address rooms individually. Returns a new plan. */
export function withIds(plan) {
    const next = structuredClone(plan);
    floorKeys(next).forEach((fk) => SECTIONS.forEach((section) => {
        (next.design[fk]?.[section] || []).forEach((it, i) => {
            if (it.id === undefined || it.id === null || it.id === '') it.id = `${fk}-${section}-${i}`;
        });
    }));
    return next;
}

const rowKey = (fk, it) => `${fk}:${it.group || it.id}`;

/** One row per room on every floor (the parts of a multi-rectangle room share a row). */
export function reviewRows(plan) {
    const rows = new Map();
    floorKeys(plan).forEach((fk) => {
        const floor = plan?.design?.[fk] || {};
        SECTIONS.forEach((section) => (floor[section] || []).forEach((it) => {
            const key = rowKey(fk, it);
            const row = rows.get(key);
            if (row) {
                row.parts += 1;
                row.area += it.width * it.length;
            } else {
                rows.set(key, {
                    key, floor: fk, name: baseName(it.name), type: it.type, parts: 1, area: it.width * it.length,
                    width: it.width, length: it.length, detection: it.detection || null,
                });
            }
        }));
    });
    return [...rows.values()];
}

/** Returns a new plan with one room (all its parts) renamed and/or retyped.
 *  A room stays in place unless its new type belongs in another section. */
export function updateRoom(plan, key, { name, type }) {
    const next = structuredClone(plan);
    floorKeys(next).forEach((fk) => {
        const floor = next.design[fk];
        const moved = [];
        SECTIONS.forEach((section) => {
            floor[section] = (floor[section] || []).filter((it) => {
                if (rowKey(fk, it) !== key) return true;
                const suffix = it.group ? String(it.name).match(/\s\([A-Z]\)$/)?.[0] ?? '' : '';
                if (name !== undefined) it.name = `${name}${suffix}`;
                if (type !== undefined) {
                    it.type = type;
                    it.detection = { ...(it.detection || {}), type_source: 'user', type_confidence: 1 };
                }
                if (sectionFor(it.type) === section) return true;
                moved.push(it);
                return false;
            });
        });
        moved.forEach((it) => floor[sectionFor(it.type)].push(it));
    });
    return next;
}

export function confidenceWord(v) {
    if (v == null) return 'n/a';
    return v >= 0.8 ? 'high' : v >= 0.6 ? 'medium' : 'low';
}
