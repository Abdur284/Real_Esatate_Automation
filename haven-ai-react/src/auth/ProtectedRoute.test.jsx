import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';

let authState;
vi.mock('./AuthContext', () => ({ useAuth: () => authState }));

import ProtectedRoute from './ProtectedRoute';

function renderAt(props) {
    return render(
        <MemoryRouter initialEntries={['/dealer-dashboard']}>
            <Routes>
                <Route path="/dealer-dashboard" element={<ProtectedRoute {...props}><div>secret area</div></ProtectedRoute>} />
                <Route path="/signup" element={<div>sign in page</div>} />
            </Routes>
        </MemoryRouter>,
    );
}

describe('ProtectedRoute', () => {
    it('sends guests to sign in', () => {
        authState = { user: null, profile: null, isAdmin: false, ready: true };
        renderAt({ role: 'seller' });
        expect(screen.getByText('sign in page')).toBeInTheDocument();
    });

    it('blocks a signed-in buyer from the dealer area', () => {
        authState = { user: { uid: 'u' }, profile: { role: 'buyer' }, isAdmin: false, ready: true };
        renderAt({ role: 'seller' });
        expect(screen.getByText('Dealer access only')).toBeInTheDocument();
        expect(screen.queryByText('secret area')).toBeNull();
    });

    it('lets a seller in', () => {
        authState = { user: { uid: 'u' }, profile: { role: 'seller' }, isAdmin: false, ready: true };
        renderAt({ role: 'seller' });
        expect(screen.getByText('secret area')).toBeInTheDocument();
    });

    it('requires the admin claim for admin pages', () => {
        authState = { user: { uid: 'u' }, profile: { role: 'seller' }, isAdmin: false, ready: true };
        renderAt({ admin: true });
        expect(screen.getByText('Administrators only')).toBeInTheDocument();
        authState = { ...authState, isAdmin: true };
        renderAt({ admin: true });
        expect(screen.getByText('secret area')).toBeInTheDocument();
    });
});
