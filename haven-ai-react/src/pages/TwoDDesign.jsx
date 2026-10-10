import FloorPlanGenerator from '../components/FloorPlanGenerator';
import { useEffect, useRef } from 'react';

export default function TwoDDesign() {
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

    const scrollToGenerator = () => document.getElementById('plan-generator')?.scrollIntoView({ behavior: 'smooth' });

    return (
        <>

            {/* TOOL HERO */}
            <section style={{
                position: 'relative', background: 'var(--bg-2)',
                borderBottom: '1px solid var(--border)',
                padding: 'calc(var(--nav-h) + 4rem) 2rem 4rem',
                textAlign: 'center', overflow: 'hidden'
            }}>
                <div style={{
                    position: 'absolute', inset: 0,
                    background: 'radial-gradient(ellipse 70% 80% at 50% 0%, rgba(59,130,246,0.15) 0%, transparent 60%), radial-gradient(ellipse 40% 40% at 80% 70%, rgba(16,185,129,0.07) 0%, transparent 50%)'
                }} />
                <div style={{ position: 'relative', zIndex: 1, maxWidth: '720px', margin: '0 auto' }}>
                    <h1 style={{ fontFamily: 'Syne, sans-serif', fontSize: 'clamp(2.4rem, 5vw, 4rem)', fontWeight: 800, color: 'var(--text)', lineHeight: 1.1, letterSpacing: '-0.03em', marginBottom: '1.25rem' }}>
                        Design your floor plan.<br /><em style={{ fontStyle: 'normal', color: 'var(--accent)' }}>Online, instantly, free.</em>
                    </h1>
                    <p style={{ fontSize: '1.1rem', color: 'var(--text-2)', lineHeight: 1.75, maxWidth: '540px', margin: '0 auto 2rem' }}>
                        An easy-to-use 2D floor plan design tool for anyone planning a home layout. Create, customize, and export your floor plan — no software to install.
                    </p>
                    <div style={{ display: 'flex', gap: '1rem', justifyContent: 'center', flexWrap: 'wrap' }}>
                        <button className="btn-hero" onClick={scrollToGenerator}>Start Your Free Floor Plan →</button>
                        <a href="#how-it-works" className="btn-hero-ghost">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="6 9 12 15 18 9" /></svg>
                            See How It Works
                        </a>
                    </div>
                </div>
            </section>

            {/* FLOOR PLAN GENERATOR */}
            <section id="plan-generator" style={{ background: 'var(--bg)', padding: '4rem 2rem', borderBottom: '1px solid var(--border)' }}>
                <div style={{ maxWidth: '1180px', margin: '0 auto' }}>
                    <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
                        <div className="sec-label">Floor Plan Generator</div>
                        <h2 style={{ fontFamily: 'Syne, sans-serif', fontSize: 'clamp(1.8rem, 3vw, 2.5rem)', fontWeight: 800, color: 'var(--text)', letterSpacing: '-0.02em', marginBottom: '0.75rem' }}>Describe your plot, get a floor plan</h2>
                        <p style={{ fontSize: '0.95rem', color: 'var(--text-2)', maxWidth: '560px', margin: '0 auto', lineHeight: 1.75 }}>The AI checks whether your rooms fit, uses up to two floors when needed, and draws the layout. Every plan is checked for overlaps and plot boundaries.</p>
                    </div>
                    <FloorPlanGenerator />
                </div>
            </section>

            {/* WHY CHOOSE */}
            <section style={{ background: 'var(--bg)', padding: '6rem 2rem', borderBottom: '1px solid var(--border)' }}>
                <div style={{ maxWidth: '1000px', margin: '0 auto', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '5rem', alignItems: 'center' }}>
                    <div>
                        <div className="sec-label">Why Choose This Tool</div>
                        <h2 style={{ fontFamily: 'Syne, sans-serif', fontSize: 'clamp(1.8rem, 3vw, 2.5rem)', fontWeight: 800, color: 'var(--text)', letterSpacing: '-0.02em', marginBottom: '1.25rem' }}>Powerful yet simple — for everyone</h2>
                        <p style={{ fontSize: '0.95rem', color: 'var(--text-2)', lineHeight: 1.8, marginBottom: '1rem' }}>
                            This platform is a powerful yet user-friendly 2D floor plan tool designed to simplify the home design process. Whether you're starting from scratch or refining a complex layout, it offers flexibility, accuracy, and speed.
                        </p>
                        <p style={{ fontSize: '0.95rem', color: 'var(--text-2)', lineHeight: 1.8 }}>
                            For those who need advanced 3D rendering and professional design capabilities, our full-featured AI modules provide a more comprehensive solution.
                        </p>
                    </div>
                    <div style={{ borderRadius: 'var(--radius)', overflow: 'hidden', border: '1px solid var(--border)', aspectRatio: '4/3', background: 'var(--surface)' }}>
                        <img src="https://images.unsplash.com/photo-1503387762-592deb58ef4e?w=800&q=85" alt="Floor Plan Design" style={{ width: '100%', height: '100%', objectFit: 'cover', filter: 'brightness(0.88)' }} />
                    </div>
                </div>
            </section>

            {/* HOW IT WORKS */}
            <section id="how-it-works" style={{ background: 'var(--bg)', padding: '6rem 2rem', borderBottom: '1px solid var(--border)' }}>
                <div style={{ textAlign: 'center', marginBottom: '4rem' }}>
                    <div className="sec-label">How It Works</div>
                    <h2 style={{ fontFamily: 'Syne, sans-serif', fontSize: 'clamp(1.8rem, 3vw, 2.5rem)', fontWeight: 800, color: 'var(--text)', letterSpacing: '-0.02em', marginBottom: '0.75rem' }}>Three steps to your perfect floor plan</h2>
                    <p style={{ fontSize: '0.95rem', color: 'var(--text-2)', maxWidth: '480px', margin: '0 auto', lineHeight: 1.75 }}>From blank canvas to export-ready design — our AI guides you every step.</p>
                </div>
                <div style={{ maxWidth: '1000px', margin: '0 auto' }}>
                    {[
                        { num: '01', title: 'Build your layout with a 2D floor plan maker', desc: 'Use the AI floor plan creator to start designing your layout in minutes. Whether you describe a concept or start from scratch, the tool draws walls, defines rooms, and structures your space accurately.', img: 'https://images.unsplash.com/photo-1558618666-fcd25c85cd64?w=700&q=85', tag: 'Step 01 — Build', btn: 'Start my 2D layout →' },
                        { num: '02', title: 'Add structural and interior elements', desc: 'As a 2D floor plan designer, you can customize your layout with windows, doors, stairs, and partitions. The AI ensures precise alignment of every feature — ideal for both professional drawings and DIY remodeling plans.', img: 'https://images.unsplash.com/photo-1483450388369-9ed95738483c?w=700&q=85', tag: 'Step 02 — Customize', btn: 'Customize my layout →' },
                        { num: '03', title: 'Finalize and export your floor plan', desc: 'Once you\'re satisfied, create a 2D floor plan that\'s clean and client-ready. Add final touches, review dimensions, and export your design. Whether presenting to a client or sharing with contractors, get a clear and detailed floor plan every time.', img: 'https://images.unsplash.com/photo-1541888946425-d81bb19240f5?w=700&q=85', tag: 'Step 03 — Export', btn: 'Export my plan →' },
                    ].map((step, i) => (
                        <div key={i} className="reveal" ref={addReveal} style={{ display: 'grid', gridTemplateColumns: '72px 1fr 1fr', gap: '2.5rem', alignItems: 'center', padding: '3rem 0', borderBottom: '1px solid var(--border)' }}>
                            <div style={{ fontFamily: 'Syne, sans-serif', fontSize: '3rem', fontWeight: 800, color: 'rgba(59,130,246,0.15)', lineHeight: 1, textAlign: 'center' }}>{step.num}</div>
                            <div>
                                <h3 style={{ fontFamily: 'Syne, sans-serif', fontSize: '1.2rem', fontWeight: 700, color: 'var(--text)', marginBottom: '0.6rem' }}>{step.title}</h3>
                                <p style={{ fontSize: '0.9rem', color: 'var(--text-2)', lineHeight: 1.7, marginBottom: '1.25rem' }}>{step.desc}</p>
                                <button className="btn-feature" onClick={scrollToGenerator}>{step.btn}</button>
                            </div>
                            <div style={{ borderRadius: '14px', overflow: 'hidden', border: '1px solid var(--border)', aspectRatio: '16/10', background: 'var(--surface)', position: 'relative' }}>
                                <img src={step.img} alt={step.title} style={{ width: '100%', height: '100%', objectFit: 'cover', filter: 'brightness(0.85)' }} />
                                <div style={{ position: 'absolute', top: '0.75rem', left: '0.75rem', background: 'rgba(0,0,0,0.65)', backdropFilter: 'blur(6px)', border: '1px solid var(--border-2)', color: 'var(--text)', fontSize: '0.68rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.08em', padding: '0.3rem 0.7rem', borderRadius: '100px' }}>{step.tag}</div>
                            </div>
                        </div>
                    ))}
                </div>
            </section>

            {/* KEY FEATURES */}
            <section style={{ background: 'var(--bg-2)', padding: '6rem 2rem', borderBottom: '1px solid var(--border)' }}>
                <div style={{ textAlign: 'center', marginBottom: '3.5rem' }}>
                    <div className="sec-label">Key Features</div>
                    <h2 style={{ fontFamily: 'Syne, sans-serif', fontSize: 'clamp(1.8rem, 3vw, 2.5rem)', fontWeight: 800, color: 'var(--text)', letterSpacing: '-0.02em' }}>Key features of this 2D floor plan tool</h2>
                </div>
                <div style={{ maxWidth: '1000px', margin: '0 auto', display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '1.25rem' }}>
                    {[
                        { icon: '🎯', title: 'Easy to use', desc: 'Start your layout in minutes with an AI-driven 2D floor plan interface that\'s made for everyone — no learning curve required.' },
                        { icon: '🖨️', title: 'High-quality, printable layouts', desc: 'Export your floor plans in high resolution — perfect for presentations, permit drawings, or contractor handoffs.' },
                        { icon: '🌐', title: 'Fully online, no installation', desc: 'Design directly in your browser. No downloads, no system requirements — works on any device, anywhere, at any time.' },
                        { icon: '📦', title: 'Thousands of templates & objects', desc: 'Access a vast library of pre-made room templates, furniture, décor, and structural components.' },
                    ].map((feat, i) => (
                        <div key={i} className="reveal" ref={addReveal} style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius)', padding: '2rem', transition: 'all 0.3s' }}>
                            <div style={{ width: '46px', height: '46px', borderRadius: '12px', background: 'rgba(59,130,246,0.1)', border: '1px solid rgba(59,130,246,0.2)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '1.25rem', marginBottom: '1.25rem' }}>{feat.icon}</div>
                            <h4 style={{ fontFamily: 'Syne, sans-serif', fontSize: '1rem', fontWeight: 700, color: 'var(--text)', marginBottom: '0.5rem' }}>{feat.title}</h4>
                            <p style={{ fontSize: '0.875rem', color: 'var(--text-2)', lineHeight: 1.65 }}>{feat.desc}</p>
                        </div>
                    ))}
                </div>
            </section>

        </>
    );
}
