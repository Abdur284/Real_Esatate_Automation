import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const analyzePlan = vi.hoisted(() => vi.fn());
vi.mock('../../api', () => ({ default: { design3d: { analyzePlan } } }));

const { default: PlanImageImport } = await import('./PlanImageImport');

const plan = {
    status: 'FEASIBLE',
    source: 'image_analysis',
    plot: { width_ft: 20, length_ft: 30, area_sqft: 600 },
    design: {
        floors: 1,
        ground_floor: {
            rooms: [
                { id: 'room_1', name: 'Room 1', type: 'other', x: 0.4, y: 0.4, width: 12, length: 14, doors: [], windows: [], detection: { type_source: 'unknown' } },
                { id: 'room_2', name: 'Staircase 1', type: 'staircase', x: 12.4, y: 0.4, width: 7, length: 14, doors: [], windows: [], detection: { type_source: 'inferred_from_stair_hatching' } },
            ],
            circulation: [], open_spaces: [],
        },
        first_floor: { rooms: [], circulation: [], open_spaces: [] },
    },
};

const analysis = (extra = {}) => ({
    method: 'computer_vision',
    confidence: { walls: 0.95, rooms: 0.9, openings: 0.6, dimensions: 1, room_types: 0.5, overall: 0.85 },
    review_required: true, low_confidence: false,
    detected: ['2 enclosed room(s)'], explicit: ['Overall size 20 × 30 ft (entered by you)'],
    inferred: ['Door vs. window'], missing: ['Printed room names'], warnings: [],
    ...extra,
});

const file = () => new File([new Uint8Array([137, 80, 78, 71])], 'plan.png', { type: 'image/png' });

function upload() {
    fireEvent.change(screen.getByTestId('plan-file'), { target: { files: [file()] } });
}

beforeEach(() => {
    analyzePlan.mockReset();
    globalThis.URL.createObjectURL = vi.fn(() => 'blob:preview');
    globalThis.URL.revokeObjectURL = vi.fn();
});

describe('PlanImageImport', () => {
    it('rejects unsupported file types before uploading', () => {
        render(<PlanImageImport onBuild={() => {}} />);
        fireEvent.change(screen.getByTestId('plan-file'), { target: { files: [new File(['x'], 'plan.gif', { type: 'image/gif' })] } });
        expect(screen.getByRole('alert')).toHaveTextContent('PNG, JPEG or WebP');
        expect(analyzePlan).not.toHaveBeenCalled();
    });

    it('analyzes, shows the review, and builds with the user\'s edits', async () => {
        let resolve;
        analyzePlan.mockReturnValue(new Promise((r) => { resolve = r; }));
        const onBuild = vi.fn();
        render(<PlanImageImport onBuild={onBuild} />);
        upload();
        fireEvent.change(screen.getByLabelText(/Overall width/), { target: { value: '20' } });
        fireEvent.click(screen.getByRole('button', { name: 'Analyze floor plan' }));
        expect(screen.getAllByText(/Analyzing your floor plan/).length).toBeGreaterThan(0);
        expect(analyzePlan).toHaveBeenCalledWith(expect.objectContaining({ widthFt: 20, front: 'bottom' }));

        resolve({ status: 'ANALYZED', message: 'Found 2 room(s).', plan, analysis: analysis() });
        expect(await screen.findByText('Review the floor plan')).toBeInTheDocument();
        expect(screen.getByText('Stairs from tread lines')).toBeInTheDocument();
        expect(screen.getByText('Shape detected; type unknown')).toBeInTheDocument();

        fireEvent.change(screen.getByLabelText('Name of Room 1'), { target: { value: 'Master bedroom' } });
        fireEvent.change(screen.getByLabelText('Type of Master bedroom'), { target: { value: 'master_bedroom' } });
        fireEvent.click(screen.getByRole('button', { name: 'Generate 3D model' }));
        const built = onBuild.mock.calls[0][0];
        const room = built.design.ground_floor.rooms.find((r) => r.id === 'room_1');
        expect(room).toMatchObject({ name: 'Master bedroom', type: 'master_bedroom', width: 12, length: 14 });
    });

    it('asks for dimensions instead of guessing', async () => {
        analyzePlan.mockResolvedValue({
            status: 'NEEDS_DIMENSIONS', message: 'Unable to confidently detect the floor-plan dimensions.',
            analysis: { counts: { rooms: 5 }, hint: 'The drawing is 0.62× as wide as it is deep.' },
        });
        render(<PlanImageImport onBuild={() => {}} />);
        upload();
        fireEvent.click(screen.getByRole('button', { name: 'Analyze floor plan' }));
        const alert = await screen.findByRole('alert');
        expect(alert).toHaveTextContent('NEEDS DIMENSIONS');
        expect(alert).toHaveTextContent('5 enclosed room(s)');
        expect(screen.queryByRole('button', { name: 'Generate 3D model' })).toBeNull();
    });

    it('requires confirmation before building a low-confidence result', async () => {
        analyzePlan.mockResolvedValue({ status: 'ANALYZED', message: 'ok', plan, analysis: analysis({ low_confidence: true }) });
        const onBuild = vi.fn();
        render(<PlanImageImport onBuild={onBuild} />);
        upload();
        fireEvent.click(screen.getByRole('button', { name: 'Analyze floor plan' }));
        const build = await screen.findByRole('button', { name: 'Generate 3D model' });
        expect(build).toBeDisabled();
        fireEvent.click(screen.getByLabelText(/checked the layout/));
        await waitFor(() => expect(build).toBeEnabled());
        fireEvent.click(build);
        expect(onBuild).toHaveBeenCalled();
    });

    it('shows the server\'s reason for a rejected file', async () => {
        const err = new Error('Only PNG, JPEG or WebP floor-plan images are accepted.');
        err.status = 415;
        analyzePlan.mockRejectedValue(err);
        render(<PlanImageImport onBuild={() => {}} />);
        upload();
        fireEvent.click(screen.getByRole('button', { name: 'Analyze floor plan' }));
        expect(await screen.findByRole('alert')).toHaveTextContent('Only PNG, JPEG or WebP');
    });
});
