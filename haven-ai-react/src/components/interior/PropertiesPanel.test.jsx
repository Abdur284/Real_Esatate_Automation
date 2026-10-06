import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ObjectPanel } from './PropertiesPanel';

const catalog = { types: { sofa: { category: 'Furniture' } }, materials: { leather: { label: 'Leather' } }, palette: ['#5a3a22'] };

const fitted = (scale) => ({
    id: 'sofa_002', label: 'Chesterfield Sofa', type: 'sofa', category: 'furniture', source: 'model', placement: 'floor',
    transform: { position: { x: 0.5, y: 0.7 }, scale, rotation: 0, flip: false },
    appearance: { color: '#5a3a22', material: 'leather' },
    dimensions_m: { width: 2.6, depth: 1.12, height: 0.92 },
    capabilities: { move: true, resize: true, rotate: 'yaw', color: true, materials: ['leather'], replace: true, remove: true },
    library_item: { id: 'sofa-chesterfield-sofa', name: 'Chesterfield Sofa', realism: 'procedural',
        dimensions: { width: 220, depth: 95, height: 78 } },
    replaces: { id: 'sofa_001', label: 'Sofa' },
    fit: { mode: 'match', replaced: 'Sofa', scale: { x: 1.18, y: 1.18, z: 1.18 },
        library_size_m: { width: 2.2, depth: 0.95, height: 0.78 } },
});

describe('replacement size', () => {
    it('says it was sized to the original and offers the catalogue size', () => {
        const onApply = vi.fn();
        render(<ObjectPanel obj={fitted({ x: 1.18, y: 1.18, z: 1.18 })} catalog={catalog} onApply={onApply}
            onRemove={() => {}} onChangeObject={() => {}} />);
        expect(screen.getByText(/Sized to fill the space of the original sofa/)).toHaveTextContent('2.20 × 0.95 × 0.78 m');
        expect(screen.queryByRole('button', { name: 'Match original size' })).toBeNull();
        fireEvent.click(screen.getByRole('button', { name: 'Use catalogue size' }));
        expect(onApply).toHaveBeenCalledWith({ operation: 'fit_object', object_id: 'sofa_002', changes: { size: 'catalogue' } });
    });

    it('after a manual resize it can go back to the original size', () => {
        const onApply = vi.fn();
        render(<ObjectPanel obj={fitted({ x: 1, y: 1, z: 1 })} catalog={catalog} onApply={onApply}
            onRemove={() => {}} onChangeObject={() => {}} />);
        expect(screen.queryByRole('button', { name: 'Use catalogue size' })).toBeNull();
        fireEvent.click(screen.getByRole('button', { name: 'Match original size' }));
        expect(onApply).toHaveBeenCalledWith({ operation: 'fit_object', object_id: 'sofa_002', changes: { size: 'original' } });
    });
});
