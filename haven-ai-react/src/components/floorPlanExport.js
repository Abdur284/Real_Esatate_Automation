// Turns rendered floor-plan SVGs into downloadable files: a PNG sheet (one or
// more floors side by side, with a title and a disclaimer) or a vector SVG.

const PX_PER_FT = 16;      // PNG resolution: a 25 x 50 ft plot is ~500 x 900 px per floor
const HEADER_PX = 70;
const FOOTER_PX = 40;
const GAP_PX = 40;
const FONT = '"Inter", "Segoe UI", Arial, sans-serif';

// The latest generated 2D plan, offered on the 3D Design page ("Use existing 2D design").
export const LAST_PLAN_KEY = 'haven.design2d.lastPlan';
// PNG text-chunk keyword for the embedded plan; the backend's floor-plan
// analyser reads it back (plan_vision/image_io.py) instead of estimating.
export const PLAN_CHUNK_KEYWORD = 'haven-plan2d';

const CRC_TABLE = (() => {
    const t = new Uint32Array(256);
    for (let n = 0; n < 256; n++) {
        let c = n;
        for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
        t[n] = c >>> 0;
    }
    return t;
})();

function crc32(bytes) {
    let c = 0xffffffff;
    for (let i = 0; i < bytes.length; i++) c = CRC_TABLE[(c ^ bytes[i]) & 0xff] ^ (c >>> 8);
    return (c ^ 0xffffffff) >>> 0;
}

/** Returns a copy of a PNG with an uncompressed iTXt chunk (keyword -> UTF-8
 *  text) inserted before IEND. */
export function embedPngText(pngBytes, keyword, text) {
    const enc = new TextEncoder();
    const kw = enc.encode(keyword);
    const body = new Uint8Array([...kw, 0, 0, 0, 0, 0, ...enc.encode(text)]); // no compression, no language
    const type = enc.encode('iTXt');
    const chunk = new Uint8Array(12 + body.length);
    const view = new DataView(chunk.buffer);
    view.setUint32(0, body.length);
    chunk.set(type, 4);
    chunk.set(body, 8);
    view.setUint32(8 + body.length, crc32(new Uint8Array([...type, ...body])));
    const iend = pngBytes.length - 12; // IEND is always the last, empty chunk
    const out = new Uint8Array(pngBytes.length + chunk.length);
    out.set(pngBytes.subarray(0, iend), 0);
    out.set(chunk, iend);
    out.set(pngBytes.subarray(iend), iend + chunk.length);
    return out;
}

function saveBlob(blob, filename) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** Standalone copy of a plan SVG sized in pixels, with fonts that exist
 *  outside the page (an exported file cannot rely on the page's web fonts). */
function standaloneSvg(svg) {
    const clone = svg.cloneNode(true);
    const [, , vbW, vbH] = clone.getAttribute('viewBox').split(/\s+/).map(Number);
    clone.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
    clone.setAttribute('width', String(Math.round(vbW * PX_PER_FT)));
    clone.setAttribute('height', String(Math.round(vbH * PX_PER_FT)));
    clone.removeAttribute('style');
    clone.querySelectorAll('text').forEach((t) => t.setAttribute('font-family', FONT));
    clone.querySelectorAll('title').forEach((t) => t.remove());
    return { markup: new XMLSerializer().serializeToString(clone), width: vbW * PX_PER_FT, height: vbH * PX_PER_FT };
}

function loadSvgImage(markup) {
    return new Promise((resolve, reject) => {
        const img = new Image();
        img.onload = () => resolve(img);
        img.onerror = () => reject(new Error('Could not render the floor plan.'));
        img.src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(markup)}`;
    });
}

/**
 * floors: [{ label, svg }]  (svg = the rendered <svg> element)
 * info:   { title, subtitle }
 * plan:   optional structured plan embedded in the PNG, so uploading the file
 *         to 3D Design reproduces it exactly
 */
export async function downloadPng(floors, info, filename, plan = null) {
    const parts = await Promise.all(floors.map(async (f) => {
        const s = standaloneSvg(f.svg);
        return { ...s, label: f.label, img: await loadSvgImage(s.markup) };
    }));
    const width = parts.reduce((w, p) => w + p.width, 0) + GAP_PX * (parts.length + 1);
    const height = HEADER_PX + Math.max(...parts.map((p) => p.height)) + 30 + FOOTER_PX;

    const canvas = document.createElement('canvas');
    canvas.width = Math.ceil(width);
    canvas.height = Math.ceil(height);
    const g = canvas.getContext('2d');
    g.fillStyle = '#ffffff';
    g.fillRect(0, 0, canvas.width, canvas.height);

    g.fillStyle = '#0f172a';
    g.font = `700 24px ${FONT}`;
    g.fillText(info.title, GAP_PX, 34);
    g.fillStyle = '#475569';
    g.font = `14px ${FONT}`;
    g.fillText(info.subtitle, GAP_PX, 56);

    let x = GAP_PX;
    parts.forEach((p) => {
        g.fillStyle = '#1e293b';
        g.font = `700 16px ${FONT}`;
        g.fillText(p.label, x, HEADER_PX + 18);
        g.drawImage(p.img, x, HEADER_PX + 30, p.width, p.height);
        x += p.width + GAP_PX;
    });

    g.fillStyle = '#94a3b8';
    g.font = `12px ${FONT}`;
    g.fillText('AI-generated concept layout. Dimensions are approximate; not an approved architectural drawing.',
        GAP_PX, canvas.height - 16);

    let blob = await new Promise((resolve) => canvas.toBlob(resolve, 'image/png'));
    if (!blob) throw new Error('Could not create the image.');
    if (plan) {
        const bytes = embedPngText(new Uint8Array(await blob.arrayBuffer()), PLAN_CHUNK_KEYWORD, JSON.stringify(plan));
        blob = new Blob([bytes], { type: 'image/png' });
    }
    saveBlob(blob, filename);
}

export function downloadSvg(svg, filename) {
    const { markup } = standaloneSvg(svg);
    saveBlob(new Blob([`<?xml version="1.0" encoding="UTF-8"?>\n${markup}`], { type: 'image/svg+xml' }), filename);
}
