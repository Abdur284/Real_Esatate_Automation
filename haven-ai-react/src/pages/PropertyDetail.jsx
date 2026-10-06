import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { db, auth } from '../firebase';
import { doc, getDoc, updateDoc, increment } from 'firebase/firestore';
import Navbar from '../components/Navbar';
import Footer from '../components/Footer';

export default function PropertyDetail() {
    const navigate = useNavigate();
    const { id } = useParams();
    const [property, setProperty] = useState(null);
    const [activeImg, setActiveImg] = useState(0);
    const [loading, setLoading] = useState(true);
    const [successModal, setSuccessModal] = useState(false);
    const [message, setMessage] = useState('');

    useEffect(() => {
        const fetchAndTrack = async () => {
            let pData = null;

            if (id) {
                // Fetch from Firestore directly if ID in URL
                if (id.startsWith('mock-')) {
                    // Handle Sample Data
                    pData = {
                        id: id,
                        title: id === 'mock-p1' ? "Luxury Villa in Gulberg" : "Modern Apartment in DHA",
                        price: id === 'mock-p1' ? 45000000 : 15000000,
                        location: id === 'mock-p1' ? "Gulberg, Lahore" : "DHA Phase 6, Lahore",
                        area: "10 Marla",
                        img: "https://images.unsplash.com/photo-1512917774080-9991f1c4c750?auto=format&fit=crop&w=800&q=80"
                    };
                } else {
                    try {
                        const docRef = doc(db, 'properties', id);
                        const docSnap = await getDoc(docRef);
                        if (docSnap.exists()) {
                            pData = { id: docSnap.id, ...docSnap.data() };
                        }
                    } catch (e) {
                        console.error("Error fetching property:", e);
                    }
                }
            } else {
                // Fallback to sessionStorage
                const raw = sessionStorage.getItem('hs_property');
                if (raw) pData = JSON.parse(raw);
            }

            if (pData) {
                setProperty(pData);
                setLoading(false);

                // Increment Views in Firestore
                if (pData.id) {
                    try {
                        const propRef = doc(db, 'properties', String(pData.id));
                        await updateDoc(propRef, {
                            views: increment(1)
                        });
                    } catch (e) {
                        console.error("View tracking failed", e);
                    }
                }
            } else {
                navigate('/properties');
            }
        };
        fetchAndTrack();
    }, [id, navigate]);

    const handleContact = () => {
        const user = auth.currentUser;
        if (!user) {
            navigate('/signup?tab=signup');
            return;
        }
        navigate(`/chat?dealerId=${property.dealerId}&propertyId=${property.id}&propertyTitle=${encodeURIComponent(property.title)}`);
    };

    const sendMessage_ = () => {
        if (!message.trim()) return;
        setSuccessModal(true);
        setMessage('');
    };

    if (loading || !property) return (
        <>
            <Navbar />
            <div style={{ minHeight: '80vh', display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: '1rem' }}>
                <div style={{ fontSize: '2rem' }}>🏠</div>
                <p style={{ color: 'var(--text-2)' }}>Loading property...</p>
            </div>
            <Footer />
        </>
    );

    // Build the images array: use imgs if available, otherwise fall back to img
    const images = (property.imgs && property.imgs.length > 0)
        ? property.imgs
        : [property.img || 'https://images.unsplash.com/photo-1568605114967-8130f3a36994?w=800&q=80'];

    // Build a display price label
    const priceLabel = property.priceLabel || `RS ${(property.price || 0).toLocaleString()}`;

    return (
        <>
            <Navbar />
            <div style={{ maxWidth: 'var(--max)', margin: '1.5rem auto', padding: '0 2rem', paddingTop: 'calc(var(--nav-h) + 1rem)' }}>
                <a onClick={() => navigate('/properties')} style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem', color: 'var(--text-3)', fontSize: '0.875rem', cursor: 'pointer', fontWeight: 500, transition: 'color 0.2s' }}>
                    ← Back to Listings
                </a>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 380px', gap: '2rem', maxWidth: 'var(--max)', margin: '0 auto 4rem', padding: '0 2rem', alignItems: 'start' }}>
                {/* Main Column */}
                <div>
                    <div style={{ borderRadius: 'var(--radius)', overflow: 'hidden', background: 'var(--surface)', border: '1px solid var(--border)', aspectRatio: '16/10', position: 'relative' }}>
                        <img src={images[activeImg] || property.img} alt={property.title} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                        <div style={{ position: 'absolute', bottom: '1rem', right: '1rem', display: 'flex', gap: '0.5rem' }}>
                            {images.map((src, i) => (
                                <div key={i} onClick={() => setActiveImg(i)} style={{ width: '64px', height: '48px', borderRadius: '8px', overflow: 'hidden', border: `2px solid ${i === activeImg ? 'rgba(255,255,255,0.8)' : 'rgba(255,255,255,0.25)'}`, cursor: 'pointer' }}>
                                    <img src={src} alt={`View ${i + 1}`} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                                </div>
                            ))}
                        </div>
                    </div>

                    <div style={{ marginTop: '1.5rem' }}>
                        <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem' }}>
                            <span style={{ fontSize: '0.72rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', padding: '0.3rem 0.85rem', borderRadius: '100px', background: 'rgba(59,130,246,0.12)', color: 'var(--accent-2)', border: '1px solid rgba(59,130,246,0.2)' }}>
                                {property.type?.charAt(0).toUpperCase() + property.type?.slice(1)}
                            </span>
                            <span style={{ fontSize: '0.72rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', padding: '0.3rem 0.85rem', borderRadius: '100px', background: 'rgba(16,185,129,0.12)', color: 'var(--green)', border: '1px solid rgba(16,185,129,0.2)' }}>
                                {property.status === 'for-sale' ? 'For Sale' : 'For Rent'}
                            </span>
                        </div>
                        <div style={{ fontFamily: 'Syne, sans-serif', fontSize: '2.2rem', fontWeight: 800, color: 'var(--text)', marginBottom: '0.35rem' }}>{priceLabel}</div>
                        <div style={{ fontSize: '1.4rem', fontWeight: 600, color: 'var(--text)', marginBottom: '0.4rem' }}>{property.title}</div>
                        <div
                            onClick={() => property.mapUrl && window.open(property.mapUrl, '_blank')}
                            style={{
                                color: 'var(--text-3)',
                                fontSize: '0.9rem',
                                display: 'flex',
                                alignItems: 'center',
                                gap: '0.4rem',
                                marginBottom: '1.5rem',
                                cursor: property.mapUrl ? 'pointer' : 'default',
                                transition: 'color 0.2s'
                            }}
                            onMouseEnter={e => property.mapUrl && (e.currentTarget.style.color = 'var(--accent-2)')}
                            onMouseLeave={e => property.mapUrl && (e.currentTarget.style.color = 'var(--text-3)')}
                        >
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0118 0z" /><circle cx="12" cy="10" r="3" /></svg>
                            {property.location} {property.mapUrl && <span style={{ fontSize: '0.75rem', marginLeft: '0.5rem', textDecoration: 'underline' }}>(View on Google Maps)</span>}
                        </div>

                        <div style={{ marginBottom: '2.5rem', background: 'var(--bg-2)', padding: '1.5rem', borderRadius: '16px', border: '1px solid var(--border)' }}>
                            <h4 style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--text)', marginBottom: '1.25rem', display: 'flex', alignItems: 'center', gap: '8px' }}>
                                📍 Location & Map Area
                            </h4>
                            
                            {/* NEW: Display Map Image / Plot Plan if it exists */}
                            {property.mapImage && (
                                <div style={{ marginBottom: '1.5rem', borderRadius: '12px', overflow: 'hidden', border: '1px solid var(--border)', boxShadow: '0 8px 32px rgba(0,0,0,0.15)' }}>
                                    <div style={{ padding: '0.6rem 1rem', background: 'var(--accent)', color: '#fff', fontSize: '0.75rem', fontWeight: 800, textTransform: 'uppercase' }}>Society Map / Plot Plan</div>
                                    <img src={property.mapImage} alt="Plot Plan" style={{ width: '100%', maxHeight: '400px', objectFit: 'contain', background: '#fff' }} />
                                </div>
                            )}

                            <div
                                onClick={() => property.mapUrl ? window.open(property.mapUrl, '_blank') : alert("Please contact the dealer for the exact coordinates.")}
                                style={{
                                    width: '100%',
                                    height: '220px',
                                    borderRadius: '12px',
                                    overflow: 'hidden',
                                    position: 'relative',
                                    cursor: 'pointer',
                                    border: '1px solid var(--border)',
                                    boxShadow: '0 10px 30px rgba(0,0,0,0.1)',
                                    background: 'var(--bg-2)'
                                }}
                            >
                                <img
                                    src="https://images.unsplash.com/photo-1526778548025-fa2f459cd5ce?w=800&q=80"
                                    alt="Map Preview"
                                    style={{ width: '100%', height: '100%', objectFit: 'cover', filter: property.mapUrl ? 'brightness(0.6)' : 'brightness(0.3) grayscale(0.8)' }}
                                />
                                <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: '0.8rem', background: 'rgba(0,0,0,0.3)' }}>
                                    <div style={{ fontSize: '2.5rem', filter: 'drop-shadow(0 5px 15px rgba(0,0,0,0.5))' }}>📍</div>
                                    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.5rem' }}>
                                        <div style={{ background: property.mapUrl ? 'var(--accent)' : 'var(--text-3)', color: '#fff', padding: '0.75rem 2rem', borderRadius: '100px', fontSize: '0.9rem', fontWeight: 800, boxShadow: '0 10px 30px rgba(59, 130, 246, 0.4)', display: 'flex', alignItems: 'center', gap: '10px' }}>
                                            {property.mapUrl ? '🚀 Get Live Directions on Google Maps' : 'Location'}
                                        </div>
                                        {property.mapUrl && <p style={{ fontSize: '0.7rem', color: '#fff', fontWeight: 600 }}>Click to open in a new tab</p>}
                                    </div>
                                </div>
                            </div>
                        </div>

                        <div style={{ display: 'flex', background: 'var(--surface)', borderRadius: '12px', overflow: 'hidden', border: '1px solid var(--border)', marginBottom: '1.75rem' }}>
                            {[{ val: property.beds > 0 ? property.beds : 'Studio', label: 'Bedrooms' }, { val: property.baths, label: 'Bathrooms' }, { val: `${property.area || 'N/A'}`, label: 'Area' }, { val: property.type?.charAt(0).toUpperCase() + property.type?.slice(1), label: 'Type' }].map((s, i) => (
                                <div key={i} style={{ flex: 1, padding: '1rem', textAlign: 'center', borderRight: i < 3 ? '1px solid var(--border)' : 'none' }}>
                                    <div style={{ fontFamily: 'Syne, sans-serif', fontSize: '1.3rem', fontWeight: 800, color: 'var(--text)' }}>{s.val}</div>
                                    <div style={{ fontSize: '0.72rem', color: 'var(--text-3)', marginTop: '0.2rem', textTransform: 'uppercase', letterSpacing: '0.06em' }}>{s.label}</div>
                                </div>
                            ))}
                        </div>

                        <div style={{ marginBottom: '1.75rem' }}>
                            <h4 style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--text)', marginBottom: '0.75rem', paddingBottom: '0.5rem', borderBottom: '1px solid var(--border)' }}>About This Property</h4>
                            <p style={{ fontSize: '0.875rem', color: 'var(--text-2)', lineHeight: 1.75 }}>{property.description || 'No description available.'}</p>
                        </div>

                        {property.features && property.features.length > 0 && (
                            <div style={{ marginBottom: '1.75rem' }}>
                                <h4 style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--text)', marginBottom: '0.75rem', paddingBottom: '0.5rem', borderBottom: '1px solid var(--border)' }}>Features & Amenities</h4>
                                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem' }}>
                                    {property.features.map((f, i) => (
                                        <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.82rem', color: 'var(--text-2)' }}>
                                            <span style={{ color: 'var(--green)', fontWeight: 700 }}>✓</span> {f}
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}

                    </div>
                </div>

                {/* Sidebar */}
                <div style={{ position: 'sticky', top: 'calc(var(--nav-h) + 1.5rem)', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                    <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius)', padding: '1.75rem', boxShadow: '0 4px 40px rgba(0,0,0,0.3)' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.85rem', marginBottom: '1.25rem', paddingBottom: '1.25rem', borderBottom: '1px solid var(--border)' }}>
                            <div style={{ width: '48px', height: '48px', borderRadius: '50%', background: 'rgba(59,130,246,0.1)', border: '1px solid rgba(59,130,246,0.2)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '1.2rem' }}>
                                {property.seller?.avatar || '🏡'}
                            </div>
                            <div>
                                <div style={{ fontWeight: 600, fontSize: '0.95rem', color: 'var(--text)' }}>{property.seller?.name || property.dealerName || 'Property Owner'}</div>
                                <div style={{ fontSize: '0.75rem', color: 'var(--text-3)' }}>{property.seller?.tag || 'Verified Seller'}</div>
                                <div style={{ color: 'var(--green)', fontSize: '0.72rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '0.25rem', marginTop: '0.15rem' }}>✓ Verified Seller</div>
                            </div>
                        </div>
                        <h3 style={{ fontFamily: 'Syne, sans-serif', fontSize: '1.05rem', color: 'var(--text)', marginBottom: '0.35rem' }}>Interested in this property?</h3>
                        <p style={{ fontSize: '0.82rem', color: 'var(--text-2)', marginBottom: '1.25rem' }}>Contact the seller directly to ask questions or arrange a viewing.</p>
                        <div style={{ background: 'rgba(59,130,246,0.08)', border: '1px solid rgba(59,130,246,0.2)', borderRadius: '10px', padding: '1.1rem', textAlign: 'center', marginBottom: '0.75rem' }}>
                            <p style={{ fontSize: '0.82rem', color: 'var(--text-2)', marginBottom: '0.6rem', lineHeight: 1.5 }}>
                                {auth.currentUser ? 'Chat with the dealer directly to get more details or ask questions.' : '🔒 Login required to contact the seller.'}
                            </p>
                            {!auth.currentUser && (
                                <a onClick={() => navigate('/signup?tab=login')} style={{ color: 'var(--accent)', fontWeight: 600, cursor: 'pointer' }}>Login now →</a>
                            )}
                        </div>
                        <button style={{ width: '100%', padding: '0.9rem', background: 'var(--accent)', color: '#fff', border: 'none', borderRadius: '10px', fontFamily: 'Inter, sans-serif', fontSize: '0.95rem', fontWeight: 600, cursor: 'pointer', marginBottom: '0.75rem', boxShadow: '0 0 20px rgba(59,130,246,0.3)' }} onClick={handleContact}>Contact Seller</button>
                        <button style={{ width: '100%', padding: '0.9rem', background: 'transparent', color: 'var(--text)', border: '1.5px solid var(--border-2)', borderRadius: '10px', fontFamily: 'Inter, sans-serif', fontSize: '0.95rem', fontWeight: 600, cursor: 'pointer' }} onClick={handleContact}>Request a Viewing</button>
                    </div>

                    <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius)', padding: '1.25rem 1.5rem' }}>
                        <h4 style={{ fontFamily: 'Syne, sans-serif', fontSize: '0.9rem', fontWeight: 700, color: 'var(--text)', marginBottom: '1rem' }}>Property Highlights</h4>
                        {[
                            { icon: '💰', label: 'Price', val: `RS ${(property.price || 0).toLocaleString()}` },
                            { icon: '📐', label: 'Size', val: `${property.area || 'N/A'}` },
                            { icon: '🛏', label: 'Bedrooms', val: property.beds > 0 ? property.beds : 'Studio' },
                            { icon: '📍', label: 'Location', val: property.location },
                        ].map((h, i) => (
                            <div key={i} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.82rem', marginBottom: '0.6rem' }}>
                                <span style={{ color: 'var(--text-3)' }}>{h.icon} {h.label}</span>
                                <span style={{ fontWeight: 600, color: 'var(--text)' }}>{h.val}</span>
                            </div>
                        ))}
                    </div>
                </div>
            </div>

            {/* Success Modal */}
            {successModal && (
                <div className="modal-overlay" onClick={() => setSuccessModal(false)}>
                    <div className="modal-content" style={{ textAlign: 'center' }} onClick={e => e.stopPropagation()}>
                        <button className="close-btn" onClick={() => setSuccessModal(false)}>×</button>
                        <div style={{ fontSize: '3rem', marginBottom: '0.75rem' }}>✅</div>
                        <h2 style={{ marginBottom: '0.5rem' }}>Message Sent!</h2>
                        <p style={{ fontSize: '0.875rem', color: 'var(--text-2)', marginBottom: '1.5rem' }}>Your message was sent to {property.seller?.name || property.dealerName}. Expect a reply within 24 hours.</p>
                        <button className="modal-submit" onClick={() => setSuccessModal(false)}>Done</button>
                    </div>
                </div>
            )}

            <Footer />
        </>
    );
}