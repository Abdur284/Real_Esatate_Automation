import { useEffect, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { auth, db } from '../firebase';
import { onAuthStateChanged, signOut } from 'firebase/auth';
import { doc, getDoc } from 'firebase/firestore';

export default function Navbar() {
    const [scrolled, setScrolled] = useState(false);
    const [user, setUser] = useState(null);
    const location = useLocation();
    const navigate = useNavigate();

    useEffect(() => {
        const updateAuth = () => {
            const saved = localStorage.getItem("housing_user");
            if (saved) {
                try { setUser(JSON.parse(saved)); } catch (e) { setUser(null); }
            } else { setUser(null); }
        };
        updateAuth();
        window.addEventListener("storage", updateAuth);
        return () => window.removeEventListener("storage", updateAuth);
    }, []);

    useEffect(() => {
        const handleScroll = () => setScrolled(window.scrollY > 20);
        window.addEventListener('scroll', handleScroll);
        return () => window.removeEventListener('scroll', handleScroll);
    }, []);

    const handleLogout = () => {
        localStorage.removeItem("housing_user");
        setUser(null);
        navigate("/");
        window.location.reload();
    };

    const isActive = (path) => location.pathname === path ? 'active' : '';

    return (
        <header className={`main-header${scrolled ? ' scrolled' : ''}`}>
            <nav className="main-nav">
                <Link to="/" className="logo">HAVEN<span>.</span>AI</Link>
                <ul className="nav-links">
                    {/* Only show AI tools if NOT a buyer (or guest) */}
                    {(!user || user.role !== "buyer") && (
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
                                <span style={{ fontSize: '0.85rem', color: 'var(--text-2)' }}>Hi, {user.name || 'User'}</span>
                                {user.role === 'seller' && <Link to="/dealer-dashboard" style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--accent)' }}>Dealer Dashboard</Link>}
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
