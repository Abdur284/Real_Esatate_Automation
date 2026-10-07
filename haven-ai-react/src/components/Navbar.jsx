import { useEffect, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';

export default function Navbar() {
    const [scrolled, setScrolled] = useState(false);
    const { user, profile, isAdmin, logout } = useAuth();
    const location = useLocation();
    const navigate = useNavigate();

    useEffect(() => {
        const handleScroll = () => setScrolled(window.scrollY > 20);
        window.addEventListener('scroll', handleScroll);
        return () => window.removeEventListener('scroll', handleScroll);
    }, []);

    const handleLogout = async () => {
        await logout();
        navigate('/');
    };

    const isActive = (path) => location.pathname === path ? 'active' : '';

    return (
        <header className={`main-header${scrolled ? ' scrolled' : ''}`}>
            <nav className="main-nav">
                <Link to="/" className="logo">HAVEN<span>.</span>AI</Link>
                <ul className="nav-links">
                    {/* Only show AI tools if NOT a buyer (or guest) */}
                    {(!user || profile?.role !== "buyer") && (
                        <>
                            <li><Link to="/2d-design" className={isActive('/2d-design')}>2D Design</Link></li>
                            <li><Link to="/3d-design" className={isActive('/3d-design')}>3D Design</Link></li>
                            <li><Link to="/cost-estimation" className={isActive('/cost-estimation')}>Cost Estimation</Link></li>
                            <li><Link to="/interior-design" className={isActive('/interior-design')}>Interior Design</Link></li>
                        </>
                    )}
                    <li><Link to="/properties" className={isActive('/properties')}>Properties</Link></li>
                </ul>
                <div className="auth-btns">
                    {user ? (
                        <>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginRight: '0.5rem' }}>
                                <span style={{ fontSize: '0.85rem', color: 'var(--text-2)' }}>Hi, {profile?.name || 'User'}</span>
                                <Link to="/chat" style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--text-2)' }}>Messages</Link>
                                {profile?.role === 'seller' && <Link to="/dealer-dashboard" style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--accent)' }}>Dealer Dashboard</Link>}
                                {isAdmin && <Link to="/admin" style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--accent)' }}>Admin</Link>}
                            </div>
                            <button className="btn-ghost" onClick={handleLogout}>Logout</button>
                        </>
                    ) : (
                        <>
                            <button className="btn-ghost" onClick={() => navigate('/signup?tab=login')}>Login</button>
                            <button className="btn-cta" onClick={() => navigate('/signup?tab=signup')}>Start for Free</button>
                        </>
                    )}
                </div>
            </nav>
        </header>
    );
}
