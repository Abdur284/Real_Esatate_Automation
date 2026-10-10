# Haven AI Backend

FastAPI backend for Haven.AI: the ArchiBot chatbot, 2D floor-plan generation,
3D model generation, interior design editing and the admin API.

## Project structure

```
app/
  main.py                 FastAPI app, CORS, routers
  core/
    config.py             settings from .env (see .env.example)
    firebase.py           the single Firebase Admin app + Firestore client
    auth.py               Firebase ID-token checks: optional_user, require_user, require_admin
    ratelimit.py          per-user/IP request limits on expensive endpoints
  api/endpoints/          chat, design_2d, design_3d, interior, admin
  services/
    chat/                 chatbot: routing.py, modules.py, templates.py, cache.py, orchestrator.py
    gemini.py             shared Gemini client with model fallbacks
    design2d/ design3d/   plan and model generators
    plan_vision/          floor-plan image analysis (OpenCV)
    interior/             room segmentation, scene editing, renderer, object library
    admin.py              admin dashboard data access (Firestore)
scripts/
  set_admin.py            grant / revoke administrator access
  fetch_interior_assets.py
tests/                    pytest suite
```

## Getting started

```bash
python -m venv venv
venv\Scripts\activate          # macOS/Linux: source venv/bin/activate
pip install -r requirements-dev.txt
pip install --no-deps rapidocr-onnxruntime==1.4.4   # floor-plan text (OCR); optional
copy .env.example .env            # macOS/Linux: cp .env.example .env  — then fill it in
uvicorn app.main:app --reload
```

The API runs on `http://localhost:8000`; interactive docs at `/docs`.

### Secrets

* `.env` — Gemini key and settings. Template: `.env.example`.
* `firebase-credentials.json` — Firebase **service-account** key (Firebase
  console → Project settings → Service accounts → Generate new private key).

Both are listed in the repository's `.gitignore` and must never be committed.
If a key was ever shared or committed, revoke it and generate a new one.

## Security model

| Concern | How it is handled |
|---|---|
| Who is calling | The frontend signs in with Firebase Auth and sends `Authorization: Bearer <ID token>`; `app/core/auth.py` verifies it. |
| Administrators | Firebase custom claim `admin: true`, granted only with the service account: `python scripts/set_admin.py you@example.com` (sign out and in again afterwards). Every `/api/admin/*` route requires it. |
| Direct Firestore access from the browser | Restricted by `/firestore.rules` (deploy with `firebase deploy --only firestore:rules` from the repository root). |
| AI chat sessions | Signed-in users are keyed by their verified uid; guests by a random id their browser generated — never by a user id sent in the body. |
| Abuse / quota | `RATE_LIMIT_PER_MINUTE` (default 20) per user or IP on chat, 2D/3D generation and interior uploads/renders. |
| Errors | Clients get a generic message; details go to the server log. |

## API overview

| Prefix | Purpose |
|---|---|
| `POST /api/chat/send` | ArchiBot chatbot (routes to the modules below) |
| `POST /api/design/2d/generate` | 2D floor plan from a brief (Gemini + deterministic validation) |
| `/api/design/3d/...` | 3D model from a brief, a 2D plan, a plan image or a property photo |
| `/api/interior/...` | Room photo → editable scene, object library, saved designs |
| `/api/admin/...` | Admin dashboard (admin claim required) |

## Tests

```bash
python -m pytest              # whole suite (about 4 minutes; the interior model tests need the ONNX model)
python -m pytest tests/test_security.py tests/test_chat.py
```

## Interior Design module (`/api/interior`)

Upload a room photo, then move, resize, rotate, recolour, re-material, replace,
add and remove what is in it. Code: `app/services/interior/`, API:
`app/api/endpoints/interior.py`, tests: `tests/test_interior_*.py`.

**Segmentation model (required once).** Room analysis uses SegFormer-B2
trained on ADE20K, exported to ONNX, run on the CPU with `onnxruntime`
(about 2 s per photo, no API key). Put the files in `ml_models/segformer-b2-ade/`:

```bash
mkdir -p ml_models/segformer-b2-ade && cd ml_models/segformer-b2-ade
curl -L -o model.onnx https://huggingface.co/Xenova/segformer-b2-finetuned-ade-512-512/resolve/main/onnx/model.onnx
curl -L -o config.json https://huggingface.co/Xenova/segformer-b2-finetuned-ade-512-512/resolve/main/config.json
```

Without it the rest of the API still runs; `POST /api/interior/scenes`
answers 503. The weights are NVIDIA's SegFormer release (research /
non-commercial licence) — replace them before any commercial use.

**Real 3D furniture and photographed materials (recommended).** The library's
realistic pieces are 3D models of real furniture and decor (photoscanned or
modelled, with PBR textures: colour, normal, roughness/metal, ambient
occlusion), and floors, walls and upholstery use photographed texture sets --
all CC0 from [Poly Haven](https://polyhaven.com). Download them once:

```bash
python scripts/fetch_interior_assets.py          # standard quality, ~210 MB (editing)
python scripts/fetch_interior_assets.py --high   # + high quality, ~660 MB more (final renders)
```

Files go to `INTERIOR_ASSET_DIR` (default `assets/interior`) and are checked by
MD5. Without them the editor still works with the simpler procedural models
and textures; items whose model is missing are left out of the library.

How a real model gets into the photo (`meshes.py`, `raster.py`,
`mesh_render.py`, `lighting.py`): the glTF is loaded at its real size,
placed through the photo's camera model, rasterised with a z-buffer
(supersampled, alpha-tested leaves, see-through glass) and shaded with GGX
PBR under the room's light estimated from the photo (key light from a
visible window/lamp or from above toward the brighter side, bounce light
from walls and floor, exposure and white balance calibrated on the walls);
glossy and metal parts reflect the photo itself. It casts a soft shadow on
the floor and walls from that light (shadow map) plus contact occlusion
under it, and shadows itself. Upholstery can be recoloured or given another
material (tri-planar PBR texture at real scale) while wood, metal and glass
keep their real finish. Quality levels: previews (library thumbnails),
standard 1k textures while editing, 2k textures and finer anti-aliasing for
the final render.

**Settings (`.env`).** `INTERIOR_SEG_MODEL_DIR`, `INTERIOR_STORAGE_DIR`
(default `storage/interior`: uploaded rooms and their history; unsaved rooms
are deleted after `INTERIOR_SCENE_TTL_HOURS`, default 24), `FIREBASE_CREDS_PATH`.

**No cloud AI provider.** The module runs entirely on the server: a local
segmentation model (any model behind the `segment()` contract in
`segmentation.py` can replace it), geometry, and the 3D renderer. The final
image is that renderer's output with the high-quality assets, downloaded as
PNG (lossless) or JPEG (high 95 / standard 85):
`POST /api/interior/scenes/{id}/final {"format": "png" | "jpg", "quality": "high" | "standard"}`,
then `GET` the returned `url` (`?download=true` to save it). The uploaded
photo is never modified.

**Object library.** `app/services/interior/library_data/` holds the catalogue:
`categories.json` (groups, categories, placement, allowed materials,
synonyms for search) and `items/*.json` (one entry per piece: name, style,
material, colour options, dimensions in cm, and a model reference).
Add pieces or whole categories by editing JSON only; the loader validates
every entry at start-up. Model kinds: `mesh` (a real 3D model, e.g.
`{"kind": "mesh", "source": "polyhaven", "asset": "sofa_03"}` in
`items/scanned.json`; size measured from the model; optional `yaw`,
`recolor` / `recolor_mask` for upholstery that may change colour),
`parametric` (a generator in `furniture3d.py` / `wall2d.py` plus
parameters; typical sizes), `image` (a transparent PNG in
`library_data/assets/`, drawn upright at real size). Real models are
listed first and can be filtered (`realism=real`, or words like "realistic").
**Replacing keeps size, place and turn** (`fit.py`). The catalogue size is
the starting point; the new piece is scaled to fill the replaced object's
space -- for a piece from the photo by matching its outline in the picture
through the same camera, for a 3D piece by its size in metres. Furniture is
scaled uniformly on its dominant dimension (so it keeps its proportions);
rugs and curtains fit width and length independently. Send
`"fit": "catalogue"` with `replace_object` for the real size instead, or
switch later with `{"operation": "fit_object", "changes": {"size": "original" | "catalogue"}}`.
Manual resizing stays available.
Material properties (roughness, metalness, texture set and its real size)
are in `library_data/pbr_materials.json`.
Previews are rendered by the room renderer on first request (all of them are
pre-rendered in the background when the library is first opened) and cached
in `INTERIOR_STORAGE_DIR/thumbs`. Search, filters, facets, sorting and
pagination run on the server (`/api/interior/library/...`).

**Licence note.** The SegFormer-B2 weights are released by NVIDIA for
research / non-commercial use only. That is fine for this academic project;
swap them for a commercially licensed model before any commercial deployment.

**Saved designs** are Firestore documents in `interior_designs`, written by
the backend after verifying the user's Firebase ID token
(`Authorization: Bearer <token>`); the photo stays in `INTERIOR_STORAGE_DIR`.

**Tests.** `python -m pytest tests/test_interior_api.py tests/test_interior_render.py`
use a synthetic room and no model; `tests/test_interior_model.py` runs the
real model on the photos in `tests/fixtures/rooms/` (skipped if the model is missing).
