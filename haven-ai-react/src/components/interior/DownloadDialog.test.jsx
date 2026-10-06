import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import api from '../../api';
import { BeforeAfter, DownloadDialog } from './RoomEditor';

if (!URL.revokeObjectURL) URL.revokeObjectURL = () => {};
afterEach(() => vi.restoreAllMocks());

describe('Download design', () => {
    it('renders the chosen format, downloads it and shows before/after', async () => {
        const final = vi.spyOn(api.interior, 'final').mockResolvedValue({
            version: 3, format: 'png', quality: 'lossless', width: 1280, height: 853, bytes: 2_400_000,
            filename: 'haven-design-v3.png', url: '/api/interior/scenes/x/files/final_v3.png',
        });
        vi.spyOn(api.interior, 'image').mockResolvedValue({ url: 'blob:final' });
        const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
        render(<DownloadDialog sceneId="x" originalUrl="blob:original" onClose={() => {}} />);

        expect(screen.getByText('Quality')).toBeInTheDocument();             // JPG by default
        fireEvent.click(screen.getByLabelText(/PNG/));
        expect(screen.queryByText('Quality')).toBeNull();                   // PNG is lossless
        fireEvent.click(screen.getByRole('button', { name: /Download Design/ }));

        expect(await screen.findByText(/Downloaded haven-design-v3.png/)).toHaveTextContent('1280 × 853 px · 2.3 MB');
        expect(final).toHaveBeenCalledWith('x', 'png', 'high');
        expect(click).toHaveBeenCalled();
        expect(screen.getByAltText('Before: the original photo')).toHaveAttribute('src', 'blob:original');
        expect(screen.getByAltText('After: your design')).toHaveAttribute('src', 'blob:final');
    });

    it('JPG at standard quality', async () => {
        const final = vi.spyOn(api.interior, 'final').mockRejectedValue(new Error('Render failed'));
        render(<DownloadDialog sceneId="x" originalUrl={null} onClose={() => {}} />);
        fireEvent.click(screen.getByLabelText(/Standard/));
        fireEvent.click(screen.getByRole('button', { name: /Download Design/ }));
        expect(await screen.findByText('Render failed')).toBeInTheDocument();
        expect(final).toHaveBeenCalledWith('x', 'jpg', 'standard');
    });
});

describe('Before / after slider', () => {
    it('moves the divider with the keyboard control', () => {
        const { container } = render(<BeforeAfter before="b.png" after="a.png" />);
        const slider = screen.getByLabelText('Before / after divider');
        fireEvent.change(slider, { target: { value: 30 } });
        expect(container.querySelector('.ie-ba-before').style.clipPath).toBe('inset(0 70% 0 0)');
        expect(container.querySelector('.ie-ba-line').style.left).toBe('30%');
    });
});
