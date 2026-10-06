import { Suspense, lazy, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import Navbar from '../components/Navbar';
import Footer from '../components/Footer';
import api from '../api';
import ReferenceAnalysis from '../components/ReferenceAnalysis';
import FloorPlanViewer from '../components/FloorPlanViewer';
import ModelToolbar from '../components/threeD/ModelToolbar';
import PlanImageImport from '../components/threeD/PlanImageImport';
import { LAST_PLAN_KEY } from '../components/floorPlanExport';
import { photoToPixels } from '../photoPixels';

// Three.js + React Three Fiber are large and only this page needs them, so
// the viewer is split out of the main bundle rather than loaded on every route.
const ThreeDViewer = lazy(() => import('../components/threeD/ThreeDViewer'));

const STORAGE_KEY = 'haven.design3d.brief';
const PHOTO_TYPES = ['image/jpeg', 'image/png', 'image/webp'];
const MAX_PHOTO_MB = 8;

const EXAMPLES = [
    '25 x 50 ft plot, 3 bedrooms, 2 bathrooms, kitchen, drawing room, TV lounge, car parking, double storey',
    '10 marla plot, 4 bedrooms, 3 bathrooms, kitchen, TV lounge, parking, double storey',
    '30 x 60 ft plot, single storey, 2 bedrooms, 1 bathroom, kitchen, TV lounge',
];

const ROOM_SWATCHES = {
    bedroom: '#86efac', bathroom: '#c4b5fd', kitchen: '#93c5fd',
    drawing_room: '#fca5a5', tv_lounge: '#fdba74', family_hall: '#fcd34d',
    store_room: '#d1d5db', stairs: '#fde68a', parking: '#cbd5e1',
    corridor: '#e5e7eb', terrace: '#a7f3d0', dining_room: '#a5f3fc',
    study: '#fbcfe8', prayer_room: '#f5d0fe', courtyard: '#6ee7b7', lawn: '#4ade80',
};

const SOURCES = [
    ['brief', '✍️ Describe requirements'],
    ['upload', '📐 Upload 2D design'],
    ['existing', '🗂️ Use existing 2D design'],
];

const DEFAULT_LAYERS = {
    showWalls: true, showRoof: true, transparentWalls: false,
    showDoors: true, showWindows: true, showFurniture: true,
};

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

function readLastPlan() {
    try {
        const raw = localStorage.getItem(LAST_PLAN_KEY);
        return raw ? JSON.parse(raw) : null;
    } catch {
        return null;
    }
}

/** The same room description the GLB carries in its extras, built from the
 *  model JSON (so the room list and 3D clicks select the same thing). */
function roomInfo(room, storey, model) {
    const ox = model.footprint.origin_x_ft || 0;
    const oy = model.footprint.origin_y_ft || 0;
    return {
        id: String(room.id), level: storey.level, label: room.label, type: room.type,
        x_ft: room.x + ox, y_ft: room.y + oy, width_ft: room.width, depth_ft: room.depth,
        area_sqft: Math.round(room.width * room.depth * 10) / 10,
        enclosed: room.enclosed !== false, group: room.group, detection: room.detection,
    };
}

const sameRoom = (a, b) => Boolean(a && b && a.level === b.level && a.id === b.id);

export default function ThreeDDesign() {
    const location = useLocation();
    const plan2d = location.state?.plan2d;

    const [source, setSource] = useState(plan2d ? 'existing' : 'brief');
    const [prompt, setPrompt] = useState('');
    const [width, setWidth] = useState('');
    const [length, setLength] = useState('');
    const [storeys, setStoreys] = useState('auto');
    const [loading, setLoading] = useState(false);
    const [loadingLabel, setLoadingLabel] = useState('');
    const [result, setResult] = useState(null);
    const [error, setError] = useState(null);
    const [notice, setNotice] = useState(null);
    const [photo, setPhoto] = useState(null);
    const [photoUrl, setPhotoUrl] = useState(null);
    const [photoPixels, setPhotoPixels] = useState(null);
    const [frontWindows, setFrontWindows] = useState('');
    const [garageDoor, setGarageDoor] = useState(false);
    const [existingBalcony, setExistingBalcony] = useState(false);
    const [lastPlan] = useState(readLastPlan);

    // Preview URL for the chosen photo, released when it changes.
    useEffect(() => {
        if (!photo) { setPhotoUrl(null); return undefined; }
        const url = URL.createObjectURL(photo);
        setPhotoUrl(url);
        return () => URL.revokeObjectURL(url);
    }, [photo]);

    const pickPhoto = (e) => {
        const file = e.target.files?.[0];
        e.target.value = '';
        if (!file) return;
        if (!PHOTO_TYPES.includes(file.type)) { setError('Please choose a JPEG, PNG or WebP photo.'); return; }
        if (file.size > MAX_PHOTO_MB * 1024 * 1024) { setError(`The photo must be smaller than ${MAX_PHOTO_MB} MB.`); return; }
        setError(null);
        setPhoto(file);
        setPhotoPixels(null);
        // Decoded here in the browser for the backend's built-in analyser.
        photoToPixels(file)
            .then(setPhotoPixels)
            .catch(() => { setPhoto(null); setError("That photo couldn't be read. Please try another JPEG, PNG or WebP file."); });
    };

    const removePhoto = () => {
        setPhoto(null);
        setPhotoPixels(null);
        setFrontWindows('');
        setGarageDoor(false);
        setExistingBalcony(false);
    };

    // ── Viewer state ──
    const [layers, setLayers] = useState(DEFAULT_LAYERS);
    const [levelFilter, setLevelFilter] = useState('all');
    const [selectedRoom, setSelectedRoom] = useState(null);
    const [viewRequest, setViewRequest] = useState(null);
    const requestView = (name) => setViewRequest((v) => ({ name, n: (v?.n || 0) + 1 }));

    // design.md 2.4 asks for a mobile-first layout; inline styles cannot carry
    // a media query, so the viewport/properties split collapses on narrow screens.
    const [narrow, setNarrow] = useState(() => typeof window !== 'undefined' && window.innerWidth < 900);
    useEffect(() => {
        const onResize = () => setNarrow(window.innerWidth < 900);
        window.addEventListener('resize', onResize);
        return () => window.removeEventListener('resize', onResize);
    }, []);

    const showResult = (data) => {
        setResult(data);
        setLevelFilter('all');
        setSelectedRoom(null);
        setLayers(DEFAULT_LAYERS);
    };

    /** Structured plan (2D module or reviewed image analysis) -> 3D model + GLB. */
    const buildFromPlan = useCallback(async (plan) => {
        setLoading(true);
        setLoadingLabel('Generating 3D model…');
        setError(null);
        setResult(null);
        try {
            showResult(await api.design3d.fromPlan2d(plan));
        } catch {
            setError("Couldn't build the 3D model from this plan. Make sure the backend is running, then try again.");
        } finally {
            setLoading(false);
        }
    }, []);

    // A plan sent from the 2D Design page ("View in 3D") arrives in the router
    // state; it is built once on arrival. Router state survives a page reload.
    const importedRef = useRef(false);
    useEffect(() => {
        if (!plan2d || importedRef.current) return;
        importedRef.current = true;
        buildFromPlan(plan2d);
    }, [plan2d, buildFromPlan]);

    const model = result?.status === 'FEASIBLE' ? result.model : null;
    const modelUrl = model ? api.design3d.modelUrl(result.glb?.model_url) : null;
    const levels = useMemo(() => (model ? model.storeys.map((s) => s.level) : []), [model]);
    const viewerOptions = useMemo(() => ({
        ...layers,
        visibleLevels: levelFilter === 'all' ? levels : [Number(levelFilter)],
    }), [layers, levelFilter, levels]);
    const existingPlan = plan2d || lastPlan;

    const selectRoom = (room) => {
        setSelectedRoom(room);
        if (room && levelFilter !== 'all' && Number(levelFilter) !== room.level) setLevelFilter(String(room.level));
    };

    const onView = (name) => {
        if (name === 'interior') {
            // Inside a room: show only its floor so upper storeys don't matter.
            const lvl = selectedRoom?.level ?? levels[0];
            if (lvl) setLevelFilter(String(lvl));
        }
        requestView(name);
    };

    const generate = async (e) => {
        e?.preventDefault();
        if ((!prompt.trim() && !photo) || loading || (photo && !photoPixels)) return;
        setLoading(true);
        setLoadingLabel(photo ? 'Analysing photo…' : 'Generating 3D model…');
        setError(null);
        setNotice(null);
        setResult(null);
        try {
            const data = photo ? await api.design3d.generateFromImage({
                image: photo,
                prompt,
                plotWidthFt: width ? parseFloat(width) : undefined,
                plotLengthFt: length ? parseFloat(length) : undefined,
                storeys: storeys === 'auto' ? undefined : parseInt(storeys, 10),
                pixels: photoPixels,
                existing: { frontWindows, garageDoor, balcony: existingBalcony },
            }) : await api.design3d.generate({
                prompt,
                plotWidthFt: width ? parseFloat(width) : undefined,
                plotLengthFt: length ? parseFloat(length) : undefined,
                storeys: storeys === 'auto' ? undefined : parseInt(storeys, 10),
            });
            showResult(data);
        } catch (err) {
            // Photo requests return readable reasons (bad file, AI quota); keep those.
            setError(photo && err.message && !err.message.startsWith('API error') && err.message !== 'Failed to fetch'
                ? err.message
                : "Couldn't reach the 3D design service. Make sure the backend is running, then try again.");
        } finally {
            setLoading(false);
        }
    };

    const saveBrief = () => {
        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify({ prompt, width, length, storeys }));
            setNotice('Design brief saved to this browser.');
        } catch {
            setNotice('Could not save — browser storage is unavailable.');
        }
    };

    const loadBrief = () => {
        try {
            const raw = localStorage.getItem(STORAGE_KEY);
            if (!raw) { setNotice('No saved design brief found.'); return; }
            const saved = JSON.parse(raw);
            setPrompt(saved.prompt ?? '');
            setWidth(saved.width ?? '');
            setLength(saved.length ?? '');
            setStoreys(saved.storeys ?? 'auto');
            setNotice('Saved brief loaded — press Generate to rebuild it.');
        } catch {
            setNotice('Could not load the saved brief.');
        }
    };

    return (
        <>
            <Navbar />
            <section className="page-hero">
                <div className="page-hero-inner">
                    <div className="page-hero-icon">🏛️</div>
                    <div>
                        <h1>3D Design Visualizer</h1>
                        <p>Describe your plot and requirements, upload a 2D floor plan, or use a design from
                            HAVEN's 2D Design page. The backend reads the architecture, builds exact 3D geometry,
                            and you explore it here — orbit, zoom, pan, look inside and inspect each room.</p>
                    </div>
                </div>
            </section>

            <div className="page-content" style={{ maxWidth: '1180px' }}>
                {/* ── Input source ── */}
                <div role="tablist" aria-label="How to create the 3D design" style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginBottom: '1rem' }}>
                    {SOURCES.map(([key, label]) => (
                        <button key={key} type="button" role="tab" aria-selected={source === key}
                            onClick={() => setSource(key)} style={{ ...btn(source === key), padding: '0.55rem 1rem', fontSize: '0.82rem' }}>
                            {label}
                        </button>
                    ))}
                </div>

                {source === 'brief' && (
                    <form onSubmit={generate} style={{
                        background: 'var(--surface)', border: '1px solid var(--border)',
                        borderRadius: 'var(--radius)', padding: '1.25rem', marginBottom: '1.25rem',
                    }}>
                        <label htmlFor="brief" style={{ display: 'block', fontSize: '0.78rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--text-3)', marginBottom: '0.5rem' }}>
                            Your requirements
                        </label>
                        <textarea
                            id="brief"
                            value={prompt}
                            onChange={(e) => setPrompt(e.target.value)}
                            placeholder='e.g. "25 x 50 ft plot, 3 bedrooms, 2 bathrooms, kitchen, drawing room, TV lounge, car parking, double storey"'
                            rows={3}
                            style={{ ...field, width: '100%', resize: 'vertical', marginBottom: '0.75rem' }}
                        />

                        {/* Optional photo of the existing property */}
                        <div style={{
                            display: 'flex', gap: '0.8rem', alignItems: 'center', flexWrap: 'wrap',
                            border: '1.5px dashed var(--border)', borderRadius: '10px', padding: '0.7rem 0.8rem', marginBottom: '0.75rem',
                        }}>
                            {photoUrl ? (
                                <img src={photoUrl} alt="Selected property photo" style={{ width: 88, height: 64, objectFit: 'cover', borderRadius: 6 }} />
                            ) : (
                                <span aria-hidden="true" style={{ fontSize: '1.6rem' }}>🏠</span>
                            )}
                            <div style={{ flex: 1, minWidth: 200 }}>
                                <div style={{ fontSize: '0.82rem', fontWeight: 600, color: 'var(--text)' }}>
                                    {photo ? photo.name : 'Photo of your existing property (optional)'}
                                </div>
                                <div style={{ fontSize: '0.72rem', color: 'var(--text-3)', lineHeight: 1.5 }}>
                                    {photo
                                        ? 'Used as a visual reference only. Give the plot size and number of storeys, describe the changes you want above, and tell us what is on the front now.'
                                        : `JPEG, PNG or WebP, up to ${MAX_PHOTO_MB} MB. Used as a reference, not as exact measurements.`}
                                </div>
                                {photo && (
                                    <div style={{ display: 'flex', gap: '0.9rem', flexWrap: 'wrap', alignItems: 'center', marginTop: '0.45rem', fontSize: '0.74rem', color: 'var(--text-2)' }}>
                                        <span style={{ color: 'var(--text-3)' }}>What's on the front now:</span>
                                        <label style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}>
                                            Windows per floor
                                            <input type="number" min="0" max="12" value={frontWindows} placeholder="auto"
                                                onChange={(e) => setFrontWindows(e.target.value)}
                                                style={{ ...field, width: 64, padding: '0.25rem 0.4rem', fontSize: '0.74rem' }} />
                                        </label>
                                        <label style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem', cursor: 'pointer' }}>
                                            <input type="checkbox" checked={garageDoor} onChange={(e) => setGarageDoor(e.target.checked)} /> Garage door
                                        </label>
                                        <label style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem', cursor: 'pointer' }}>
                                            <input type="checkbox" checked={existingBalcony} onChange={(e) => setExistingBalcony(e.target.checked)} /> Balcony
                                        </label>
                                    </div>
                                )}
                            </div>
                            <label style={{ ...btn(false), display: 'inline-block' }}>
                                {photo ? 'Change photo' : 'Upload photo'}
                                <input type="file" accept={PHOTO_TYPES.join(',')} onChange={pickPhoto} style={{ display: 'none' }} />
                            </label>
                            {photo && <button type="button" onClick={removePhoto} style={btn(false)}>Remove</button>}
                        </div>

                        <div style={{ display: 'flex', gap: '0.6rem', flexWrap: 'wrap', alignItems: 'center' }}>
                            <input style={{ ...field, width: 150 }} type="number" min="0" placeholder="Width ft (optional)"
                                value={width} onChange={(e) => setWidth(e.target.value)} aria-label="Plot width in feet" />
                            <input style={{ ...field, width: 150 }} type="number" min="0" placeholder="Length ft (optional)"
                                value={length} onChange={(e) => setLength(e.target.value)} aria-label="Plot length in feet" />
                            <select style={{ ...field, width: 165 }} value={storeys}
                                onChange={(e) => setStoreys(e.target.value)} aria-label="Number of storeys">
                                <option value="auto">Storeys: auto</option>
                                <option value="1">Single storey</option>
                                <option value="2">Double storey</option>
                            </select>
                            <button type="submit" disabled={loading} style={{
                                ...btn(true), padding: '0.55rem 1.4rem', opacity: loading ? 0.6 : 1,
                                cursor: loading ? 'wait' : 'pointer',
                            }}>
                                {loading ? (photo ? 'Analysing photo…' : 'Generating…') : (photo ? 'Generate from Photo' : 'Generate 3D Model')}
                            </button>
                            <button type="button" onClick={saveBrief} style={btn(false)}>Save</button>
                            <button type="button" onClick={loadBrief} style={btn(false)}>Load</button>
                        </div>

                        <div style={{ marginTop: '0.85rem', display: 'flex', gap: '0.5rem', flexWrap: 'wrap', alignItems: 'center' }}>
                            <span style={{ fontSize: '0.72rem', color: 'var(--text-3)' }}>Try:</span>
                            {EXAMPLES.map((ex, i) => (
                                <button key={i} type="button" onClick={() => setPrompt(ex)}
                                    style={{ ...btn(false), fontSize: '0.72rem', padding: '0.3rem 0.7rem' }}>
                                    {ex.split(',')[0]}…
                                </button>
                            ))}
                        </div>
                        {notice && <p style={{ marginTop: '0.6rem', fontSize: '0.78rem', color: 'var(--text-3)' }}>{notice}</p>}
                    </form>
                )}

                {source === 'upload' && <PlanImageImport onBuild={buildFromPlan} building={loading} />}

                {source === 'existing' && (
                    <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius)', padding: '1.1rem', marginBottom: '1.25rem' }}>
                        {existingPlan?.design ? (
                            <div style={{ display: 'flex', gap: '1.1rem', flexWrap: 'wrap', alignItems: 'center' }}>
                                <div style={{ width: 170, flexShrink: 0, borderRadius: 8, overflow: 'hidden' }}>
                                    <FloorPlanViewer plot={existingPlan.plot} floor={existingPlan.design.ground_floor} />
                                </div>
                                <div style={{ flex: 1, minWidth: 220 }}>
                                    <div style={{ fontWeight: 700, fontSize: '0.92rem', marginBottom: '0.3rem' }}>
                                        {plan2d ? 'Plan sent from 2D Design' : 'Your latest 2D design'}
                                    </div>
                                    <p style={{ fontSize: '0.82rem', color: 'var(--text-2)', marginBottom: '0.7rem' }}>
                                        {existingPlan.plot?.width_ft} × {existingPlan.plot?.length_ft} ft plot,{' '}
                                        {existingPlan.design.floors} floor{existingPlan.design.floors === 2 ? 's' : ''}. Its rooms,
                                        doors and windows are used directly — no image analysis is needed.
                                    </p>
                                    <div style={{ display: 'flex', gap: '0.6rem', flexWrap: 'wrap' }}>
                                        <button type="button" disabled={loading} onClick={() => buildFromPlan(existingPlan)}
                                            style={{ ...btn(true), opacity: loading ? 0.6 : 1 }}>
                                            {loading ? 'Generating 3D model…' : 'Build this design in 3D'}
                                        </button>
                                        <Link to="/2d-design" style={{ ...btn(false), textDecoration: 'none' }}>Open 2D Design</Link>
                                    </div>
                                </div>
                            </div>
                        ) : (
                            <p style={{ fontSize: '0.86rem', color: 'var(--text-2)' }}>
                                No 2D design yet. Create one on the <Link to="/2d-design" style={{ color: 'var(--accent)', fontWeight: 600 }}>2D Design page</Link>{' '}
                                — it will appear here, or use its "View in 3D" button.
                            </p>
                        )}
                    </div>
                )}

                {loading && (
                    <div aria-live="polite" data-testid="page-loading" style={{
                        background: 'rgba(59,130,246,0.08)', border: '1px solid rgba(59,130,246,0.3)',
                        padding: '0.8rem 1.1rem', borderRadius: '10px', marginBottom: '1.25rem',
                        fontSize: '0.85rem', color: 'var(--text-2)',
                    }}>
                        {loadingLabel}
                    </div>
                )}

                {error && (
                    <div role="alert" style={{
                        background: 'rgba(220,38,38,0.1)', border: '1px solid rgba(220,38,38,0.3)',
                        color: '#fca5a5', padding: '0.9rem 1.1rem', borderRadius: '10px', marginBottom: '1.25rem',
                    }}>⚠ {error}</div>
                )}

                {result && result.status !== 'FEASIBLE' && (
                    <div role="alert" style={{
                        background: 'rgba(217,119,6,0.1)', border: '1px solid rgba(217,119,6,0.3)',
                        padding: '1.1rem 1.25rem', borderRadius: '10px', marginBottom: '1.25rem',
                    }}>
                        <div style={{ fontWeight: 700, color: '#fbbf24', marginBottom: '0.4rem' }}>
                            {result.status.replace(/_/g, ' ')}
                        </div>
                        <p style={{ fontSize: '0.88rem', color: 'var(--text-2)', lineHeight: 1.6 }}>{result.message}</p>
                        {result.suggestion && (
                            <p style={{ fontSize: '0.88rem', color: 'var(--text-2)', marginTop: '0.5rem' }}>
                                <strong>Suggestion:</strong> {result.suggestion}
                            </p>
                        )}
                        {result.clarifications?.length > 0 && (
                            <ul style={{ fontSize: '0.86rem', color: 'var(--text-2)', marginTop: '0.6rem', paddingLeft: '1.1rem', lineHeight: 1.6 }}>
                                {result.clarifications.map((q, i) => (
                                    <li key={i}><strong>{q.question}</strong>{q.reason ? <span style={{ color: 'var(--text-3)' }}> — {q.reason}</span> : null}</li>
                                ))}
                            </ul>
                        )}
                        {result.status === 'NEEDS_CLARIFICATION' && (
                            <p style={{ fontSize: '0.8rem', color: 'var(--text-3)', marginTop: '0.6rem' }}>
                                Add the answers to your description or the form fields, then generate again.
                            </p>
                        )}
                    </div>
                )}

                {model && (
                    <>
                        {result.source === 'plan2d' && (
                            <p style={{ fontSize: '0.8rem', color: 'var(--text-3)', marginBottom: '0.6rem' }}>
                                {result.message}{' '}
                                {plan2d && <Link to="/2d-design" style={{ color: 'var(--accent)', fontWeight: 600 }}>← Back to 2D Design</Link>}
                            </p>
                        )}

                        <ModelToolbar
                            layers={layers}
                            onToggle={(key) => setLayers((l) => ({ ...l, [key]: !l[key] }))}
                            storeys={model.storeys}
                            levelFilter={levelFilter}
                            onLevel={setLevelFilter}
                            onView={onView}
                            onReset={() => { setLayers(DEFAULT_LAYERS); setLevelFilter('all'); setSelectedRoom(null); requestView('exterior'); }}
                        />

                        <div style={{
                            display: 'grid',
                            gridTemplateColumns: narrow ? 'minmax(0,1fr)' : 'minmax(0,1fr) 290px',
                            gap: '1.1rem', alignItems: 'start',
                        }}>
                            {/* ── Viewport ── */}
                            <div style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius)', overflow: 'hidden' }}>
                                {modelUrl ? (
                                    <Suspense fallback={
                                        <div style={{ height: narrow ? 380 : 540, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-3)', fontSize: '0.85rem' }}>
                                            Loading 3D viewer…
                                        </div>
                                    }>
                                        <ThreeDViewer
                                            url={modelUrl}
                                            height={narrow ? 380 : 540}
                                            options={viewerOptions}
                                            selected={selectedRoom}
                                            onSelectRoom={selectRoom}
                                            viewRequest={viewRequest}
                                        />
                                    </Suspense>
                                ) : (
                                    <div role="alert" style={{ height: 220, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '1rem', textAlign: 'center', color: 'var(--text-2)', fontSize: '0.86rem' }}>
                                        {result.glb_error || 'The 3D model file is not available for this design.'}
                                    </div>
                                )}
                                <div style={{ padding: '0.5rem 0.85rem', fontSize: '0.72rem', color: 'var(--text-3)', background: 'var(--surface)', borderTop: '1px solid var(--border)' }}>
                                    Drag to orbit · scroll to zoom · right-drag to pan · click a room to inspect it
                                </div>
                            </div>

                            {/* ── Properties panel ── */}
                            <aside style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius)', padding: '1rem' }}>
                                {selectedRoom && (
                                    <div data-testid="room-card" style={{ border: '1.5px solid rgba(59,130,246,0.45)', borderRadius: 10, padding: '0.75rem', marginBottom: '1rem', background: 'rgba(59,130,246,0.06)' }}>
                                        <div style={{ display: 'flex', justifyContent: 'space-between', gap: '0.5rem', alignItems: 'baseline' }}>
                                            <h3 style={{ fontFamily: 'Syne, sans-serif', fontSize: '0.95rem', fontWeight: 700 }}>{selectedRoom.label}</h3>
                                            <button type="button" onClick={() => setSelectedRoom(null)} aria-label="Clear selection"
                                                style={{ background: 'none', border: 'none', color: 'var(--text-3)', cursor: 'pointer' }}>✕</button>
                                        </div>
                                        <dl style={{ fontSize: '0.78rem', color: 'var(--text-2)', display: 'grid', gridTemplateColumns: '1fr auto', rowGap: '0.25rem', marginTop: '0.4rem' }}>
                                            <dt>Type</dt><dd>{String(selectedRoom.type).replace(/_/g, ' ')}</dd>
                                            <dt>Floor</dt><dd>{model.storeys.find((s) => s.level === selectedRoom.level)?.label}</dd>
                                            <dt>Size</dt><dd>{selectedRoom.group ? 'part of an L-shaped room' : `${selectedRoom.width_ft} × ${selectedRoom.depth_ft} ft`}</dd>
                                            <dt>Area</dt><dd>{selectedRoom.area_sqft} sq ft</dd>
                                            {selectedRoom.detection && (
                                                <><dt>Type from</dt><dd>{({ user: 'you', unknown: 'not identified' })[selectedRoom.detection.type_source] || 'inferred'}</dd></>
                                            )}
                                        </dl>
                                        <button type="button" onClick={() => onView('interior')} style={{ ...btn(false), marginTop: '0.55rem', fontSize: '0.72rem', padding: '0.3rem 0.7rem' }}>
                                            Look inside
                                        </button>
                                    </div>
                                )}

                                <h3 style={{ fontFamily: 'Syne, sans-serif', fontSize: '0.95rem', fontWeight: 700, marginBottom: '0.65rem' }}>
                                    Model properties
                                </h3>
                                <dl style={{ fontSize: '0.8rem', color: 'var(--text-2)', display: 'grid', gridTemplateColumns: '1fr auto', rowGap: '0.3rem', marginBottom: '1rem' }}>
                                    <dt>Plot</dt><dd>{model.plot.width_ft} × {model.plot.length_ft} ft</dd>
                                    <dt>Building</dt><dd>{model.footprint.width_ft} × {model.footprint.depth_ft} ft</dd>
                                    <dt>Storeys</dt><dd>{model.totals.storeys}</dd>
                                    <dt>Covered area</dt><dd>{model.totals.covered_area_sqft} sqft</dd>
                                    <dt>Height</dt><dd>{model.totals.building_height_ft} ft</dd>
                                </dl>

                                {model.storeys.map((storey) => (
                                    <div key={storey.level} style={{ marginBottom: '0.9rem' }}>
                                        <h4 style={{ fontSize: '0.8rem', fontWeight: 700, marginBottom: '0.4rem' }}>
                                            {storey.label} <span style={{ color: 'var(--text-3)', fontWeight: 400 }}>
                                                ({storey.covered_area_sqft} sqft)
                                            </span>
                                        </h4>
                                        <ul style={{ listStyle: 'none', padding: 0, margin: 0, fontSize: '0.76rem' }}>
                                            {storey.rooms.map((room) => {
                                                const info = roomInfo(room, storey, model);
                                                const active = sameRoom(info, selectedRoom);
                                                return (
                                                    <li key={room.id}>
                                                        <button type="button" onClick={() => selectRoom(active ? null : info)} aria-pressed={active}
                                                            style={{
                                                                display: 'flex', alignItems: 'center', gap: '0.45rem', width: '100%', textAlign: 'left',
                                                                padding: '0.2rem 0.3rem', borderRadius: 6, cursor: 'pointer', font: 'inherit',
                                                                color: 'var(--text-2)', border: 'none',
                                                                background: active ? 'rgba(59,130,246,0.15)' : 'transparent',
                                                            }}>
                                                            <span aria-hidden="true" style={{
                                                                width: 10, height: 10, borderRadius: 2, flexShrink: 0,
                                                                background: ROOM_SWATCHES[room.type] ?? '#e5e7eb',
                                                            }} />
                                                            <span style={{ flex: 1 }}>{room.label}</span>
                                                            <span style={{ color: 'var(--text-3)' }}>{room.width}×{room.depth} ft</span>
                                                        </button>
                                                    </li>
                                                );
                                            })}
                                        </ul>
                                    </div>
                                ))}

                                {result.assumptions?.length > 0 && (
                                    <details style={{ fontSize: '0.72rem', color: 'var(--text-3)' }}>
                                        <summary style={{ cursor: 'pointer', fontWeight: 600 }}>Assumptions</summary>
                                        <ul style={{ paddingLeft: '1rem', marginTop: '0.4rem', lineHeight: 1.5 }}>
                                            {result.assumptions.map((a, i) => <li key={i} style={{ marginBottom: '0.3rem' }}>{a}</li>)}
                                            {result.glb?.metadata?.furniture_pieces > 0 && (
                                                <li>Furniture is indicative only, placed automatically to give a sense of scale.</li>
                                            )}
                                        </ul>
                                    </details>
                                )}
                            </aside>
                        </div>
                    </>
                )}

                {result?.reference && <ReferenceAnalysis result={result} photoUrl={photoUrl} />}
            </div>
            <Footer />
        </>
    );
}
