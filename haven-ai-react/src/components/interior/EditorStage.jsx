import { useEffect, useRef, useState } from 'react';
import api from '../../api';
import {
    angleTo, clamp, constrainPosition, handlesFor, hitTest, previewBox, resizeFromHandle,
} from './editorMath';

// The room picture with everything you can touch on it. Tap/click selects,
// dragging moves, the handles resize and rotate, two fingers pinch-resize.
// While a gesture is in progress the selected object is shown as a cut-out
// ("sprite") at its new place; on release one operation is sent and the
// cut-out stays until the new render has loaded, so nothing jumps.

const MIN_MOVE = 0.004;   // below this a press is a click, not a drag

function boxStyle(b) {
    return { left: `${b.x * 100}%`, top: `${b.y * 100}%`, width: `${b.w * 100}%`, height: `${b.h * 100}%` };
}

function points(outline) {
    return (outline || []).map(([x, y]) => `${x},${y}`).join(' ');
}

export default function EditorStage({ scene, imageUrl, originalUrl, showOriginal, selected, onSelect, onTransform, busy }) {
    const wrapRef = useRef(null);
    const pointers = useRef(new Map());
    const [gesture, setGesture] = useState(null);
    const [preview, setPreview] = useState(null);
    const [settling, setSettling] = useState(false);
    const [sprite, setSprite] = useState(null);
    const [hover, setHover] = useState(null);

    const obj = selected?.kind === 'object' ? scene.objects.find((o) => o.id === selected.id) : null;
    const surface = selected?.kind === 'surface' ? scene.surfaces.find((s) => s.id === selected.id) : null;
    const caps = obj?.capabilities || {};

    // Cut-out of the selected object for live previews.
    useEffect(() => {
        // (a cut-out is only ever shown for the object it was made of)
        if (!obj || (!obj.capabilities.move && !obj.capabilities.resize)) return undefined;
        let alive = true;
        let url = null;
        api.interior.image(`/api/interior/scenes/${scene.scene_id}/objects/${obj.id}/sprite?v=${scene.version}`)
            .then((r) => { if (alive) { url = r.url; setSprite({ url: r.url, id: obj.id }); } else URL.revokeObjectURL(r.url); })
            .catch(() => alive && setSprite(null));
        return () => { alive = false; if (url) setTimeout(() => URL.revokeObjectURL(url), 2000); };
    }, [scene.scene_id, scene.version, obj?.id]);  // eslint-disable-line react-hooks/exhaustive-deps

    const toNorm = (e) => {
        const r = wrapRef.current.getBoundingClientRect();
        return { x: (e.clientX - r.left) / r.width, y: (e.clientY - r.top) / r.height, aspect: r.height / r.width };
    };

    const startGesture = (e, g) => {
        e.currentTarget.setPointerCapture?.(e.pointerId);
        setGesture({ ...g, start: toNorm(e) });
    };

    const onStageDown = (e) => {
        if (showOriginal) return;
        const p = toNorm(e);
        pointers.current.set(e.pointerId, p);
        if (pointers.current.size === 2 && obj && caps.resize) {
            const [a, b] = [...pointers.current.values()];
            setGesture({ mode: 'pinch', id: obj.id, dist0: Math.hypot(a.x - b.x, a.y - b.y) || 0.01 });
            return;
        }
        const hit = hitTest(scene, p.x, p.y);
        onSelect(hit);
        if (hit?.kind === 'object') {
            const o = scene.objects.find((x) => x.id === hit.id);
            if (o?.capabilities.move) startGesture(e, { mode: 'move', id: o.id, origin: o.transform.position });
        }
    };

    const onMove = (e) => {
        const p = toNorm(e);
        if (pointers.current.has(e.pointerId)) pointers.current.set(e.pointerId, p);
        if (!gesture) {
            if (e.pointerType === 'mouse' && !showOriginal) {
                const hit = hitTest(scene, p.x, p.y);
                setHover(hit && !(hit.kind === selected?.kind && hit.id === selected?.id) ? hit : null);
            }
            return;
        }
        const o = scene.objects.find((x) => x.id === gesture.id);
        if (!o) return;
        if (gesture.mode === 'pinch') {
            const vals = [...pointers.current.values()];
            if (vals.length < 2) return;
            const m = Math.hypot(vals[0].x - vals[1].x, vals[0].y - vals[1].y) / gesture.dist0;
            const mul = { x: clamp(m, 0.3, 3), y: clamp(m, 0.3, 3) };
            setPreview({ id: o.id, box: previewBox(scene, o, o.transform.position, mul), mul, mode: 'resize' });
            return;
        }
        const dx = p.x - gesture.start.x;
        const dy = p.y - gesture.start.y;
        if (gesture.mode === 'move') {
            if (Math.hypot(dx, dy) < MIN_MOVE && !preview) return;
            const pos = constrainPosition(scene, o, gesture.origin.x + dx, gesture.origin.y + dy);
            setPreview({ id: o.id, box: previewBox(scene, o, pos), pos, mode: 'move' });
        } else if (gesture.mode === 'resize') {
            const mul = resizeFromHandle(gesture.handle, o, dx, dy, !e.shiftKey);
            setPreview({ id: o.id, box: previewBox(scene, o, o.transform.position, mul), mul, mode: 'resize' });
        } else if (gesture.mode === 'rotate') {
            let angle;
            if (caps.rotate === 'yaw') {
                angle = Math.round(((o.transform.rotation || 0) + dx * 540) % 360 + 360) % 360;
            } else {
                const b = o.bounds;
                angle = Math.round(clamp(angleTo({ x: b.x + b.w / 2, y: b.y + b.h / 2 }, p, p.aspect), -45, 45));
            }
            setPreview({ id: o.id, box: o.bounds, rotation: angle, mode: 'rotate', tilt: caps.rotate === 'tilt' });
        }
    };

    const onUp = (e) => {
        pointers.current.delete(e.pointerId);
        const g = gesture;
        setGesture(null);
        if (!g || !preview || preview.id !== g.id) { setPreview(null); return; }
        const o = scene.objects.find((x) => x.id === g.id);
        let changes = null;
        if (preview.mode === 'move') changes = { position: { x: +preview.pos.x.toFixed(4), y: +preview.pos.y.toFixed(4) } };
        if (preview.mode === 'resize') {
            const s = o.transform.scale;
            const scale = { x: +(s.x * preview.mul.x).toFixed(3), y: +(s.y * preview.mul.y).toFixed(3) };
            if (o.source === 'model' && o.placement !== 'wall') scale.z = +((s.z ?? 1) * preview.mul.x).toFixed(3);
            changes = { scale };
        }
        if (preview.mode === 'rotate') changes = { rotation: preview.rotation };
        if (!changes) { setPreview(null); return; }
        setSettling(true);
        Promise.resolve(onTransform(o, changes)).then((ok) => { if (!ok) { setPreview(null); setSettling(false); } });
    };

    const onImageLoad = () => {
        if (settling) { setPreview(null); setSettling(false); }
    };

    const shownBox = preview && obj && preview.id === obj.id ? preview.box : obj?.bounds;
    const hoverEl = hover && (hover.kind === 'object'
        ? scene.objects.find((o) => o.id === hover.id) : scene.surfaces.find((s) => s.id === hover.id));

    return (
        <div
            ref={wrapRef}
            className={`ie-stage${gesture ? ' is-dragging' : ''}`}
            onPointerDown={onStageDown}
            onPointerMove={onMove}
            onPointerUp={onUp}
            onPointerCancel={onUp}
            onPointerLeave={() => setHover(null)}
            role="application"
            aria-label="Room editor. Click an object or surface to select it; drag to move."
        >
            {imageUrl
                ? <img src={showOriginal ? originalUrl || imageUrl : imageUrl} className="ie-render" alt="Your room"
                    draggable={false} onLoad={onImageLoad} />
                : <div className="ie-render-placeholder" style={{ aspectRatio: `${scene.image.width} / ${scene.image.height}` }} />}

            {!showOriginal && (
                <svg className="ie-overlay" viewBox="0 0 1 1" preserveAspectRatio="none" aria-hidden="true">
                    {hoverEl && <polygon points={points(hoverEl.outline)} className="ie-outline is-hover" />}
                    {surface && <polygon points={points(surface.outline)} className="ie-outline is-surface" />}
                    {obj && !preview && <polygon points={points(obj.outline)} className="ie-outline is-selected" />}
                    {obj && preview && preview.mode === 'move' && (
                        <polygon points={points(obj.outline)} className="ie-outline is-ghost" />
                    )}
                </svg>
            )}

            {!showOriginal && preview && sprite && sprite.id === preview.id && (
                <img
                    src={sprite.url}
                    alt=""
                    className="ie-sprite"
                    style={{
                        ...boxStyle(preview.box),
                        transform: preview.tilt ? `rotate(${preview.rotation - (obj?.transform.rotation || 0)}deg)` : undefined,
                    }}
                    draggable={false}
                />
            )}

            {!showOriginal && obj && shownBox && (
                <div className="ie-selection" style={boxStyle(shownBox)}>
                    {caps.resize && handlesFor(obj).map((h) => (
                        <div
                            key={h}
                            className={`ie-handle ie-handle-${h}`}
                            onPointerDown={(e) => { e.stopPropagation(); startGesture(e, { mode: 'resize', id: obj.id, handle: h }); }}
                            aria-label={`Resize (${h})`}
                        />
                    ))}
                    {(caps.rotate === 'yaw' || caps.rotate === 'tilt') && (
                        <div
                            className="ie-rotate"
                            title={caps.rotate === 'yaw' ? 'Drag sideways to turn' : 'Drag to tilt'}
                            onPointerDown={(e) => { e.stopPropagation(); startGesture(e, { mode: 'rotate', id: obj.id }); }}
                        >⟳</div>
                    )}
                    {preview?.mode === 'rotate' && <div className="ie-angle">{preview.rotation}°</div>}
                </div>
            )}

            {busy && <div className="ie-busy"><span className="ie-spinner" /> Updating…</div>}
        </div>
    );
}
