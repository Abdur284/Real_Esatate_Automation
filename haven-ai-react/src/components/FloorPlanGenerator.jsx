import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api';
import FloorPlanViewer from './FloorPlanViewer';
import { ROOM_COLORS } from './floorPlanColors';
import { LAST_PLAN_KEY, downloadPng, downloadSvg } from './floorPlanExport';

const EXAMPLES = [
    'My plot is 25 by 50 feet. I want 4 bedrooms, 3 bathrooms, one kitchen, a drawing room, a TV lounge and parking for one car.',
    '30 x 60 ft plot, single storey, 2 bedrooms, 1 bathroom, kitchen, TV lounge',
    '10 marla house, 3 bedrooms with attached baths, kitchen, drawing room, lounge, 1 car parking',
];

const FLOORS = [['ground_floor', 'Ground Floor'], ['first_floor', 'First Floor']];
const DESIGN_STATUSES = ['FEASIBLE', 'FEASIBLE_WITH_TWO_FLOORS'];

const btn = (active) => ({
    background: active ? 'rgba(59,130,246,0.15)' : 'var(--surface)',
    border: `1.5px solid ${active ? 'rgba(59,130,246,0.5)' : 'var(--border)'}`,
    color: active ? 'var(--accent)' : 'var(--text-2)',
    padding: '0.45rem 0.9rem', borderRadius: '8px',
    fontFamily: 'Inter, sans-serif', fontSize: '0.78rem', fontWeight: 600,
    cursor: 'pointer', transition: 'all 0.2s',
});

const field = {
    background: 'var(--surface)', border: '1.5px solid var(--border)',
    color: 'var(--text)', padding: '0.55rem 0.75rem', borderRadius: '8px',
    fontFamily: 'Inter, sans-serif', fontSize: '0.85rem',
};

const card = {
    background: 'var(--surface)', border: '1px solid var(--border)',
    borderRadius: 'var(--radius)', padding: '1rem',
};

const heading = { fontFamily: 'Syne, sans-serif', fontSize: '0.95rem', fontWeight: 700, marginBottom: '0.6rem' };

function Notes({ title, items, color = 'var(--text-3)' }) {
    if (!items?.length) return null;
    return (
        <details style={{ fontSize: '0.75rem', color, marginTop: '0.6rem' }}>
            <summary style={{ cursor: 'pointer', fontWeight: 600 }}>{title} ({items.length})</summary>
            <ul style={{ paddingLeft: '1rem', marginTop: '0.4rem', lineHeight: 1.5 }}>
                {items.map((a, i) => <li key={i} style={{ marginBottom: '0.3rem' }}>{a}</li>)}
            </ul>
        </details>
    );
}

export default function FloorPlanGenerator() {
    const [prompt, setPrompt] = useState('');
    const [width, setWidth] = useState('');
    const [length, setLength] = useState('');
    const [floors, setFloors] = useState('auto');
    const [loading, setLoading] = useState(false);
    const [result, setResult] = useState(null);
    const [error, setError] = useState(null);
    const [activeFloor, setActiveFloor] = useState('ground_floor');
    const [selected, setSelected] = useState(null);
    const navigate = useNavigate();
    const exportRef = useRef(null);
    const [downloading, setDownloading] = useState(false);

    const [narrow, setNarrow] = useState(() => typeof window !== 'undefined' && window.innerWidth < 900);
    useEffect(() => {
        const onResize = () => setNarrow(window.innerWidth < 900);
        window.addEventListener('resize', onResize);
        return () => window.removeEventListener('resize', onResize);
    }, []);

    const generate = async (e) => {
        e?.preventDefault();
        if (!prompt.trim() || loading) return;
        setLoading(true);
        setError(null);
        setResult(null);
        setSelected(null);
        try {
            const data = await api.design2d.generate({
                prompt,
                plotWidthFt: width ? parseFloat(width) : undefined,
                plotLengthFt: length ? parseFloat(length) : undefined,
                floors: floors === 'auto' ? undefined : parseInt(floors, 10),
            });
            setResult(data);
            setActiveFloor('ground_floor');
            // Offered on the 3D Design page as "Use existing 2D design".
            if (DESIGN_STATUSES.includes(data.status)) {
                try { localStorage.setItem(LAST_PLAN_KEY, JSON.stringify(data)); } catch { /* storage unavailable */ }
            }
        } catch (err) {
            setError(err.message?.startsWith('Failed to fetch') || err.message?.startsWith('API error')
                ? "Couldn't reach the 2D design service. Make sure the backend is running, then try again."
                : err.message);
        } finally {
            setLoading(false);
        }
    };

    const hasDesign = result && DESIGN_STATUSES.includes(result.status);
    const design = result?.design || {};
    const analysis = result?.analysis || {};
    const validation = result?.validation || {};
    const floorTabs = FLOORS.slice(0, design.floors === 2 ? 2 : 1);
    const floor = design[activeFloor] || {};
    const floorItems = ['rooms', 'circulation', 'open_spaces'].flatMap((section) =>
        (floor[section] || []).map((it, i) => ({ ...it, _key: `${section}-${i}` })));
    const selectedItem = floorItems.find((it) => it._key === selected);

    // Downloads use clean copies of each floor rendered off-screen (below), so
    // a highlighted room never ends up in the file.
    const exportSvgFor = (key) => exportRef.current?.querySelector(`[data-floor="${key}"] svg`);
    const fileBase = () => `floor-plan-${result.plot.width_ft}x${result.plot.length_ft}ft`;
    const download = async (kind) => {
        if (downloading) return;
        setDownloading(true);
        setError(null);
        try {
            const label = (key) => FLOORS.find(([k]) => k === key)[1];
            const slug = (key) => label(key).toLowerCase().replace(/\s+/g, '-');
            if (kind === 'svg') {
                downloadSvg(exportSvgFor(activeFloor), `${fileBase()}-${slug(activeFloor)}.svg`);
            } else {
                const keys = kind === 'png-all' ? floorTabs.map(([k]) => k) : [activeFloor];
                await downloadPng(
                    keys.map((k) => ({ label: label(k), svg: exportSvgFor(k) })),
                    {
                        title: `Floor Plan — ${result.plot.width_ft} × ${result.plot.length_ft} ft plot`,
                        subtitle: `${result.plot.area_sqft} sq ft · ${design.floors} floor${design.floors === 2 ? 's' : ''} · `
                            + `${result.status.replace(/_/g, ' ').toLowerCase()} · generated by Haven AI`,
                    },
                    `${fileBase()}-${kind === 'png-all' ? 'all-floors' : slug(activeFloor)}.png`,
                    result,
                );
            }
        } catch (err) {
            setError(`Download failed: ${err.message}`);
        } finally {
            setDownloading(false);
        }
    };

    return (
        <div>
            <form onSubmit={generate} style={{ ...card, padding: '1.25rem', marginBottom: '1.25rem' }}>
                <label htmlFor="plan-brief" style={{ display: 'block', fontSize: '0.78rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--text-3)', marginBottom: '0.5rem' }}>
                    Your plot and requirements
                </label>
                <textarea id="plan-brief" value={prompt} onChange={(e) => setPrompt(e.target.value)} rows={3}
                    placeholder='e.g. "My plot is 25 by 50 feet. I want 4 bedrooms, 3 bathrooms, a kitchen, a drawing room, a TV lounge and parking for one car."'
                    style={{ ...field, width: '100%', resize: 'vertical', marginBottom: '0.75rem' }} />
                <div style={{ display: 'flex', gap: '0.6rem', flexWrap: 'wrap', alignItems: 'center' }}>
                    <input style={{ ...field, width: 150 }} type="number" min="0" placeholder="Width ft (optional)"
                        value={width} onChange={(e) => setWidth(e.target.value)} aria-label="Plot width in feet" />
                    <input style={{ ...field, width: 150 }} type="number" min="0" placeholder="Length ft (optional)"
                        value={length} onChange={(e) => setLength(e.target.value)} aria-label="Plot length in feet" />
                    <select style={{ ...field, width: 160 }} value={floors} onChange={(e) => setFloors(e.target.value)}
                        aria-label="Number of floors">
                        <option value="auto">Floors: auto</option>
                        <option value="1">Single storey</option>
                        <option value="2">Double storey</option>
                    </select>
                    <button type="submit" disabled={loading} style={{
                        ...btn(true), padding: '0.55rem 1.4rem', opacity: loading ? 0.6 : 1, cursor: loading ? 'wait' : 'pointer',
                    }}>
                        {loading ? 'Designing… (up to a minute)' : 'Generate Floor Plan'}
                    </button>
                </div>
                <div style={{ marginTop: '0.85rem', display: 'flex', gap: '0.5rem', flexWrap: 'wrap', alignItems: 'center' }}>
                    <span style={{ fontSize: '0.72rem', color: 'var(--text-3)' }}>Try:</span>
                    {EXAMPLES.map((ex, i) => (
                        <button key={i} type="button" onClick={() => setPrompt(ex)}
                            style={{ ...btn(false), fontSize: '0.72rem', padding: '0.3rem 0.7rem' }}>
                            {ex.length > 44 ? `${ex.slice(0, 44)}…` : ex}
                        </button>
                    ))}
                </div>
            </form>

            {error && (
                <div role="alert" style={{
                    background: 'rgba(220,38,38,0.1)', border: '1px solid rgba(220,38,38,0.3)',
                    color: '#fca5a5', padding: '0.9rem 1.1rem', borderRadius: '10px', marginBottom: '1.25rem',
                }}>⚠ {error}</div>
            )}

            {result && !hasDesign && (
                <div role="alert" style={{
                    background: 'rgba(217,119,6,0.1)', border: '1px solid rgba(217,119,6,0.3)',
                    padding: '1.1rem 1.25rem', borderRadius: '10px', marginBottom: '1.25rem',
                }}>
                    <div style={{ fontWeight: 700, color: '#fbbf24', marginBottom: '0.4rem' }}>
                        {String(result.status).replace(/_/g, ' ')}
                    </div>
                    <p style={{ fontSize: '0.88rem', color: 'var(--text-2)', lineHeight: 1.6 }}>{analysis.reason}</p>
                    {analysis.missing_information?.length > 0 && (
                        <ul style={{ fontSize: '0.85rem', color: 'var(--text-2)', marginTop: '0.5rem', paddingLeft: '1.1rem' }}>
                            {analysis.missing_information.map((m, i) => <li key={i}>Please provide: {m}</li>)}
                        </ul>
                    )}
                    {analysis.suggestions?.length > 0 && (
                        <>
                            <p style={{ fontSize: '0.85rem', color: 'var(--text-2)', marginTop: '0.6rem', fontWeight: 600 }}>Suggestions</p>
                            <ul style={{ fontSize: '0.85rem', color: 'var(--text-2)', paddingLeft: '1.1rem' }}>
                                {analysis.suggestions.map((m, i) => <li key={i}>{m}</li>)}
                            </ul>
                        </>
                    )}
                </div>
            )}

            {hasDesign && (
                <>
                    {!validation.passed && (
                        <div role="alert" style={{
                            background: 'rgba(217,119,6,0.1)', border: '1px solid rgba(217,119,6,0.3)', color: '#fbbf24',
                            padding: '0.8rem 1.1rem', borderRadius: '10px', marginBottom: '1rem', fontSize: '0.85rem',
                        }}>
                            ⚠ This layout failed {validation.errors?.length} automatic check(s) — treat it as a rough draft.
                            <ul style={{ paddingLeft: '1.1rem', marginTop: '0.4rem', color: 'var(--text-2)' }}>
                                {validation.errors?.map((m, i) => <li key={i}>{m}</li>)}
                            </ul>
                        </div>
                    )}

                    <div style={{ display: 'flex', gap: '0.55rem', flexWrap: 'wrap', alignItems: 'center', marginBottom: '0.9rem' }}>
                        {floorTabs.map(([key, label]) => (
                            <button key={key} onClick={() => { setActiveFloor(key); setSelected(null); }}
                                style={btn(activeFloor === key)}>{label}</button>
                        ))}
                        <div style={{ flex: 1 }} />
                        <button onClick={() => download('png')} disabled={downloading} style={btn(false)}
                            title="Download this floor as a PNG image">
                            ⬇ PNG
                        </button>
                        {floorTabs.length > 1 && (
                            <button onClick={() => download('png-all')} disabled={downloading} style={btn(false)}
                                title="Download both floors side by side as one PNG image">
                                ⬇ PNG (all floors)
                            </button>
                        )}
                        <button onClick={() => download('svg')} disabled={downloading} style={btn(false)}
                            title="Download this floor as a scalable SVG drawing">
                            ⬇ SVG
                        </button>
                        <button onClick={() => navigate('/3d-design', { state: { plan2d: result } })}
                            style={{ ...btn(true), padding: '0.5rem 1.1rem' }}
                            title="Build this exact layout as a 3D model on the 3D Design page">
                            🏛️ View in 3D →
                        </button>
                    </div>

                    {/* Off-screen, unselected copies of every floor for downloads */}
                    <div ref={exportRef} aria-hidden="true" style={{ position: 'absolute', left: -10000, top: 0, width: 800 }}>
                        {floorTabs.map(([key]) => (
                            <div key={key} data-floor={key}>
                                <FloorPlanViewer plot={result.plot} floor={design[key] || {}} />
                            </div>
                        ))}
                    </div>

                    <div style={{ display: 'grid', gridTemplateColumns: narrow ? 'minmax(0,1fr)' : 'minmax(0,1fr) 300px', gap: '1.1rem', alignItems: 'start' }}>
                        <div style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius)', overflow: 'hidden' }}>
                            <div style={{ maxHeight: narrow ? 'none' : 640, overflow: 'auto', display: 'flex', justifyContent: 'center', background: '#fff' }}>
                                <div style={{ width: '100%', maxWidth: Math.max(320, (result.plot.width_ft / result.plot.length_ft) * 620) }}>
                                    <FloorPlanViewer plot={result.plot} floor={floor} selected={selected} onSelect={setSelected} />
                                </div>
                            </div>
                            <div style={{ padding: '0.5rem 0.85rem', fontSize: '0.72rem', color: 'var(--text-3)', background: 'var(--surface)', borderTop: '1px solid var(--border)', display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
                                <span><span style={{ color: '#d97706' }}>━</span> Door (solid = main entrance)</span>
                                <span><span style={{ color: '#0ea5e9' }}>═</span> Window</span>
                                <span>Dashed = open space</span>
                                <span>Click a room for details</span>
                            </div>
                        </div>

                        <aside style={card}>
                            {selectedItem ? (
                                <>
                                    <h3 style={heading}>{selectedItem.name}</h3>
                                    <dl style={{ fontSize: '0.8rem', color: 'var(--text-2)', display: 'grid', gridTemplateColumns: 'auto 1fr', columnGap: '0.8rem', rowGap: '0.3rem' }}>
                                        <dt>Size</dt><dd>{selectedItem.width} × {selectedItem.length} ft ({Math.round(selectedItem.width * selectedItem.length)} sqft)</dd>
                                        <dt>Position</dt><dd>{selectedItem.position || `(${selectedItem.x}, ${selectedItem.y})`}</dd>
                                        {selectedItem.purpose && <><dt>Purpose</dt><dd>{selectedItem.purpose}</dd></>}
                                        {selectedItem.connections?.length > 0 && <><dt>Connects</dt><dd>{selectedItem.connections.join(', ')}</dd></>}
                                        <dt>Openings</dt><dd>{selectedItem.doors?.length || 0} door(s), {selectedItem.windows?.length || 0} window(s)</dd>
                                    </dl>
                                    <Notes title="Special requirements" items={selectedItem.special_requirements} />
                                    <button onClick={() => setSelected(null)} style={{ ...btn(false), marginTop: '0.8rem' }}>← All rooms</button>
                                </>
                            ) : (
                                <>
                                    <h3 style={heading}>Plan summary</h3>
                                    <dl style={{ fontSize: '0.8rem', color: 'var(--text-2)', display: 'grid', gridTemplateColumns: '1fr auto', rowGap: '0.3rem', marginBottom: '0.9rem' }}>
                                        <dt>Status</dt><dd>{result.status.replace(/_/g, ' ')}</dd>
                                        <dt>Plot</dt><dd>{result.plot.width_ft} × {result.plot.length_ft} ft</dd>
                                        <dt>Plot area</dt><dd>{result.plot.area_sqft} sqft</dd>
                                        <dt>Floors</dt><dd>{design.floors}</dd>
                                    </dl>
                                    <ul style={{ listStyle: 'none', padding: 0, margin: 0, fontSize: '0.76rem' }}>
                                        {floorItems.map((it) => (
                                            <li key={it._key}>
                                                <button onClick={() => setSelected(it._key)} style={{
                                                    display: 'flex', alignItems: 'center', gap: '0.45rem', width: '100%', padding: '0.2rem 0',
                                                    background: 'none', border: 'none', color: 'var(--text-2)', cursor: 'pointer', textAlign: 'left', font: 'inherit',
                                                }}>
                                                    <span aria-hidden="true" style={{ width: 10, height: 10, borderRadius: 2, flexShrink: 0, background: ROOM_COLORS[it.type] || ROOM_COLORS.other }} />
                                                    <span style={{ flex: 1 }}>{it.name}</span>
                                                    <span style={{ color: 'var(--text-3)' }}>{it.width}×{it.length} ft</span>
                                                </button>
                                            </li>
                                        ))}
                                    </ul>
                                    {analysis.reason && <p style={{ fontSize: '0.75rem', color: 'var(--text-3)', lineHeight: 1.55, marginTop: '0.9rem' }}>{analysis.reason}</p>}
                                    <Notes title="Assumptions" items={analysis.assumptions} />
                                    <Notes title="Privacy" items={result.architectural_requirements?.privacy} />
                                    <Notes title="Ventilation & light" items={[...(result.architectural_requirements?.ventilation || []), ...(result.architectural_requirements?.natural_light || [])]} />
                                    <Notes title="Parking & staircase" items={[...(result.architectural_requirements?.parking || []), ...(result.architectural_requirements?.staircase || [])]} />
                                    <Notes title="Validation notes" items={[...(validation.warnings || []), ...(validation.corrections || [])]} color="#fbbf24" />
                                    <p style={{ fontSize: '0.68rem', color: 'var(--text-3)', marginTop: '0.9rem', lineHeight: 1.5 }}>
                                        AI-generated concept layout ({validation.model}). Not an approved architectural drawing.
                                    </p>
                                </>
                            )}
                        </aside>
                    </div>
                </>
            )}
        </div>
    );
}
