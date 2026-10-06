import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { db } from '../firebase';
import { collection, getDocs } from 'firebase/firestore';

export default function RecommendationSidebar() {
    const navigate = useNavigate();
    const [properties, setProperties] = useState([]);
    const [aiFilters, setAiFilters] = useState(null);

    useEffect(() => {
        const handleAIUpdate = (e) => {
            setAiFilters(e.detail.filters);
            const sidebar = document.querySelector('.sidebar-recommendations');
            if (sidebar) sidebar.scrollTo({ top: 0, behavior: 'smooth' });
        };
        window.addEventListener('ai-recommendation-update', handleAIUpdate);
        
        const fetchProperties = async () => {
            try {
                const snap = await getDocs(collection(db, 'properties'));
                const list = [];
                snap.forEach(docSnap => {
                    const data = docSnap.data();
                    list.push({
                        id: docSnap.id,
                        title: data.title || 'Untitled Property',
                        type: (data.propertyType || data.category || 'house').toLowerCase(),
                        price: typeof data.price === 'number' ? data.price : parseFloat(data.price) || 0,
                        location: data.location || 'Location not specified',
                        area: data.area || 'N/A',
                        img: data.image || data.img || 'https://images.unsplash.com/photo-1568605114967-8130f3a36994?w=800&q=80',
                        mapUrl: data.mapUrl || '',
                        views: data.views || 0,
                    });
                });
                setProperties(list);
            } catch (error) {
                console.error("Error fetching sidebar properties:", error);
            }
        };

        fetchProperties();
        return () => window.removeEventListener('ai-recommendation-update', handleAIUpdate);
    }, []);

    const openProperty = (p) => {
        sessionStorage.setItem('hs_property', JSON.stringify(p));
        navigate('/property-detail');
    };

    return (
        <aside className="sidebar-recommendations" style={{ 
            width: '320px', 
            flexShrink: 0, 
            position: 'fixed', 
            top: '80px', 
            right: '0',
            bottom: '0',
            maxHeight: 'calc(100vh - 80px)', 
            overflowY: 'auto', 
            padding: '1.5rem', 
            borderLeft: '1px solid var(--border)', 
            background: 'var(--surface)', 
            boxShadow: '-10px 0 30px rgba(0,0,0,0.1)',
            zIndex: 999,
            transition: 'all 0.3s ease'
        }}>
            <h2 style={{ fontSize: '1.1rem', fontWeight: 800, marginBottom: '2rem', fontFamily: 'Syne, sans-serif', letterSpacing: '-0.02em', borderBottom: '2px solid var(--accent)', paddingBottom: '0.5rem', color: 'var(--text)' }}>AI INSIGHTS</h2>

            {aiFilters && (
                <div style={{ background: 'rgba(59,130,246,0.1)', border: '1px solid var(--accent)', padding: '1rem', borderRadius: '12px', marginBottom: '1.5rem' }}>
                    <div style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--accent-2)', textTransform: 'uppercase', marginBottom: '0.4rem' }}>✨ AI Refined</div>
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-2)' }}>
                        Showing {aiFilters.property_type || 'properties'} {aiFilters.location ? `in ${aiFilters.location}` : ''}
                    </div>
                    <button onClick={() => setAiFilters(null)} style={{ background: 'none', border: 'none', color: 'var(--accent)', fontSize: '0.72rem', fontWeight: 600, padding: 0, marginTop: '0.4rem', cursor: 'pointer', textDecoration: 'underline' }}>Clear AI Filters</button>
                </div>
            )}

            {/*  Geospatial Recommendations */}
            <div className="rec-section">
                <h4 style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '1rem', fontFamily: 'Syne, sans-serif' }}>📍 {aiFilters ? 'AI Location Picks' : 'Geospatial Picks'}</h4>
                <div className="rec-grid" style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                    {(aiFilters
                        ? properties.filter(p => {
                            const locMatch = aiFilters.location ? p.location.toLowerCase().includes(aiFilters.location.toLowerCase()) : true;
                            const typeMatch = aiFilters.property_type ? p.type.toLowerCase().includes(aiFilters.property_type.toLowerCase()) : true;
                            return locMatch && typeMatch;
                        })
                        : properties
                    ).slice(0, 3).map(p => (
                        <div key={`geo-${p.id}`} className="rec-card" onClick={() => openProperty(p)} style={{ background: 'var(--surface)', borderRadius: '12px', overflow: 'hidden', border: '1px solid var(--border)', cursor: 'pointer' }}>
                            <div className="rec-card-img" style={{ height: '120px', overflow: 'hidden' }}>
                                <img src={p.img} alt={p.title} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                            </div>
                            <div className="rec-card-body" style={{ padding: '0.8rem' }}>
                                <div className="rec-card-price" style={{ color: 'var(--accent-2)', fontWeight: 800, fontSize: '0.9rem' }}>RS {p.price.toLocaleString()}</div>
                                <div className="rec-card-title" style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{p.title}</div>
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '0.4rem' }}>
                                    <div className="rec-card-loc" style={{ fontSize: '0.7rem', color: 'var(--text-3)' }}>{p.location}</div>
                                    {p.mapUrl && (
                                        <button 
                                            onClick={(e) => { e.stopPropagation(); window.open(p.mapUrl, '_blank'); }}
                                            style={{ background: 'var(--bg-2)', border: '1px solid var(--border)', borderRadius: '6px', padding: '4px 8px', fontSize: '0.65rem', color: 'var(--accent)', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px' }}
                                        >
                                            🗺️ Map
                                        </button>
                                    )}
                                </div>
                            </div>
                        </div>
                    ))}
                </div>
            </div>

            {/*  Future Value Properties */}
            <div className="rec-section" style={{ marginTop: '2rem' }}>
                <h4 style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '1rem', fontFamily: 'Syne, sans-serif' }}>📈 Future Value</h4>
                <div className="rec-grid" style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                    {(aiFilters
                        ? properties.filter(p => {
                            const locMatch = aiFilters.location ? p.location.toLowerCase().includes(aiFilters.location.toLowerCase()) : true;
                            return locMatch && p.price < 50000000;
                        })
                        : properties.filter(p => p.price < 50000000)
                    ).slice(0, 2).map(p => (
                        <div key={`val-${p.id}`} className="rec-card" onClick={() => openProperty(p)} style={{ background: 'var(--surface)', borderRadius: '12px', overflow: 'hidden', border: '1px solid var(--border)', cursor: 'pointer' }}>
                             <div className="rec-card-img" style={{ height: '100px', overflow: 'hidden' }}>
                                <img src={p.img} alt={p.title} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                            </div>
                            <div className="rec-card-body" style={{ padding: '0.8rem' }}>
                                <div className="rec-card-price" style={{ color: 'var(--accent-2)', fontWeight: 800, fontSize: '0.9rem' }}>RS {p.price.toLocaleString()}</div>
                                <div className="rec-card-title" style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{p.title}</div>
                                <div className="rec-card-loc" style={{ fontSize: '0.7rem', color: 'var(--text-3)', marginTop: '0.2rem' }}>{p.location}</div>
                            </div>
                        </div>
                    ))}
                </div>
            </div>

            {/*  Trending Properties */}
            <div className="rec-section" style={{ marginTop: '2rem' }}>
                <h4 style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '1rem', fontFamily: 'Syne, sans-serif' }}>🔥 Trending Now</h4>
                <div className="rec-grid" style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                    {[...properties].sort((a, b) => (b.views || 0) - (a.views || 0)).slice(0, 2).map(p => (
                        <div key={`trend-${p.id}`} className="rec-card" onClick={() => openProperty(p)} style={{ background: 'var(--surface)', borderRadius: '12px', overflow: 'hidden', border: '1px solid var(--border)', cursor: 'pointer' }}>
                            <div className="rec-card-body" style={{ padding: '0.8rem' }}>
                                <div className="rec-card-price" style={{ color: 'var(--gold)', fontWeight: 800, fontSize: '0.9rem' }}>RS {p.price.toLocaleString()}</div>
                                <div className="rec-card-title" style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text)' }}>{p.title}</div>
                                <div className="rec-card-loc" style={{ fontSize: '0.7rem', color: 'var(--text-3)', marginTop: '0.2rem' }}>{p.location}</div>
                            </div>
                        </div>
                    ))}
                </div>
            </div>
        </aside>
    );
}
