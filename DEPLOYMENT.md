# Deploying Haven.AI

This guide deploys the **backend** (FastAPI) to **Render** as a Docker image and
the **frontend** (React/Vite) to **Vercel**. Any equivalent hosts work the same
way — the only requirements are: the backend runs the Docker image, and the
frontend is a static build that knows the backend URL.

```
Browser ──> Vercel (static React)         VITE_API_BASE_URL
                │                          ──────────────────>  Render (FastAPI)
                └── Firebase Auth / Firestore (client SDK)      firebase-credentials.json
```

---

## 0. Before anything: the large files problem

Two things the backend needs at runtime are **gitignored** and live only on your
machine, so a host that builds from GitHub will not have them:

| File | Size | Used by |
|---|---|---|
| `haven-ai-backend/ml_models/segformer-b2-ade/model.onnx` | ~110 MB | Interior Design (room segmentation) |
| `haven-ai-backend/assets/interior/models`, `.../textures/*` | ~0.9 GB | Interior Design 3D objects & textures |

Because of this, **build the Docker image on your machine** (where the files
exist) and push it to a registry, then have Render deploy that image. Building
straight from the repo will start fine but Interior Design and 3D texturing will
fail at runtime. (If you don't need Interior Design in the deployed demo, you can
skip the image-build route and let Render build from the repo.)

---

## 1. Backend → Render

### 1a. Build and push the image (from your machine)

```bash
# From the repo root. Use any registry you like (Docker Hub shown).
docker build -t YOUR_DOCKERHUB_USER/haven-ai-backend:latest haven-ai-backend
docker push YOUR_DOCKERHUB_USER/haven-ai-backend:latest
```

### 1b. Create the service on Render

- **New → Web Service → Deploy an existing image**, use the image from 1a.
  (Or **New → Blueprint** and point it at `render.yaml` if you committed the
  large files via Git LFS instead.)
- Plan: **Starter or higher** — the free tier does not have enough RAM/disk for
  onnxruntime + opencv + xgboost + the ONNX model.
- Add a **Disk**: mount path `/app/storage`, 2 GB (keeps interior-design scenes
  across restarts).
- Health check path: `/api/health`.
- Instances: **1** (password-reset codes and interior scenes are per-instance).

### 1c. Environment variables (Render → Environment)

| Key | Value |
|---|---|
| `GEMINI_API_KEY` | your Google AI Studio key |
| `FIREBASE_CREDS_PATH` | `/etc/secrets/firebase-credentials.json` |
| `CORS_ORIGINS` | your Vercel URL, e.g. `https://haven-ai.vercel.app` (comma-separate if several) |
| `RATE_LIMIT_PER_MINUTE` | `20` |
| `DESIGN3D_TEXT_GENERATOR` | `gemini` (or `builtin`) |
| `PLAN_ANALYZER` | `gemini` (or `builtin`) |
| `DESIGN3D_PHOTO_ANALYZER` | `gemini` (or `builtin`) |
| `RESET_CODE_LOG_ONLY` | `false` (set `true` only if you skip SMTP for a demo) |
| `SMTP_HOST` `SMTP_PORT` `SMTP_USER` `SMTP_PASSWORD` `SMTP_FROM` | for password-reset emails (Gmail: App Password) |
| `ZAMEEN_API_URL` `ZAMEEN_API_KEY` | optional property listings; leave blank to disable |

### 1d. Firebase service-account key (Secret File)

Render → the service → **Environment → Secret Files → Add Secret File**:
- Filename: `firebase-credentials.json`
- Contents: paste the full JSON of your `haven-ai-backend/firebase-credentials.json`

It mounts at `/etc/secrets/firebase-credentials.json`, which `FIREBASE_CREDS_PATH`
above points to. **Never commit this file.**

### 1e. Verify

Open `https://YOUR-BACKEND.onrender.com/api/health` → `{"status":"ok"}`.
Interactive API docs are at `/docs`.

---

## 2. Frontend → Vercel

1. **New Project → import the repo**, set **Root Directory** to `haven-ai-react`.
   Vercel auto-detects Vite; `vercel.json` sets the build and SPA rewrites.
2. **Environment Variables** (copy from `.env.production.example`):
   - `VITE_API_BASE_URL` = your Render backend URL (no trailing slash)
   - `VITE_FIREBASE_*` = your Firebase web config (optional; falls back to the
     values in `src/firebase.js`)
3. Deploy. Note the resulting URL (e.g. `https://haven-ai.vercel.app`).
4. Go back and make sure `CORS_ORIGINS` on Render includes this exact URL.

---

## 3. Firebase one-time setup

```bash
# From the repo root, with the Firebase CLI installed and `firebase use <project-id>`.
firebase deploy --only firestore:rules
```

- **Authorized domains:** Firebase console → Authentication → Settings →
  **Authorized domains** → add your Vercel domain, or sign-in will be blocked.
- **Admin account:** create your account on the live site, then:
  ```bash
  cd haven-ai-backend && python scripts/set_admin.py you@example.com
  ```
  Sign out and back in; the **Admin** link appears.

---

## 4. Smoke test (in the deployed site)

- [ ] `/api/health` returns ok; home page loads.
- [ ] Sign up / log in works (Firebase authorized domain set).
- [ ] ArchiBot chat replies (Gemini key set).
- [ ] 2D plan and 3D model generate.
- [ ] Interior Design: upload a room photo → it segments (needs the ONNX model
      and assets baked into the image — see section 0).
- [ ] Forgot-password sends a code (SMTP set) or logs it (`RESET_CODE_LOG_ONLY`).
- [ ] Admin dashboard loads for the admin account.

---

## Known limitations (by design, not bugs)

- **Password reset** codes are stored in the backend's memory: they are lost on
  restart and do not work across multiple instances. Keep `numInstances: 1`.
- **Cost estimation** uses the committed `ml_models/xgb_cost_model.pkl`; if that
  file or its deps are missing it falls back to a typical-rate estimate.
- **Property recommendations** in chat still return sample listings (Phase 3,
  deliberately deferred).
- **Gemini free tier** will return 429s under real traffic; the rate limiter
  softens this but a paid key is needed for sustained load.
