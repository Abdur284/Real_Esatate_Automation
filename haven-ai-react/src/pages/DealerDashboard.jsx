import { useState, useEffect, useCallback } from 'react';
import { collection, addDoc, query, where, getDocs, serverTimestamp, deleteDoc, doc, onSnapshot } from 'firebase/firestore';
import { useNavigate } from 'react-router-dom';
import { db } from '../firebase';
import { useAuth } from '../auth/AuthContext';
import { useToast } from '../components/Toast';

export default function DealerDashboard() {
    const navigate = useNavigate();
    const toast = useToast();
    const { user, profile } = useAuth();
    const [properties, setProperties] = useState([]);
    const [allProperties, setAllProperties] = useState([]);
    const [inquiries, setInquiries] = useState([]);
    const [loading, setLoading] = useState(true);
    const [showUpload, setShowUpload] = useState(false);
    const [activeTab, setActiveTab] = useState('my'); // 'my' or 'all'

    // Form State
    const [formData, setFormData] = useState({
        title: '',
        price: '',
        location: '',
        type: 'For Sale',
        beds: '',
        baths: '',
        area: '',
        description: '',
        mapUrl: '',
        mapImage: '',
        image: 'https://images.unsplash.com/photo-1568605114967-8130f3a36994?w=800&q=80'
    });

    const fetchAllProperties = useCallback(async () => {
        try {
            const snap = await getDocs(collection(db, 'properties'));
            const list = [];
            snap.forEach(docSnap => {
                const data = docSnap.data();
                // Normalizing just like Properties.jsx
                const status = data.type === 'For Sale' ? 'for-sale' : data.type === 'For Rent' ? 'for-rent' : (data.status || 'for-sale');
                const price = typeof data.price === 'number' ? data.price : parseFloat(data.price) || 0;
                list.push({
                    id: docSnap.id,
                    ...data,
                    status: status,
                    priceVal: price,
                    priceLabel: data.priceLabel || `RS ${price.toLocaleString()}`,
                    img: data.image || data.img || 'https://images.unsplash.com/photo-1568605114967-8130f3a36994?w=800&q=80',
                    location: data.location || data.loc || 'N/A'
                });
            });
            setAllProperties(list);
        } catch (e) {
            console.error("Global fetch failed", e);
        }
    }, []);

    const fetchMyProperties = useCallback(async () => {
        setLoading(true);
        try {
            const q = query(collection(db, 'properties'), where('dealerId', '==', user.uid));
            const snap = await getDocs(q);
            const list = [];
            snap.forEach(d => list.push({ id: d.id, ...d.data() }));
            setProperties(list);
        } catch (error) {
            console.error("Error fetching properties:", error);
        } finally {
            setLoading(false);
        }
    }, [user]);

    useEffect(() => {
        if (user) {
            fetchMyProperties();
            fetchAllProperties();

            // Listen to chats/inquiries for this dealer
            const chatQuery = query(collection(db, 'chats'), where('dealerId', '==', user.uid));
            const unsub = onSnapshot(chatQuery, (snap) => {
                const list = [];
                snap.forEach(d => list.push({ id: d.id, ...d.data() }));
                setInquiries(list);
            });
            return () => unsub();
        }
    }, [user, fetchMyProperties, fetchAllProperties]);

    const handleUpload = async (e) => {
        e.preventDefault();
        if (!user) return;

        try {
            await addDoc(collection(db, 'properties'), {
                ...formData,
                price: parseFloat(formData.price),
                beds: parseInt(formData.beds),
                baths: parseInt(formData.baths),
                dealerId: user.uid,
                dealerName: profile?.name || user.displayName || 'Dealer',
                verified: false,
                views: 0,
                createdAt: serverTimestamp()
            });
            setShowUpload(false);
            setFormData({
                title: '', price: '', location: '', type: 'For Sale',
                beds: '', baths: '', area: '', description: '', mapUrl: '', mapImage: '',
                image: 'https://images.unsplash.com/photo-1568605114967-8130f3a36994?w=800&q=80'
            });
            fetchMyProperties();
            toast.success('Your listing is published.');
        } catch {
            toast.error('The listing could not be published. Please check the form and try again.');
        }
    };

    const handleDelete = async (id) => {
        if (window.confirm("Are you sure you want to delete this listing?")) {
            try {
                await deleteDoc(doc(db, 'properties', id));
                fetchMyProperties();
                toast.success('Listing deleted.');
            } catch {
                toast.error('The listing could not be deleted.');
            }
        }
    };

    return (
        <>
            <div className="page-hero">
                <div className="page-hero-inner">
                    <div className="page-hero-icon">🏢</div>
                    <div>
                        <h1>Dealer Dashboard</h1>
                        <p>Manage your listings and connect with potential buyers</p>
                    </div>
                </div>
            </div>

            <div className="page-content" style={{ maxWidth: '1200px' }}>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 340px', gap: '2.5rem' }}>

                    {/* Main Content: Properties */}
                    <div>
                        <div style={{ display: 'flex', gap: '1rem', marginBottom: '1.5rem' }}>
                            <button 
                                onClick={() => setActiveTab('my')}
                                style={{ padding: '0.6rem 1.5rem', borderRadius: '10px', background: activeTab === 'my' ? 'var(--accent)' : 'var(--surface)', border: '1px solid var(--border)', color: activeTab === 'my' ? '#fff' : 'var(--text-3)', fontWeight: 700, cursor: 'pointer', transition: 'all 0.2s' }}
                            >
                                👤 My Listings
                            </button>
                            <button 
                                onClick={() => setActiveTab('all')}
                                style={{ padding: '0.6rem 1.5rem', borderRadius: '10px', background: activeTab === 'all' ? 'var(--accent)' : 'var(--surface)', border: '1px solid var(--border)', color: activeTab === 'all' ? '#fff' : 'var(--text-3)', fontWeight: 700, cursor: 'pointer', transition: 'all 0.2s' }}
                            >
                                🌍 Browse All ({allProperties.length})
                            </button>
                        </div>

                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
                            <h2 style={{ fontFamily: 'Syne, sans-serif' }}>
                                {activeTab === 'my' ? 'My Property Listings' : 'Global Property Database'}
                            </h2>
                            <button className="btn-cta" onClick={() => setShowUpload(!showUpload)}>
                                {showUpload ? 'Cancel' : '+ Post New Property'}
                            </button>
                        </div>

                        {showUpload && (
                            <div style={{ background: 'var(--surface)', padding: '2.5rem', borderRadius: 'var(--radius)', border: '1px solid var(--border)', marginBottom: '3rem' }}>
                                <h2 style={{ marginBottom: '2rem', color: 'var(--accent)', fontFamily: 'Syne, sans-serif' }}>Upload New Property</h2>
                                
                                <form onSubmit={handleUpload} style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem' }}>
                                    {/* SECTION 1: BASIC SPECS */}
                                    <div style={{ gridColumn: 'span 2' }}>
                                        <h3 style={{ fontSize: '1rem', marginBottom: '1rem', borderBottom: '1px solid var(--border)', paddingBottom: '0.5rem' }}>1. Basic Information</h3>
                                    </div>
                                    <input className="modal-input" placeholder="Property Title" value={formData.title} onChange={e => setFormData({ ...formData, title: e.target.value })} required />
                                    <input className="modal-input" type="number" placeholder="Price (RS)" value={formData.price} onChange={e => setFormData({ ...formData, price: e.target.value })} required />
                                    <input className="modal-input" placeholder="City / Area" value={formData.location} onChange={e => setFormData({ ...formData, location: e.target.value })} required />
                                    <select className="modal-input" value={formData.type} onChange={e => setFormData({ ...formData, type: e.target.value })}>
                                        <option>For Sale</option>
                                        <option>For Rent</option>
                                    </select>
                                    <input className="modal-input" type="number" placeholder="Bedrooms" value={formData.beds} onChange={e => setFormData({ ...formData, beds: e.target.value })} required />
                                    <input className="modal-input" type="number" placeholder="Bathrooms" value={formData.baths} onChange={e => setFormData({ ...formData, baths: e.target.value })} required />
                                    <input className="modal-input" placeholder="Area Size (e.g. 5 Marla / 1 Kanal)" value={formData.area} onChange={e => setFormData({ ...formData, area: e.target.value })} required style={{ gridColumn: 'span 2' }} />

                                    {/* SECTION 2: THE DEDICATED MAP SECTION (AS REQUESTED) */}
                                    <div style={{ gridColumn: 'span 2', marginTop: '1rem', padding: '2rem', background: 'rgba(59, 130, 246, 0.03)', borderRadius: '16px', border: '2px dashed var(--accent)', position: 'relative' }}>
                                        <div style={{ position: 'absolute', top: '-12px', left: '20px', background: 'var(--accent)', color: '#fff', padding: '4px 12px', borderRadius: '100px', fontSize: '0.75rem', fontWeight: 800 }}>DEDICATED LOCATION SECTION</div>
                                        <h3 style={{ fontSize: '1.1rem', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '10px' }}>📍 Google Maps Location URL</h3>
                                        <p style={{ fontSize: '0.8rem', color: 'var(--text-3)', marginBottom: '1.25rem' }}>Paste the shareable link from Google Maps to enable live navigation for buyers.</p>
                                        
                                        <input 
                                            className="modal-input" 
                                            placeholder="https://goo.gl/maps/..." 
                                            value={formData.mapUrl} 
                                            onChange={e => setFormData({ ...formData, mapUrl: e.target.value })} 
                                            required
                                            style={{ width: '100%', border: '1px solid var(--accent)', background: 'var(--surface)' }}
                                        />
                                        
                                        {formData.mapUrl && (
                                            <div style={{ marginTop: '1rem', color: 'var(--green)', fontSize: '0.8rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '6px' }}>
                                                ✅ Location Link Successfully Added
                                            </div>
                                        )}
                                    </div>

                                    {/* SECTION 3: MEDIA & DESC */}
                                    <div style={{ gridColumn: 'span 2', marginTop: '1rem' }}>
                                        <h3 style={{ fontSize: '1rem', marginBottom: '1rem', borderBottom: '1px solid var(--border)', paddingBottom: '0.5rem' }}>2. Media & Description</h3>
                                    </div>
                                    <input className="modal-input" placeholder="Main Property Image URL" value={formData.image} onChange={e => setFormData({ ...formData, image: e.target.value })} required style={{ gridColumn: 'span 2' }} />
                                    <textarea className="modal-input" style={{ gridColumn: 'span 2', minHeight: '120px' }} placeholder="Provide a detailed description of the property..." value={formData.description} onChange={e => setFormData({ ...formData, description: e.target.value })} required />

                                    <button type="submit" className="modal-submit" style={{ gridColumn: 'span 2', marginTop: '1.5rem', padding: '1.25rem', fontSize: '1rem' }}>Publish Property Listing</button>
                                </form>
                            </div>
                        )}

                        {loading ? (
                            <p>Loading listings...</p>
                        ) : (activeTab === 'my' ? properties : allProperties).length === 0 ? (
                            <div style={{ textAlign: 'center', padding: '4rem', background: 'var(--bg-2)', borderRadius: 'var(--radius)' }}>
                                <p style={{ color: 'var(--text-3)' }}>{activeTab === 'my' ? "You haven't uploaded any properties yet." : "No properties found in the database."}</p>
                            </div>
                        ) : (
                            <div className="prop-grid" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))' }}>
                                {(activeTab === 'my' ? properties : allProperties).map(prop => (
                                    <div key={prop.id} className="prop-card" onClick={() => activeTab === 'all' && navigate(`/property/${prop.id}`)} style={{ cursor: activeTab === 'all' ? 'pointer' : 'default' }}>
                                        <div className="prop-card-img">
                                            <img src={prop.image || prop.img} alt={prop.title} />
                                            <div className={`prop-badge ${prop.status === 'for-sale' || prop.type === 'For Sale' ? 'for-sale' : 'for-rent'}`}>
                                                {prop.status === 'for-rent' || prop.type === 'For Rent' ? 'For Rent' : 'For Sale'}
                                            </div>
                                        </div>
                                        <div className="prop-card-body">
                                            <div className="prop-price" style={{ color: 'var(--accent-2)', fontWeight: 800 }}>{prop.priceLabel || `RS ${prop.price.toLocaleString()}`}</div>
                                            <div className="prop-title" style={{ fontWeight: 700 }}>{prop.title}</div>
                                            <div className="prop-location">📍 {prop.location || prop.loc}</div>
                                            
                                            {activeTab === 'my' ? (
                                                <div style={{ display: 'flex', gap: '1rem', marginTop: '1rem', borderTop: '1px solid var(--border)', paddingTop: '0.75rem' }}>
                                                    <div style={{ fontSize: '0.8rem', color: 'var(--text-2)' }}>👁️ {prop.views || 0} Views</div>
                                                    <button
                                                        onClick={(e) => { e.stopPropagation(); handleDelete(prop.id); }}
                                                        style={{ marginLeft: 'auto', background: 'none', border: 'none', color: 'var(--red)', fontSize: '0.8rem', cursor: 'pointer', fontWeight: 600 }}
                                                    >
                                                        Delete
                                                    </button>
                                                </div>
                                            ) : (
                                                <div style={{ marginTop: '1rem', borderTop: '1px solid var(--border)', paddingTop: '0.75rem', fontSize: '0.75rem', color: 'var(--text-3)' }}>
                                                    Listed by: <span style={{ color: 'var(--text-2)', fontWeight: 600 }}>{prop.dealerName || 'Verified Dealer'}</span>
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>

                    {/* Sidebar: Inquiries */}
                    <div>
                        <h3 style={{ fontFamily: 'Syne, sans-serif', marginBottom: '1.5rem' }}>Recent Inquiries</h3>
                        {inquiries.length === 0 ? (
                            <div style={{ padding: '2rem', background: 'var(--bg-2)', borderRadius: 'var(--radius)', textAlign: 'center' }}>
                                <p style={{ fontSize: '0.85rem', color: 'var(--text-3)' }}>No inquiries yet.</p>
                            </div>
                        ) : (
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                                {inquiries.map(chat => (
                                    <div
                                        key={chat.id}
                                        onClick={() => navigate(`/chat/${chat.id}`)}
                                        style={{
                                            padding: '1.25rem', background: 'var(--surface)', borderRadius: '12px', border: '1px solid var(--border)', cursor: 'pointer', transition: 'all 0.2s'
                                        }}
                                        onMouseEnter={e => e.currentTarget.style.borderColor = 'var(--accent)'}
                                        onMouseLeave={e => e.currentTarget.style.borderColor = 'var(--border)'}
                                    >
                                        <div style={{ fontWeight: 700, fontSize: '0.9rem', marginBottom: '0.2rem' }}>{chat.buyerName}</div>
                                        <div style={{ fontSize: '0.75rem', color: 'var(--accent)', marginBottom: '0.5rem' }}>Re: {chat.propertyTitle}</div>
                                        <div style={{ fontSize: '0.8rem', color: 'var(--text-3)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                            {chat.lastMessage || 'Starting a conversation...'}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>

                </div>
            </div>
        </>
    );
}
