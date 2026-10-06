import { render, screen, fireEvent, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const api = vi.hoisted(() => ({ fromPlan2d: vi.fn(), generate: vi.fn(), analyzePlan: vi.fn() }));
const viewerProps = vi.hoisted(() => ({ last: null }));
vi.mock('../api', () => ({
    default: { design3d: { ...api, modelUrl: (p) => (p ? `http://api${p}` : null) } },
}));
vi.mock('../components/Navbar', () => ({ default: () => null }));
vi.mock('../components/Footer', () => ({ default: () => null }));
vi.mock('../components/threeD/ThreeDViewer', () => ({
    default: (props) => {
        viewerProps.last = props;
        return (
            <div data-testid="stub-viewer">
                <button type="button" onClick={() => props.onSelectRoom({ id: 'r1_2', level: 1, label: 'Bedroom', type: 'bedroom', width_ft: 8, depth_ft: 18, area_sqft: 144 })}>
                    click bedroom in 3D
                </button>
            </div>
        );
    },
}));

const { default: ThreeDDesign } = await import('./ThreeDDesign');
const { LAST_PLAN_KEY } = await import('../components/floorPlanExport');

const savedPlan = {
    status: 'FEASIBLE', plot: { width_ft: 20, length_ft: 30, area_sqft: 600 },
    design: {
        floors: 1,
        ground_floor: { rooms: [{ id: 'a', name: 'Lounge', type: 'tv_lounge', x: 0, y: 0, width: 12, length: 18 }], circulation: [], open_spaces: [] },
        first_floor: { rooms: [], circulation: [], open_spaces: [] },
    },
};

const built = {
    status: 'FEASIBLE', source: 'plan2d', message: 'Built a 1-storey model from your 2D floor plan.',
    assumptions: ['A conceptual massing model.'],
    glb: { model_url: '/api/design/3d/models/abc.glb', format: 'glb', metadata: { furniture_pieces: 3 } },
    model: {
        plot: { width_ft: 20, length_ft: 30 },
        footprint: { width_ft: 20, depth_ft: 30, origin_x_ft: 0, origin_y_ft: 0 },
        totals: { storeys: 1, covered_area_sqft: 600, building_height_ft: 11 },
        storeys: [{
            level: 1, label: 'Ground Floor', elevation_ft: 0, covered_area_sqft: 600, walls: [],
            rooms: [
                { id: 'r1_1', type: 'tv_lounge', label: 'Lounge', x: 0, y: 0, width: 12, depth: 18, enclosed: true },
                { id: 'r1_2', type: 'bedroom', label: 'Bedroom', x: 12, y: 0, width: 8, depth: 18, enclosed: true },
            ],
        }],
    },
};

const renderPage = () => render(<MemoryRouter><ThreeDDesign /></MemoryRouter>);

beforeEach(() => {
    Object.values(api).forEach((f) => f.mockReset());
    localStorage.clear();
    viewerProps.last = null;
});

describe('3D Design page', () => {
    it('offers the three ways in and explains when there is no 2D design yet', () => {
        renderPage();
        expect(screen.getByRole('tab', { name: /Describe requirements/ })).toHaveAttribute('aria-selected', 'true');
        fireEvent.click(screen.getByRole('tab', { name: /Upload 2D design/ }));
        expect(screen.getByRole('button', { name: 'Analyze floor plan' })).toBeDisabled();
        fireEvent.click(screen.getByRole('tab', { name: /Use existing 2D design/ }));
        expect(screen.getByText(/No 2D design yet/)).toBeInTheDocument();
    });

    it('builds the latest 2D design, shows progress, then the viewer and room details', async () => {
        localStorage.setItem(LAST_PLAN_KEY, JSON.stringify(savedPlan));
        let resolve;
        api.fromPlan2d.mockReturnValue(new Promise((r) => { resolve = r; }));
        renderPage();
        fireEvent.click(screen.getByRole('tab', { name: /Use existing 2D design/ }));
        fireEvent.click(screen.getByRole('button', { name: 'Build this design in 3D' }));
        expect(screen.getByTestId('page-loading')).toHaveTextContent('Generating 3D model…');
        expect(api.fromPlan2d).toHaveBeenCalledWith(savedPlan);

        resolve(built);
        expect(await screen.findByTestId('stub-viewer')).toBeInTheDocument();
        expect(viewerProps.last.url).toBe('http://api/api/design/3d/models/abc.glb');
        expect(viewerProps.last.options).toMatchObject({ showWalls: true, showRoof: true, visibleLevels: [1] });

        // Toolbar toggles reach the viewer.
        fireEvent.click(screen.getByRole('button', { name: /Roof/ }));
        expect(viewerProps.last.options.showRoof).toBe(false);
        fireEvent.click(screen.getByRole('button', { name: /Furniture/ }));
        expect(viewerProps.last.options.showFurniture).toBe(false);

        // Selecting in 3D shows the room card; the list shows it as selected.
        fireEvent.click(screen.getByRole('button', { name: 'click bedroom in 3D' }));
        const card = screen.getByTestId('room-card');
        expect(within(card).getByText('8 × 18 ft')).toBeInTheDocument();
        expect(within(card).getByText('144 sq ft')).toBeInTheDocument();

        // Selecting from the list selects the same room object shape.
        fireEvent.click(screen.getByRole('button', { name: /Lounge/ }));
        expect(viewerProps.last.selected).toMatchObject({ id: 'r1_1', level: 1, width_ft: 12, depth_ft: 18 });

        // View buttons issue camera requests.
        fireEvent.click(screen.getByRole('button', { name: 'Top' }));
        expect(viewerProps.last.viewRequest.name).toBe('top');
        fireEvent.click(screen.getByRole('button', { name: 'Interior' }));
        expect(viewerProps.last.viewRequest.name).toBe('interior');
    });

    it('shows a readable message when the plan cannot be built', async () => {
        localStorage.setItem(LAST_PLAN_KEY, JSON.stringify(savedPlan));
        api.fromPlan2d.mockResolvedValue({ status: 'NOT_FEASIBLE', message: 'The 2D plan\'s geometry is invalid.' });
        renderPage();
        fireEvent.click(screen.getByRole('tab', { name: /Use existing 2D design/ }));
        fireEvent.click(screen.getByRole('button', { name: 'Build this design in 3D' }));
        expect(await screen.findByText('NOT FEASIBLE')).toBeInTheDocument();
        expect(screen.queryByTestId('stub-viewer')).toBeNull();
    });

    it('reports an unreachable backend without crashing', async () => {
        localStorage.setItem(LAST_PLAN_KEY, JSON.stringify(savedPlan));
        api.fromPlan2d.mockRejectedValue(new Error('Failed to fetch'));
        renderPage();
        fireEvent.click(screen.getByRole('tab', { name: /Use existing 2D design/ }));
        fireEvent.click(screen.getByRole('button', { name: 'Build this design in 3D' }));
        expect(await screen.findByText(/Make sure the backend is running/)).toBeInTheDocument();
    });
});
