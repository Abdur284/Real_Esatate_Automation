import { useCallback, useEffect, useState } from 'react';
import api from '../api';
import { useAuth } from '../auth/AuthContext';
import { useToast } from '../components/Toast';

// Admin Command Center. Access is the `admin` custom claim on the signed-in
// account (ProtectedRoute in App.jsx for the UI, require_admin on the
// backend for the data); every action below is a backend call.

function Modal({ title, onClose, children, width = '800px' }) {
    return (
        <div className="modal-overlay" onClick={onClose}>
            <div className="modal-content" role="dialog" aria-label={title} style={{ maxWidth: width, background: 'var(--surface)', padding: '2rem', borderRadius: '20px' }} onClick={e => e.stopPropagation()}>
                <h2>{title}</h2>
                {children}
                <button className="btn-feature" style={{ marginTop: '2rem' }} onClick={onClose}>Close</button>
            </div>
        </div>
    );
}

export default function AdminDashboard() {
    const { user } = useAuth();
    const toast = useToast();
    const [stats, setStats] = useState(null);
    const [activity, setActivity] = useState([]);
    const [loadError, setLoadError] = useState(null);
    const [activeModal, setActiveModal] = useState(null); // 'users' | 'properties' | 'health' | 'reset'
    const [allUsers, setAllUsers] = useState(null);
    const [unverifiedProps, setUnverifiedProps] = useState(null);
    const [health, setHealth] = useState(null);
    const [busy, setBusy] = useState(false);

    const load = useCallback(async () => {
        setLoadError(null);
        try {
            const [s, a] = await Promise.all([api.admin.stats(), api.admin.activity()]);
            setStats(s);
            setActivity(a.items);
        } catch (e) {
            setLoadError(e.message);
        }
    }, []);

    useEffect(() => { load(); }, [load]);

    const openUserManagement = async () => {
        setActiveModal('users');
        setAllUsers(null);
        try { setAllUsers((await api.admin.users()).users); } catch (e) { toast.error(e.message); setActiveModal(null); }
    };

    const openPropertyVerification = async () => {
        setActiveModal('properties');
        setUnverifiedProps(null);
        try { setUnverifiedProps((await api.admin.properties(false)).properties); } catch (e) { toast.error(e.message); setActiveModal(null); }
    };

    const handleHealthCheck = async () => {
        setActiveModal('health');
        setHealth(null);
        try { setHealth(await api.admin.health()); } catch (e) { setHealth({ error: e.message }); }
    };

    const verifyProperty = async (id) => {
        try {
            await api.admin.verifyProperty(id);
            setUnverifiedProps(prev => prev.filter(p => p.id !== id));
            toast.success('Property verified.');
        } catch (e) { toast.error(e.message); }
    };

    const deleteUser = async (u) => {
        if (!window.confirm(`Delete ${u.name || u.email} permanently? This removes their profile and sign-in account.`)) return;
        try {
            await api.admin.deleteUser(u.id);
            setAllUsers(prev => prev.filter(x => x.id !== u.id));
            toast.success('User deleted.');
            load();
        } catch (e) { toast.error(e.message); }
    };

    const resetViews = async () => {
        setBusy(true);
        try {
            const r = await api.admin.resetViews();
            toast.success(`View counters reset on ${r.reset} listings.`);
            setActiveModal(null);
            load();
        } catch (e) { toast.error(e.message); } finally { setBusy(false); }
    };

    if (loadError) {
        return (
            <div className="page-content" style={{ padding: '8rem 2rem', textAlign: 'center' }}>
                <p style={{ color: 'var(--text-2)', marginBottom: '1.5rem' }}>{loadError}</p>
                <button className="btn-cta" onClick={load}>Retry</button>
            </div>
        );
    }
    if (!stats) return <div className="loading-screen">Loading Admin Panel...</div>;

    return (
        <>
            <div className="page-hero">
                <div className="page-hero-inner">
                    <div className="page-hero-icon">⚙️</div>
                    <div>
                        <h1>Admin Command Center</h1>
                        <p>Signed in as {user?.email}. Monitor users, dealers, properties and conversations.</p>
                    </div>
                </div>
            </div>

            <div className="page-content" style={{ maxWidth: '1200px' }}>
                {/* Stats Grid */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '1.5rem', marginBottom: '3rem' }}>
                    {[
                        { label: 'Total Users', value: stats.total_users, icon: '👤', color: 'var(--accent)' },
                        { label: 'Total Dealers', value: stats.total_dealers, icon: '💼', color: 'var(--green)' },
                        { label: 'Properties Listed', value: stats.total_properties, icon: '🏠', color: 'var(--gold)' },
                        { label: 'Total Property Views', value: stats.total_views, icon: '👁️', color: 'var(--accent-2)' },
                    ].map((s) => (
                        <div key={s.label} className="stat-item" style={{ textAlign: 'left', padding: '1.5rem', background: 'var(--surface)' }}>
                            <div style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>{s.icon}</div>
                            <div className="stat-num" style={{ fontSize: '2.4rem', color: s.color }}>{s.value}</div>
                            <div className="stat-desc" style={{ fontSize: '0.9rem', fontWeight: 600 }}>{s.label}</div>
                        </div>
                    ))}
                </div>

                <div className="admin-grid" style={{ display: 'grid', gridTemplateColumns: '2fr 1.2fr', gap: '2rem' }}>
                    {/* Activity Section */}
                    <div style={{ background: 'var(--surface)', borderRadius: 'var(--radius)', padding: '2rem', border: '1px solid var(--border)' }}>
                        <h2 style={{ marginBottom: '1.5rem', fontFamily: 'Syne, sans-serif' }}>Recent Activity</h2>
                        {activity.length === 0 ? (
                            <p style={{ color: 'var(--text-3)' }}>No recent chat activity found.</p>
                        ) : (
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                                {activity.map(item => (
                                    <div key={`${item.type}-${item.id}`} style={{ padding: '1rem', background: 'var(--bg-2)', borderRadius: '10px', border: '1px solid var(--border)', position: 'relative' }}>
                                        <div style={{ position: 'absolute', top: '1rem', right: '1rem', fontSize: '0.6rem', fontWeight: 800, padding: '0.2rem 0.5rem', borderRadius: '100px', background: item.type === 'AI' ? 'rgba(59,130,246,0.1)' : 'rgba(16,185,129,0.1)', color: item.type === 'AI' ? 'var(--accent)' : 'var(--green)', border: '1px solid currentColor' }}>
                                            {item.type}
                                        </div>
                                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                                            <span style={{ fontWeight: 600, fontSize: '0.9rem' }}>{item.title}</span>
                                            <span style={{ fontSize: '0.75rem', color: 'var(--text-3)', marginRight: '4rem' }}>{item.time ? new Date(item.time).toLocaleString() : ''}</span>
                                        </div>
                                        <div style={{ fontSize: '0.75rem', color: 'var(--text-3)', fontStyle: 'italic', marginBottom: '0.4rem' }}>{item.subtitle}</div>
                                        <p style={{ fontSize: '0.85rem', color: 'var(--text-2)', margin: 0 }}>{item.message}</p>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>

                    {/* Quick Controls */}
                    <div style={{ background: 'var(--surface)', borderRadius: 'var(--radius)', padding: '2rem', border: '1px solid var(--border)' }}>
                        <h2 style={{ marginBottom: '1.5rem', fontFamily: 'Syne, sans-serif' }}>Site Management</h2>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                            <button className="btn-feature" style={{ width: '100%', justifyContent: 'center' }} onClick={openUserManagement}>Manage Users</button>
                            <button className="btn-feature" style={{ width: '100%', justifyContent: 'center' }} onClick={openPropertyVerification}>Verify Properties</button>
                            <button className="btn-feature" style={{ width: '100%', justifyContent: 'center' }} onClick={handleHealthCheck}>System Health Check</button>
                            <button className="btn-feature" style={{ width: '100%', justifyContent: 'center', borderColor: 'var(--red)', color: 'var(--red)' }} onClick={() => setActiveModal('reset')}>Reset View Counters</button>
                        </div>
                    </div>
                </div>

                {/* --- Modals --- */}
                {activeModal === 'users' && (
                    <Modal title="User Management" onClose={() => setActiveModal(null)}>
                        {allUsers === null ? <p>Loading users…</p> : (
                            <div style={{ overflowX: 'auto' }}>
                                <table style={{ width: '100%', borderCollapse: 'collapse', marginTop: '1rem' }}>
                                    <thead>
                                        <tr style={{ borderBottom: '1px solid var(--border)', color: 'var(--text-3)' }}>
                                            <th style={{ textAlign: 'left', padding: '1rem' }}>Name</th>
                                            <th style={{ textAlign: 'left', padding: '1rem' }}>Role</th>
                                            <th style={{ textAlign: 'left', padding: '1rem' }}>Email</th>
                                            <th style={{ textAlign: 'right', padding: '1rem' }}>Action</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {allUsers.map(u => (
                                            <tr key={u.id} style={{ borderBottom: '1px solid var(--border)' }}>
                                                <td style={{ padding: '1rem' }}>{u.name}</td>
                                                <td style={{ padding: '1rem' }}><span style={{ textTransform: 'uppercase', fontSize: '0.7rem', fontWeight: 800 }}>{u.role}</span></td>
                                                <td style={{ padding: '1rem', color: 'var(--text-3)' }}>{u.email}</td>
                                                <td style={{ padding: '1rem', textAlign: 'right' }}>
                                                    {u.id === user?.uid ? <span style={{ color: 'var(--text-3)', fontSize: '0.8rem' }}>You</span> : (
                                                        <button onClick={() => deleteUser(u)} style={{ background: 'none', border: 'none', color: 'var(--red)', cursor: 'pointer' }}>Delete</button>
                                                    )}
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        )}
                    </Modal>
                )}

                {activeModal === 'properties' && (
                    <Modal title="Unverified Properties" onClose={() => setActiveModal(null)}>
                        {unverifiedProps === null ? <p>Loading properties…</p> : unverifiedProps.length === 0 ? <p>All properties are verified!</p> : (
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', marginTop: '1rem' }}>
                                {unverifiedProps.map(p => (
                                    <div key={p.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '1rem', padding: '1rem', background: 'var(--bg-2)', borderRadius: '10px' }}>
                                        <div>
                                            <div style={{ fontWeight: 600 }}>{p.title}</div>
                                            <div style={{ fontSize: '0.8rem', color: 'var(--text-3)' }}>{p.location}</div>
                                        </div>
                                        <button className="btn-feature" onClick={() => verifyProperty(p.id)}>Approve & Verify</button>
                                    </div>
                                ))}
                            </div>
                        )}
                    </Modal>
                )}

                {activeModal === 'health' && (
                    <Modal title="System Health" width="460px" onClose={() => setActiveModal(null)}>
                        {health === null ? <p>Checking…</p> : health.error ? <p>❌ Backend unreachable: {health.error}</p> : (
                            <ul style={{ listStyle: 'none', padding: 0, lineHeight: 2, fontSize: '1rem' }}>
                                <li>{health.api === 'ok' ? '✅' : '❌'} Backend API</li>
                                <li>{health.firebase_configured ? '✅' : '⚠️'} Firebase Admin credentials</li>
                                <li>{health.gemini_configured ? '✅' : '⚠️'} Gemini API key</li>
                            </ul>
                        )}
                    </Modal>
                )}

                {activeModal === 'reset' && (
                    <Modal title="Reset view counters?" width="460px" onClose={() => setActiveModal(null)}>
                        <p style={{ color: 'var(--text-2)', margin: '1rem 0' }}>Every listing's view count will be set to zero. This cannot be undone.</p>
                        <button className="btn-feature" disabled={busy} style={{ borderColor: 'var(--red)', color: 'var(--red)' }} onClick={resetViews}>
                            {busy ? 'Resetting…' : 'Reset all counters'}
                        </button>
                    </Modal>
                )}
            </div>
        </>
    );
}
