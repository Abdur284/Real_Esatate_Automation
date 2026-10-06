// Shows what the backend read from an uploaded property photo, kept strictly
// apart: what was visible, what a photo cannot tell, what the user asked to
// change, and what was kept. Also shows the optional photorealistic render.

const card = {
    background: 'var(--surface)', border: '1px solid var(--border)',
    borderRadius: 'var(--radius)', padding: '1rem',
};
const h3 = { fontFamily: 'Syne, sans-serif', fontSize: '0.92rem', fontWeight: 700, marginBottom: '0.55rem' };
const list = { paddingLeft: '1.05rem', margin: 0, fontSize: '0.8rem', color: 'var(--text-2)', lineHeight: 1.6 };

function Swatch({ label, color }) {
    if (!color) return null;
    return (
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem', fontSize: '0.72rem', color: 'var(--text-3)', marginRight: '0.8rem' }}>
            <span aria-hidden="true" style={{ width: 14, height: 14, borderRadius: 3, background: color, border: '1px solid var(--border)' }} />
            {label}
        </span>
    );
}

function elevationText(rows) {
    return (rows || []).map((r) => {
        const bits = [`${r.doors ?? 0} door(s)`, `${r.windows ?? 0} window(s)`];
        if (r.garage_door) bits.push('garage door');
        if (r.balcony) bits.push('balcony');
        return `Level ${r.level}: ${bits.join(', ')}`;
    });
}

export default function ReferenceAnalysis({ result, photoUrl }) {
    const ref = result?.reference;
    if (!ref) return null;
    const observed = ref.observed || {};
    const request = ref.request || {};
    const proposed = ref.proposed || {};
    const render = result.render;

    const seen = [
        observed.building_type,
        observed.visible_floors != null && (observed.floors_confidence === 'provided by you'
            ? `${observed.visible_floors} floor(s) (provided by you)`
            : `${observed.visible_floors} visible floor(s) (${observed.floors_confidence || 'unknown'} confidence)`),
        ...elevationText(observed.front_elevation),
        observed.roof && `Roof: ${observed.roof.type}${observed.roof.parapet ? ', with parapet' : ''}${observed.roof.terrace_visible ? ', terrace visible' : ''}`,
        observed.exterior_walls && `Walls: ${observed.exterior_walls}`,
        observed.materials?.length && `Materials: ${observed.materials.join(', ')}`,
        observed.architectural_style && `Style: ${observed.architectural_style}`,
        ...(observed.major_elements || []),
    ].filter(Boolean);

    return (
        <section style={{ marginTop: '1.25rem' }} aria-label="Photo analysis">
            <h2 style={{ fontFamily: 'Syne, sans-serif', fontSize: '1.1rem', fontWeight: 800, marginBottom: '0.4rem' }}>
                From your photo
            </h2>
            {ref.summary && <p style={{ fontSize: '0.85rem', color: 'var(--text-2)', lineHeight: 1.6, marginBottom: '0.9rem' }}>{ref.summary}</p>}

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '1rem' }}>
                {photoUrl && (
                    <div style={{ ...card, padding: 0, overflow: 'hidden' }}>
                        <img src={photoUrl} alt="Your property (reference)" style={{ width: '100%', display: 'block', maxHeight: 260, objectFit: 'cover' }} />
                        <div style={{ padding: '0.5rem 0.8rem', fontSize: '0.72rem', color: 'var(--text-3)' }}>Reference photo — not measured</div>
                    </div>
                )}
                <div style={card}>
                    <h3 style={h3}>👁️ Observed in the photo</h3>
                    <ul style={list}>{seen.map((s, i) => <li key={i}>{s}</li>)}</ul>
                </div>
                <div style={card}>
                    <h3 style={h3}>❓ Cannot be determined from a photo</h3>
                    <ul style={list}>{(ref.not_determinable || []).map((s, i) => <li key={i}>{s}</li>)}</ul>
                    <p style={{ fontSize: '0.72rem', color: 'var(--text-3)', marginTop: '0.6rem', lineHeight: 1.5 }}>
                        These must come from you or be verified by an architect/engineer.
                    </p>
                </div>
                <div style={card}>
                    <h3 style={h3}>✏️ Requested changes</h3>
                    <ul style={list}>
                        {(request.modifications || []).map((m, i) => <li key={i}><strong>{m.element}:</strong> {m.change}</li>)}
                        {!request.modifications?.length && <li>None — the existing property is modelled as seen.</li>}
                    </ul>
                    {request.preserve?.length > 0 && (
                        <>
                            <h3 style={{ ...h3, marginTop: '0.8rem' }}>🔒 Kept from the existing property</h3>
                            <ul style={list}>{request.preserve.map((s, i) => <li key={i}>{s}</li>)}</ul>
                        </>
                    )}
                    {request.unreliable_structural_requests?.length > 0 && (
                        <>
                            <h3 style={{ ...h3, marginTop: '0.8rem', color: '#fbbf24' }}>⚠ Needs an engineer</h3>
                            <ul style={list}>{request.unreliable_structural_requests.map((s, i) => <li key={i}>{s}</li>)}</ul>
                        </>
                    )}
                </div>
                {(proposed.style || proposed.colors) && (
                    <div style={card}>
                        <h3 style={h3}>🎨 Proposed finish</h3>
                        <p style={{ fontSize: '0.8rem', color: 'var(--text-2)', marginBottom: '0.6rem' }}>
                            {proposed.style}{proposed.facade_cladding && proposed.facade_cladding !== 'none' ? ` · ${proposed.facade_cladding} facade` : ''}
                        </p>
                        <div>
                            {Object.entries(proposed.colors || {}).map(([k, v]) => <Swatch key={k} label={k.replace('_', ' ')} color={v} />)}
                        </div>
                    </div>
                )}
            </div>

            {render && (
                <div style={{ ...card, marginTop: '1rem' }}>
                    <h3 style={h3}>📷 Photorealistic render</h3>
                    {render.available ? (
                        <>
                            <img src={render.image} alt="AI-generated visualization of the proposed design"
                                style={{ width: '100%', borderRadius: 8, display: 'block' }} />
                            <p style={{ fontSize: '0.72rem', color: 'var(--text-3)', marginTop: '0.5rem', lineHeight: 1.5 }}>{render.note}</p>
                        </>
                    ) : (
                        <p style={{ fontSize: '0.8rem', color: 'var(--text-2)', lineHeight: 1.6 }}>Not available: {render.reason}</p>
                    )}
                </div>
            )}
            {ref.model && <p style={{ fontSize: '0.68rem', color: 'var(--text-3)', marginTop: '0.6rem' }}>Photo analysed by {ref.model}.</p>}
        </section>
    );
}
