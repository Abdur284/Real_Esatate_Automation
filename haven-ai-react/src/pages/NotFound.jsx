import { Link } from 'react-router-dom';

export default function NotFound() {
    return (
        <div className="page-content" style={{ padding: '8rem 2rem', textAlign: 'center' }}>
            <div style={{ fontSize: '4rem', fontWeight: 800, fontFamily: 'Syne, sans-serif', color: 'var(--accent)' }}>404</div>
            <h2 style={{ fontFamily: 'Syne, sans-serif', marginTop: '0.5rem' }}>Page not found</h2>
            <p style={{ color: 'var(--text-3)', margin: '1rem 0 2rem' }}>The page you are looking for does not exist or has moved.</p>
            <Link to="/" className="btn-cta">Go to the home page</Link>
        </div>
    );
}
