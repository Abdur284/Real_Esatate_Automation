// Shrinks a photo to a small RGB grid for the backend's built-in photo
// analyser (no AI service). The browser decodes the image, so the backend
// needs no image library; the grid is at most MAX_SIDE pixels a side.

const MAX_SIDE = 128;

export async function photoToPixels(file) {
    const bitmap = await createImageBitmap(file);
    const scale = Math.min(1, MAX_SIDE / Math.max(bitmap.width, bitmap.height));
    const width = Math.max(8, Math.round(bitmap.width * scale));
    const height = Math.max(8, Math.round(bitmap.height * scale));

    const canvas = document.createElement('canvas');
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(bitmap, 0, 0, width, height);
    bitmap.close?.();

    const rgba = ctx.getImageData(0, 0, width, height).data;
    const rgb = new Uint8Array(width * height * 3);
    for (let i = 0, j = 0; i < rgba.length; i += 4, j += 3) {
        rgb[j] = rgba[i];
        rgb[j + 1] = rgba[i + 1];
        rgb[j + 2] = rgba[i + 2];
    }
    let binary = '';
    for (let i = 0; i < rgb.length; i += 0x8000) {
        binary += String.fromCharCode(...rgb.subarray(i, i + 0x8000));
    }
    return { data: btoa(binary), width, height };
}
