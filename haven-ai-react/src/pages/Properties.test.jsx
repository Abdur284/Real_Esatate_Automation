import { render, screen, fireEvent, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const external = vi.hoisted(() => vi.fn());
const ownDocs = vi.hoisted(() => ({ list: [] }));
vi.mock('../api', () => ({ default: { properties: { external } } }));
vi.mock('../firebase', () => ({ db: {} }));
vi.mock('firebase/firestore', () => ({
    collection: () => ({}),
    getDocs: () => Promise.resolve({ forEach: (fn) => ownDocs.list.forEach((d) => fn({ id: d.id, data: () => d })) }),
}));
vi.mock('../auth/AuthContext', () => ({ useAuth: () => ({ user: { uid: 'buyer' } }) }));

const { default: Properties } = await import('./Properties');

const zameenItem = {
    id: 'zameen-1', source: 'zameen', title: '10 Marla House', type: 'house', status: 'for-sale', price: 100,
    location: 'DHA', city: 'Lahore', beds: 4, baths: 4, area: '10 Marla', img: null,
    url: 'https://www.zameen.com/Property/1.html', agency: 'ABC',
};

const renderPage = () => render(<MemoryRouter><Properties /></MemoryRouter>);
const card = (title) => screen.getByText(title).closest('.prop-card');

describe('Properties with Zameen.com listings', () => {
    beforeEach(() => {
        external.mockReset();
        ownDocs.list = [{ id: 'own-1', title: 'Our Dealer House', price: 50, dealerId: 'd1', type: 'For Sale' }];
    });

    it('shows Zameen listings next to ours, with a link out instead of chat', async () => {
        external.mockResolvedValue({ mode: 'live', listings: [zameenItem], error: null });
        const open = vi.spyOn(window, 'open').mockImplementation(() => null);
        renderPage();

        expect(await screen.findByText('10 Marla House')).toBeTruthy();
        expect(screen.getByText('Our Dealer House')).toBeTruthy();

        const z = within(card('10 Marla House'));
        expect(z.getByText('Zameen.com')).toBeTruthy();
        expect(z.queryByText('Contact Dealer')).toBeNull();
        fireEvent.click(z.getByRole('button', { name: /View on Zameen.com/ }));
        expect(open).toHaveBeenCalledWith(zameenItem.url, '_blank', 'noopener,noreferrer');

        expect(within(card('Our Dealer House')).getByText('Contact Dealer')).toBeTruthy();
        open.mockRestore();
    });

    it('still shows our listings when Zameen is unavailable', async () => {
        external.mockResolvedValue({ mode: 'live', listings: [], error: 'Zameen.com listings are not available right now.' });
        renderPage();
        expect(await screen.findByText('Our Dealer House')).toBeTruthy();
        expect(await screen.findByText(/Showing Haven.AI listings only/)).toBeTruthy();
    });

    it('still shows our listings when the backend is down', async () => {
        external.mockRejectedValue(new Error('offline'));
        renderPage();
        expect(await screen.findByText('Our Dealer House')).toBeTruthy();
    });
});
