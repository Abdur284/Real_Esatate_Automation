import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import api from '../../api';
import RoomEditor from './RoomEditor';
import RoomUpload from './RoomUpload';
import { checkDimensions, checkFile } from './uploadCheck';

const box = (x, y, w, h) => ({ x, y, w, h });
const rect = (b) => [[b.x, b.y], [b.x + b.w, b.y], [b.x + b.w, b.y + b.h], [b.x, b.y + b.h]];

function makeScene(version = 0, overrides = {}) {
    const sofaBox = box(0.2, 0.45, 0.4, 0.25);
    return {
        scene_id: 'a'.repeat(32), version, image: { width: 800, height: 600 }, warnings: [],
        camera: { horizon: 0.3, vanishing_x: 0.5 },
        layout: { columns: [0, 1], floor_y: [0.6, 0.6], ceiling_y: [-1, -1] },
        floor_rows: [[0.6, 0, 1]],
        surfaces: [{
            id: 'wall_001', type: 'wall', label: 'Wall', color: '#dddddd', bbox: box(0, 0, 1, 0.6),
            outline: rect(box(0, 0, 1, 0.6)), appearance: { color: null, material: 'original' },
            capabilities: { color: true, materials: ['paint', 'brick'] },
        }],
        objects: [{
            id: 'sofa_001', type: 'sofa', label: 'Sofa', category: 'furniture', placement: 'floor', source: 'detected',
            confidence: 0.95, color: '#30504b', material_guess: 'fabric', material_source: 'assumed', depth: 3,
            bounds: sofaBox, outline: rect(sofaBox), dimensions_m: { width: 2.1, height: 0.8 },
            transform: { position: { x: 0.4, y: 0.7 }, scale: { x: 1, y: 1 }, rotation: 0, flip: false },
            appearance: { color: null, material: 'original' },
            capabilities: { move: true, resize: true, rotate: 'mirror', color: true, materials: ['fabric', 'leather'],
                replace: true, library_category: 'sofa', remove: true },
        }],
        removed: [],
        ...overrides,
    };
}

const response = (scene, extra = {}) => ({
    scene, can_undo: scene.version > 0, can_redo: false, notes: [],
    render_url: `/api/interior/scenes/${scene.scene_id}/render?v=${scene.version}`,
    original_url: `/api/interior/scenes/${scene.scene_id}/original`, ...extra,
});

const catalog = {
    types: { sofa: { label: 'Sofa', category: 'furniture' }, sectional_sofa: { label: 'Sectional sofa', category: 'furniture' } },
    addable: [{ type: 'armchair', label: 'Armchair', category: 'furniture' }],
    materials: { fabric: { label: 'Fabric', tintable: true }, leather: { label: 'Leather', tintable: true },
        paint: { label: 'Paint', tintable: true }, brick: { label: 'Brick', tintable: false } },
    palette: ['#222222', '#f5f3ee'],
};

beforeEach(() => {
    vi.spyOn(api.interior, 'image').mockResolvedValue({ url: 'blob:render', bounds: null });
    globalThis.URL.createObjectURL = vi.fn(() => 'blob:preview');
    globalThis.URL.revokeObjectURL = vi.fn();
});
afterEach(() => vi.restoreAllMocks());

function renderEditor(scene = makeScene()) {
    return render(<MemoryRouter><RoomEditor initial={response(scene)} catalog={catalog} onClose={() => {}} /></MemoryRouter>);
}

describe('upload checks', () => {
    it('accepts JPG/PNG/WebP and rejects other files', () => {
        expect(checkFile(new File(['x'], 'room.jpg', { type: 'image/jpeg' }))).toBeNull();
        expect(checkFile(new File(['x'], 'room.gif', { type: 'image/gif' }))).toMatch(/JPG, PNG or WebP/);
        expect(checkFile(new File([], 'room.png', { type: 'image/png' }))).toMatch(/empty/);
        const big = { name: 'big.jpg', type: 'image/jpeg', size: 11 * 1024 * 1024 };
        expect(checkFile(big)).toMatch(/larger than 10 MB/);
        expect(checkDimensions({ width: 200, height: 900 })).toMatch(/too small/);
        expect(checkDimensions({ width: 1200, height: 900 })).toBeNull();
    });

    it('shows an error for an unsupported file instead of uploading', async () => {
        const analyze = vi.spyOn(api.interior, 'analyze');
        const { container } = render(<RoomUpload onAnalyzed={() => {}} />);
        const input = container.querySelector('input[type=file]');
        fireEvent.change(input, { target: { files: [new File(['x'], 'doc.pdf', { type: 'application/pdf' })] } });
        expect(await screen.findByRole('alert')).toHaveTextContent('JPG, PNG or WebP');
        expect(analyze).not.toHaveBeenCalled();
    });
});

describe('room editor', () => {
    it('lists what was found and opens its properties', async () => {
        renderEditor();
        fireEvent.click(await screen.findByRole('button', { name: /Sofa/ }));
        expect(screen.getByText(/Found in your photo · 95% sure/)).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /Mirror/ })).toBeInTheDocument();
        expect(screen.getByText(/To turn it, change it for a 3D model/)).toBeInTheDocument();
    });

    it('sends one explicit operation for a colour change and shows the new version', async () => {
        const apply = vi.spyOn(api.interior, 'apply').mockImplementation(async (id, base, op) => {
            const s = makeScene(1);
            s.objects[0].appearance.color = op.changes.color;
            return response(s);
        });
        renderEditor();
        fireEvent.click(await screen.findByRole('button', { name: /Sofa/ }));
        fireEvent.click(screen.getAllByRole('button', { name: 'Colour #222222' })[0]);
        await waitFor(() => expect(apply).toHaveBeenCalledWith('a'.repeat(32), 0, {
            operation: 'update_object', object_id: 'sofa_001', changes: { color: '#222222' },
        }));
        expect(await screen.findByText(/Version 1/)).toBeInTheDocument();
    });

    it('recolours walls through update_surface', async () => {
        const apply = vi.spyOn(api.interior, 'apply').mockResolvedValue(response(makeScene(1)));
        renderEditor();
        fireEvent.click(await screen.findByRole('button', { name: /Wall/ }));
        fireEvent.click(screen.getByRole('radio', { name: /Brick/ }));
        await waitFor(() => expect(apply).toHaveBeenCalledWith('a'.repeat(32), 0, {
            operation: 'update_surface', surface_id: 'wall_001', changes: { material: 'brick' },
        }));
    });

    it('undo, redo and delete call the backend', async () => {
        const undo = vi.spyOn(api.interior, 'undo').mockResolvedValue(response(makeScene(0)));
        const apply = vi.spyOn(api.interior, 'apply').mockResolvedValue(response(makeScene(2, { objects: [] })));
        renderEditor(makeScene(1));
        fireEvent.click(await screen.findByRole('button', { name: /Sofa/ }));
        fireEvent.keyDown(window, { key: 'Delete' });
        await waitFor(() => expect(apply).toHaveBeenCalledWith('a'.repeat(32), 1,
            { operation: 'remove_object', object_id: 'sofa_001' }));
        fireEvent.keyDown(window, { key: 'z', ctrlKey: true });
        await waitFor(() => expect(undo).toHaveBeenCalled());
    });

    it('explains adjustments and errors from the server', async () => {
        vi.spyOn(api.interior, 'apply').mockRejectedValue(Object.assign(new Error('Scale must be between 0.3 and 3.0 (got 5).'), { status: 422 }));
        renderEditor();
        fireEvent.click(await screen.findByRole('button', { name: /Sofa/ }));
        const width = screen.getAllByRole('spinbutton')[2];
        fireEvent.change(width, { target: { value: '250' } });
        fireEvent.blur(width);
        expect(await screen.findByText(/Scale must be between/)).toBeInTheDocument();
    });

    it('changes the selected sofa for a library item through one replace operation', async () => {
        vi.spyOn(api.interior.library, 'categories').mockResolvedValue({ total: 1, groups: [] });
        vi.spyOn(api.interior.library, 'search').mockResolvedValue({
            items: [{ id: 'sofa-chesterfield-sofa', name: 'Chesterfield Sofa', category: 'sofa', category_label: 'Sofas',
                subcategory: '3-seater', style: 'traditional', material: 'leather', material_label: 'Leather',
                color: '#6b4a32', colors: [{ name: 'brown', hex: '#6b4a32' }], unit: 'cm',
                dimensions: { width: 220, depth: 95, height: 78 }, thumbnail_url: '/x.png' }],
            total: 1, page: 1, page_size: 24, pages: 1, facets: {}, filters: {}, interpreted: null, relaxed: [],
        });
        const next = makeScene(1);
        next.last_operation = { operation: 'replace_object', assigned_id: 'sofa_002' };
        const apply = vi.spyOn(api.interior, 'apply').mockResolvedValue(response(next));
        renderEditor();
        fireEvent.click(await screen.findByRole('button', { name: /Sofa/ }));
        fireEvent.click(screen.getByRole('button', { name: /Change sofa/ }));
        fireEvent.click(await screen.findByRole('button', { name: 'Use this' }));
        await waitFor(() => expect(apply).toHaveBeenCalledWith('a'.repeat(32), 0, {
            operation: 'replace_object', object_id: 'sofa_001',
            changes: { library_item: 'sofa-chesterfield-sofa', color: '#6b4a32' },
        }));
        await waitFor(() => expect(screen.queryByRole('dialog', { name: 'Change Sofa' })).not.toBeInTheDocument());
    });

    it('asks guests to sign in before saving', async () => {
        renderEditor();
        fireEvent.click(screen.getByTitle('Save design'));
        expect(await screen.findByText(/to save designs to your account/)).toBeInTheDocument();
    });
});
