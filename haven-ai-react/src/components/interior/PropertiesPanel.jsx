import { useState } from 'react';
import api from '../../api';
import { materialLabel, metres, pct } from './editorMath';

// Properties of what is selected. Only what makes sense for that element is
// shown: a wall has colour and finish; a sofa from the photo can move,
// resize, mirror, change colour/material or be swapped for a 3D model; a 3D
// model can also turn. Every change is one operation (see RoomEditor).

function NumberField({ label, value, onCommit, min, max, step = 1, suffix }) {
    // null = not being edited: show the scene's value
    const [text, setText] = useState(null);
    const commit = () => {
        const v = Number(text);
        setText(null);
        if (text === null || text === '' || !Number.isFinite(v)) return;
        const c = Math.min(max, Math.max(min, v));
        if (c !== value) onCommit(c);
    };
    return (
        <label className="ie-field">
            <span>{label}</span>
            <span className="ie-input-wrap">
                <input type="number" value={text ?? String(value)} min={min} max={max} step={step}
                    onChange={(e) => setText(e.target.value)} onBlur={commit}
                    onKeyDown={(e) => { if (e.key === 'Enter') e.currentTarget.blur(); }} />
                {suffix && <em>{suffix}</em>}
            </span>
        </label>
    );
}

function ColorPicker({ value, original, palette, onChange }) {
    const current = value || original || '#808080';
    return (
        <div className="ie-colors">
            <div className="ie-swatches">
                {palette.map((c) => (
                    <button key={c} type="button" className={`ie-swatch${value === c ? ' is-on' : ''}`}
                        style={{ background: c }} onClick={() => onChange(c)} aria-label={`Colour ${c}`} title={c} />
                ))}
            </div>
            <div className="ie-color-row">
                <label className="ie-custom-color" title="Pick any colour">
                    <input type="color" value={current} onChange={(e) => onChange(e.target.value)} />
                    <span>{current.toUpperCase()}</span>
                </label>
                {value && <button type="button" className="ie-link" onClick={() => onChange(null)}>Use photo colour</button>}
            </div>
        </div>
    );
}

function Section({ title, children }) {
    return (
        <div className="ie-section">
            <h4>{title}</h4>
            {children}
        </div>
    );
}

function MaterialGrid({ options, value, onChange, color, catalog, includeOriginal }) {
    const list = includeOriginal ? ['original', ...options] : options;
    return (
        <div className="ie-material-grid" role="radiogroup">
            {list.map((m) => (
                <button key={m} type="button" role="radio" aria-checked={(value || 'original') === m}
                    className={(value || 'original') === m ? 'is-on' : ''} onClick={() => onChange(m)}
                    title={materialLabel(catalog, m)}>
                    {m === 'original'
                        ? <span className="ie-mat-photo">Photo</span>
                        : <img src={api.interior.library.swatch(m, catalog.materials[m]?.tintable ? color : null)} alt="" loading="lazy" />}
                    <span>{materialLabel(catalog, m)}</span>
                </button>
            ))}
        </div>
    );
}

export function SurfacePanel({ surface, catalog, scene, onApply }) {
    const ap = surface.appearance;
    const walls = scene.surfaces.filter((s) => s.type === 'wall');
    const set = (changes) => onApply({ operation: 'update_surface', surface_id: surface.id, changes });
    return (
        <div className="ie-panel-body">
            <div className="ie-panel-head">
                <strong>{surface.label}</strong>
                <span className="ie-chip">Surface</span>
            </div>
            {surface.type === 'wall' && walls.length > 1 && (
                <p className="ie-hint">This photo has {walls.length} wall sections. Paint one differently for an accent wall.</p>
            )}
            <Section title={surface.type === 'floor' ? 'Colour' : 'Paint colour'}>
                <ColorPicker value={ap.color} original={surface.color} palette={catalog.palette} onChange={(c) => set({ color: c })} />
            </Section>
            <Section title={surface.type === 'floor' ? 'Flooring' : 'Finish'}>
                <MaterialGrid options={surface.capabilities.materials} value={ap.material} color={ap.color}
                    catalog={catalog} includeOriginal onChange={(m) => set({ material: m })} />
                {ap.material && ap.material !== 'original' && catalog.materials[ap.material]?.tintable === false && ap.color && (
                    <p className="ie-hint">The colour tints this material's own pattern.</p>
                )}
            </Section>
            {(ap.color || (ap.material && ap.material !== 'original')) && (
                <button type="button" className="ie-btn" onClick={() => set({ color: null, material: 'original' })}>Back to the photo</button>
            )}
        </div>
    );
}

// How a replacement was sized, and one click back to that size or to the
// piece's real catalogue size.
function FitHint({ obj, onFit }) {
    const fit = obj.fit;
    const lib = fit.library_size_m;
    const s = obj.transform.scale;
    const same = (a, b) => ['x', 'y', 'z'].every((k) => Math.abs((a?.[k] ?? 1) - (b?.[k] ?? 1)) < 1e-3);
    const atCatalogue = same(s, { x: 1, y: 1, z: 1 });
    const atMatch = fit.mode === 'match' && same(s, fit.scale);
    const size = `${lib.width.toFixed(2)} × ${lib.depth.toFixed(2)} × ${lib.height.toFixed(2)} m`;
    return (
        <>
            <p className="ie-hint">
                {atMatch ? `Sized to fill the space of the original ${fit.replaced.toLowerCase()}. ` : ''}
                Catalogue size: {size}.
            </p>
            <div className="ie-grid2">
                {fit.mode === 'match' && !atMatch && (
                    <button type="button" className="ie-btn" onClick={() => onFit('original')}>Match original size</button>
                )}
                {!atCatalogue && (
                    <button type="button" className="ie-btn" onClick={() => onFit('catalogue')}>Use catalogue size</button>
                )}
            </div>
        </>
    );
}

export function ObjectPanel({ obj, catalog, onApply, onRemove, onChangeObject }) {
    const caps = obj.capabilities;
    const t = obj.transform;
    const ap = obj.appearance;
    const dims = obj.dimensions_m;
    const isModel = obj.source === 'model';
    const [lock, setLock] = useState(true);
    const transform = (changes) => onApply({ operation: 'transform_object', object_id: obj.id, changes });
    const update = (changes) => onApply({ operation: 'update_object', object_id: obj.id, changes });

    const setScale = (axis, factor) => {
        const s = { ...t.scale };
        if (lock && axis !== 'z') {
            const k = factor / s[axis];
            s.x = +(s.x * k).toFixed(3);
            s.y = +(s.y * k).toFixed(3);
            if (isModel && s.z != null) s.z = +(s.z * k).toFixed(3);
        } else {
            s[axis] = +factor.toFixed(3);
        }
        transform({ scale: s });
    };

    return (
        <div className="ie-panel-body">
            <div className="ie-panel-head">
                <strong>{obj.label}</strong>
                <span className="ie-chip">{catalog.types[obj.type]?.category || obj.category}</span>
            </div>
            <p className="ie-meta">
                {isModel ? (obj.library_item ? 'From the object library' : '3D model')
                    : `Found in your photo · ${Math.round((obj.confidence || 0) * 100)}% sure`}
                {!isModel && obj.material_source === 'assumed' && obj.material_guess && ap.material === 'original'
                    ? ` · looks like ${materialLabel(catalog, obj.material_guess).toLowerCase()} (not measured)` : ''}
            </p>

            {caps.move && (
                <Section title="Position">
                    <div className="ie-grid2">
                        <NumberField label="X" suffix="%" min={0} max={100} value={Math.round(t.position.x * 100)}
                            onCommit={(v) => transform({ position: { x: v / 100, y: t.position.y } })} />
                        <NumberField label="Y" suffix="%" min={0} max={100} value={Math.round(t.position.y * 100)}
                            onCommit={(v) => transform({ position: { x: t.position.x, y: v / 100 } })} />
                    </div>
                    <p className="ie-hint">Or drag it in the picture. {obj.placement === 'floor' ? 'It stays on the floor and gets smaller further away.' : ''}</p>
                </Section>
            )}

            {caps.resize && (
                <Section title="Size">
                    {isModel ? (
                        <div className="ie-grid3">
                            <NumberField label="Width" suffix="m" step={0.05} min={0.1} max={6} value={dims.width}
                                onCommit={(v) => setScale('x', (v / dims.width) * t.scale.x)} />
                            {obj.placement !== 'wall' && (
                                <NumberField label="Depth" suffix="m" step={0.05} min={0.05} max={6} value={dims.depth}
                                    onCommit={(v) => setScale('z', (v / dims.depth) * (t.scale.z ?? 1))} />
                            )}
                            <NumberField label="Height" suffix="m" step={0.05} min={0.01} max={4} value={dims.height}
                                onCommit={(v) => setScale('y', (v / dims.height) * t.scale.y)} />
                        </div>
                    ) : (
                        <div className="ie-grid2">
                            <NumberField label="Width" suffix="%" min={30} max={300} value={Math.round(t.scale.x * 100)}
                                onCommit={(v) => setScale('x', v / 100)} />
                            <NumberField label="Height" suffix="%" min={30} max={300} value={Math.round(t.scale.y * 100)}
                                onCommit={(v) => setScale('y', v / 100)} />
                        </div>
                    )}
                    <label className="ie-check">
                        <input type="checkbox" checked={lock} onChange={(e) => setLock(e.target.checked)} /> Keep proportions
                    </label>
                    {isModel && obj.fit?.library_size_m && (
                        <FitHint obj={obj} onFit={(size) => onApply({ operation: 'fit_object', object_id: obj.id, changes: { size } })} />
                    )}
                    {!isModel && dims && (
                        <p className="ie-hint">About {metres(dims.width)} wide{dims.height ? `, ${metres(dims.height)} high` : ''} (estimated from the photo).</p>
                    )}
                    {!isModel && !dims && <p className="ie-hint">Size shown as a percentage of the original: {pct(t.scale.x)}.</p>}
                </Section>
            )}

            {caps.rotate === 'yaw' && (
                <Section title="Rotation">
                    <div className="ie-range">
                        <input type="range" min={0} max={359} key={t.rotation} defaultValue={Math.round(t.rotation)}
                            onPointerUp={(e) => transform({ rotation: Number(e.currentTarget.value) })}
                            onKeyUp={(e) => transform({ rotation: Number(e.currentTarget.value) })}
                            aria-label="Rotation in degrees" />
                        <NumberField label="" suffix="°" min={0} max={359} value={Math.round(t.rotation)}
                            onCommit={(v) => transform({ rotation: v })} />
                    </div>
                    {Math.round(t.rotation) % 360 !== 0 && (
                        <button type="button" className="ie-btn" onClick={() => transform({ rotation: 0 })}>Reset rotation</button>
                    )}
                </Section>
            )}
            {caps.rotate === 'tilt' && (
                <Section title="Tilt">
                    <NumberField label="Angle" suffix="°" min={-45} max={45} value={Math.round(t.rotation)}
                        onCommit={(v) => transform({ rotation: v })} />
                    {Math.round(t.rotation) !== 0 && (
                        <button type="button" className="ie-btn" onClick={() => transform({ rotation: 0 })}>Reset rotation</button>
                    )}
                </Section>
            )}
            {caps.rotate === 'mirror' && (
                <Section title="Orientation">
                    <button type="button" className={`ie-btn${t.flip ? ' is-on' : ''}`} onClick={() => transform({ flip: !t.flip })}>
                        ⇋ Mirror
                    </button>
                    {caps.replace && <p className="ie-hint">To turn it, change it for a 3D model from the library below.</p>}
                </Section>
            )}

            {caps.color && (
                <Section title="Colour">
                    <ColorPicker value={ap.color} original={obj.color} palette={catalog.palette} onChange={(c) => update({ color: c })} />
                </Section>
            )}

            {caps.materials.length > (isModel ? 1 : 0) && (
                <Section title="Material">
                    <MaterialGrid options={caps.materials} value={ap.material} color={ap.color} catalog={catalog}
                        includeOriginal={!isModel} onChange={(m) => update({ material: m })} />
                </Section>
            )}

            {caps.replace && (
                <Section title="Object">
                    <button type="button" className="ie-btn is-primary ie-change" onClick={() => onChangeObject(obj)}>
                        ⇄ Change {obj.library_item ? 'object' : obj.label.toLowerCase()}…
                    </button>
                    {obj.library_item && (
                        <p className="ie-hint">{obj.library_item.name}
                            {obj.library_item.realism === 'real' ? ' · real 3D model, catalogue size ' : ' · typical catalogue size '}
                            {Math.round(obj.library_item.dimensions.width)} ×{' '}
                            {Math.round(obj.library_item.dimensions.depth)} × {Math.round(obj.library_item.dimensions.height)} cm
                            {obj.replaces ? ` · replaced the ${obj.replaces.label.toLowerCase()} (Reset brings it back)` : ''}</p>
                    )}
                    {obj.library_item?.realism === 'real' && !caps.color && (
                        <p className="ie-hint">This piece keeps its real finish; pick another item to change the look.</p>
                    )}
                </Section>
            )}

            <div className="ie-actions">
                <button type="button" className="ie-btn" onClick={() => onApply({ operation: 'reset_object', object_id: obj.id })}>
                    Reset
                </button>
                {caps.remove && (
                    <button type="button" className="ie-btn is-danger" onClick={onRemove}>Delete</button>
                )}
            </div>
            {!caps.move && !caps.remove && <p className="ie-hint">Part of the building: it can be refinished but not moved.</p>}
        </div>
    );
}

export function LayersPanel({ scene, onSelect, onRestore }) {
    return (
        <div className="ie-panel-body">
            <div className="ie-panel-head"><strong>In this room</strong></div>
            <p className="ie-hint">Tap anything in the picture, or pick it here.</p>
            <ul className="ie-layers">
                {scene.surfaces.map((s) => (
                    <li key={s.id}><button type="button" onClick={() => onSelect({ kind: 'surface', id: s.id })}>
                        <span className="ie-dot" style={{ background: s.appearance.color || s.color }} />{s.label}
                    </button></li>
                ))}
                {scene.objects.map((o) => (
                    <li key={o.id}><button type="button" onClick={() => onSelect({ kind: 'object', id: o.id })}>
                        <span className="ie-dot" style={{ background: o.appearance.color || o.color || '#888' }} />
                        {o.label}<em>{o.source === 'model' ? '3D' : o.id.split('_').pop()}</em>
                    </button></li>
                ))}
            </ul>
            {scene.objects.length === 0 && <p className="ie-hint">No furniture found. Use “Add” to furnish the room.</p>}
            {scene.removed?.length > 0 && (
                <>
                    <div className="ie-panel-head" style={{ marginTop: '1rem' }}><strong>Removed</strong></div>
                    <ul className="ie-layers">
                        {scene.removed.map((r) => (
                            <li key={r.id}><button type="button" onClick={() => onRestore(r.id)}>↺ {r.label}<em>restore</em></button></li>
                        ))}
                    </ul>
                </>
            )}
        </div>
    );
}
