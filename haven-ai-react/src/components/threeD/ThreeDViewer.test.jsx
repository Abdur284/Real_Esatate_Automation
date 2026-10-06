// Loading, error and unsupported states of the viewer. WebGL itself cannot
// run in jsdom; real rendering is checked in the browser.
import { render, screen, fireEvent } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

const loader = vi.hoisted(() => ({ webgl: true, load: null }));
vi.mock('./houseLoader', () => ({
    webglAvailable: () => loader.webgl,
    loadHouse: (...args) => loader.load(...args),
    disposeScene: () => {},
}));
vi.mock('@react-three/fiber', () => ({
    Canvas: () => { throw new Error('WebGL context lost'); },
    useFrame: () => {},
    useThree: () => ({}),
}));

const { default: ThreeDViewer } = await import('./ThreeDViewer');

const props = { url: '/api/design/3d/models/abc.glb', options: { visibleLevels: [1] }, height: 300 };

afterEach(() => { loader.webgl = true; vi.restoreAllMocks(); });

describe('ThreeDViewer states', () => {
    it('shows a loading state while the GLB downloads', () => {
        loader.load = () => new Promise(() => {});
        render(<ThreeDViewer {...props} />);
        expect(screen.getByTestId('viewer-loading')).toHaveTextContent('Loading 3D model');
    });

    it('explains an expired model', async () => {
        loader.load = () => Promise.reject(new Error('expired'));
        vi.spyOn(console, 'error').mockImplementation(() => {});
        render(<ThreeDViewer {...props} />);
        expect(await screen.findByTestId('viewer-error')).toHaveTextContent('expired');
    });

    it('offers a retry when loading fails', async () => {
        let calls = 0;
        loader.load = () => { calls += 1; return Promise.reject(new Error('HTTP 500')); };
        vi.spyOn(console, 'error').mockImplementation(() => {});
        render(<ThreeDViewer {...props} />);
        fireEvent.click(await screen.findByRole('button', { name: 'Try again' }));
        await screen.findByTestId('viewer-error');
        expect(calls).toBe(2);
    });

    it('contains a rendering crash instead of breaking the page', async () => {
        loader.load = () => Promise.resolve({ scene: {}, index: { meta: {} } });
        vi.spyOn(console, 'error').mockImplementation(() => {});
        render(<div><p>rest of page</p><ThreeDViewer {...props} /></div>);
        expect(await screen.findByTestId('viewer-error')).toHaveTextContent("couldn't be displayed");
        expect(screen.getByText('rest of page')).toBeInTheDocument();
    });

    it('explains when WebGL is unavailable', () => {
        loader.webgl = false;
        render(<ThreeDViewer {...props} />);
        expect(screen.getByTestId('viewer-unsupported')).toHaveTextContent('WebGL');
    });
});
