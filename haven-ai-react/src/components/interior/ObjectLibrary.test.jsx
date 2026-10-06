import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import api from '../../api';
import ObjectLibrary from './ObjectLibrary';

const categories = {
    total: 3,
    groups: [{ id: 'seating', label: 'Seating', count: 3, categories: [
        { id: 'sofa', label: 'Sofas', count: 2, placement: 'floor' },
        { id: 'armchair', label: 'Armchairs', count: 1, placement: 'floor' },
    ] }],
};

const item = (id, name, extra = {}) => ({
    id, name, category: 'sofa', category_label: 'Sofas', subcategory: '3-seater', style: 'modern',
    material: 'fabric', material_label: 'Fabric', material_family: 'fabric', color: '#8c8a86',
    colors: [{ name: 'gray', hex: '#8c8a86' }, { name: 'navy', hex: '#2c3e57' }],
    dimensions: { width: 220, depth: 90, height: 85 }, unit: 'cm', dimensions_source: 'nominal',
    size: 'medium', placement: 'floor', tags: [], model_kind: 'parametric',
    thumbnail_url: `/api/interior/library/items/${id}/thumbnail.png`, ...extra,
});

function page(items, extra = {}) {
    return {
        items, total: extra.total ?? items.length, page: extra.page ?? 1, page_size: 24, pages: 1,
        facets: { style: [{ value: 'modern', label: 'Modern', count: 2 }, { value: 'luxury', label: 'Luxury', count: 1 }],
            material: [], color: [], size: [] },
        filters: extra.filters || {}, interpreted: extra.interpreted || null, relaxed: extra.relaxed || [],
    };
}

const sofa = { id: 'sofa_001', label: 'Sofa', capabilities: { library_category: 'sofa' } };
let search;

beforeEach(() => {
    vi.spyOn(api.interior.library, 'categories').mockResolvedValue(categories);
    search = vi.spyOn(api.interior.library, 'search').mockImplementation(async (p) => {
        if (p.page === 2) return page([item('sofa-c', 'Chesterfield Sofa')], { total: 3, page: 2 });
        if (p.q === 'modern gray sofa') {
            return page([item('sofa-a', 'Modern 3-Seater Sofa')], {
                filters: { category: 'sofa', style: 'modern', color: 'gray' },
                interpreted: { category: 'sofa', style: 'modern', color: 'gray', keywords: [] },
            });
        }
        return page([item('sofa-a', 'Modern 3-Seater Sofa'), item('sofa-b', 'Velvet Sofa')], { total: 3 });
    });
});
afterEach(() => vi.restoreAllMocks());

describe('object library', () => {
    it('marks real 3D models and their measured size', async () => {
        search.mockResolvedValue(page([
            item('ph-sofa-03', 'Victorian Leather Sofa', { realism: 'real', dimensions_source: 'measured', model_kind: 'mesh',
                dimensions: { width: 273.1, depth: 92.5, height: 111.8 } }),
            item('sofa-a', 'Modern 3-Seater Sofa', { realism: 'procedural' }),
        ]));
        render(<ObjectLibrary mode="replace" target={sofa} onUse={() => {}} onClose={() => {}} />);
        expect(await screen.findByText('Victorian Leather Sofa')).toBeInTheDocument();
        expect(screen.getAllByText('Real 3D model')).toHaveLength(1);
        expect(screen.getByText(/273 × 93 × 112 cm/)).toHaveTextContent('real size');
        expect(screen.getByText(/220 × 90 × 85 cm/)).toHaveTextContent('typical');
    });

    it('opens on the selected object\'s category and shows previews with sizes', async () => {
        render(<ObjectLibrary mode="replace" target={sofa} onUse={() => {}} onClose={() => {}} />);
        expect(await screen.findByText('Modern 3-Seater Sofa')).toBeInTheDocument();
        expect(search).toHaveBeenCalledWith(expect.objectContaining({ category: 'sofa', page: 1 }));
        expect(screen.getByRole('dialog', { name: 'Change Sofa' })).toBeInTheDocument();
        expect(screen.getAllByText(/220 × 90 × 85 cm/)[0]).toBeInTheDocument();
        const img = screen.getByAltText('Velvet Sofa');
        expect(img.getAttribute('src')).toContain('/api/interior/library/items/sofa-b/thumbnail.png');
        expect(img.getAttribute('loading')).toBe('lazy');
    });

    it('searches in plain words on the server and shows what it understood', async () => {
        render(<ObjectLibrary mode="add" onUse={() => {}} onClose={() => {}} />);
        fireEvent.change(await screen.findByLabelText('Search the library'), { target: { value: 'modern gray sofa' } });
        await waitFor(() => expect(search).toHaveBeenCalledWith(expect.objectContaining({ q: 'modern gray sofa' })));
        expect(await screen.findByText(/Understood:/)).toBeInTheDocument();
        expect(screen.getByText('gray')).toBeInTheDocument();
    });

    it('filters, pages and switches category', async () => {
        render(<ObjectLibrary mode="replace" target={sofa} onUse={() => {}} onClose={() => {}} />);
        fireEvent.change(await screen.findByLabelText('Style'), { target: { value: 'luxury' } });
        await waitFor(() => expect(search).toHaveBeenCalledWith(expect.objectContaining({ style: 'luxury', category: 'sofa' })));
        fireEvent.click(await screen.findByRole('button', { name: 'Load more' }));
        expect(await screen.findByText('Chesterfield Sofa')).toBeInTheDocument();
        expect(screen.getByText('Showing 3 of 3')).toBeInTheDocument();
        fireEvent.click(screen.getByRole('button', { name: /Armchairs/ }));
        await waitFor(() => expect(search).toHaveBeenCalledWith(expect.objectContaining({ category: 'armchair', page: 1 })));
        fireEvent.click(screen.getByRole('button', { name: /Browse all/ }));
        await waitFor(() => expect(search).toHaveBeenLastCalledWith(expect.not.objectContaining({ category: 'armchair' })));
    });

    it('uses the chosen item in the chosen colour', async () => {
        const onUse = vi.fn();
        render(<ObjectLibrary mode="replace" target={sofa} onUse={onUse} onClose={() => {}} />);
        await screen.findByText('Velvet Sofa');
        fireEvent.click(screen.getAllByRole('radio', { name: 'navy' })[1]);
        fireEvent.click(screen.getAllByRole('button', { name: 'Use this' })[1]);
        expect(onUse).toHaveBeenCalledWith(expect.objectContaining({ id: 'sofa-b' }), '#2c3e57');
    });
});
