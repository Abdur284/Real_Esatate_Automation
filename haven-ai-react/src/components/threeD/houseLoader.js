// Loading and disposing the backend's GLB house model.
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { applyCladding } from './cladding';
import { indexScene } from './viewerUtils';

export function webglAvailable() {
    try {
        const canvas = document.createElement('canvas');
        return Boolean(canvas.getContext('webgl2') || canvas.getContext('webgl'));
    } catch {
        return false;
    }
}

/** Parses GLB bytes and prepares the scene for display (shadows, glass,
 *  cladding textures). Returns { scene, index }. */
export async function parseHouse(buffer) {
    const gltf = await new GLTFLoader().parseAsync(buffer, '');
    const scene = gltf.scene;
    scene.traverse((obj) => {
        if (!obj.isMesh) return;
        const transparent = obj.material?.transparent;
        if (transparent) obj.material.depthWrite = false;
        obj.castShadow = !transparent && obj.userData.kind !== 'room';
        obj.receiveShadow = true;
    });
    applyCladding(scene);
    return { scene, index: indexScene(scene) };
}

/** Fetches a GLB. Throws Error('expired') for a model the server no longer has. */
export async function loadHouse(url, signal) {
    const res = await fetch(url, { signal });
    if (res.status === 404) throw new Error('expired');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return parseHouse(await res.arrayBuffer());
}

export function disposeScene(root) {
    root?.traverse((obj) => {
        if (!obj.isMesh && !obj.isLine) return;
        obj.geometry?.dispose();
        const mats = [obj.material, obj.userData.opaqueMaterial, obj.userData.clearMaterial].filter(Boolean);
        mats.forEach((m) => { m.map?.dispose(); m.dispose(); });
    });
}
