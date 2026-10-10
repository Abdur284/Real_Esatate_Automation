import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { db } from '../firebase';
import { useAuth } from '../auth/AuthContext';
import { collection, getDocs } from 'firebase/firestore';
import api from '../api';

const PLACEHOLDER_IMG = 'https://images.unsplash.com/photo-1568605114967-8130f3a36994?w=800&q=80';
const isZameen = (p) => p.source === 'zameen';

export default function Properties() {
    const navigate = useNavigate();
    const { user } = useAuth();
    const [properties, setProperties] = useState([]);
    const [loading, setLoading] = useState(true);
    const [searchQ, setSearchQ] = useState('');
    const [filterType, setFilterType] = useState('');
    const [filterStatus, setFilterStatus] = useState('');
    const [filterBeds, setFilterBeds] = useState('');
    const [activeTab, setActiveTab] = useState('all');
    const [zameenNote, setZameenNote] = useState('');
    const [zameenListings, setZameenListings] = useState([]);
    useEffect(() => {
        const fetchProperties = async () => {
            setLoading(true);
            try {
                const snap = await getDocs(collection(db, 'properties'));
                const list = [];
                snap.forEach(docSnap => {
                    const data = docSnap.data();

                    // Normalize Firebase fields to match what the UI expects
                    const status = data.type === 'For Sale' ? 'for-sale'
                        : data.type === 'For Rent' ? 'for-rent'
                            : (data.status || 'for-sale');

                    const propertyType = (data.propertyType || data.category || 'house').toLowerCase();

                    const price = typeof data.price === 'number' ? data.price : parseFloat(data.price) || 0;

                    list.push({
                        id: docSnap.id,
                        title: data.title || 'Untitled Property',
                        type: propertyType,
                        status: status,
                        price: price,
                        priceLabel: data.priceLabel || (status === 'for-rent'
                            ? `RS ${price.toLocaleString()}/mo`
                            : `RS ${price.toLocaleString()}`),
                        location: data.location || 'Location not specified',
                        beds: parseInt(data.beds) || 0,
                        baths: parseInt(data.baths) || 0,
                        area: data.area || 'N/A',
                        description: data.description || '',
                        features: data.features || [],
                        img: data.image || data.img || 'https://images.unsplash.com/photo-1568605114967-8130f3a36994?w=800&q=80',
                        imgs: data.imgs || [data.image || data.img || 'https://images.unsplash.com/photo-1568605114967-8130f3a36994?w=800&q=80'],
                        seller: data.seller || {
                            name: data.dealerName || 'Property Owner',
                            tag: 'Verified Seller',
                            avatar: '🏡'
                        },
                        dealerId: data.dealerId || '',
                        dealerName: data.dealerName || '',
                        views: data.views || 0,
                        mapUrl: data.mapUrl || '',
                        createdAt: data.createdAt || null,
                    });
                });
                setProperties(list);
            } catch (error) {
                console.error("Error fetching properties:", error);
            } finally {
                setLoading(false);
            }
        };
        fetchProperties();

        // Zameen.com listings come through our backend and are added after
        // our own; if Zameen is off or down the page simply shows ours.
        let alive = true;
        api.properties.external()
            .then(res => {
                if (!alive) return;
                if (res.error) setZameenNote(res.error);
                const extra = (res.listings || []).map(z => ({
                    ...z,
                    img: z.img || PLACEHOLDER_IMG,
                    imgs: [z.img || PLACEHOLDER_IMG],
                    seller: { name: z.agency || 'Zameen.com', tag: 'Zameen.com listing', avatar: '🏢' },
                }));
                setZameenListings(extra);
            })
            .catch(() => { /* backend unreachable: our own listings still show */ });
        return () => { alive = false; };
    }, []);

    const allListings = [...properties, ...zameenListings];
    const filtered = allListings.filter(p => {
        if (searchQ && !p.title.toLowerCase().includes(searchQ.toLowerCase()) && !p.location.toLowerCase().includes(searchQ.toLowerCase())) return false;

        const pType = (p.type || '').toLowerCase();
        const fType = (filterType || '').toLowerCase();
        if (fType && pType !== fType) return false;

        const pStatus = (p.status || p.type || '').toLowerCase().replace(/\s+/g, '-');
        const fStatus = (filterStatus || (activeTab !== 'all' ? activeTab : '') || '').toLowerCase().replace(/\s+/g, '-');
        
        if (fStatus && !pStatus.includes(fStatus)) return false;

        if (filterBeds) {
            const pBeds = parseInt(p.beds);
            if (filterBeds === '4' && pBeds < 4) return false;
            if (filterBeds !== '4' && pBeds !== parseInt(filterBeds)) return false;
        }
        return true;
    });

    const openZameen = (p) => { if (p.url) window.open(p.url, '_blank', 'noopener,noreferrer'); };
    const openProperty = (p) => (isZameen(p) ? openZameen(p) : navigate(`/property/${p.id}`));

    const contactAndRedirect = (e, p) => {
        e.stopPropagation();
        const target = `/chat?propertyId=${encodeURIComponent(p.id)}`;
        navigate(user ? target : `/signup?tab=login&next=${encodeURIComponent(target)}`);
    };

    return (
        <>
            <section className="page-hero">
                <div className="page-hero-inner">
                    <div className="page-hero-icon">🏡</div>
                    <div style={{ flex: 1 }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                            <div>
                                <h1>Property Listings</h1>
                                <p>Browse verified properties, contact sellers directly, and list your own — all in one place.</p>
                            </div>
                            <div style={{ background: 'rgba(255,255,255,0.1)', padding: '1rem 1.5rem', borderRadius: '16px', backdropFilter: 'blur(10px)', textAlign: 'center', border: '1px solid rgba(255,255,255,0.2)' }}>
                                <div style={{ fontSize: '1.5rem', fontWeight: 800, color: '#fff' }}>{allListings.length}</div>
                                <div style={{ fontSize: '0.65rem', textTransform: 'uppercase', letterSpacing: '0.1em', marginTop: '0.2rem', opacity: 0.8 }}>Listings</div>
                            </div>
                        </div>
                    </div>
                </div>
            </section>

            <div className="page-content" style={{ maxWidth: '1440px', padding: '0 2rem' }}>
                {/* Search Bar */}
                <div className="prop-search-bar">
                    <input className="prop-search-input" type="text" placeholder="🔍 Search by location, title, or keyword..." value={searchQ} onChange={e => setSearchQ(e.target.value)} />
                    <select className="prop-filter-select" value={filterType} onChange={e => setFilterType(e.target.value)}>
                        <option value="">All Types</option>
                        <option value="house">House</option>
                        <option value="apartment">Apartment</option>
                        <option value="villa">Villa</option>
                        <option value="studio">Studio</option>
                        <option value="townhouse">Townhouse</option>
                    </select>
                    <select className="prop-filter-select" value={filterStatus} onChange={e => setFilterStatus(e.target.value)}>
                        <option value="">For Sale & Rent</option>
                        <option value="for-sale">For Sale</option>
                        <option value="for-rent">For Rent</option>
                    </select>
                    <select className="prop-filter-select" value={filterBeds} onChange={e => setFilterBeds(e.target.value)}>
                        <option value="">Any Beds</option>
                        <option value="1">1 Bed</option>
                        <option value="2">2 Beds</option>
                        <option value="3">3 Beds</option>
                        <option value="4">4+ Beds</option>
                    </select>
                    <button className="btn-search">Search</button>
                </div>

                <div className="properties-layout">
                    {/* Main Content Area */}
                    <div className="main-prop-content">
                        {/* Tabs */}
                        <div className="prop-tabs">
                            {['all', 'for-sale', 'for-rent'].map(tab => (
                                <button key={tab} className={`prop-tab${activeTab === tab ? ' active' : ''}`} onClick={() => { setActiveTab(tab); setFilterStatus(tab === 'all' ? '' : tab); }}>
                                    {tab === 'all' ? 'All Properties' : tab === 'for-sale' ? 'For Sale' : 'For Rent'}
                                </button>
                            ))}
                        </div>

                        {zameenNote && (
                            <p role="status" style={{ fontSize: '0.8rem', color: 'var(--text-3)', margin: '0 0 1rem' }}>{zameenNote} Showing Haven.AI listings only.</p>
                        )}

                        {/* Loading State */}
                        {loading ? (
                            <div style={{ textAlign: 'center', padding: '4rem 0', color: 'var(--text-3)' }}>
                                <div style={{ fontSize: '2.5rem', marginBottom: '1rem', animation: 'pulse 1.5s ease-in-out infinite' }}>🏠</div>
                                <p style={{ fontFamily: 'Syne, sans-serif', fontSize: '1.1rem' }}>Loading properties...</p>
                            </div>
                        ) : filtered.length === 0 ? (
                            <div style={{ textAlign: 'center', padding: '6rem 0', color: 'var(--text-3)' }}>
                                <div style={{ fontSize: '4rem', marginBottom: '1.5rem', opacity: 0.5 }}>🔍</div>
                                <h3 style={{ color: 'var(--text)', marginBottom: '0.75rem', fontFamily: 'Syne, sans-serif', fontSize: '1.5rem' }}>No properties found</h3>
                                <p style={{ marginBottom: '2rem' }}>We couldn't find anything matching your current filters.</p>
                                <button 
                                    onClick={() => { setSearchQ(''); setFilterType(''); setFilterStatus(''); setActiveTab('all'); }}
                                    style={{ padding: '0.8rem 2rem', background: 'var(--accent)', color: '#fff', border: 'none', borderRadius: '12px', fontWeight: 700, cursor: 'pointer', boxShadow: '0 10px 25px rgba(59,130,246,0.2)' }}
                                >
                                    🔄 Clear All Filters & Show All
                                </button>
                            </div>
                        ) : (
                            <div className="prop-grid">
                                {filtered.map(p => (
                                <div key={p.id} className="prop-card" onClick={() => openProperty(p)} style={{ background: 'var(--surface)', borderRadius: '16px', overflow: 'hidden', border: '1px solid var(--border)', transition: 'transform 0.3s ease, box-shadow 0.3s ease', cursor: 'pointer', display: 'flex', flexDirection: 'column' }} onMouseEnter={e => { e.currentTarget.style.transform = 'translateY(-5px)'; e.currentTarget.style.boxShadow = '0 12px 40px rgba(0,0,0,0.12)'; }} onMouseLeave={e => { e.currentTarget.style.transform = 'translateY(0)'; e.currentTarget.style.boxShadow = 'none'; }}>
                                    <div className="prop-card-img" style={{ height: '220px', position: 'relative', overflow: 'hidden' }}>
                                        <img src={p.img} alt={p.title} loading="lazy" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                                        <span className={`prop-badge ${p.status}`} style={{ position: 'absolute', top: '1rem', left: '1rem', padding: '0.4rem 0.8rem', borderRadius: '100px', fontSize: '0.7rem', fontWeight: 700, textTransform: 'uppercase', background: p.status === 'for-sale' ? 'var(--accent)' : 'var(--green)', color: '#fff', boxShadow: '0 4px 12px rgba(0,0,0,0.2)' }}>
                                            {p.status === 'for-sale' ? 'For Sale' : 'For Rent'}
                                        </span>
                                        {isZameen(p) && (
                                            <span style={{ position: 'absolute', top: '1rem', right: '1rem', padding: '0.4rem 0.8rem', borderRadius: '100px', fontSize: '0.7rem', fontWeight: 800, background: '#fff', color: '#0b7d3e', boxShadow: '0 4px 12px rgba(0,0,0,0.2)' }}>
                                                Zameen.com
                                            </span>
                                        )}
                                    </div>
                                    <div className="prop-card-body" style={{ padding: '1.5rem', flex: 1, display: 'flex', flexDirection: 'column' }}>
                                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
                                            <div className="prop-price" style={{ color: 'var(--accent-2)', fontWeight: 800, fontSize: '1.25rem', fontFamily: 'Syne, sans-serif' }}>RS {(p.price || 0).toLocaleString()}</div>
                                            {p.mapUrl && (
                                                <button 
                                                    className="btn-map-link"
                                                    onClick={(e) => { e.stopPropagation(); window.open(p.mapUrl, '_blank'); }}
                                                    style={{ background: 'var(--bg-2)', border: '1px solid var(--border)', borderRadius: '8px', padding: '6px 12px', fontSize: '0.72rem', color: 'var(--accent)', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 700 }}
                                                >
                                                    🗺️ Map
                                                </button>
                                            )}
                                        </div>
                                        <div className="prop-title" style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--text)', marginBottom: '0.5rem', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{p.title}</div>
                                        <div className="prop-location" style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: 'var(--text-3)', fontSize: '0.85rem', marginBottom: '1.25rem' }}>
                                            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0118 0z" /><circle cx="12" cy="10" r="3" /></svg>
                                            {p.location}
                                        </div>
                                        
                                        <div className="prop-specs" style={{ display: 'flex', gap: '1rem', padding: '1rem 0', borderTop: '1px solid var(--border)', marginTop: 'auto' }}>
                                            <div style={{ fontSize: '0.8rem', color: 'var(--text-2)', display: 'flex', alignItems: 'center', gap: '4px' }}>🛏 {p.beds}</div>
                                            <div style={{ fontSize: '0.8rem', color: 'var(--text-2)', display: 'flex', alignItems: 'center', gap: '4px' }}>🚿 {p.baths}</div>
                                            <div style={{ fontSize: '0.8rem', color: 'var(--text-2)', display: 'flex', alignItems: 'center', gap: '4px' }}>📐 {p.area}</div>
                                        </div>
                                        
                                        {isZameen(p) ? (
                                            <button
                                                disabled={!p.url}
                                                title={p.url ? 'Opens the listing on Zameen.com' : 'Sample listing: no Zameen.com page'}
                                                style={{ marginTop: '1rem', width: '100%', padding: '0.8rem', background: '#0b7d3e', border: 'none', borderRadius: '12px', color: '#fff', fontFamily: 'Inter, sans-serif', fontSize: '0.85rem', fontWeight: 700, cursor: p.url ? 'pointer' : 'not-allowed', opacity: p.url ? 1 : 0.6, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem' }}
                                                onClick={e => { e.stopPropagation(); openZameen(p); }}
                                            >
                                                View on Zameen.com ↗
                                            </button>
                                        ) : (
                                        <button 
                                            style={{ marginTop: '1rem', width: '100%', padding: '0.8rem', background: 'var(--accent)', border: 'none', borderRadius: '12px', color: '#fff', fontFamily: 'Inter, sans-serif', fontSize: '0.85rem', fontWeight: 700, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem', boxShadow: '0 4px 15px rgba(59,130,246,0.2)' }} 
                                            onClick={e => contactAndRedirect(e, p)}
                                        >
                                            Contact Dealer
                                        </button>
                                        )}
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