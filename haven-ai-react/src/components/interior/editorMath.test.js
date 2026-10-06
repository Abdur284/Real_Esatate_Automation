import { describe, expect, it } from 'vitest';
import {
    constrainPosition, handlesFor, hitTest, perspectiveFactor, pointInPolygon, previewBox, resizeFromHandle, seamAt,
} from './editorMath';

// A small scene in the backend's format: horizon at 0.3, wall/floor seam at 0.6.
const box = (x, y, w, h) => ({ x, y, w, h });
const rect = (b) => [[b.x, b.y], [b.x + b.w, b.y], [b.x + b.w, b.y + b.h], [b.x, b.y + b.h]];
const sofa = {
    id: 'sofa_001', placement: 'floor', depth: 3.0, bounds: box(0.2, 0.45, 0.4, 0.25),
    transform: { position: { x: 0.4, y: 0.7 }, scale: { x: 1, y: 1 }, rotation: 0 },
};
sofa.outline = rect(sofa.bounds);
const chair = {
    id: 'chair_001', placement: 'floor', depth: 2.0, bounds: box(0.5, 0.55, 0.15, 0.3),
    transform: { position: { x: 0.575, y: 0.85 }, scale: { x: 1, y: 1 }, rotation: 0 },
};
chair.outline = rect(chair.bounds);
const painting = {
    id: 'painting_001', placement: 'wall', depth: 5, bounds: box(0.7, 0.1, 0.1, 0.2),
    transform: { position: { x: 0.75, y: 0.2 }, scale: { x: 1, y: 1 }, rotation: 0 },
};
painting.outline = rect(painting.bounds);
const scene = {
    camera: { horizon: 0.3, vanishing_x: 0.5 },
    layout: { columns: [0, 0.5, 1], floor_y: [0.6, 0.6, 0.6] },
    floor_rows: [[0.6, 0.05, 0.95], [0.8, 0.0, 1.0], [0.98, 0.0, 1.0]],
    objects: [sofa, chair, painting],
    surfaces: [
        { id: 'wall_001', type: 'wall', bbox: box(0, 0, 1, 0.6), outline: rect(box(0, 0, 1, 0.6)) },
        { id: 'floor_001', type: 'floor', bbox: box(0, 0.6, 1, 0.4), outline: rect(box(0, 0.6, 1, 0.4)) },
    ],
};

describe('hit testing', () => {
    it('finds points inside polygons', () => {
        expect(pointInPolygon([0.5, 0.5], rect(box(0, 0, 1, 1)))).toBe(true);
        expect(pointInPolygon([1.5, 0.5], rect(box(0, 0, 1, 1)))).toBe(false);
    });

    it('prefers the nearer object where two overlap', () => {
        expect(hitTest(scene, 0.55, 0.6)).toEqual({ kind: 'object', id: 'chair_001' });
        expect(hitTest(scene, 0.3, 0.5)).toEqual({ kind: 'object', id: 'sofa_001' });
    });

    it('falls back to the wall or floor', () => {
        expect(hitTest(scene, 0.1, 0.2)).toEqual({ kind: 'surface', id: 'wall_001' });
        expect(hitTest(scene, 0.1, 0.9)).toEqual({ kind: 'surface', id: 'floor_001' });
        expect(seamAt(scene, 0.3)).toBeCloseTo(0.6);
    });
});

describe('perspective', () => {
    it('makes floor objects bigger nearer the camera', () => {
        const { kx } = perspectiveFactor(scene, sofa, 0.9);
        expect(kx).toBeCloseTo((0.9 - 0.3) / (0.7 - 0.3));
        expect(perspectiveFactor(scene, painting, 0.9)).toEqual({ kx: 1, ky: 1 });
    });

    it('keeps the anchor fixed when previewing a scale change', () => {
        const b = previewBox(scene, sofa, sofa.transform.position, { x: 2, y: 2 });
        expect(b.x + b.w / 2).toBeCloseTo(0.4);                 // centred on the anchor
        expect(b.y + b.h).toBeCloseTo(0.7);                     // feet stay on the floor
        expect(b.w).toBeCloseTo(0.8);
    });

    it('moves the preview with the anchor and scales it with depth', () => {
        const b = previewBox(scene, sofa, { x: 0.5, y: 0.9 });
        expect(b.y + b.h).toBeCloseTo(0.9);
        expect(b.w).toBeCloseTo(0.4 * 1.5);
    });
});

describe('constraints', () => {
    it('keeps floor furniture on the floor', () => {
        const p = constrainPosition(scene, sofa, 0.5, 0.1);
        expect(p.y).toBeGreaterThanOrEqual(0.6);
        const q = constrainPosition(scene, sofa, 0.0, 0.6);
        expect(q.x).toBeCloseTo(0.05);                          // floor band at that row starts at 0.05
    });

    it('keeps wall items above the floor', () => {
        const p = constrainPosition(scene, painting, 0.5, 0.95);
        expect(p.y + painting.bounds.h / 2).toBeLessThanOrEqual(0.6 + 1e-9);
    });

    it('lets ceiling items slide sideways only', () => {
        const lamp = { ...painting, placement: 'ceiling', transform: { ...painting.transform, position: { x: 0.5, y: 0.05 } } };
        expect(constrainPosition(scene, lamp, 0.2, 0.5)).toEqual({ x: 0.2, y: 0.05 });
    });
});

describe('resize handles', () => {
    it('grows symmetrically from a side handle', () => {
        expect(resizeFromHandle('e', sofa, 0.1, 0).x).toBeCloseTo((0.4 + 0.2) / 0.4);
        expect(resizeFromHandle('w', sofa, 0.1, 0).x).toBeCloseTo((0.4 - 0.2) / 0.4);
    });

    it('grows floor furniture upwards from the top handle', () => {
        expect(resizeFromHandle('n', sofa, 0, -0.05).y).toBeCloseTo((0.25 + 0.05) / 0.25);
    });

    it('keeps proportions on corners unless told not to', () => {
        const m = resizeFromHandle('ne', sofa, 0.1, 0, true);
        expect(m.x).toBeCloseTo(m.y);
        const free = resizeFromHandle('ne', sofa, 0.1, 0, false);
        expect(free.y).toBeCloseTo(1);
    });

    it('never lets floor pieces lift their feet', () => {
        expect(handlesFor(sofa)).not.toContain('s');
        expect(handlesFor(painting)).toContain('s');
    });
});
