import { describe, expect, it } from 'vitest';
import { reviewRows, updateRoom, withIds } from './planReview';
import { embedPngText } from '../floorPlanExport';

const plan = () => ({
    status: 'FEASIBLE',
    plot: { width_ft: 30, length_ft: 30 },
    design: {
        floors: 1,
        ground_floor: {
            rooms: [
                { id: 'room_1_1', group: 'g1', name: 'Room 1 (A)', type: 'other', x: 0, y: 0, width: 30, length: 12, detection: { type_source: 'unknown' } },
                { id: 'room_1_2', group: 'g1', name: 'Room 1 (B)', type: 'other', x: 0, y: 12, width: 12, length: 18, detection: { type_source: 'unknown' } },
                { id: 'room_2', name: 'Room 2', type: 'other', x: 12, y: 12, width: 18, length: 18 },
            ],
            circulation: [],
            open_spaces: [],
        },
        first_floor: { rooms: [], circulation: [], open_spaces: [] },
    },
});

describe('plan review', () => {
    it('shows a multi-part room as one row', () => {
        const rows = reviewRows(plan());
        expect(rows).toHaveLength(2);
        expect(rows[0]).toMatchObject({ key: 'ground_floor:g1', floor: 'ground_floor', name: 'Room 1', parts: 2, area: 30 * 12 + 12 * 18 });
    });

    it('renames and retypes every part, keeps geometry, and does not mutate the input', () => {
        const before = plan();
        const after = updateRoom(before, 'ground_floor:g1', { name: 'Lounge', type: 'tv_lounge' });
        const parts = after.design.ground_floor.rooms.filter((r) => r.group === 'g1');
        expect(parts.map((p) => p.name)).toEqual(['Lounge (A)', 'Lounge (B)']);
        expect(parts.every((p) => p.type === 'tv_lounge' && p.detection.type_source === 'user')).toBe(true);
        expect(parts.map((p) => [p.x, p.y, p.width, p.length])).toEqual([[0, 0, 30, 12], [0, 12, 12, 18]]);
        expect(before.design.ground_floor.rooms[0].name).toBe('Room 1 (A)');
    });

    it('moves a room to the section its new type belongs to', () => {
        const after = updateRoom(plan(), 'ground_floor:room_2', { type: 'corridor' });
        expect(after.design.ground_floor.circulation.map((r) => r.id)).toEqual(['room_2']);
        const back = updateRoom(after, 'ground_floor:room_2', { type: 'terrace' });
        expect(back.design.ground_floor.open_spaces.map((r) => r.id)).toEqual(['room_2']);
        expect(back.design.ground_floor.circulation).toEqual([]);
    });
});

describe('plans from the 2D module (no room ids, two floors)', () => {
    const twoFloor = () => ({
        status: 'FEASIBLE_WITH_TWO_FLOORS', plot: { width_ft: 20, length_ft: 30 },
        design: {
            floors: 2,
            ground_floor: { rooms: [{ name: 'Lounge', type: 'tv_lounge', x: 0, y: 0, width: 20, length: 15 }, { name: 'Kitchen', type: 'kitchen', x: 0, y: 15, width: 20, length: 15 }], circulation: [], open_spaces: [] },
            first_floor: { rooms: [{ name: 'Bedroom', type: 'bedroom', x: 0, y: 0, width: 20, length: 30 }], circulation: [], open_spaces: [] },
        },
    });

    it('lists every room on both floors and edits exactly one', () => {
        const plan = withIds(twoFloor());
        const rows = reviewRows(plan);
        expect(rows.map((r) => [r.floor, r.name])).toEqual([
            ['ground_floor', 'Lounge'], ['ground_floor', 'Kitchen'], ['first_floor', 'Bedroom'],
        ]);
        expect(new Set(rows.map((r) => r.key)).size).toBe(3);
        const after = updateRoom(plan, rows[0].key, { name: 'Family lounge' });
        expect(after.design.ground_floor.rooms.map((r) => r.name)).toEqual(['Family lounge', 'Kitchen']);
        expect(after.design.first_floor.rooms[0].name).toBe('Bedroom');
    });
});

describe('PNG plan embedding', () => {
    // Smallest valid PNG: signature, IHDR (1x1), IDAT, IEND.
    const png = Uint8Array.from(atob('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=='), (c) => c.charCodeAt(0));

    it('inserts an iTXt chunk before IEND that decodes back to the plan', () => {
        const out = embedPngText(png, 'haven-plan2d', JSON.stringify({ a: 'é' }));
        const view = new DataView(out.buffer);
        const chunks = [];
        for (let pos = 8; pos < out.length;) {
            const len = view.getUint32(pos);
            const type = String.fromCharCode(...out.subarray(pos + 4, pos + 8));
            chunks.push({ type, body: out.subarray(pos + 8, pos + 8 + len) });
            pos += 12 + len;
        }
        expect(chunks.map((c) => c.type)).toEqual(['IHDR', 'IDAT', 'iTXt', 'IEND']);
        const body = chunks[2].body;
        const text = new TextDecoder().decode(body.subarray('haven-plan2d'.length + 5));
        expect(JSON.parse(text)).toEqual({ a: 'é' });
    });
});
