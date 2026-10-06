// ── Centralized API configuration ──
// In development, requests are proxied via Vite (/api → http://localhost:8000/api)
// In production, set VITE_API_BASE_URL to your deployed backend URL

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

const api = {
  chat: {
    /** Send a message to the AI chat backend */
    send: async ({ userId = 'guest', message, context = '', history = [] }) => {
      const res = await fetch(`${API_BASE_URL}/api/chat/send`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          message,
          context,
          conversation_history: history
        }),
      });
      if (!res.ok) {
        throw new Error(`API error: ${res.status}`);
      }
      return res.json();
    },

    /** Check if the chat service is active */
    status: async () => {
      const res = await fetch(`${API_BASE_URL}/api/chat/status`);
      return res.json();
    },
  },

  design2d: {
    /** Generate a 2D floor-plan specification (Gemini + server-side validation) */
    generate: async ({ prompt, plotWidthFt, plotLengthFt, floors }) => {
      const res = await fetch(`${API_BASE_URL}/api/design/2d/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt,
          plot_width_ft: plotWidthFt ?? null,
          plot_length_ft: plotLengthFt ?? null,
          floors: floors ?? null,
        }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        throw new Error(detail?.detail || `API error: ${res.status}`);
      }
      return res.json();
    },
  },

  design3d: {
    /** Generate a validated 3D building model from a brief + optional plot dims */
    generate: async ({ prompt, plotWidthFt, plotLengthFt, storeys }) => {
      const res = await fetch(`${API_BASE_URL}/api/design/3d/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt,
          plot_width_ft: plotWidthFt ?? null,
          plot_length_ft: plotLengthFt ?? null,
          storeys: storeys ?? null,
        }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        throw new Error(detail?.detail || `API error: ${res.status}`);
      }
      return res.json();
    },

    /** Generate a 3D design from a photo of the existing property (+ brief) */
    generateFromImage: async ({ image, prompt, plotWidthFt, plotLengthFt, storeys, render, pixels, existing = {} }) => {
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
      const res = await fetch(`${API_BASE_URL}/api/design/3d/generate-from-image`, { method: 'POST', body: form });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        throw new Error(detail?.detail || `API error: ${res.status}`);
      }
      return res.json();
    },

    /** Layer 1: read a 2D floor-plan image into a structured plan (for review) */
    analyzePlan: async ({ image, widthFt, depthFt, front = 'bottom' }) => {
      const form = new FormData();
      form.append('image', image);
      if (widthFt) form.append('width_ft', String(widthFt));
      if (depthFt) form.append('depth_ft', String(depthFt));
      form.append('front', front);
      const res = await fetch(`${API_BASE_URL}/api/design/3d/analyze`, { method: 'POST', body: form });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        const err = new Error(typeof detail?.detail === 'string' ? detail.detail : `API error: ${res.status}`);
        err.status = res.status;
        throw err;
      }
      return res.json();
    },

    /** Absolute URL of a generated GLB (the API returns a path) */
    modelUrl: (path) => (path ? `${API_BASE_URL}${path}` : null),

    /** Build a 3D model from a structured plan (design2d.generate or analyzePlan) */
    fromPlan2d: async (plan) => {
      const res = await fetch(`${API_BASE_URL}/api/design/3d/from-2d`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ plan }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        throw new Error(detail?.detail || `API error: ${res.status}`);
      }
      return res.json();
    },
  },

  interior: {
    /** The signed-in user's Firebase ID token (saved by the Signup page), or null */
    token: () => {
      try { return JSON.parse(localStorage.getItem('housing_user') || 'null')?.idToken || null; } catch { return null; }
    },

    /** Upload a room photo; reports upload progress (0-1). Resolves to the scene response. */
    analyze: (file, onProgress) => new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open('POST', `${API_BASE_URL}/api/interior/scenes`);
      const token = api.interior.token();
      if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`);
      xhr.upload.onprogress = (e) => { if (e.lengthComputable && onProgress) onProgress(e.loaded / e.total); };
      xhr.upload.onload = () => onProgress && onProgress(1);
      xhr.onload = () => {
        let body = null;
        try { body = JSON.parse(xhr.responseText); } catch { /* not JSON */ }
        if (xhr.status >= 200 && xhr.status < 300) return resolve(body);
        const err = new Error(typeof body?.detail === 'string' ? body.detail : `Upload failed (${xhr.status}).`);
        err.status = xhr.status;
        reject(err);
      };
      xhr.onerror = () => reject(new Error('Could not reach the server. Check your connection and try again.'));
      xhr.ontimeout = () => reject(new Error('The server took too long to answer. Please try again.'));
      xhr.timeout = 120000;
      const form = new FormData();
      form.append('image', file);
      xhr.send(form);
    }),

    /** JSON request with the user's token; errors carry .status and the server's message */
    request: async (path, { method = 'GET', body } = {}) => {
      const headers = {};
      const token = api.interior.token();
      if (token) headers.Authorization = `Bearer ${token}`;
      if (body !== undefined) headers['Content-Type'] = 'application/json';
      let res;
      try {
        res = await fetch(`${API_BASE_URL}/api/interior${path}`, {
          method, headers, body: body === undefined ? undefined : JSON.stringify(body),
        });
      } catch {
        throw new Error('Could not reach the server. Check your connection and try again.');
      }
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        const err = new Error(typeof detail?.detail === 'string' ? detail.detail : `Request failed (${res.status}).`);
        err.status = res.status;
        throw err;
      }
      return res.json();
    },

    /** Fetches an image the API serves (with the token) and returns an object URL */
    image: async (path) => {
      const headers = {};
      const token = api.interior.token();
      if (token) headers.Authorization = `Bearer ${token}`;
      const res = await fetch(`${API_BASE_URL}${path}`, { headers });
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

  /** Health check — root endpoint */
  health: async () => {
    const res = await fetch(`${API_BASE_URL}/`);
    return res.json();
  },
};

export default api;
