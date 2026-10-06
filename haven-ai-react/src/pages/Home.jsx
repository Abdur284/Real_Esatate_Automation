import { useEffect, useRef } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import Navbar from '../components/Navbar';
import Footer from '../components/Footer';

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
            <Navbar />

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
                            { num: '5', suffix: '+', label: 'AI Modules' },
                            { num: '10k', suffix: '+', label: 'Designs Created' },
                            { num: '98', suffix: '%', label: 'Satisfaction Rate' },
                            { num: '2', suffix: 'min', label: 'Avg. AI Response' },
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
                        <p className="sec-sub" style={{ margin: '0 auto' }}>Whether you're building, buying, designing, or selling — Housing.AI has a tool for you.</p>
                    </div>
                    <div className="audience-grid">
                        {[
                            { emoji: '🏠', role: 'Homeowners', title: 'Design your dream home', desc: 'Plan renovations, visualize interiors, and estimate costs before committing to any project.', stat: 'Users save an average of <strong>30% on renovation costs</strong> by planning ahead.' },
                            { emoji: '🏗️', role: 'Architects & Designers', title: 'Speed up your workflow', desc: 'Generate draft floor plans and 3D concepts in minutes. Share with clients instantly and iterate faster.', stat: 'Designers report <strong>2× faster project delivery</strong> using AI drafts.' },
                            { emoji: '🔑', role: 'Property Buyers', title: 'Find the right property', desc: 'Browse curated listings, filter by your exact needs, and contact verified sellers directly from the platform.', stat: 'Buyers close deals <strong>40% faster</strong> with direct seller contact.' },
                            { emoji: '📋', role: 'Property Sellers', title: 'Reach more buyers', desc: 'List your property for free and get immediate exposure to thousands of qualified, active buyers on the platform.', stat: 'Listings get <strong>3× more inquiries</strong> than traditional listings.' },
                        ].map((card, i) => (
                            <div key={i} className="audience-card reveal" ref={addReveal}>
                                <div className="audience-emoji">{card.emoji}</div>
                                <div className="role">{card.role}</div>
                                <h3>{card.title}</h3>
                                <p>{card.desc}</p>
                                <div className="audience-stat" dangerouslySetInnerHTML={{ __html: card.stat }} />
                            </div>
                        ))}
                    </div>
                </div>
            </section>

            {/* ── STATS ── */}
            <section id="stats">
                <div className="stats-inner">
                    {[
                        { num: '10k', accent: '+', desc: 'AI designs generated to date' },
                        { num: '4.8', accent: '★', desc: 'Average user satisfaction rating' },
                        { num: '2', accent: 'min', desc: 'Average time to first AI response' },
                        { num: '5', accent: '+', desc: 'Specialized AI modules available' },
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
                        <div className="sec-label">Testimonials</div>
                        <h2 className="sec-title">What our users say</h2>
                    </div>
                    <div className="testimonials-grid">
                        {[
                            { stars: '★★★★★', quote: '"I described my apartment layout in plain English and got a detailed floor plan in under two minutes. This completely changed how I approach renovation planning."', avatar: '👩', name: 'Sarah K.', role: 'Homeowner, Austin TX' },
                            { stars: '★★★★★', quote: '"The cost estimation tool saved me from massive budget overruns. I got a detailed itemized breakdown before even meeting a contractor — and the AI estimate was within 8% of the final quote."', avatar: '👨', name: 'David M.', role: 'Property Developer, Chicago' },
                            { stars: '★★★★★', quote: '"I sold my apartment in 3 weeks after listing on Housing.AI. The direct contact feature brought in serious buyers only. I\'d never list anywhere else again."', avatar: '👩‍💼', name: 'Layla R.', role: 'Property Seller, New York' },
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
                    <p>Join thousands of homeowners, designers, and property seekers already using Housing.AI to design smarter and find faster.</p>
                    <div className="cta-actions">
                        <button className="btn-hero" onClick={() => navigate('/signup?tab=signup')}>Start for Free →</button>
                        <a href="#solutions" className="btn-hero-ghost">Explore All Tools</a>
                    </div>
                </div>
            </section>

            <Footer />
        </>
    );
}
