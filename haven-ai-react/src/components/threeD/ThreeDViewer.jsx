import { Component, useEffect, useMemo, useRef, useState } from 'react';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js';
import { disposeScene, loadHouse, webglAvailable } from './houseLoader';
import {
    DEFAULT_FOV, applyVisibility, computeView, modelBounds, pickRoom, roomBounds, roomKey, setWallsTransparent,
} from './viewerUtils';

/**
 * Layer 3: loads the backend's GLB and renders it with React Three Fiber.
 *
 * Every dimension comes from the GLB; this component never creates or moves
 * architecture. It only toggles layers, highlights the selected room and
 * moves the camera.
 */

const FOV = DEFAULT_FOV;
const BACKGROUND = '#e8edf3';

/** Soft studio reflections for the PBR materials (no external HDR file). */
function StudioEnvironment() {
    const gl = useThree((s) => s.gl);
    const get = useThree((s) => s.get);
    useEffect(() => {
        const pmrem = new THREE.PMREMGenerator(gl);
        const env = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
        const { scene } = get();
        scene.environment = env;
        scene.environmentIntensity = 0.55;
        return () => { scene.environment = null; env.dispose(); pmrem.dispose(); };
    }, [gl, get]);
    return null;
}

function Lights({ meta }) {
    const b = modelBounds(meta);
    const cx = (b.min[0] + b.max[0]) / 2;
    const cz = (b.min[2] + b.max[2]) / 2;
    const r = Math.hypot(b.max[0] - b.min[0], b.max[2] - b.min[2]) / 2 + 6;
    const sun = useRef();
    useEffect(() => {
        if (!sun.current) return;
        sun.current.target.position.set(cx, 0, cz);
        sun.current.target.updateMatrixWorld();
    }, [cx, cz]);
    return (
        <>
            <hemisphereLight args={['#dbeafe', '#8a9a7b', 0.9]} />
            <directionalLight
                ref={sun} castShadow intensity={2.2} position={[cx + r * 0.7, r * 1.4, cz + r * 0.9]}
                shadow-mapSize={[2048, 2048]} shadow-bias={-0.0004} shadow-normalBias={0.03}
                shadow-camera-left={-r} shadow-camera-right={r} shadow-camera-top={r} shadow-camera-bottom={-r}
                shadow-camera-near={0.5} shadow-camera-far={r * 4}
            />
        </>
    );
}

function setFov(camera, fov) {
    camera.fov = fov;
    camera.updateProjectionMatrix();
}

/** OrbitControls plus smooth fly-to transitions. */
function CameraRig({ rigRef }) {
    const { camera, gl } = useThree();
    const anim = useRef(null);
    const controls = useMemo(() => {
        const c = new OrbitControls(camera, gl.domElement);
        c.enableDamping = true;
        c.dampingFactor = 0.08;
        c.screenSpacePanning = true;
        c.maxPolarAngle = Math.PI / 2 - 0.02; // stay above the ground
        c.minDistance = 0.1;
        c.maxDistance = 400;
        return c;
    }, [camera, gl]);
    useEffect(() => () => controls.dispose(), [controls]);

    useEffect(() => {
        rigRef.current = {
            controls,
            camera,
            flyTo: ({ position, target, fov = FOV }, instant = false) => {
                const to = { p: new THREE.Vector3(...position), t: new THREE.Vector3(...target), fov };
                if (instant) {
                    camera.position.copy(to.p);
                    controls.target.copy(to.t);
                    setFov(camera, fov);
                    controls.update();
                    anim.current = null;
                    return;
                }
                anim.current = { from: { p: camera.position.clone(), t: controls.target.clone(), fov: camera.fov }, to, k: 0 };
            },
        };
        return () => { rigRef.current = null; };
    }, [camera, controls, rigRef]);

    useFrame((_, dt) => {
        const a = anim.current;
        if (a) {
            a.k = Math.min(1, a.k + dt / 0.75);
            const e = 1 - (1 - a.k) ** 3; // ease-out cubic
            camera.position.lerpVectors(a.from.p, a.to.p, e);
            controls.target.lerpVectors(a.from.t, a.to.t, e);
            if (a.from.fov !== a.to.fov) {
                setFov(camera, a.from.fov + (a.to.fov - a.from.fov) * e);
            }
            if (a.k >= 1) anim.current = null;
        }
        controls.update();
    });
    return null;
}

function RoomHighlight({ room, meta }) {
    const b = roomBounds(room, meta);
    const [sx, sy, sz] = b.max.map((v, i) => v - b.min[i]);
    const size = [sx, sy, sz];
    const center = b.min.map((v, i) => v + size[i] / 2);
    const edges = useMemo(() => new THREE.EdgesGeometry(new THREE.BoxGeometry(sx, sy, sz)), [sx, sy, sz]);
    useEffect(() => () => edges.dispose(), [edges]);
    return (
        <group position={center} raycast={() => null}>
            <mesh raycast={() => null} renderOrder={2}>
                <boxGeometry args={size} />
                <meshBasicMaterial color="#3b82f6" transparent opacity={0.16} depthWrite={false} />
            </mesh>
            <lineSegments geometry={edges} raycast={() => null}>
                <lineBasicMaterial color="#1d4ed8" />
            </lineSegments>
        </group>
    );
}

function House({ house, options, selected, onSelectRoom, onHover }) {
    const { index, scene } = house;
    useEffect(() => { applyVisibility(index, options); }, [index, options]);
    useEffect(() => { setWallsTransparent(index, Boolean(options.transparentWalls)); }, [index, options.transparentWalls]);
    return (
        <primitive
            object={scene}
            onClick={(e) => {
                if (e.delta > 4) return; // a drag, not a click
                e.stopPropagation();
                const room = pickRoom(e.intersections);
                onSelectRoom?.(room && roomKey(room) === roomKey(selected) ? null : room);
            }}
            onPointerMove={(e) => onHover(Boolean(pickRoom(e.intersections)))}
            onPointerOut={() => onHover(false)}
        />
    );
}

function Scene({ house, options, selected, onSelectRoom, viewRequest, rigRef }) {
    const { size } = useThree();
    const [hover, setHover] = useState(false);
    const { meta } = house.index;
    const aspect = size.width / Math.max(1, size.height);

    useEffect(() => { document.body.style.cursor = hover ? 'pointer' : ''; }, [hover]);
    useEffect(() => () => { document.body.style.cursor = ''; }, []);

    // Frame a newly loaded model instantly; later view requests animate.
    const framed = useRef(null);
    useEffect(() => {
        const rig = rigRef.current;
        if (!rig || framed.current === house) return;
        framed.current = house;
        rig.flyTo(computeView('exterior', { meta, fov: FOV, aspect }), true);
    }, [house, meta, aspect, rigRef]);

    useEffect(() => {
        const rig = rigRef.current;
        if (!rig || !viewRequest) return;
        const rooms = house.index.rooms.map((r) => r.userData)
            .filter((r) => !options.visibleLevels || options.visibleLevels.includes(r.level));
        const dir = rig.camera.position.clone().sub(rig.controls.target).normalize();
        rig.flyTo(computeView(viewRequest.name, {
            meta, fov: FOV, aspect, rooms,
            room: ['interior', 'fit', 'room'].includes(viewRequest.name) ? selected : null,
            currentDirection: dir.toArray(),
        }));
    }, [viewRequest]); // eslint-disable-line react-hooks/exhaustive-deps

    const far = Math.max(meta.plot.width_ft, meta.plot.length_ft) * 0.3048 * 12;
    return (
        <>
            <color attach="background" args={[BACKGROUND]} />
            <fog attach="fog" args={[BACKGROUND, far * 0.35, far]} />
            <StudioEnvironment />
            <Lights meta={meta} />
            <mesh rotation-x={-Math.PI / 2} position={[0, -0.12, 0]} receiveShadow raycast={() => null}>
                <circleGeometry args={[far, 64]} />
                <meshStandardMaterial color="#d5dce4" roughness={1} />
            </mesh>
            <House house={house} options={options} selected={selected} onSelectRoom={onSelectRoom} onHover={setHover} />
            {selected && (!options.visibleLevels || options.visibleLevels.includes(selected.level)) && (
                <RoomHighlight room={selected} meta={meta} />
            )}
            <CameraRig rigRef={rigRef} />
        </>
    );
}

class ViewerErrorBoundary extends Component {
    constructor(props) {
        super(props);
        this.state = { error: null };
    }

    static getDerivedStateFromError(error) {
        return { error };
    }

    componentDidCatch(error) {
        console.error('3D viewer crashed:', error);
    }

    render() {
        if (this.state.error) {
            return this.props.fallback(() => this.setState({ error: null }));
        }
        return this.props.children;
    }
}

const overlay = {
    position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', gap: '0.6rem',
    alignItems: 'center', justifyContent: 'center', textAlign: 'center', padding: '1.5rem',
    fontSize: '0.88rem', color: '#334155', background: 'rgba(232,237,243,0.85)',
};

/**
 * Props:
 *   url           GLB model URL from the backend
 *   options       { visibleLevels, showWalls, showRoof, transparentWalls, showDoors, showWindows, showFurniture }
 *   selected      selected room extras (or null); onSelectRoom(roomExtras | null)
 *   viewRequest   { name, n } - a new object triggers a camera move
 *   onLoaded(meta)
 */
export default function ThreeDViewer({ url, options, selected, onSelectRoom, viewRequest, onLoaded, height = 520 }) {
    const [attempt, setAttempt] = useState(0);
    const key = `${url}#${attempt}`;
    // `loaded` belongs to one url/attempt; anything else means still loading.
    const [loaded, setLoaded] = useState({ key: null, house: null, error: null });
    const state = loaded.key !== key ? { status: 'loading' }
        : loaded.error ? { status: 'error', error: loaded.error } : { status: 'ready', house: loaded.house };
    const rigRef = useRef(null);
    const supported = useMemo(() => webglAvailable(), []);
    const onLoadedRef = useRef(onLoaded);
    useEffect(() => { onLoadedRef.current = onLoaded; }, [onLoaded]);

    useEffect(() => {
        if (!url || !supported) return undefined;
        const ctrl = new AbortController();
        let house = null;
        loadHouse(url, ctrl.signal)
            .then((h) => {
                house = h;
                setLoaded({ key, house: h, error: null });
                onLoadedRef.current?.(h.index.meta);
            })
            .catch((err) => {
                if (ctrl.signal.aborted) return;
                console.error('GLB load failed:', err);
                setLoaded({ key, house: null, error: err.message === 'expired' ? 'expired' : 'failed' });
            });
        return () => { ctrl.abort(); disposeScene(house?.scene); };
    }, [url, key, supported]);

    const box = { position: 'relative', width: '100%', height, background: BACKGROUND };
    if (!supported) {
        return (
            <div style={box} data-testid="viewer-unsupported">
                <div style={overlay}>
                    <strong>3D view unavailable</strong>
                    Your browser or device doesn't support WebGL, which is needed to show the 3D model.
                    The model details are still listed alongside.
                </div>
            </div>
        );
    }

    const failure = (retry) => (
        <div style={overlay} role="alert" data-testid="viewer-error">
            <strong>{state.error === 'expired' ? 'This 3D model has expired' : "The 3D model couldn't be displayed"}</strong>
            <span>{state.error === 'expired'
                ? 'Generated models are kept for two hours. Generate the design again to view it.'
                : 'Something went wrong while loading or drawing the model.'}</span>
            {state.error !== 'expired' && (
                <button type="button" onClick={retry} style={{ padding: '0.4rem 0.9rem', borderRadius: 8, border: '1px solid #94a3b8', background: '#fff', cursor: 'pointer' }}>
                    Try again
                </button>
            )}
        </div>
    );

    return (
        <div style={box} data-testid="viewer">
            {state.status === 'ready' && (
                <ViewerErrorBoundary fallback={(reset) => failure(() => { reset(); setAttempt((a) => a + 1); })}>
                    <Canvas
                        shadows="percentage"
                        dpr={[1, 2]}
                        camera={{ fov: FOV, near: 0.05, far: 2000, position: [20, 15, 20] }}
                        gl={{ antialias: true, preserveDrawingBuffer: true }}
                        onPointerMissed={(e) => { if (e.type === 'click') onSelectRoom?.(null); }}
                        style={{ width: '100%', height: '100%' }}
                    >
                        <Scene house={state.house} options={options} selected={selected}
                            onSelectRoom={onSelectRoom} viewRequest={viewRequest} rigRef={rigRef} />
                    </Canvas>
                </ViewerErrorBoundary>
            )}
            {state.status === 'loading' && (
                <div style={overlay} data-testid="viewer-loading" aria-live="polite">Loading 3D model…</div>
            )}
            {state.status === 'error' && failure(() => setAttempt((a) => a + 1))}
        </div>
    );
}
