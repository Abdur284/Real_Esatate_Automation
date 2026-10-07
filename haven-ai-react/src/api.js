// ── Centralized API configuration ──
// In development, requests are proxied via Vite (/api → http://localhost:8000/api)
// In production, set VITE_API_BASE_URL to your deployed backend URL

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

// ── Who is calling ──
// AuthContext registers a function returning the signed-in user's Firebase ID
// token (refreshed automatically by the SDK); null for guests.
let tokenProvider = null;

export function setTokenProvider(fn) {
  tokenProvider = fn;
}

async function authHeaders() {
  if (!tokenProvider) return {};
  try {
    const token = await tokenProvider();
    return token ? { Authorization: `Bearer ${token}` } : {};
  } catch {
    return {};
  }
}

// Guests' AI chat is kept together by a random id this browser generated once.
const GUEST_SESSION_KEY = 'haven_chat_session';

function guestSessionId() {
  try {
    let id = localStorage.getItem(GUEST_SESSION_KEY);
    if (!id || !/^[A-Za-z0-9_-]{8,64}$/.test(id)) {
      id = (crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`).replace(/[^A-Za-z0-9_-]/g, '');
      localStorage.setItem(GUEST_SESSION_KEY, id);
    }
    return id;
  } catch {
    return `tab${Date.now()}`;
  }
}

function errorFrom(status, detail, fallback) {
  const err = new Error(typeof detail?.detail === 'string' ? detail.detail : fallback);
  err.status = status;
  return err;
}

/** fetch with the user's token; JSON in and out; errors carry .status and the server's message */
async function request(path, { method = 'GET', body, form, fallback } = {}) {
  const headers = await authHeaders();
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  let res;
  try {
    res = await fetch(`${API_BASE_URL}${path}`, {
      method,
      headers,
      body: form || (body === undefined ? undefined : JSON.stringify(body)),
    });
  } catch {
    throw new Error('Could not reach the server. Check your connection and try again.');
  }
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw errorFrom(res.status, detail, fallback || `Request failed (${res.status}).`);
  }
  return res.json();
}

const api = {
  chat: {
    /** Send a message to the AI chat backend (signed-in users are identified by their token) */
    send: ({ message, context = '', history = [] }) =>
      request('/api/chat/send', {
        method: 'POST',
        body: { session_id: guestSessionId(), message, context, conversation_history: history },
      }),

    /** Check if the chat service is active */
    status: () => request('/api/chat/status'),
  },

  design2d: {
    /** Generate a 2D floor-plan specification (Gemini + server-side validation) */
    generate: ({ prompt, plotWidthFt, plotLengthFt, floors }) =>
      request('/api/design/2d/generate', {
        method: 'POST',
        body: {
          prompt,
          plot_width_ft: plotWidthFt ?? null,
          plot_length_ft: plotLengthFt ?? null,
          floors: floors ?? null,
        },
      }),
  },

  design3d: {
    /** Generate a validated 3D building model from a brief + optional plot dims */
    generate: ({ prompt, plotWidthFt, plotLengthFt, storeys }) =>
      request('/api/design/3d/generate', {
        method: 'POST',
        body: {
          prompt,
          plot_width_ft: plotWidthFt ?? null,
          plot_length_ft: plotLengthFt ?? null,
          storeys: storeys ?? null,
        },
      }),

    /** Generate a 3D design from a photo of the existing property (+ brief) */
    generateFromImage: ({ image, prompt, plotWidthFt, plotLengthFt, storeys, render, pixels, existing = {} }) => {
      const form = new FormData();
      form.append('image', image);
      form.append('prompt', prompt || '');
      if (plotWidthFt) form.append('plot_width_ft', String(plotWidthFt));
      if (plotLengthFt) form.append('plot_length_ft', String(plotLengthFt));
      if (storeys) form.append('storeys', String(storeys));
      form.append('render', render ? 'true' : 'false');
      // Built-in analyser inputs: a small RGB grid of the photo and the
      // facade details the user described.
      if (pixels) {
        form.append('pixels', pixels.data);
        form.append('pixels_width', String(pixels.width));
        form.append('pixels_height', String(pixels.height));
      }
      if (existing.frontWindows !== undefined && existing.frontWindows !== '') {
        form.append('front_windows', String(existing.frontWindows));
      }
      form.append('garage_door', existing.garageDoor ? 'true' : 'false');
      form.append('existing_balcony', existing.balcony ? 'true' : 'false');
      return request('/api/design/3d/generate-from-image', { method: 'POST', form });
    },

    /** Layer 1: read a 2D floor-plan image into a structured plan (for review) */
    analyzePlan: ({ image, widthFt, depthFt, front = 'bottom' }) => {
      const form = new FormData();
      form.append('image', image);
      if (widthFt) form.append('width_ft', String(widthFt));
      if (depthFt) form.append('depth_ft', String(depthFt));
      form.append('front', front);
      return request('/api/design/3d/analyze', { method: 'POST', form });
    },

    /** Absolute URL of a generated GLB (the API returns a path) */
    modelUrl: (path) => (path ? `${API_BASE_URL}${path}` : null),

    /** Build a 3D model from a structured plan (design2d.generate or analyzePlan) */
    fromPlan2d: (plan) => request('/api/design/3d/from-2d', { method: 'POST', body: { plan } }),
  },

  interior: {
    /** Upload a room photo; reports upload progress (0-1). Resolves to the scene response. */
    analyze: async (file, onProgress) => {
      const headers = await authHeaders();
      return new Promise((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        xhr.open('POST', `${API_BASE_URL}/api/interior/scenes`);
        if (headers.Authorization) xhr.setRequestHeader('Authorization', headers.Authorization);
        xhr.upload.onprogress = (e) => { if (e.lengthComputable && onProgress) onProgress(e.loaded / e.total); };
        xhr.upload.onload = () => onProgress && onProgress(1);
        xhr.onload = () => {
          let body = null;
          try { body = JSON.parse(xhr.responseText); } catch { /* not JSON */ }
          if (xhr.status >= 200 && xhr.status < 300) return resolve(body);
          reject(errorFrom(xhr.status, body, `Upload failed (${xhr.status}).`));
        };
        xhr.onerror = () => reject(new Error('Could not reach the server. Check your connection and try again.'));
        xhr.ontimeout = () => reject(new Error('The server took too long to answer. Please try again.'));
        xhr.timeout = 120000;
        const form = new FormData();
        form.append('image', file);
        xhr.send(form);
      });
    },

    /** JSON request under /api/interior with the user's token */
    request: (path, opts) => request(`/api/interior${path}`, opts),

    /** Fetches an image the API serves (with the token) and returns an object URL */
    image: async (path) => {
      const res = await fetch(`${API_BASE_URL}${path}`, { headers: await authHeaders() });
      if (!res.ok) {
        const err = new Error(`Image request failed (${res.status}).`);
        err.status = res.status;
        throw err;
      }
      return { url: URL.createObjectURL(await res.blob()), bounds: res.headers.get('X-Bounds') };
    },

    catalog: () => api.interior.request('/catalog'),
    library: {
      categories: () => api.interior.request('/library/categories'),
      /** Server-side search: q (free text / natural language), category, group, style, material, color, size, sort, page */
      search: (params = {}) => {
        const qs = new URLSearchParams();
        Object.entries(params).forEach(([k, v]) => { if (v !== undefined && v !== null && v !== '') qs.set(k, v); });
        return api.interior.request(`/library/search?${qs.toString()}`);
      },
      item: (id) => api.interior.request(`/library/items/${encodeURIComponent(id)}`),
      /** Previews are public and cacheable, so they load as plain <img> URLs */
      url: (path) => `${API_BASE_URL}${path}`,
      swatch: (material, color) =>
        `${API_BASE_URL}/api/interior/library/materials/${material}/swatch.png${color ? `?color=${encodeURIComponent(color)}` : ''}`,
    },
    scene: (id) => api.interior.request(`/scenes/${id}`),
    apply: (id, baseVersion, operation) =>
      api.interior.request(`/scenes/${id}/operations`, { method: 'POST', body: { base_version: baseVersion, operation } }),
    undo: (id) => api.interior.request(`/scenes/${id}/undo`, { method: 'POST' }),
    redo: (id) => api.interior.request(`/scenes/${id}/redo`, { method: 'POST' }),
    reset: (id) => api.interior.request(`/scenes/${id}/reset`, { method: 'POST' }),
    /** Final image of the design: format 'png' (lossless) or 'jpg'; quality 'high' | 'standard' (JPEG) */
    final: (id, format = 'jpg', quality = 'high') =>
      api.interior.request(`/scenes/${id}/final`, { method: 'POST', body: { format, quality } }),
    designs: {
      list: () => api.interior.request('/designs'),
      save: (sceneId, name) => api.interior.request('/designs', { method: 'POST', body: { scene_id: sceneId, name } }),
      open: (id) => api.interior.request(`/designs/${id}`),
      rename: (id, name) => api.interior.request(`/designs/${id}`, { method: 'PUT', body: { name } }),
      remove: (id) => api.interior.request(`/designs/${id}`, { method: 'DELETE' }),
    },
  },

  /** Administrator endpoints (require the `admin` claim on the signed-in account) */
  admin: {
    stats: () => request('/api/admin/stats'),
    activity: () => request('/api/admin/activity'),
    users: () => request('/api/admin/users'),
    deleteUser: (uid) => request(`/api/admin/users/${encodeURIComponent(uid)}`, { method: 'DELETE' }),
    properties: (verified) =>
      request(`/api/admin/properties${verified === undefined ? '' : `?verified=${verified}`}`),
    verifyProperty: (id) => request(`/api/admin/properties/${encodeURIComponent(id)}/verify`, { method: 'POST' }),
    resetViews: () => request('/api/admin/properties/reset-views', { method: 'POST' }),
    health: () => request('/api/admin/health'),
  },

  /** Health check — root endpoint */
  health: () => request('/'),
};

export default api;
