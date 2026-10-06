// Layer 3 logic against real GLB files produced by the backend exporter.
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import process from 'node:process';
import { describe, expect, it, beforeAll } from 'vitest';
import { parseHouse } from './houseLoader';
import {
    FT_TO_M, applyVisibility, computeView, isShown, pickRoom, roomBounds, setWallsTransparent,
} from './viewerUtils';

const fixture = (name) => {
    const buf = readFileSync(resolve(process.cwd(), 'src/components/threeD/__fixtures__', name));
    // Copy into an ArrayBuffer of this realm (GLTFLoader checks instanceof).
    const out = new ArrayBuffer(buf.length);
    new Uint8Array(out).set(buf);
    return out;
};

let one;
let two;
beforeAll(async () => {
    one = await parseHouse(fixture('one-floor.glb'));
    two = await parseHouse(fixture('two-storey.glb'));
});

describe('GLB loading and indexing', () => {
    it('finds metadata, storeys, layers, roof and every room', () => {
        const { index } = one;
        expect(index.meta.units).toBe('m');
        expect(index.meta.plot).toEqual({ width_ft: 20, length_ft: 30 });
        expect([...index.storeys.keys()]).toEqual([1]);
        expect(index.layers.has('1:walls')).toBe(true);
        expect(index.layers.has('1:doors')).toBe(true);
        expect(index.layers.has('1:windows')).toBe(true);
        expect(index.roofs.has(1)).toBe(true);
        const labels = index.rooms.map((r) => r.userData.label).sort();
        expect(labels).toEqual(['Bedroom', 'Kitchen', 'Lounge']);
        const lounge = index.rooms.find((r) => r.userData.label === 'Lounge').userData;
        expect(lounge).toMatchObject({ width_ft: 12, depth_ft: 18, area_sqft: 216, level: 1 });
        expect(lounge.detection).toEqual({ type_source: 'user' });
    });

    it('keeps real-world dimensions in metres', () => {
        const walls = one.index.layers.get('1:walls');
        walls.updateWorldMatrix(true, true);
        let maxY = 0;
        walls.traverse((m) => {
            if (!m.isMesh) return;
            m.geometry.computeBoundingBox();
            maxY = Math.max(maxY, m.geometry.boundingBox.max.y);
        });
        expect(maxY).toBeCloseTo(10 * FT_TO_M, 4);
    });

    it('marks glass as transparent without depth writes and shadows on solids', () => {
        let glass = null;
        let wall = null;
        one.scene.traverse((m) => {
            if (m.isMesh && m.material.name === 'glass') glass = m;
            if (m.isMesh && m.material.name === 'wall') wall = m;
        });
        expect(glass.material.transparent).toBe(true);
        expect(glass.material.depthWrite).toBe(false);
        expect(glass.castShadow).toBe(false);
        expect(wall.castShadow).toBe(true);
    });
});

describe('layer visibility', () => {
    it('toggles walls, doors, windows, furniture and roof', () => {
        const { index } = one;
        applyVisibility(index, { visibleLevels: [1], showWalls: false, showDoors: true, showWindows: false, showFurniture: false, showRoof: false });
        expect(index.layers.get('1:walls').visible).toBe(false);
        expect(index.layers.get('1:doors').visible).toBe(true);
        expect(index.layers.get('1:windows').visible).toBe(false);
        expect(index.layers.get('1:furniture')?.visible ?? false).toBe(false);
        expect(index.roofs.get(1).visible).toBe(false);
        applyVisibility(index, { visibleLevels: [1], showWalls: true, showDoors: true, showWindows: true, showFurniture: true, showRoof: true });
        expect(index.layers.get('1:walls').visible).toBe(true);
        expect(index.roofs.get(1).visible).toBe(true);
    });

    it('isolating a storey hides the others and the roof', () => {
        const { index } = two;
        applyVisibility(index, { visibleLevels: [1], showRoof: true });
        expect(index.storeys.get(1).visible).toBe(true);
        expect(index.storeys.get(2).visible).toBe(false);
        [...index.roofs.values()].forEach((r) => expect(r.visible).toBe(false));
        applyVisibility(index, { visibleLevels: [2], showRoof: true });
        [...index.roofs.values()].forEach((r) => expect(r.visible).toBe(false));
        applyVisibility(index, { visibleLevels: [1, 2], showRoof: true });
        expect(index.storeys.get(2).visible).toBe(true);
        expect([...index.roofs.values()].some((r) => r.visible)).toBe(true);
    });

    it('see-through walls swap to a transparent copy and back', () => {
        const { index } = one;
        const mesh = [];
        index.layers.get('1:walls').traverse((m) => m.isMesh && mesh.push(m));
        const original = mesh[0].material;
        setWallsTransparent(index, true);
        expect(mesh[0].material).not.toBe(original);
        expect(mesh[0].material.opacity).toBeLessThan(1);
        setWallsTransparent(index, false);
        expect(mesh[0].material).toBe(original);
    });
});

describe('room selection', () => {
    it('picks the first visible room along the ray, skipping walls and hidden storeys', () => {
        const { index } = two;
        applyVisibility(index, { visibleLevels: [1] });
        const upper = index.rooms.find((r) => r.userData.level === 2);
        const lower = index.rooms.find((r) => r.userData.level === 1);
        const wall = index.layers.get('1:walls');
        expect(isShown(upper)).toBe(false);
        const hit = pickRoom([{ object: wall }, { object: upper }, { object: lower }]);
        expect(hit.id).toBe(lower.userData.id);
        expect(pickRoom([{ object: wall }])).toBeNull();
    });
});

describe('camera views', () => {
    const meta = () => one.index.meta;

    it('frames the whole model for exterior, top, front and side views', () => {
        const opts = { meta: meta(), fov: 45, aspect: 1.6 };
        const ext = computeView('exterior', opts);
        const center = [10 * FT_TO_M, ext.target[1], -15 * FT_TO_M];
        expect(ext.target[0]).toBeCloseTo(center[0], 5);
        expect(ext.target[2]).toBeCloseTo(center[2], 5);
        const top = computeView('top', opts);
        expect(top.position[0]).toBeCloseTo(top.target[0], 5);
        expect(top.position[1]).toBeGreaterThan(top.target[1] + 5);
        const front = computeView('front', opts);
        expect(front.position[2]).toBeGreaterThan(0); // the road side
        expect(front.position[0]).toBeCloseTo(front.target[0], 5);
        const side = computeView('side', opts);
        expect(side.position[0]).toBeGreaterThan(20 * FT_TO_M);
    });

    it('puts the interior camera at eye height inside the chosen room', () => {
        const kitchen = one.index.rooms.find((r) => r.userData.label === 'Kitchen').userData;
        const v = computeView('interior', { meta: meta(), room: kitchen });
        const b = roomBounds(kitchen, meta());
        expect(v.position[0]).toBeGreaterThan(b.min[0]);
        expect(v.position[0]).toBeLessThan(b.max[0]);
        expect(v.position[2]).toBeGreaterThan(b.min[2]);
        expect(v.position[2]).toBeLessThan(b.max[2]);
        expect(v.position[1]).toBeCloseTo(5.3 * FT_TO_M, 5);
    });

    it('falls back to the largest room for interior view without a selection', () => {
        const rooms = one.index.rooms.map((r) => r.userData);
        const v = computeView('interior', { meta: meta(), rooms });
        expect(v.room.label).toBe('Kitchen'); // 20 x 12 = 240 sq ft
    });

    it('fit keeps the current viewing direction', () => {
        const v = computeView('fit', { meta: meta(), currentDirection: [1, 0, 0] });
        expect(v.position[1]).toBeCloseTo(v.target[1], 5);
        expect(v.position[0]).toBeGreaterThan(v.target[0]);
    });
});
