// Procedural facade cladding for models generated from a property photo.
// Each finish is drawn once onto a canvas representing an 8 x 8 ft patch of
// wall, tinted from the facade colour, and tiled over the GLB's facade
// material (its UVs are in feet, so the texture keeps true scale).
import * as THREE from 'three';

export const PATCH_FT = 8;
const claddingCanvases = new Map();

function shade(hex, amount) {
    const c = new THREE.Color(hex);
    c.offsetHSL(0, 0, amount);
    return `#${c.getHexString()}`;
}

function claddingCanvas(kind, base) {
    const key = `${kind}|${base}`;
    if (claddingCanvases.has(key)) return claddingCanvases.get(key);
    const size = 256;
    const px = size / PATCH_FT; // pixels per foot
    const canvas = document.createElement('canvas');
    canvas.width = canvas.height = size;
    const g = canvas.getContext('2d');
    let seed = 7;
    const rand = () => { seed = (seed * 16807) % 2147483647; return seed / 2147483647; };
    g.fillStyle = base;
    g.fillRect(0, 0, size, size);
    const mortar = shade(base, -0.1);

    if (kind === 'brick') {
        const bw = 0.75 * px, bh = 0.25 * px;
        for (let row = 0; row * bh < size; row++) {
            for (let x = -(row % 2) * bw / 2; x < size; x += bw) {
                g.fillStyle = shade(base, (rand() - 0.5) * 0.12);
                g.fillRect(x + 1, row * bh + 1, bw - 2, bh - 2);
            }
        }
    } else if (kind === 'stone') {
        g.fillStyle = mortar;
        g.fillRect(0, 0, size, size);
        for (let y = 0; y < size;) {
            const h = (0.6 + rand() * 0.6) * px;
            for (let x = -rand() * px; x < size;) {
                const w = (1 + rand() * 1.4) * px;
                g.fillStyle = shade(base, (rand() - 0.5) * 0.12);
                g.fillRect(x + 2, y + 2, w - 4, h - 4);
                x += w;
            }
            y += h;
        }
    } else if (kind === 'wood') {
        const plank = 0.5 * px;
        for (let x = 0; x < size; x += plank) {
            g.fillStyle = shade(base, (rand() - 0.5) * 0.1);
            g.fillRect(x, 0, plank - 1, size);
            g.fillStyle = shade(base, -0.06);
            for (let k = 0; k < 3; k++) g.fillRect(x + rand() * plank, 0, 1, size);
        }
    } else if (kind === 'tile' || kind === 'glass' || kind === 'concrete') {
        const cell = (kind === 'tile' ? 1 : kind === 'glass' ? 4 : 2) * px;
        if (kind === 'concrete') {
            for (let i = 0; i < 1500; i++) {
                g.fillStyle = shade(base, (rand() - 0.5) * 0.08);
                g.fillRect(rand() * size, rand() * size, 2, 2);
            }
        }
        g.strokeStyle = kind === 'glass' ? shade(base, -0.3) : mortar;
        g.lineWidth = kind === 'glass' ? 4 : 2;
        for (let v = 0; v <= size; v += cell) {
            g.beginPath(); g.moveTo(v, 0); g.lineTo(v, size); g.stroke();
            g.beginPath(); g.moveTo(0, v); g.lineTo(size, v); g.stroke();
        }
    }
    claddingCanvases.set(key, canvas);
    return canvas;
}

/** Applies the cladding texture to every material the backend marked with
 *  extras.cladding (GLTFLoader puts material extras in userData). */
export function applyCladding(root) {
    root.traverse((obj) => {
        const mat = obj.isMesh ? obj.material : null;
        const kind = mat?.userData?.cladding;
        if (!kind || mat.map) return;
        const texture = new THREE.CanvasTexture(claddingCanvas(kind, mat.userData.tint || '#e2e8f0'));
        texture.colorSpace = THREE.SRGBColorSpace;
        texture.wrapS = texture.wrapT = THREE.RepeatWrapping;
        texture.repeat.set(1 / PATCH_FT, 1 / PATCH_FT);
        mat.map = texture;
        mat.color.set(0xffffff); // the canvas already carries the tint
        mat.needsUpdate = true;
    });
}
