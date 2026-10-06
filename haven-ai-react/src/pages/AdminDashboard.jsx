import { useState, useEffect } from 'react';
import { db } from '../firebase';
import { collection, getDocs, query, orderBy, limit, doc, updateDoc, deleteDoc, writeBatch } from 'firebase/firestore';
import Navbar from '../components/Navbar';
import Footer from '../components/Footer';

export default function AdminDashboard() {
    const [isAdminAuthenticated, setIsAdminAuthenticated] = useState(false);
    const [loginForm, setLoginForm] = useState({ email: '', password: '' });
    const [stats, setStats] = useState({
        totalUsers: 0,
        totalDealers: 0,
        totalProperties: 0,
        totalViews: 0
    });
    const [loading, setLoading] = useState(true);
    const [recentChats, setRecentChats] = useState([]);
    const [activeModal, setActiveModal] = useState(null); // 'users', 'properties', 'health'
    const [allUsers, setAllUsers] = useState([]);
    const [unverifiedProps, setUnverifiedProps] = useState([]);
    const [healthStatus, setHealthStatus] = useState(null);

    useEffect(() => {
        // Check if already authenticated in this session
        const authStatus = sessionStorage.getItem('isAdminAuth');
        if (authStatus === 'true') setIsAdminAuthenticated(true);
    }, []);

    const handleAdminLogin = (e) => {
        e.preventDefault();
        if (loginForm.email === 'raufa8989@gmail.com' && loginForm.password === 'qwe123') {
            setIsAdminAuthenticated(true);
            sessionStorage.setItem('isAdminAuth', 'true');
        } else {
            alert("Invalid Admin Credentials");
        }
    };

    useEffect(() => {
        if (!isAdminAuthenticated) return;
        const fetchStats = async () => {
            try {
                // Fetch Users
                const usersSnap = await getDocs(collection(db, 'users'));
                let buyers = 0;
                let dealers = 0;
                usersSnap.forEach(doc => {
                    const r = (doc.data().role || '').toLowerCase();
                    if (r === 'dealer' || r === 'seller') dealers++;
                    else buyers++;
                });

                // Fetch Properties
                const propertiesSnap = await getDocs(collection(db, 'properties'));
                let totalViews = 0;
                propertiesSnap.forEach(doc => {
                    totalViews += (doc.data().views || 0);
                });

                setStats({
                    totalUsers: buyers,
                    totalDealers: dealers,
                    totalProperties: propertiesSnap.size,
                    totalViews: totalViews
                });

                // Fetch Recent Activity (Conversations + AI Chats)
                const activity = [];
                
                // 1. Dealer Conversations
                try {
                    const convSnap = await getDocs(query(collection(db, 'conversations'), orderBy('lastAt', 'desc'), limit(5)));
                    convSnap.forEach(doc => {
                        const d = doc.data();
                        activity.push({
                            id: doc.id,
                            type: 'DEALER',
                            title: `${d.buyerName || 'User'} ↔ ${d.dealerName || 'Dealer'}`,
                            subtitle: d.propertyTitle,
                            message: d.lastMessage || 'Started a conversation',
                            time: d.lastAt
                        });
                    });
                } catch(e) { console.warn("Conversations fetch failed", e); }

                // 2. AI Chatbot Sessions
                try {
                    const aiSnap = await getDocs(query(collection(db, 'chat_sessions'), orderBy('updated_at', 'desc'), limit(5)));
                    aiSnap.forEach(doc => {
                        const d = doc.data();
                        activity.push({
                            id: doc.id,
                            type: 'AI',
                            title: `AI Chat: ${d.session_id.slice(0,8)}...`,
                            subtitle: 'ArchiBot Interaction',
                            message: d.messages?.[d.messages.length - 1]?.content || 'Active session',
                            time: d.updated_at
                        });
                    });
                } catch(e) { console.warn("AI Sessions fetch failed", e); }

                setRecentChats(activity.sort((a,b) => new Date(b.time) - new Date(a.time)).slice(0, 10));

            } catch (error) {
                console.error("Error fetching admin stats:", error);
                if (error.message.includes('429') || error.message.includes('quota')) {
                    alert("Firebase Quota Exceeded for today. Data might not be visible until midnight.");
                }
            } finally {
                setLoading(false);
            }
        };

        fetchStats();
    }, [isAdminAuthenticated]);

    // --- Action Handlers ---
    const handleResetViews = async () => {
        if (!window.confirm("Are you sure you want to reset ALL view counters to zero?")) return;
        try {
            const batch = writeBatch(db);
            const snap = await getDocs(collection(db, 'properties'));
            snap.forEach(d => batch.update(doc(db, 'properties', d.id), { views: 0 }));
            await batch.commit();
            alert("All view counters have been reset!");
            window.location.reload();
        } catch (e) { alert("Error: " + e.message); }
    };

    const handleHealthCheck = async () => {
        setHealthStatus("Checking...");
        setActiveModal('health');
        try {
            const res = await fetch('http://localhost:8000/api/chat/status');
            const data = await res.json();
            setHealthStatus(data.status === "Centralized Orchestrator Chat service is active" ? "✅ Backend Online" : "⚠️ Unexpected Response");
        } catch (e) {
            setHealthStatus("❌ Backend Offline (Check if Python server is running on port 8000)");
        }
    };

    const openUserManagement = async () => {
        setActiveModal('users');
        const snap = await getDocs(collection(db, 'users'));
        setAllUsers(snap.docs.map(d => ({ id: d.id, ...d.data() })));
    };

    const openPropertyVerification = async () => {
        setActiveModal('properties');
        const snap = await getDocs(collection(db, 'properties'));
        setUnverifiedProps(snap.docs.map(d => ({ id: d.id, ...d.data() })).filter(p => !p.verified));
    };

    const verifyProperty = async (id) => {
        await updateDoc(doc(db, 'properties', id), { verified: true });
        setUnverifiedProps(prev => prev.filter(p => p.id !== id));
        alert("Property Verified!");
    };

    const deleteUser = async (id) => {
        if (!window.confirm("Delete this user permanently?")) return;
        await deleteDoc(doc(db, 'users', id));
        setAllUsers(prev => prev.filter(u => u.id !== id));
    };

    if (!isAdminAuthenticated) {
        return (
            <div style={{ minHeight: '100vh', background: 'var(--bg)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: 'inherit' }}>
                <div style={{ background: 'var(--surface)', padding: '3rem', borderRadius: '24px', border: '1px solid var(--border)', width: '100%', maxWidth: '400px', textAlign: 'center' }}>
                    <h1 style={{ fontWeight: 800, fontSize: '1.5rem', marginBottom: '0.5rem', letterSpacing: '-0.03em' }}>HAVEN <span style={{ color: 'var(--accent)' }}>AI</span></h1>
                    <p style={{ color: 'var(--text-3)', fontSize: '0.85rem', marginBottom: '2rem' }}>Administrative Login</p>
                    <form onSubmit={handleAdminLogin}>
                        <input 
                            type="email" 
                            placeholder="Admin Email" 
                            style={{ width: '100%', padding: '0.8rem', background: 'var(--bg-2)', border: '1px solid var(--border)', borderRadius: '10px', color: 'var(--text)', marginBottom: '1rem' }}
                            value={loginForm.email}
                            onChange={e => setLoginForm({...loginForm, email: e.target.value})}
                        />
                        <input 
                            type="password" 
                            placeholder="Password" 
                            style={{ width: '100%', padding: '0.8rem', background: 'var(--bg-2)', border: '1px solid var(--border)', borderRadius: '10px', color: 'var(--text)', marginBottom: '1.5rem' }}
                            value={loginForm.password}
                            onChange={e => setLoginForm({...loginForm, password: e.target.value})}
                        />
                        <button type="submit" style={{ width: '100%', padding: '0.8rem', background: 'var(--accent)', color: '#fff', border: 'none', borderRadius: '10px', fontWeight: 700, cursor: 'pointer' }}>
                            Access Dashboard
                        </button>
                    </form>
                </div>
            </div>
        );
    }

    if (loading) return <div className="loading-screen">Loading Admin Panel...</div>;

    return (
        <>
            <div style={{ padding: '1.5rem 3rem', borderBottom: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <h1 style={{ fontWeight: 800, fontSize: '1.2rem', margin: 0, letterSpacing: '-0.03em' }}>HAVEN <span style={{ color: 'var(--accent)' }}>AI</span></h1>
                <button 
                    onClick={() => { sessionStorage.removeItem('isAdminAuth'); setIsAdminAuthenticated(false); }}
                    style={{ background: 'none', border: '1px solid var(--border)', padding: '0.4rem 1rem', borderRadius: '8px', color: 'var(--text-3)', fontSize: '0.8rem', cursor: 'pointer' }}
                >
                    Logout
                </button>
            </div>
            <div className="page-hero">
                <div className="page-hero-inner">
                    <div className="page-hero-icon">⚙️</div>
                    <div>
                        <h1>Admin Command Center</h1>
                        <p>Monitor users, dealers, properties, and interactions across Haven.AI</p>
                    </div>
                </div>
            </div>

            <div className="page-content" style={{ maxWidth: '1200px' }}>
                {/* Stats Grid */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '1.5rem', marginBottom: '3rem' }}>
                    {[
                        { label: 'Total Users', value: stats.totalUsers, icon: '👤', color: 'var(--accent)' },
                        { label: 'Total Dealers', value: stats.totalDealers, icon: '💼', color: 'var(--green)' },
                        { label: 'Properties Listed', value: stats.totalProperties, icon: '🏠', color: 'var(--gold)' },
                        { label: 'Total Property Views', value: stats.totalViews, icon: '👁️', color: 'var(--accent-2)' },
                    ].map((s, i) => (
                        <div key={i} className="stat-item" style={{ textAlign: 'left', padding: '1.5rem', background: 'var(--surface)' }}>
                            <div style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>{s.icon}</div>
                            <div className="stat-num" style={{ fontSize: '2.4rem', color: s.color }}>{s.value}</div>
                            <div className="stat-desc" style={{ fontSize: '0.9rem', fontWeight: 600 }}>{s.label}</div>
                        </div>
                    ))}
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '2fr 1.2fr', gap: '2rem' }}>
                    {/* Activity Section */}
                    <div style={{ background: 'var(--surface)', borderRadius: 'var(--radius)', padding: '2rem', border: '1px solid var(--border)' }}>
                        <h2 style={{ marginBottom: '1.5rem', fontFamily: 'Syne, sans-serif' }}>Recent Chat Logs</h2>
                        {recentChats.length === 0 ? (
                            <p style={{ color: 'var(--text-3)' }}>No recent chat activity found.</p>
                        ) : (
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                                {recentChats.map(item => (
                                    <div key={item.id} style={{ padding: '1rem', background: 'var(--bg-2)', borderRadius: '10px', border: '1px solid var(--border)', position: 'relative' }}>
                                         <div style={{ position: 'absolute', top: '1rem', right: '1rem', fontSize: '0.6rem', fontWeight: 800, padding: '0.2rem 0.5rem', borderRadius: '100px', background: item.type === 'AI' ? 'rgba(59,130,246,0.1)' : 'rgba(16,185,129,0.1)', color: item.type === 'AI' ? 'var(--accent)' : 'var(--green)', border: '1px solid currentColor' }}>
                                             {item.type}
                                         </div>
                                         <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                                             <span style={{ fontWeight: 600, fontSize: "0.9rem" }}>{item.title}</span>
                                             <span style={{ fontSize: '0.75rem', color: 'var(--text-3)', marginRight: '4rem' }}>{new Date(item.time).toLocaleString()}</span>
                                         </div>
                                         <div style={{ fontSize: '0.75rem', color: 'var(--text-3)', fontStyle: 'italic', marginBottom: '0.4rem' }}>{item.subtitle}</div>
                                         <p style={{ fontSize: '0.85rem', color: 'var(--text-2)', margin: 0 }}>
                                             {item.message}
                                         </p>
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
                            <button className="btn-feature" style={{ width: '100%', justifyContent: 'center', borderColor: 'var(--red)', color: 'var(--red)' }} onClick={handleResetViews}>Reset View Counters</button>
                        </div>
                    </div>
                </div>

                {/* --- Modals --- */}
                {activeModal === 'users' && (
                    <div className="modal-overlay" onClick={() => setActiveModal(null)}>
                        <div className="modal-content" style={{ maxWidth: '800px', background: 'var(--surface)', padding: '2rem', borderRadius: '20px' }} onClick={e => e.stopPropagation()}>
                            <h2>User Management</h2>
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
                                                <button onClick={() => deleteUser(u.id)} style={{ background: 'none', border: 'none', color: 'var(--red)', cursor: 'pointer' }}>Delete</button>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                            <button className="btn-feature" style={{ marginTop: '2rem' }} onClick={() => setActiveModal(null)}>Close</button>
                        </div>
                    </div>
                )}

                {activeModal === 'properties' && (
                    <div className="modal-overlay" onClick={() => setActiveModal(null)}>
                        <div className="modal-content" style={{ maxWidth: '800px', background: 'var(--surface)', padding: '2rem', borderRadius: '20px' }} onClick={e => e.stopPropagation()}>
                            <h2>Unverified Properties</h2>
                            {unverifiedProps.length === 0 ? <p>All properties are verified!</p> : (
                                <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', marginTop: '1rem' }}>
                                    {unverifiedProps.map(p => (
                                        <div key={p.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '1rem', background: 'var(--bg-2)', borderRadius: '10px' }}>
                                            <div>
                                                <div style={{ fontWeight: 600 }}>{p.title}</div>
                                                <div style={{ fontSize: '0.8rem', color: 'var(--text-3)' }}>{p.location}</div>
                                            </div>
                                            <button className="btn-feature" onClick={() => verifyProperty(p.id)}>Approve & Verify</button>
                                        </div>
                                    ))}
                                </div>
                            )}
                            <button className="btn-feature" style={{ marginTop: '2rem' }} onClick={() => setActiveModal(null)}>Close</button>
                        </div>
                    </div>
                )}

                {activeModal === 'health' && (
                    <div className="modal-overlay" onClick={() => setActiveModal(null)}>
                        <div className="modal-content" style={{ textAlign: 'center', padding: '3rem', borderRadius: '20px' }} onClick={e => e.stopPropagation()}>
                            <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>🩺</div>
                            <h2>System Health</h2>
                            <div style={{ fontSize: '1.2rem', margin: '1.5rem 0', fontWeight: 600 }}>{healthStatus}</div>
                            <button className="btn-feature" onClick={() => setActiveModal(null)}>Dismiss</button>
                        </div>
                    </div>
                )}
            </div>
            <Footer />
        </>
    );
}
