import { useEffect, useState } from 'react';
import api from '../../api';
import FloorPlanViewer from '../FloorPlanViewer';
import { FLOORS, ROOM_TYPES, confidenceWord, reviewRows, typeLabel, updateRoom, withIds } from './planReview';

// Upload a 2D floor-plan image -> backend analysis (Layer 1) -> the user
// reviews what was detected -> onBuild(plan) hands it to the 3D engine.

const IMAGE_TYPES = ['image/png', 'image/jpeg', 'image/webp'];
const MAX_MB = 8;

const field = {
    background: 'var(--surface)', border: '1.5px solid var(--border)',
    color: 'var(--text)', padding: '0.5rem 0.7rem', borderRadius: '8px',
    fontFamily: 'Inter, sans-serif', fontSize: '0.84rem',
};
const btn = (primary, disabled) => ({
    background: primary ? 'rgba(59,130,246,0.15)' : 'var(--surface)',
    border: `1.5px solid ${primary ? 'rgba(59,130,246,0.5)' : 'var(--border)'}`,
    color: primary ? 'var(--accent)' : 'var(--text-2)',
    padding: '0.5rem 1.1rem', borderRadius: '8px', fontFamily: 'Inter, sans-serif',
    fontSize: '0.8rem', fontWeight: 600, cursor: disabled ? 'not-allowed' : 'pointer', opacity: disabled ? 0.55 : 1,
});
const panel = {
    background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius)', padding: '1.1rem',
};
const small = { fontSize: '0.74rem', color: 'var(--text-3)', lineHeight: 1.55 };

function FactList({ title, items, tone }) {
    if (!items?.length) return null;
    return (
        <div style={{ marginBottom: '0.55rem' }}>
            <div style={{ fontSize: '0.7rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.07em', color: tone }}>{title}</div>
            <ul style={{ margin: '0.2rem 0 0', paddingLeft: '1.05rem', fontSize: '0.78rem', color: 'var(--text-2)', lineHeight: 1.5 }}>
                {items.map((t, i) => <li key={i}>{t}</li>)}
            </ul>
        </div>
    );
}

export default function PlanImageImport({ onBuild, building }) {
    const [file, setFile] = useState(null);
    const [previewUrl, setPreviewUrl] = useState(null);
    const [width, setWidth] = useState('');
    const [depth, setDepth] = useState('');
    const [front, setFront] = useState('bottom');
    const [analyzing, setAnalyzing] = useState(false);
    const [result, setResult] = useState(null);
    const [plan, setPlan] = useState(null);
    const [error, setError] = useState(null);
    const [checked, setChecked] = useState(false);

    useEffect(() => {
        if (!file) { setPreviewUrl(null); return undefined; }
        const url = URL.createObjectURL(file);
        setPreviewUrl(url);
        return () => URL.revokeObjectURL(url);
    }, [file]);

    const pick = (e) => {
        const f = e.target.files?.[0];
        e.target.value = '';
        if (!f) return;
        setResult(null);
        setPlan(null);
        if (!IMAGE_TYPES.includes(f.type)) { setError('Please choose a PNG, JPEG or WebP image of the floor plan.'); return; }
        if (f.size > MAX_MB * 1024 * 1024) { setError(`The image must be smaller than ${MAX_MB} MB.`); return; }
        if (f.size === 0) { setError('That file is empty.'); return; }
        setError(null);
        setFile(f);
    };

    const analyze = async (e) => {
        e?.preventDefault();
        if (!file || analyzing) return;
        setAnalyzing(true);
        setError(null);
        setResult(null);
        setPlan(null);
        setChecked(false);
        try {
            const data = await api.design3d.analyzePlan({
                image: file,
                widthFt: width ? parseFloat(width) : undefined,
                depthFt: depth ? parseFloat(depth) : undefined,
                front,
            });
            setResult(data);
            if (data.status === 'ANALYZED') setPlan(withIds(data.plan));
        } catch (err) {
            setError(err.status && !err.message.startsWith('API error')
                ? err.message
                : "Couldn't reach the floor-plan analysis service. Make sure the backend is running, then try again.");
        } finally {
            setAnalyzing(false);
        }
    };

    const analysis = result?.analysis;
    const rows = plan ? reviewRows(plan) : [];
    const twoFloors = plan?.design?.floors === 2;
    const lowConfidence = Boolean(analysis?.low_confidence);
    const canBuild = plan && !building && (!lowConfidence || checked);

    return (
        <div>
            <form onSubmit={analyze} style={{ ...panel, marginBottom: '1.1rem' }}>
                <div style={{ display: 'flex', gap: '0.9rem', alignItems: 'center', flexWrap: 'wrap', border: '1.5px dashed var(--border)', borderRadius: 10, padding: '0.75rem 0.85rem', marginBottom: '0.8rem' }}>
                    {previewUrl
                        ? <img src={previewUrl} alt="Selected floor plan" style={{ width: 96, height: 72, objectFit: 'contain', background: '#fff', borderRadius: 6 }} />
                        : <span aria-hidden="true" style={{ fontSize: '1.7rem' }}>📐</span>}
                    <div style={{ flex: 1, minWidth: 220 }}>
                        <div style={{ fontSize: '0.84rem', fontWeight: 600, color: 'var(--text)' }}>{file ? file.name : 'Upload 2D Design'}</div>
                        <div style={small}>
                            A top-down floor plan (PNG, JPEG or WebP, up to {MAX_MB} MB) with dark walls on a light
                            background. A PNG downloaded from HAVEN's 2D Design page is read exactly.
                        </div>
                    </div>
                    <label style={{ ...btn(false, false), display: 'inline-block' }}>
                        {file ? 'Change image' : 'Choose image'}
                        <input type="file" accept={IMAGE_TYPES.join(',')} onChange={pick} style={{ display: 'none' }} data-testid="plan-file" />
                    </label>
                </div>

                <div style={{ display: 'flex', gap: '0.6rem', flexWrap: 'wrap', alignItems: 'center' }}>
                    <input style={{ ...field, width: 170 }} type="number" min="8" max="400" step="0.1" placeholder="Overall width ft"
                        value={width} onChange={(e) => setWidth(e.target.value)} aria-label="Overall width of the drawn plan in feet" />
                    <input style={{ ...field, width: 170 }} type="number" min="8" max="400" step="0.1" placeholder="Overall depth ft"
                        value={depth} onChange={(e) => setDepth(e.target.value)} aria-label="Overall depth of the drawn plan in feet" />
                    <select style={{ ...field, width: 190 }} value={front} onChange={(e) => setFront(e.target.value)} aria-label="Which side of the image faces the road">
                        <option value="bottom">Road at bottom of image</option>
                        <option value="top">Road at top of image</option>
                        <option value="left">Road at left of image</option>
                        <option value="right">Road at right of image</option>
                    </select>
                    <button type="submit" disabled={!file || analyzing} style={btn(true, !file || analyzing)}>
                        {analyzing ? 'Analyzing your floor plan…' : 'Analyze floor plan'}
                    </button>
                </div>
                <p style={{ ...small, marginTop: '0.55rem' }}>
                    Width and depth are the outside-wall-to-outside-wall size of the drawn plan. Printed measurements
                    are not read from the image, so at least one is needed to build the model to scale.
                </p>
            </form>

            {analyzing && (
                <div style={{ ...panel, marginBottom: '1.1rem', color: 'var(--text-2)', fontSize: '0.86rem' }} aria-live="polite">
                    Analyzing your floor plan… finding walls, rooms, doors and windows.
                </div>
            )}

            {error && (
                <div role="alert" style={{ background: 'rgba(220,38,38,0.1)', border: '1px solid rgba(220,38,38,0.3)', color: '#fca5a5', padding: '0.85rem 1.05rem', borderRadius: 10, marginBottom: '1.1rem' }}>
                    ⚠ {error}
                </div>
            )}

            {result && result.status !== 'ANALYZED' && (
                <div role="alert" style={{ background: 'rgba(217,119,6,0.1)', border: '1px solid rgba(217,119,6,0.3)', padding: '1rem 1.15rem', borderRadius: 10, marginBottom: '1.1rem' }}>
                    <div style={{ fontWeight: 700, color: '#fbbf24', marginBottom: '0.35rem' }}>{result.status.replace(/_/g, ' ')}</div>
                    <p style={{ fontSize: '0.86rem', color: 'var(--text-2)', lineHeight: 1.6 }}>{result.message}</p>
                    {analysis?.counts?.rooms != null && (
                        <p style={{ ...small, marginTop: '0.4rem' }}>{analysis.counts.rooms} enclosed room(s) were found in the drawing.</p>
                    )}
                    {analysis?.hint && <p style={{ ...small, marginTop: '0.25rem' }}>{analysis.hint}</p>}
                </div>
            )}

            {plan && analysis && (
                <section style={{ ...panel, marginBottom: '1.1rem' }} aria-label="Review the analysed floor plan">
                    <h3 style={{ fontFamily: 'Syne, sans-serif', fontSize: '1rem', fontWeight: 700, marginBottom: '0.3rem' }}>Review the floor plan</h3>
                    <p style={{ fontSize: '0.84rem', color: 'var(--text-2)', marginBottom: '0.8rem' }}>{result.message}</p>

                    {lowConfidence && (
                        <div role="alert" style={{ background: 'rgba(217,119,6,0.1)', border: '1px solid rgba(217,119,6,0.35)', padding: '0.7rem 0.9rem', borderRadius: 8, marginBottom: '0.8rem', fontSize: '0.82rem', color: 'var(--text-2)' }}>
                            <strong style={{ color: '#fbbf24' }}>Low confidence.</strong> Parts of this drawing were hard to read.
                            Compare the layout below with your image before building it in 3D.
                        </div>
                    )}

                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '1rem', marginBottom: '0.9rem' }}>
                        <figure style={{ margin: 0 }}>
                            <figcaption style={{ ...small, marginBottom: '0.3rem' }}>Your image</figcaption>
                            <img src={previewUrl} alt="Uploaded floor plan" style={{ width: '100%', maxHeight: 420, objectFit: 'contain', background: '#fff', borderRadius: 8 }} />
                        </figure>
                        <figure style={{ margin: 0 }}>
                            <figcaption style={{ ...small, marginBottom: '0.3rem' }}>
                                What was read ({plan.plot.width_ft} × {plan.plot.length_ft} ft)
                            </figcaption>
                            <div style={{ borderRadius: 8, overflow: 'hidden', maxHeight: 420 }}>
                                <FloorPlanViewer plot={plan.plot} floor={plan.design.ground_floor} />
                            </div>
                        </figure>
                    </div>

                    <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginBottom: '0.8rem' }}>
                        {Object.entries(analysis.confidence || {}).filter(([k]) => k !== 'overall').map(([k, v]) => (
                            <span key={k} title={`${Math.round(v * 100)}%`} style={{ fontSize: '0.72rem', padding: '0.2rem 0.55rem', borderRadius: 999, border: '1px solid var(--border)', color: 'var(--text-2)' }}>
                                {k.replace(/_/g, ' ')}: <strong>{confidenceWord(v)}</strong>
                            </span>
                        ))}
                    </div>

                    <div style={{ overflowX: 'auto', marginBottom: '0.9rem' }}>
                        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem' }}>
                            <thead>
                                <tr style={{ textAlign: 'left', color: 'var(--text-3)' }}>
                                    {twoFloors && <th style={{ padding: '0.35rem' }}>Floor</th>}
                                    <th style={{ padding: '0.35rem' }}>Name</th>
                                    <th style={{ padding: '0.35rem' }}>Type</th>
                                    <th style={{ padding: '0.35rem' }}>Size</th>
                                    <th style={{ padding: '0.35rem' }}>How it was identified</th>
                                </tr>
                            </thead>
                            <tbody>
                                {rows.map((r) => (
                                    <tr key={r.key} style={{ borderTop: '1px solid var(--border)' }}>
                                        {twoFloors && <td style={{ padding: '0.3rem', color: 'var(--text-3)' }}>{FLOORS.find(([k]) => k === r.floor)[1]}</td>}
                                        <td style={{ padding: '0.3rem' }}>
                                            <input value={r.name} maxLength={40} aria-label={`Name of ${r.name}`}
                                                onChange={(e) => setPlan((p) => updateRoom(p, r.key, { name: e.target.value }))}
                                                style={{ ...field, padding: '0.3rem 0.5rem', width: '100%', minWidth: 120 }} />
                                        </td>
                                        <td style={{ padding: '0.3rem' }}>
                                            <select value={r.type} aria-label={`Type of ${r.name}`}
                                                onChange={(e) => setPlan((p) => updateRoom(p, r.key, { type: e.target.value }))}
                                                style={{ ...field, padding: '0.3rem 0.5rem' }}>
                                                {ROOM_TYPES.map((t) => <option key={t} value={t}>{typeLabel(t)}</option>)}
                                            </select>
                                        </td>
                                        <td style={{ padding: '0.3rem', color: 'var(--text-2)', whiteSpace: 'nowrap' }}>
                                            {r.parts > 1 ? `${Math.round(r.area)} sq ft (${r.parts} parts)` : `${r.width} × ${r.length} ft`}
                                        </td>
                                        <td style={{ padding: '0.3rem', color: 'var(--text-3)' }}>
                                            {({
                                                user: 'Set by you',
                                                inferred_from_colour_legend: 'Type from HAVEN colour legend',
                                                inferred_from_stair_hatching: 'Stairs from tread lines',
                                                unknown: 'Shape detected; type unknown',
                                            })[r.detection?.type_source] || (analysis.method === 'embedded_plan' ? 'Exact (from file)' : 'Detected')}
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>

                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '0.4rem 1.2rem', marginBottom: '0.6rem' }}>
                        <FactList title="Detected in the image" items={analysis.detected} tone="#60a5fa" />
                        <FactList title="Given explicitly" items={analysis.explicit} tone="#34d399" />
                        <FactList title="Inferred" items={analysis.inferred} tone="#fbbf24" />
                        <FactList title="Missing / not read" items={analysis.missing} tone="#f87171" />
                    </div>
                    {analysis.warnings?.length > 0 && (
                        <details style={{ ...small, marginBottom: '0.8rem' }}>
                            <summary style={{ cursor: 'pointer', fontWeight: 600 }}>Notes ({analysis.warnings.length})</summary>
                            <ul style={{ paddingLeft: '1rem', marginTop: '0.3rem' }}>{analysis.warnings.map((w, i) => <li key={i}>{w}</li>)}</ul>
                        </details>
                    )}

                    <div style={{ display: 'flex', gap: '0.8rem', flexWrap: 'wrap', alignItems: 'center' }}>
                        {lowConfidence && (
                            <label style={{ display: 'inline-flex', gap: '0.4rem', alignItems: 'center', fontSize: '0.8rem', color: 'var(--text-2)', cursor: 'pointer' }}>
                                <input type="checkbox" checked={checked} onChange={(e) => setChecked(e.target.checked)} />
                                I've checked the layout matches my plan
                            </label>
                        )}
                        <button type="button" disabled={!canBuild} onClick={() => onBuild(plan)} style={btn(true, !canBuild)}>
                            {building ? 'Generating 3D model…' : 'Generate 3D model'}
                        </button>
                    </div>
                </section>
            )}
        </div>
    );
}
