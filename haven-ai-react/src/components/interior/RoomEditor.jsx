import { useCallback, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import api from '../../api';
import { useAuth } from '../../auth/AuthContext';
import EditorStage from './EditorStage';
import ObjectLibrary from './ObjectLibrary';
import { LayersPanel, ObjectPanel, SurfacePanel } from './PropertiesPanel';

// One editing session on an analysed room. The backend owns the scene: each
// change is sent as one operation and the response is the new scene (and a
// new render). Undo/redo/reset are backend history steps, so a reload or a
// saved design comes back exactly as it was.

function Toasts({ items, onClose }) {
    return (
        <div className="ie-toasts" aria-live="polite">
            {items.map((t) => (
                <div key={t.id} className={`ie-toast is-${t.kind}`}>
                    <span>{t.text}</span>
                    <button type="button" onClick={() => onClose(t.id)} aria-label="Dismiss">×</button>
                </div>
            ))}
        </div>
    );
}

function SaveMenu({ design, onSave, onClose, saving }) {
    const signedIn = !!useAuth().user;
    const [name, setName] = useState(design?.name || 'My room design');
    return (
        <div className="ie-popover ie-popover-narrow" role="dialog" aria-label="Save design">
            <div className="ie-popover-head"><strong>Save design</strong><button type="button" onClick={onClose} aria-label="Close">×</button></div>
            {signedIn ? (
                <form onSubmit={(e) => { e.preventDefault(); onSave(name); }}>
                    <label className="ie-field ie-field-block">
                        <span>Name</span>
                        <input value={name} maxLength={80} onChange={(e) => setName(e.target.value)} autoFocus />
                    </label>
                    <button type="submit" className="ie-btn is-primary" disabled={saving || !name.trim()}>
                        {saving ? 'Saving…' : design ? 'Save changes' : 'Save'}
                    </button>
                    <p className="ie-hint">Saves the photo, every object, colour and material, and the edit history.</p>
                </form>
            ) : (
                <p className="ie-hint"><Link to="/signup">Sign in</Link> to save designs to your account.</p>
            )}
        </div>
    );
}

// Before/after: the original photo over the edited room, split by a
// draggable (or keyboard-operated) divider.
export function BeforeAfter({ before, after }) {
    const [pos, setPos] = useState(50);
    const box = useRef(null);
    const drag = useRef(false);
    const moveTo = (clientX) => {
        const r = box.current.getBoundingClientRect();
        if (r.width) setPos(Math.min(100, Math.max(0, ((clientX - r.left) / r.width) * 100)));
    };
    return (
        <div className="ie-ba" ref={box}
            onPointerDown={(e) => { drag.current = true; e.currentTarget.setPointerCapture?.(e.pointerId); moveTo(e.clientX); }}
            onPointerMove={(e) => drag.current && moveTo(e.clientX)}
            onPointerUp={() => { drag.current = false; }}>
            <img src={after} alt="After: your design" draggable={false} />
            <div className="ie-ba-before" style={{ clipPath: `inset(0 ${100 - pos}% 0 0)` }}>
                <img src={before} alt="Before: the original photo" draggable={false} />
            </div>
            <div className="ie-ba-line" style={{ left: `${pos}%` }} />
            <span className="ie-ba-tag is-before">Before</span>
            <span className="ie-ba-tag is-after">After</span>
            <input type="range" className="ie-ba-range" min={0} max={100} value={Math.round(pos)}
                onChange={(e) => setPos(Number(e.target.value))} aria-label="Before / after divider" />
        </div>
    );
}

function saveFile(url, filename) {
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
}

const fileSize = (n) => (n > 1024 * 1024 ? `${(n / 1024 / 1024).toFixed(1)} MB` : `${Math.round(n / 1024)} KB`);

// Renders the final image of the current design (high-quality assets),
// downloads it as PNG or JPG and shows it against the original photo.
export function DownloadDialog({ sceneId, originalUrl, onClose }) {
    const [format, setFormat] = useState('jpg');
    const [quality, setQuality] = useState('high');
    const [state, setState] = useState({ phase: 'idle' });
    const urls = useRef([]);
    useEffect(() => () => urls.current.forEach((u) => URL.revokeObjectURL(u)), []);

    const generate = async () => {
        setState({ phase: 'working' });
        try {
            const res = await api.interior.final(sceneId, format, quality);
            const img = await api.interior.image(res.url);
            urls.current.push(img.url);
            setState({ phase: 'done', url: img.url, info: res });
            saveFile(img.url, res.filename);
        } catch (e) {
            setState({ phase: 'error', message: e.message });
        }
    };

    return (
        <div className="ie-modal" role="dialog" aria-label="Download design" onClick={(e) => e.target === e.currentTarget && onClose()}>
            <div className="ie-modal-card">
                <div className="ie-popover-head"><strong>Download design</strong><button type="button" onClick={onClose} aria-label="Close">×</button></div>
                <p className="ie-hint">Your room exactly as edited, rendered with the high-quality 3D models and textures.
                    The original photo is kept unchanged.</p>
                <div className="ie-export">
                    <fieldset>
                        <legend>Format</legend>
                        <label className="ie-check"><input type="radio" name="fmt" checked={format === 'jpg'} onChange={() => setFormat('jpg')} /> JPG (smaller file)</label>
                        <label className="ie-check"><input type="radio" name="fmt" checked={format === 'png'} onChange={() => setFormat('png')} /> PNG (lossless, best quality)</label>
                    </fieldset>
                    {format === 'jpg' && (
                        <fieldset>
                            <legend>Quality</legend>
                            <label className="ie-check"><input type="radio" name="q" checked={quality === 'high'} onChange={() => setQuality('high')} /> High</label>
                            <label className="ie-check"><input type="radio" name="q" checked={quality === 'standard'} onChange={() => setQuality('standard')} /> Standard (smaller)</label>
                        </fieldset>
                    )}
                </div>
                <button type="button" className="ie-btn is-primary" onClick={generate} disabled={state.phase === 'working'}>
                    {state.phase === 'working' ? 'Rendering…' : '⬇ Download Design'}
                </button>
                {state.phase === 'error' && <p className="ie-error">{state.message}</p>}
                {state.phase === 'done' && (
                    <>
                        <p className="ie-hint">
                            Downloaded {state.info.filename} · {state.info.width} × {state.info.height} px · {fileSize(state.info.bytes)}.{' '}
                            <a href={state.url} download={state.info.filename}>Download again</a>
                        </p>
                        {originalUrl ? <BeforeAfter before={originalUrl} after={state.url} />
                            : <img className="ie-final-img" src={state.url} alt="Your design" />}
                    </>
                )}
            </div>
        </div>
    );
}

export default function RoomEditor({ initial, catalog, design: initialDesign, onClose }) {
    const [state, setState] = useState(initial);
    const [imageUrl, setImageUrl] = useState(null);
    const [originalUrl, setOriginalUrl] = useState(null);
    const [selected, setSelected] = useState(null);
    const [busy, setBusy] = useState(false);
    const [rendering, setRendering] = useState(false);
    const [menu, setMenu] = useState(null);           // 'save' | 'final'
    const [toasts, setToasts] = useState([]);
    const [showOriginal, setShowOriginal] = useState(false);
    const [design, setDesign] = useState(initialDesign || null);
    const [saving, setSaving] = useState(false);
    const [library, setLibrary] = useState(null);     // {mode: 'add'|'replace', target}
    const busyRef = useRef(false);
    const scene = state.scene;
    const sid = scene.scene_id;

    const notify = useCallback((text, kind = 'info') => {
        const id = Math.random().toString(36).slice(2);
        setToasts((t) => [...t.slice(-3), { id, text, kind }]);
        setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), kind === 'error' ? 8000 : 4500);
    }, []);

    useEffect(() => {
        try { sessionStorage.setItem('haven.interior.scene', sid); } catch { /* storage unavailable */ }
    }, [sid]);

    // The render for the current version.
    useEffect(() => {
        let alive = true;
        setRendering(true);
        api.interior.image(state.render_url)
            .then((r) => {
                if (!alive) { URL.revokeObjectURL(r.url); return; }
                setImageUrl((prev) => { if (prev) setTimeout(() => URL.revokeObjectURL(prev), 1500); return r.url; });
            })
            .catch((e) => alive && notify(`The picture could not be updated: ${e.message}`, 'error'))
            .finally(() => alive && setRendering(false));
        return () => { alive = false; };
    }, [state.render_url, notify]);

    useEffect(() => {
        let url = null;
        api.interior.image(state.original_url).then((r) => { url = r.url; setOriginalUrl(r.url); }).catch(() => {});
        return () => { if (url) URL.revokeObjectURL(url); };
    }, [state.original_url]);

    // Drop a selection that no longer exists (after undo, remove...).
    useEffect(() => {
        if (!selected) return;
        const list = selected.kind === 'object' ? scene.objects : scene.surfaces;
        if (!list.some((x) => x.id === selected.id)) setSelected(null);
    }, [scene, selected]);

    const run = useCallback(async (call) => {
        if (busyRef.current) return null;
        busyRef.current = true;
        setBusy(true);
        try {
            const res = await call();
            setState(res);
            (res.notes || []).forEach((n) => notify(n));
            return res;
        } catch (e) {
            if (e.status === 409 && !/nothing to/i.test(e.message)) {
                try { setState(await api.interior.scene(sid)); } catch { /* keep current */ }
            }
            notify(e.message, e.status === 409 && /nothing to/i.test(e.message) ? 'info' : 'error');
            return null;
        } finally {
            busyRef.current = false;
            setBusy(false);
        }
    }, [sid, notify]);

    const apply = useCallback((operation) => run(() => api.interior.apply(sid, scene.version, operation)),
        [run, sid, scene.version]);

    const undo = useCallback(() => run(() => api.interior.undo(sid)), [run, sid]);
    const redo = useCallback(() => run(() => api.interior.redo(sid)), [run, sid]);
    const reset = () => {
        if (window.confirm('Reset the room to the original photo? You can undo this.')) run(() => api.interior.reset(sid));
    };
    const removeSelected = useCallback(() => {
        const o = selected?.kind === 'object' && scene.objects.find((x) => x.id === selected.id);
        if (o?.capabilities.remove) apply({ operation: 'remove_object', object_id: o.id });
    }, [selected, scene.objects, apply]);

    // A library pick either replaces the selected object or adds a new one;
    // either way the new object is selected so it can be moved straight away.
    const pickLibraryItem = async (item, color) => {
        const target = library?.target;
        const operation = library?.mode === 'replace' && target
            ? { operation: 'replace_object', object_id: target.id, changes: { library_item: item.id, color } }
            : { operation: 'add_object', object: { library_item: item.id, color } };
        const res = await apply(operation);
        const id = res?.scene?.last_operation?.assigned_id;
        if (id) {
            setLibrary(null);
            setSelected({ kind: 'object', id });
        }
    };

    const save = async (name) => {
        setSaving(true);
        try {
            const saved = await api.interior.designs.save(sid, name);
            setDesign(saved);
            setMenu(null);
            notify(`Saved “${saved.name}”.`);
        } catch (e) {
            notify(e.message, 'error');
        } finally {
            setSaving(false);
        }
    };

    // Keyboard: Ctrl+Z / Ctrl+Y (or Ctrl+Shift+Z), Delete, Escape.
    useEffect(() => {
        const onKey = (e) => {
            const typing = ['INPUT', 'SELECT', 'TEXTAREA'].includes(e.target.tagName);
            if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'z' && !typing) {
                e.preventDefault();
                if (e.shiftKey) redo(); else undo();
            } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'y' && !typing) {
                e.preventDefault();
                redo();
            } else if ((e.key === 'Delete' || e.key === 'Backspace') && !typing) {
                removeSelected();
            } else if (e.key === 'Escape' && !library) {
                setSelected(null);
                setMenu(null);
            }
        };
        window.addEventListener('keydown', onKey);
        return () => window.removeEventListener('keydown', onKey);
    }, [undo, redo, removeSelected, library]);

    const onTransform = async (o, changes) => !!(await apply({ operation: 'transform_object', object_id: o.id, changes }));

    const obj = selected?.kind === 'object' ? scene.objects.find((o) => o.id === selected.id) : null;
    const surface = selected?.kind === 'surface' ? scene.surfaces.find((s) => s.id === selected.id) : null;

    return (
        <div className="ie-editor">
            <div className="ie-toolbar" role="toolbar" aria-label="Editor tools">
                <button type="button" className={library?.mode === 'add' ? 'is-on' : ''} onClick={() => setLibrary({ mode: 'add' })} title="Add from the object library">
                    <span aria-hidden="true">＋</span><small>Add</small>
                </button>
                <button type="button" onClick={undo} disabled={!state.can_undo || busy} title="Undo (Ctrl+Z)">
                    <span aria-hidden="true">↶</span><small>Undo</small>
                </button>
                <button type="button" onClick={redo} disabled={!state.can_redo || busy} title="Redo (Ctrl+Y)">
                    <span aria-hidden="true">↷</span><small>Redo</small>
                </button>
                <button type="button" onClick={removeSelected} disabled={!obj?.capabilities.remove || busy} title="Delete selected (Del)">
                    <span aria-hidden="true">🗑</span><small>Delete</small>
                </button>
                <button type="button" onPointerDown={() => setShowOriginal(true)} onPointerUp={() => setShowOriginal(false)}
                    onPointerLeave={() => setShowOriginal(false)} title="Hold to see the original photo">
                    <span aria-hidden="true">◐</span><small>Compare</small>
                </button>
                <button type="button" onClick={reset} disabled={busy} title="Reset to the original">
                    <span aria-hidden="true">⟲</span><small>Reset</small>
                </button>
                <button type="button" className={menu === 'save' ? 'is-on' : ''} onClick={() => setMenu(menu === 'save' ? null : 'save')} title="Save design">
                    <span aria-hidden="true">💾</span><small>Save</small>
                </button>
                <button type="button" className="is-primary" onClick={() => setMenu('final')} title="Download design (PNG or JPG)">
                    <span aria-hidden="true">⬇</span><small>Download</small>
                </button>
                <button type="button" onClick={onClose} title="Start over with another photo">
                    <span aria-hidden="true">⤺</span><small>New</small>
                </button>
                {menu === 'save' && <SaveMenu design={design} saving={saving} onSave={save} onClose={() => setMenu(null)} />}
            </div>

            <div className="ie-canvas-col">
                {scene.warnings?.length > 0 && (
                    <div className="ie-warnings">{scene.warnings.map((w) => <p key={w}>⚠ {w}</p>)}</div>
                )}
                <EditorStage
                    scene={scene}
                    imageUrl={imageUrl}
                    originalUrl={originalUrl}
                    showOriginal={showOriginal}
                    selected={selected}
                    onSelect={setSelected}
                    onTransform={onTransform}
                    busy={busy || rendering}
                />
                <div className="ie-download-row">
                    <button type="button" className="ie-btn is-primary" onClick={() => setMenu('final')}>⬇ Download Design</button>
                </div>
                <p className="ie-status">
                    {design ? `Design: ${design.name} · ` : ''}Version {scene.version}
                    {' · '}{scene.objects.length} {scene.objects.length === 1 ? 'object' : 'objects'} · {showOriginal ? 'showing the original photo' : 'tap to select, drag to move'}
                </p>
            </div>

            <aside className="ie-panel" aria-label="Properties">
                {obj && <ObjectPanel key={obj.id} obj={obj} catalog={catalog} onApply={apply} onRemove={removeSelected}
                    onChangeObject={(o) => setLibrary({ mode: 'replace', target: o })} />}
                {surface && <SurfacePanel key={surface.id} surface={surface} scene={scene} catalog={catalog} onApply={apply} />}
                {!obj && !surface && (
                    <LayersPanel scene={scene} onSelect={setSelected}
                        onRestore={(id) => apply({ operation: 'restore_object', object_id: id })} />
                )}
                {(obj || surface) && (
                    <button type="button" className="ie-link ie-back" onClick={() => setSelected(null)}>← All items</button>
                )}
            </aside>

            {menu === 'final' && <DownloadDialog sceneId={sid} originalUrl={originalUrl} onClose={() => setMenu(null)} />}
            {library && (
                <ObjectLibrary mode={library.mode} target={library.target} busy={busy}
                    onUse={pickLibraryItem} onClose={() => setLibrary(null)} />
            )}
            <Toasts items={toasts} onClose={(id) => setToasts((t) => t.filter((x) => x.id !== id))} />
        </div>
    );
}
