import { Link, Navigate, useLocation } from 'react-router-dom';
import { useAuth } from './AuthContext';

/**
 * Renders its children only for signed-in users, optionally with a given
 * role ('seller') or the admin claim. This is a convenience for the UI; the
 * real protection is in the Firestore rules and the backend.
 */
export default function ProtectedRoute({ children, role, admin = false }) {
    const { user, profile, isAdmin, ready } = useAuth();
    const location = useLocation();

    if (!ready) return <div className="loading-screen">Loading…</div>;

    if (!user) {
        const next = encodeURIComponent(location.pathname + location.search);
        return <Navigate to={`/signup?tab=login&next=${next}`} replace />;
    }

    const allowed = admin ? isAdmin : !role || profile?.role === role;
    if (!allowed) {
        return (
            <div className="page-content" style={{ padding: '8rem 2rem', textAlign: 'center' }}>
                <h2 style={{ fontFamily: 'Syne, sans-serif' }}>{admin ? 'Administrators only' : 'Dealer access only'}</h2>
                <p style={{ color: 'var(--text-3)', margin: '1rem 0 2rem' }}>
                    {admin
                        ? 'Your account does not have administrator access.'
                        : 'This area is for accounts registered as a seller / dealer.'}
                </p>
                <Link to="/" className="btn-cta">Return Home</Link>
            </div>
        );
    }
    return children;
}
