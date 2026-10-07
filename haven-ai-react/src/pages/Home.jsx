import { useEffect, useRef } from 'react';
import { Link, useNavigate } from 'react-router-dom';

export default function Home() {
    const navigate = useNavigate();
    const revealRefs = useRef([]);

    useEffect(() => {
        const observer = new IntersectionObserver(
            (entries) => entries.forEach(e => { if (e.isIntersecting) e.target.classList.add('visible'); }),
            { threshold: 0.1 }
        );
        revealRefs.current.forEach(el => el && observer.observe(el));
        return () => observer.disconnect();
    }, []);

    const addReveal = (el) => { if (el && !revealRefs.current.includes(el)) revealRefs.current.push(el); };

    return (
        <>

            {/* ── HERO ── */}
            <section id="hero">
                <div className="hero-inner">
                    <h1>Design Smarter.<br /><span className="gradient-text">Find Faster.</span></h1>
                    <p>From 2D floor plans to 3D visualizations, interior design to property search — everything you need to design, build, and find your perfect home. Powered by AI.</p>
                    <div className="hero-actions">
                        <button className="btn-hero" onClick={() => navigate('/signup?tab=signup')}>Start for Free →</button>
                        <a href="#features" className="btn-hero-ghost">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10" /><polygon points="10 8 16 12 10 16 10 8" /></svg>
                            See How It Works
                        </a>
                    </div>
                    <div className="hero-stats">
                        {[
                            { num: '5', suffix: '', label: 'AI Modules' },
                            { num: '2D', suffix: '→3D', label: 'Plan to Model' },
                            { num: '150', suffix: '', label: 'Object Classes Recognised' },
                            { num: '0', suffix: '₨', label: 'Free to Use' },
                        ].map((s, i) => (
                            <div key={i} className="hero-stat">
                                <div className="hero-stat-num">{s.num}<span>{s.suffix}</span></div>
                                <div className="hero-stat-label">{s.label}</div>
                            </div>
                        ))}
                    </div>
                </div>
                <div className="scroll-indicator">
                    <div className="scroll-line"></div>
                    Scroll
                </div>
            </section>

            {/* ── SOLUTIONS ── */}
            <section id="solutions">
                <div className="section-inner">
                    <div className="solutions-header">
                        <div className="sec-label">Solutions</div>
                        <h2 className="sec-title">Everything for Your Housing Journey</h2>
                        <p className="sec-sub">Whether you're designing a new home, finding a property, or planning an interior — our AI tools handle the heavy lifting.</p>
                    </div>
                    <div className="solutions-grid">
                        {[
                            { icon: '🏗️', title: '2D Floor Plans', desc: 'Describe your space and get AI-generated floor plans with precise room layouts, dimensions, and placements.', link: '/2d-design', label: 'Explore 2D Design →' },
                            { icon: '🏛️', title: '3D Visualization', desc: 'Turn your floor plan into an immersive 3D experience. See your future home before a single brick is laid.', link: '/3d-design', label: 'Explore 3D Design →' },
                            { icon: '🎨', title: 'Interior Design', desc: 'Get curated style recommendations — colors, furniture, textures — tailored to your taste and lifestyle.', link: '/interior-design', label: 'Explore Interiors →' },
                            { icon: '💰', title: 'Cost Estimation', desc: 'Transparent, itemized AI cost breakdowns for any construction or renovation project. No surprises.', link: '/cost-estimation', label: 'Get an Estimate →' },
                            { icon: '🏡', title: 'Property Search', desc: 'Browse verified listings, contact sellers directly, and list your own property — all in one place.', link: '/properties', label: 'Browse Properties →' },
                        ].map((card, i) => (
                            <Link key={i} to={card.link} className="sol-card reveal" ref={addReveal}>
                                <div className="sol-icon">{card.icon}</div>
                                <div>
                                    <h3>{card.title}</h3>
                                    <p>{card.desc}</p>
                                </div>
                                <div className="sol-arrow">{card.label}</div>
                            </Link>
                        ))}
                    </div>
                </div>
            </section>

            {/* ── FEATURES ── */}
            <section id="features">
                <div className="section-inner">
                    <div className="features-header">
                        <div className="sec-label">Features</div>
                        <h2 className="sec-title">Built for people who move fast</h2>
                        <p className="sec-sub" style={{ margin: '0 auto' }}>Three steps from idea to reality — our AI guides you every step of the way.</p>
                    </div>

                    {[
                        {
                            img: 'https://images.unsplash.com/photo-1503387762-592deb58ef4e?w=900&q=85',
                            alt: '2D Floor Plan Design', badge: 'Step 01 — Design',
                            step: 'Design', title: 'Create your space effortlessly',
                            desc: 'Just describe what you need — in plain language. Our AI translates your vision into professional 2D floor plans and 3D models, instantly.',
                            bullets: ['AI-generated 2D floor plans with dimensions', 'Automatic room layout optimization', 'Full 3D volumetric design from description', 'Iterative refinement through conversation'],
                            link: '/2d-design', linkLabel: 'Try 2D Design →', reverse: false
                        },
                        {
                            img: 'https://images.unsplash.com/photo-1555041469-a586c61ea9bc?w=900&q=85',
                            alt: 'Interior Design', badge: 'Step 02 — Visualize',
                            step: 'Visualize', title: 'See your home come alive',
                            desc: 'From style palettes to furniture placement, our Interior Design AI paints a vivid picture of every room.',
                            bullets: ['Personalized style recommendations', 'Room-by-room color and material palettes', 'Furniture and décor suggestions with pricing', 'Lighting design for any ambiance'],
                            link: '/interior-design', linkLabel: 'Try Interior Design →', reverse: true
                        },
                        {
                            img: 'https://images.unsplash.com/photo-1568605114967-8130f3a36994?w=900&q=85',
                            alt: 'Property Search', badge: 'Step 03 — Find',
                            step: 'Find', title: 'Buy, sell, and connect — seamlessly',
                            desc: 'Browse real property listings from verified sellers. Contact them directly once you\'re logged in.',
                            bullets: ['Browse properties with smart filters', 'Direct messaging with sellers — login required', 'Request viewings in seconds', 'List your property free of charge'],
                            link: '/properties', linkLabel: 'Browse Properties →', reverse: false
                        }
                    ].map((feat, i) => (
                        <div key={i} className={`feature-block${feat.reverse ? ' reverse' : ''} reveal`} ref={addReveal}>
                            <div className="feature-visual">
                                <img src={feat.img} alt={feat.alt} />
                                <div className="feature-visual-badge">{feat.badge}</div>
                            </div>
                            <div className="feature-text">
                                <div className="feature-step">{feat.step}</div>
                                <h2>{feat.title}</h2>
                                <p>{feat.desc}</p>
                                <ul className="feature-bullets">
                                    {feat.bullets.map((b, bi) => <li key={bi}>{b}</li>)}
                                </ul>
                                <Link to={feat.link} className="btn-feature">{feat.linkLabel}</Link>
                            </div>
                        </div>
                    ))}
                </div>
            </section>

            {/* ── AUDIENCE ── */}
            <section id="audience">
                <div className="section-inner">
                    <div className="audience-header">
                        <div className="sec-label">For Everyone</div>
                        <h2 className="sec-title">Built for every housing need</h2>
                        <p className="sec-sub" style={{ margin: '0 auto' }}>Whether you're building, buying, designing, or selling — Haven.AI has a tool for you.</p>
                    </div>
                    <div className="audience-grid">
                        {[
                            { emoji: '🏠', role: 'Homeowners', title: 'Design your dream home', desc: 'Plan renovations, visualize interiors, and estimate costs before committing to any project.', stat: <>See <strong>colours, materials and furniture</strong> in your own room before you buy.</> },
                            { emoji: '🏗️', role: 'Architects & Designers', title: 'Speed up your workflow', desc: 'Generate draft floor plans and 3D concepts in minutes. Share with clients instantly and iterate faster.', stat: <>Every plan is <strong>checked for overlaps and fit</strong> before it is shown.</> },
                            { emoji: '🔑', role: 'Property Buyers', title: 'Find the right property', desc: 'Browse curated listings, filter by your exact needs, and contact verified sellers directly from the platform.', stat: <>Message the <strong>dealer directly</strong> from any listing.</> },
                            { emoji: '📋', role: 'Property Sellers', title: 'Reach more buyers', desc: 'List your property for free, track its views, and answer buyer enquiries from one dashboard.', stat: <>Listings are <strong>reviewed and verified</strong> by our team.</> },
                        ].map((card, i) => (
                            <div key={i} className="audience-card reveal" ref={addReveal}>
                                <div className="audience-emoji">{card.emoji}</div>
                                <div className="role">{card.role}</div>
                                <h3>{card.title}</h3>
                                <p>{card.desc}</p>
                                <div className="audience-stat">{card.stat}</div>
                            </div>
                        ))}
                    </div>
                </div>
            </section>

            {/* ── STATS ── */}
            <section id="stats">
                <div className="stats-inner">
                    {[
                        { num: '5', accent: '', desc: 'Specialised AI modules in one assistant' },
                        { num: '2', accent: ' floors', desc: 'Validated floor plans for up to two storeys' },
                        { num: '100', accent: '%', desc: 'Room analysis runs on our own server — no photo sent to third parties' },
                        { num: '24', accent: '/7', desc: 'AI assistant available on every page' },
                    ].map((s, i) => (
                        <div key={i} className="stat-item reveal" ref={addReveal}>
                            <div className="stat-num">{s.num}<span className="accent">{s.accent}</span></div>
                            <div className="stat-desc">{s.desc}</div>
                        </div>
                    ))}
                </div>
            </section>

            {/* ── TESTIMONIALS ── */}
            <section id="testimonials">
                <div className="section-inner">
                    <div className="testimonials-header">
                        <div className="sec-label">How it works</div>
                        <h2 className="sec-title">From an idea to a home in three steps</h2>
                    </div>
                    <div className="testimonials-grid">
                        {[
                            { stars: 'Step 1', quote: 'Describe your plot and the rooms you need in plain language — for example "5 marla, 3 bedrooms, open kitchen".', avatar: '✍️', name: 'Describe', role: '2D Design' },
                            { stars: 'Step 2', quote: 'Get a floor plan that is checked automatically, then turn it into an interactive 3D model you can walk around.', avatar: '🏛️', name: 'Visualise', role: '2D → 3D Design' },
                            { stars: 'Step 3', quote: 'Upload a photo of a room to restyle it, compare listings, and contact dealers directly when you are ready.', avatar: '🔑', name: 'Decide', role: 'Interior Design & Properties' },
                        ].map((t, i) => (
                            <div key={i} className="testi-card reveal" ref={addReveal}>
                                <div className="testi-stars">{t.stars}</div>
                                <p className="testi-quote">{t.quote}</p>
                                <div className="testi-author">
                                    <div className="testi-avatar">{t.avatar}</div>
                                    <div>
                                        <div className="testi-name">{t.name}</div>
                                        <div className="testi-role">{t.role}</div>
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            </section>

            {/* ── CTA BANNER ── */}
            <section id="cta-banner">
                <div className="cta-box">
                    <div className="sec-label" style={{ textAlign: 'center' }}>Get Started Today</div>
                    <h2>Your dream home starts here.</h2>
                    <p>Plan, visualise and find your next home with Haven.AI — free to start, no credit card needed.</p>
                    <div className="cta-actions">
                        <button className="btn-hero" onClick={() => navigate('/signup?tab=signup')}>Start for Free →</button>
                        <a href="#solutions" className="btn-hero-ghost">Explore All Tools</a>
                    </div>
                </div>
            </section>

        </>
    );
}
