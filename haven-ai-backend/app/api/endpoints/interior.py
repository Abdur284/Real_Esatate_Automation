"""
Interior Design API (/api/interior).

    POST   /scenes                         upload a room photo -> editable scene
    GET    /scenes/{id}                    current scene state
    POST   /scenes/{id}/operations         apply one edit operation
    POST   /scenes/{id}/undo | /redo | /reset
    GET    /scenes/{id}/render?v=&w=       composite image of a scene version
    GET    /scenes/{id}/original           the uploaded photo (working size)
    GET    /scenes/{id}/objects/{oid}/sprite   one object alone (drag preview)
    POST   /scenes/{id}/final              final image to download (PNG or JPEG)
    GET    /scenes/{id}/files/{name}       a generated final image
    GET    /catalog                        types, materials, palette the editor offers
    GET    /library/categories | /library/search | /library/items/{id}[/thumbnail.png]
                                           the object library (search, filters, previews)
    GET    /library/materials/{key}/swatch.png   material sample
    POST   /designs  GET /designs  GET|PUT|DELETE /designs/{id}   saved designs (sign-in)

Scenes are reachable by their unguessable id; a scene uploaded while signed in
is private to that user. Saving requires sign-in (Firebase ID token).
"""
import logging
from typing import Annotated, Literal, Optional, Union

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool

from app.core.auth import optional_user, require_user
from app.core.firebase import FirebaseUnavailable
from app.core.ratelimit import rate_limit
from app.services.interior import service
from app.services.interior.designs import DesignNotFound, get_repository
from app.services.interior.image_input import MAX_IMAGE_BYTES, RoomImageRejected
from app.services.interior.library import DETECTED_TO_CATEGORY, get_library
from app.services.interior.operations import OperationError
from app.services.interior.segmentation import SegmentationUnavailable
from app.services.interior.store import HistoryConflict, SceneForbidden, SceneNotFound

router = APIRouter()
logger = logging.getLogger(__name__)


# ---- request schemas -----------------------------------------------------------

class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class XY(Strict):
    x: Optional[float] = None
    y: Optional[float] = None


class Scale(Strict):
    x: Optional[float] = None
    y: Optional[float] = None
    z: Optional[float] = None


class AppearanceChanges(Strict):
    color: Optional[str] = Field(None, description="#RRGGBB, or null to go back to the photo's colour")
    material: Optional[str] = Field(None, description="material key from /catalog, or 'original'")


class TransformChanges(Strict):
    position: Optional[XY] = None
    scale: Optional[Scale] = None
    rotation: Optional[float] = None
    flip: Optional[bool] = None


class ReplaceChanges(Strict):
    library_item: Optional[str] = Field(None, description="id of the object-library item to put in its place")
    type: Optional[str] = Field(None, description="older clients: a type; its category's standard item is used")
    color: Optional[str] = None
    fit: Optional[Literal["match", "catalogue"]] = Field(
        None, description="'match' (default): scaled to fill the replaced object's space; 'catalogue': real size")


class FitChanges(Strict):
    size: Literal["original", "catalogue"] = Field(
        ..., description="'original': the size it was fitted to when it replaced something; 'catalogue': real size")


class NewObject(Strict):
    library_item: Optional[str] = None
    type: Optional[str] = None
    position: Optional[XY] = None
    color: Optional[str] = None
    material: Optional[str] = None


class UpdateObjectOp(Strict):
    operation: Literal["update_object"]
    object_id: str
    changes: AppearanceChanges


class UpdateSurfaceOp(Strict):
    operation: Literal["update_surface"]
    surface_id: str
    changes: AppearanceChanges


class TransformObjectOp(Strict):
    operation: Literal["transform_object"]
    object_id: str
    changes: TransformChanges


class ReplaceObjectOp(Strict):
    operation: Literal["replace_object"]
    object_id: str
    changes: ReplaceChanges


class FitObjectOp(Strict):
    operation: Literal["fit_object"]
    object_id: str
    changes: FitChanges


class AddObjectOp(Strict):
    operation: Literal["add_object"]
    object: NewObject


class RemoveObjectOp(Strict):
    operation: Literal["remove_object"]
    object_id: str


class RestoreObjectOp(Strict):
    operation: Literal["restore_object"]
    object_id: str


class ResetObjectOp(Strict):
    operation: Literal["reset_object"]
    object_id: str


Operation = Annotated[Union[UpdateObjectOp, UpdateSurfaceOp, TransformObjectOp, ReplaceObjectOp, FitObjectOp,
                            AddObjectOp, RemoveObjectOp, RestoreObjectOp, ResetObjectOp], Field(discriminator="operation")]


class OperationRequest(Strict):
    base_version: Optional[int] = Field(None, description="scene version the edit was made on (409 if stale)")
    operation: Operation


class FinalRequest(Strict):
    format: Literal["png", "jpg"] = Field("jpg", description="png = lossless, jpg = smaller")
    quality: Literal["high", "standard"] = Field("high", description="JPEG only: high = 95, standard = 85")


class SaveRequest(Strict):
    scene_id: str
    name: str = Field("", max_length=80)


class RenameRequest(Strict):
    name: str = Field(..., min_length=1, max_length=80)


# ---- error mapping -------------------------------------------------------------

def _fail(exc: Exception):
    if isinstance(exc, HTTPException):
        raise exc
    if isinstance(exc, RoomImageRejected):
        raise HTTPException(status_code=exc.status, detail=str(exc))
    if isinstance(exc, OperationError):
        raise HTTPException(status_code=422, detail=str(exc))
    if isinstance(exc, HistoryConflict):
        raise HTTPException(status_code=409, detail="The room changed in the meantime (another tab?). "
                                                    "It has been reloaded; please repeat the change.")
    if isinstance(exc, (SceneNotFound, DesignNotFound, KeyError)):
        raise HTTPException(status_code=404, detail="This room or design was not found. It may have expired; "
                                                    "please upload the photo again.")
    if isinstance(exc, SceneForbidden):
        raise HTTPException(status_code=403, detail="This room belongs to another account.")
    if isinstance(exc, SegmentationUnavailable):
        raise HTTPException(status_code=503, detail="Room analysis is not available on this server right now.")
    if isinstance(exc, FirebaseUnavailable):
        raise HTTPException(status_code=503, detail="Saved designs are not available right now. "
                                                    "Please try again later.")
    if isinstance(exc, FileNotFoundError):
        raise HTTPException(status_code=410, detail="The photo for this design is no longer on the server.")
    logger.exception("Interior design request failed")
    raise HTTPException(status_code=500, detail="Something went wrong while processing the room. "
                                                "Please try again.")


# ---- scenes --------------------------------------------------------------------

@router.post("/scenes", dependencies=[Depends(rate_limit("interior-upload"))])
async def create_scene(image: UploadFile = File(...), uid: Optional[str] = Depends(optional_user)):
    """Upload a room photo (JPG/PNG/WebP, max 10 MB, checked by content). The
    photo is analysed once (about 2-4 s on CPU) into an editable scene."""
    data = await image.read(MAX_IMAGE_BYTES + 1)
    await image.close()
    try:
        return await run_in_threadpool(service.analyze_room, data, uid)
    except Exception as exc:
        _fail(exc)


@router.get("/scenes/{scene_id}")
async def get_scene(scene_id: str, uid: Optional[str] = Depends(optional_user)):
    try:
        return await run_in_threadpool(service.get_scene, scene_id, uid)
    except Exception as exc:
        _fail(exc)


@router.post("/scenes/{scene_id}/operations")
async def apply_operation(scene_id: str, req: OperationRequest, uid: Optional[str] = Depends(optional_user)):
    """Apply one edit. The response carries the whole new scene, notes about
    adjustments (e.g. a piece kept on the floor) and the new render URL."""
    op = req.operation.model_dump(exclude_unset=True)
    try:
        return await run_in_threadpool(service.apply, scene_id, uid, req.base_version, op)
    except Exception as exc:
        _fail(exc)


@router.post("/scenes/{scene_id}/undo")
async def undo(scene_id: str, uid: Optional[str] = Depends(optional_user)):
    try:
        return await run_in_threadpool(service.undo, scene_id, uid)
    except HistoryConflict:
        raise HTTPException(status_code=409, detail="There is nothing to undo.")
    except Exception as exc:
        _fail(exc)


@router.post("/scenes/{scene_id}/redo")
async def redo(scene_id: str, uid: Optional[str] = Depends(optional_user)):
    try:
        return await run_in_threadpool(service.redo, scene_id, uid)
    except HistoryConflict:
        raise HTTPException(status_code=409, detail="There is nothing to redo.")
    except Exception as exc:
        _fail(exc)


@router.post("/scenes/{scene_id}/reset")
async def reset(scene_id: str, uid: Optional[str] = Depends(optional_user)):
    try:
        return await run_in_threadpool(service.reset, scene_id, uid)
    except Exception as exc:
        _fail(exc)


@router.get("/scenes/{scene_id}/render")
async def render(scene_id: str, v: Optional[int] = None, w: int = Query(0, ge=0, le=4096),
                 uid: Optional[str] = Depends(optional_user)):
    try:
        data = await run_in_threadpool(service.render_version, scene_id, uid, v, w)
    except Exception as exc:
        _fail(exc)
    return Response(content=data, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=86400"})


@router.get("/scenes/{scene_id}/original")
async def original(scene_id: str, uid: Optional[str] = Depends(optional_user)):
    try:
        data = await run_in_threadpool(service.original_image, scene_id, uid)
    except Exception as exc:
        _fail(exc)
    return Response(content=data, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=86400"})


@router.get("/scenes/{scene_id}/objects/{object_id}/sprite")
async def sprite(scene_id: str, object_id: str, uid: Optional[str] = Depends(optional_user)):
    """PNG of one object alone at its current place; X-Bounds holds its
    normalised box (x,y,w,h) in the image."""
    try:
        out = await run_in_threadpool(service.sprite, scene_id, uid, object_id)
    except Exception as exc:
        _fail(exc)
    if out is None:
        raise HTTPException(status_code=404, detail="That object is not in the room.")
    data, b = out
    return Response(content=data, media_type="image/png",
                    headers={"X-Bounds": f"{b['x']:.5f},{b['y']:.5f},{b['w']:.5f},{b['h']:.5f}",
                             "Access-Control-Expose-Headers": "X-Bounds", "Cache-Control": "no-store"})


@router.post("/scenes/{scene_id}/final", dependencies=[Depends(rate_limit("interior-final"))])
async def final(scene_id: str, req: FinalRequest, uid: Optional[str] = Depends(optional_user)):
    """Final image of the current design, rendered from the scene with the
    high-quality assets, as PNG or JPEG."""
    try:
        return await service.final_render(scene_id, uid, req.format, req.quality)
    except Exception as exc:
        _fail(exc)


@router.get("/scenes/{scene_id}/files/{name}")
async def final_file(scene_id: str, name: str, download: bool = False, uid: Optional[str] = Depends(optional_user)):
    """A stored image of the room (original photo or a final render);
    `download=true` asks the browser to save it."""
    try:
        data = await run_in_threadpool(service.final_file, scene_id, uid, name)
    except Exception as exc:
        _fail(exc)
    if data is None:
        raise HTTPException(status_code=404, detail="File not found.")
    media = "image/png" if name.endswith(".png") else "image/jpeg"
    return Response(content=data, media_type=media,
                    headers={"Content-Disposition": f'{"attachment" if download else "inline"}; '
                                                    f'filename="haven-interior-{name}"'})


@router.get("/catalog")
async def get_catalog():
    return service.catalog_response()


# ---- object library ----------------------------------------------------------------

LIBRARY_CACHE = {"Cache-Control": "public, max-age=86400"}


@router.get("/library/categories")
async def library_categories():
    """Groups and categories of the object library with item counts."""
    from app.services.interior.thumbnails import warm_up
    lib = get_library()
    warm_up(lib)
    return {**lib.categories_tree(), "type_map": DETECTED_TO_CATEGORY}


@router.get("/library/search")
async def library_search(q: str = Query("", max_length=200), category: Optional[str] = None,
                         group: Optional[str] = None, style: Optional[str] = None, material: Optional[str] = None,
                         color: Optional[str] = None, size: Optional[str] = None,
                         realism: Optional[Literal["real", "procedural"]] = None,
                         sort: Literal["relevance", "name", "width_asc", "width_desc"] = "relevance",
                         page: int = Query(1, ge=1, le=1000), page_size: int = Query(24, ge=1, le=60)):
    """Searches the library on the server: free text (also natural language,
    e.g. "modern gray sofa"), filters, sorting, pagination and facet counts
    for the filters that apply to the current results."""
    lib = get_library()
    if category and category not in lib.categories:
        raise HTTPException(status_code=422, detail=f"Unknown category '{category}'.")
    return lib.search(q=q, category=category, group=group, style=style, material=material, color=color,
                      size=size, sort=sort, page=page, page_size=page_size, realism=realism)


@router.get("/library/items/{item_id}")
async def library_item(item_id: str):
    lib = get_library()
    try:
        return lib.detail(lib.get(item_id))
    except KeyError:
        raise HTTPException(status_code=404, detail="That item is not in the library.")


@router.get("/library/items/{item_id}/thumbnail.png")
async def library_thumbnail(item_id: str):
    """Preview of the item (its real model, drawn by the room renderer).
    Made on first request, then cached."""
    from app.services.interior.thumbnails import item_etag, thumbnail_png
    lib = get_library()
    try:
        item = lib.get(item_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="That item is not in the library.")
    data = await run_in_threadpool(thumbnail_png, lib, item)
    return Response(content=data, media_type="image/png", headers={**LIBRARY_CACHE, "ETag": item_etag(item)})


@router.get("/library/materials/{material}/swatch.png")
async def material_swatch(material: str, color: Optional[str] = Query(None, pattern=r"^#[0-9a-fA-F]{6}$")):
    from app.services.interior.catalog import MATERIALS
    from app.services.interior.thumbnails import swatch_png
    if material not in MATERIALS:
        raise HTTPException(status_code=404, detail="Unknown material.")
    data = await run_in_threadpool(swatch_png, material, color)
    return Response(content=data, media_type="image/png", headers=LIBRARY_CACHE)


# ---- saved designs ---------------------------------------------------------------

@router.post("/designs")
async def save_design(req: SaveRequest, uid: str = Depends(require_user), repo=Depends(get_repository)):
    """Saves the room's current state (creates the design, or updates the one
    this room was saved as before)."""
    try:
        return await run_in_threadpool(service.save_design, repo, req.scene_id, uid, req.name)
    except Exception as exc:
        _fail(exc)


@router.get("/designs")
async def list_designs(uid: str = Depends(require_user), repo=Depends(get_repository)):
    from app.services.interior.designs import summary
    try:
        rows = await run_in_threadpool(repo.list_for, uid)
        return {"designs": [summary(r) for r in rows]}
    except Exception as exc:
        _fail(exc)


@router.get("/designs/{design_id}")
async def open_design(design_id: str, uid: str = Depends(require_user), repo=Depends(get_repository)):
    try:
        return await run_in_threadpool(service.open_design, repo, design_id, uid)
    except Exception as exc:
        _fail(exc)


@router.put("/designs/{design_id}")
async def rename_design(design_id: str, req: RenameRequest, uid: str = Depends(require_user),
                        repo=Depends(get_repository)):
    from app.services.interior.designs import now, summary
    try:
        record = await run_in_threadpool(service._owned, repo, design_id, uid)
        fields = {"name": req.name.strip(), "updated_at": now()}
        await run_in_threadpool(repo.update, design_id, fields)
        return summary(record | fields)
    except Exception as exc:
        _fail(exc)


@router.delete("/designs/{design_id}")
async def delete_design(design_id: str, uid: str = Depends(require_user), repo=Depends(get_repository)):
    try:
        await run_in_threadpool(service.delete_design, repo, design_id, uid)
        return {"deleted": design_id}
    except Exception as exc:
        _fail(exc)
