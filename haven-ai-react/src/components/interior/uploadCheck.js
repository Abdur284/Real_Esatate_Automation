// Quick checks on a chosen room photo before it is uploaded. The server
// checks again from the file's content; these only give a fast answer.

export const ACCEPTED_TYPES = ['image/jpeg', 'image/png', 'image/webp'];
const ACCEPTED_EXT = /\.(jpe?g|png|webp)$/i;
export const MAX_MB = 10;
export const MIN_SIDE = 320;

/** Returns an error message, or null if the file may be sent. */
export function checkFile(file) {
    if (!file) return 'Choose a photo first.';
    if (!ACCEPTED_TYPES.includes(file.type) && !ACCEPTED_EXT.test(file.name || '')) {
        return 'Use a JPG, PNG or WebP photo.';
    }
    if (file.size === 0) return 'This file is empty.';
    if (file.size > MAX_MB * 1024 * 1024) return `The photo is larger than ${MAX_MB} MB. Use a smaller one.`;
    return null;
}

/** Error message when the decoded photo is too small, else null. */
export function checkDimensions({ width, height }) {
    if (Math.min(width, height) < MIN_SIDE) {
        return `The photo is too small (${width}×${height}). Use one at least ${MIN_SIDE} px on each side.`;
    }
    return null;
}
