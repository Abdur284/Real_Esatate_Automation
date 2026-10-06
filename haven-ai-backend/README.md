# Haven AI Backend

This is the FastAPI backend for the Haven AI project.

## Project Structure

- `app/main.py`: Entry point for the FastAPI application.
- `app/api/`: Contains the API endpoints.
- `app/core/`: Contains the core configuration and security settings.
- `app/models/`: Place for your ML/AI models and data models.
- `requirements.txt`: Python dependencies.

## Getting Started

### 1. Create a Virtual Environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Run the Backend
```bash
uvicorn app.main:app --reload
```
The API will be available at `http://localhost:8000`.
You can access the interactive API documentation at `http://localhost:8000/docs`.

### 4. ML/AI Integration
Add your model loading logic in `app/models/` and utilize them in `app/api/endpoints/`.

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

**Saved designs** are Firestore documents in `interior_designs`, written by
the backend after verifying the user's Firebase ID token
(`Authorization: Bearer <token>`); the photo stays in `INTERIOR_STORAGE_DIR`.

**Tests.** `python -m pytest tests/test_interior_api.py tests/test_interior_render.py`
use a synthetic room and no model; `tests/test_interior_model.py` runs the
real model on the photos in `tests/fixtures/rooms/` (skipped if the model is missing).
