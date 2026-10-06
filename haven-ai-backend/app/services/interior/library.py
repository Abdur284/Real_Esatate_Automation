"""
The interior object library: what can be put into a room.

Data-driven: categories and items live in library_data/ (categories.json and
items/*.json). Adding a piece or a whole category means adding JSON; the
editor and API do not change. Each item references a model:

  {"kind": "parametric", "generator": "sofa", "params": {...}}
      drawn by furniture3d.py / wall2d.py (every shipped item)
  {"kind": "image", "file": "assets/xyz.png"}
      a cut-out picture (with transparency) drawn as a flat stand-up at real
      size -- the 2D asset route
  {"kind": "mesh", "source": "polyhaven", "asset": "sofa_03", ...}
      a real 3D model (glTF with PBR textures, photoscanned or modelled from
      a real piece; CC0) rendered by mesh_render.py. Its dimensions are
      measured from the model itself unless the item gives them. Optional:
      "yaw" (degrees, to face the model forwards), "recolor" (names of the
      model's materials that a new colour/material applies to, e.g. the
      upholstery) or "recolor_mask" ({"color": "#938c82", "tolerance": 30}:
      the upholstery is the part of the texture close to that colour);
      without either the piece keeps its real finish.
      Items whose files are not installed (scripts/fetch_interior_assets.py)
      are skipped with a warning.

Parametric and image items give the typical (nominal) size of that kind of
product, marked as such; real 3D models are marked "measured".

Search runs here, on the server: filters (category or group, style,
material, colour, size), keywords, sorting, pagination and facet counts,
plus a rule-based reading of natural-language requests ("modern gray sofa",
"king size bed") that only ever returns items that exist in the library.
"""
import json
import logging
import os
import re
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

from . import meshes
from .catalog import MATERIALS
from .furniture3d import GENERATORS, WALL_GENERATORS

logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(__file__), "library_data")
SUPPORTED_KINDS = {"parametric", "image", "mesh"}
PLACEMENTS = {"floor", "floor_flat", "wall", "ceiling", "surface"}
MAX_PAGE_SIZE = 60

MATERIAL_FAMILY = {
    "fabric": "fabric", "linen": "linen", "velvet": "velvet", "leather": "leather", "rattan": "rattan",
    "wood_oak": "wood", "wood_walnut": "wood", "white_wood": "wood", "wood_planks": "wood", "herringbone": "wood",
    "wood_panel": "wood", "metal_black": "metal", "metal_brass": "metal", "metal_steel": "metal",
    "marble_white": "marble", "marble_black": "marble", "glass": "glass", "painted": "painted", "carpet": "carpet",
}
FAMILY_LABELS = {"fabric": "Fabric", "linen": "Linen", "velvet": "Velvet", "leather": "Leather", "rattan": "Rattan",
                 "wood": "Wood", "metal": "Metal", "marble": "Marble", "glass": "Glass", "painted": "Painted / ceramic",
                 "carpet": "Carpet / wool"}

# Words people use -> the library's vocabulary.
STYLE_WORDS = {
    "modern": "modern", "contemporary": "contemporary", "minimalist": "minimalist", "minimal": "minimalist",
    "traditional": "traditional", "classic": "traditional", "luxury": "luxury", "luxurious": "luxury",
    "glam": "luxury", "elegant": "luxury", "scandinavian": "scandinavian", "scandi": "scandinavian",
    "nordic": "scandinavian", "industrial": "industrial", "rustic": "rustic", "farmhouse": "rustic",
    "bohemian": "bohemian", "boho": "bohemian", "mid-century": "mid-century", "midcentury": "mid-century",
    "retro": "mid-century", "vintage": "mid-century",
}
MATERIAL_WORDS = {
    "leather": "leather", "velvet": "velvet", "linen": "linen", "fabric": "fabric", "upholstered": "fabric",
    "cloth": "fabric", "wood": "wood", "wooden": "wood", "timber": "wood", "oak": "wood", "walnut": "wood",
    "metal": "metal", "iron": "metal", "steel": "metal", "brass": "metal", "marble": "marble", "stone": "marble",
    "glass": "glass", "rattan": "rattan", "cane": "rattan", "wicker": "rattan", "ceramic": "painted",
    "wool": "carpet",
}
COLOR_WORDS = {"grey": "gray", "golden": "gold", "brass": "gold", "offwhite": "cream", "ivory": "cream",
               "dark": None, "light": None}
REALISM_WORDS = {"real", "realistic", "photoreal", "photorealistic", "scanned", "lifelike", "authentic"}
SIZE_WORDS = {"small": "small", "compact": "small", "mini": "small", "little": "small", "medium": "medium",
              "large": "large", "big": "large", "huge": "large", "oversized": "large"}
STOPWORDS = {"a", "an", "the", "me", "show", "find", "give", "i", "want", "need", "with", "for", "some", "please",
             "and", "or", "in", "of", "to", "my", "that", "is", "looking", "like", "would", "furniture", "any",
             "something", "one", "set", "items", "item", "style", "styled", "color", "colour", "size", "piece"}
GROUP_WORDS = {"bedroom": "bedroom", "lighting": "lighting", "lights": "lighting", "light": "lighting",
               "seating": "seating", "seats": "seating", "decor": "decoration", "decoration": "decoration",
               "decorative": "decoration", "living": "living", "tables": "tables", "rugs": "rugs",
               "curtains": "curtains", "window": "curtains"}

# Detected object types (from the photo) -> the library category to offer.
DETECTED_TO_CATEGORY = {
    "sofa": "sofa", "sectional_sofa": "sofa", "armchair": "armchair", "chair": "dining_chair",
    "office_chair": "office_chair", "ottoman": "ottoman", "stool": "stool", "bench": "bench", "bed": "bed",
    "table": "dining_table", "coffee_table": "coffee_table", "side_table": "side_table", "desk": "desk",
    "dining_table": "dining_table", "cabinet": "cabinet", "sideboard": "sideboard", "wardrobe": "wardrobe",
    "chest_of_drawers": "dresser", "bookshelf": "bookshelf", "shelf": "bookshelf", "tv_unit": "tv_unit",
    "tv": "tv", "floor_lamp": "floor_lamp", "ceiling_light": "ceiling_light", "chandelier": "chandelier",
    "sconce": "wall_light", "plant": "plant", "vase": "vase", "painting": "wall_art", "mirror": "mirror",
    "clock": "clock", "rug": "rug", "curtain": "curtains", "decor": "decor", "cushion": "decor",
}


class LibraryError(ValueError):
    pass


@dataclass
class Category:
    id: str
    label: str
    group: str
    placement: str
    generator: str
    size_breaks_cm: Tuple[float, float]
    materials: List[str]
    synonyms: List[str]


@dataclass
class Item:
    id: str
    name: str
    category: str
    subcategory: str
    style: str
    material: str
    color: str
    colors: List[Dict[str, str]]
    dimensions: Dict[str, float]
    unit: str
    dimensions_source: str
    tags: List[str]
    model: Dict
    size: str = "medium"
    placement: Optional[str] = None
    raw: Dict = field(default_factory=dict)
    text: str = ""

    @property
    def material_family(self) -> str:
        return MATERIAL_FAMILY.get(self.material, self.material)


def _norm(word: str) -> str:
    w = word.lower()
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


def _tokens(text: str) -> List[str]:
    return [_norm(t) for t in re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)*", (text or "").lower())]


class Library:
    def __init__(self, data_dir: str = DATA_DIR):
        self.data_dir = data_dir
        with open(os.path.join(data_dir, "categories.json"), encoding="utf-8") as f:
            meta = json.load(f)
        self.groups = meta["groups"]
        self.color_names: Dict[str, str] = meta.get("colors", {})
        self.categories: Dict[str, Category] = {}
        for c in meta["categories"]:
            cat = Category(c["id"], c["label"], c["group"], c["placement"], c["generator"],
                           tuple(c.get("size_breaks_cm", (0, 0))), list(c.get("materials", [])),
                           [s.lower() for s in c.get("synonyms", [])])
            if cat.placement not in PLACEMENTS:
                raise LibraryError(f"Category {cat.id}: unknown placement {cat.placement}")
            self.categories[cat.id] = cat
        self.items: Dict[str, Item] = {}
        items_dir = os.path.join(data_dir, "items")
        for name in sorted(os.listdir(items_dir)):
            if not name.endswith(".json"):
                continue
            with open(os.path.join(items_dir, name), encoding="utf-8") as f:
                for raw in json.load(f):
                    item = self._validate(raw, name)
                    if item is not None:
                        self.items[item.id] = item
        self.by_category: Dict[str, List[Item]] = {}
        for it in self.items.values():
            self.by_category.setdefault(it.category, []).append(it)
        # longest phrases first, so "coffee table" wins over "table"
        self.phrases: List[Tuple[str, str]] = sorted(
            ((syn, cid) for cid, c in self.categories.items() for syn in c.synonyms + [c.label.lower(), cid.replace("_", " ")]),
            key=lambda p: -len(p[0]))
        logger.info("Interior library: %d items in %d categories", len(self.items), len(self.categories))

    # ---- loading ----
    def _validate(self, raw: Dict, source: str) -> Optional[Item]:
        where = f"{source}: {raw.get('id', '?')}"
        for key in ("id", "name", "category", "material", "model"):
            if key not in raw:
                raise LibraryError(f"{where}: missing '{key}'")
        if "dimensions" not in raw and (raw["model"] or {}).get("kind") != "mesh":
            raise LibraryError(f"{where}: missing 'dimensions'")
        if raw["id"] in getattr(self, "items", {}):
            raise LibraryError(f"{where}: duplicate id")
        cat = self.categories.get(raw["category"])
        if cat is None:
            raise LibraryError(f"{where}: unknown category '{raw['category']}'")
        if raw["material"] not in MATERIALS:
            raise LibraryError(f"{where}: unknown material '{raw['material']}'")
        model = dict(raw["model"])
        kind = model.get("kind")
        if kind not in SUPPORTED_KINDS:
            logger.warning("Interior library: %s skipped (model kind '%s' is not supported yet)", where, kind)
            return None
        placement = raw.get("placement")
        if placement is not None and placement not in PLACEMENTS:
            raise LibraryError(f"{where}: unknown placement '{placement}'")
        dims_source = raw.get("dimensions_source", "nominal")
        native = None
        if kind == "mesh":
            asset = model.get("asset", "")
            if not meshes.available(asset):
                logger.warning("Interior library: %s skipped (3D asset '%s' not installed; "
                               "run scripts/fetch_interior_assets.py)", where, asset)
                return None
            try:
                info = meshes.asset_info(asset, float(model.get("yaw", 0.0)))
            except Exception as e:             # a broken download must not stop the library
                logger.warning("Interior library: %s skipped (3D asset unreadable: %s)", where, e)
                return None
            unknown = set(model.get("recolor") or []) - set(info["materials"])
            if unknown:
                raise LibraryError(f"{where}: recolor names unknown materials {sorted(unknown)}")
            rm = model.get("recolor_mask")
            if rm is not None and not (isinstance(rm, dict) and re.match(r"^#[0-9a-fA-F]{6}$", str(rm.get("color")))):
                raise LibraryError(f"{where}: recolor_mask needs a colour like #938c82")
            native = info["color"]
            model.update(native_color=native, license="CC0",
                         source_url=f"https://polyhaven.com/a/{asset}" if model.get("source") == "polyhaven" else None)
            if "dimensions" not in raw:
                raw = dict(raw, dimensions={"width": round(info["width_m"] * 100, 1),
                                            "depth": round(info["depth_m"] * 100, 1),
                                            "height": round(info["height_m"] * 100, 1)})
                dims_source = "measured"
        dims = raw["dimensions"]
        if not all(isinstance(dims.get(k), (int, float)) and dims[k] > 0 for k in ("width", "depth", "height")):
            raise LibraryError(f"{where}: dimensions need positive width, depth and height")
        if kind == "parametric":
            gen = model.get("generator")
            if gen not in GENERATORS and gen not in WALL_GENERATORS:
                raise LibraryError(f"{where}: unknown generator '{gen}'")
        if kind == "image":
            path = os.path.join(self.data_dir, model.get("file", ""))
            if not os.path.isfile(path):
                raise LibraryError(f"{where}: image asset not found ({model.get('file')})")
        colors = []
        for c in raw.get("colors") or []:
            hexv = self.color_names.get(c, c)
            if not re.match(r"^#[0-9a-fA-F]{6}$", hexv):
                raise LibraryError(f"{where}: bad colour '{c}'")
            colors.append({"name": c if c in self.color_names else "tinted", "hex": hexv.lower()})
        if native:
            # a real model's own colour comes first, named after the closest library colour
            if not (model.get("recolor") or model.get("recolor_mask")):
                colors = []
            name = self.closest_color_name(native)
            colors = [{"name": name, "hex": native}] + [c for c in colors if c["name"] != name]
        color = raw.get("color") or native or (colors[0]["hex"] if colors else MATERIALS[raw["material"]]["color"])
        color = self.color_names.get(color, color)
        if not re.match(r"^#[0-9a-fA-F]{6}$", color):
            raise LibraryError(f"{where}: bad colour '{color}'")
        w = dims["width"]
        lo, hi = cat.size_breaks_cm if len(cat.size_breaks_cm) == 2 else (0, 1e9)
        size = "small" if w < lo else "large" if w > hi else "medium"
        item = Item(id=raw["id"], name=raw["name"], category=cat.id, subcategory=raw.get("subcategory", ""),
                    style=raw.get("style", ""), material=raw["material"], color=color.lower(), colors=colors,
                    dimensions={k: float(dims[k]) for k in ("width", "depth", "height")}, unit=raw.get("unit", "cm"),
                    dimensions_source=dims_source, tags=list(raw.get("tags", [])),
                    model=model, size=size, placement=placement, raw=raw)
        item.text = " ".join(_tokens(" ".join([item.name, item.subcategory, item.style, cat.label,
                                               item.material_family, " ".join(c["name"] for c in colors),
                                               " ".join(item.tags)])))
        return item

    def closest_color_name(self, hexv: str) -> str:
        def lab(h):
            b = np.array([[[int(h[5:7], 16), int(h[3:5], 16), int(h[1:3], 16)]]], np.uint8)
            return cv2.cvtColor(b, cv2.COLOR_BGR2LAB)[0, 0].astype(np.float32)
        target = lab(hexv)
        names = {k: v for k, v in self.color_names.items() if k not in ("oak", "walnut", "natural")}
        w = np.array([0.5, 1.0, 1.0], np.float32)
        return min(names, key=lambda k: float(np.sum(((lab(names[k]) - target) * w) ** 2)))

    # ---- lookups ----
    def get(self, item_id: str) -> Item:
        if item_id not in self.items:
            raise KeyError(item_id)
        return self.items[item_id]

    def category_for_type(self, type_: str, placement: Optional[str] = None) -> Optional[str]:
        if type_ in self.categories:
            return type_
        if type_ == "lamp":
            return "floor_lamp" if placement == "floor" else "table_lamp"
        return DETECTED_TO_CATEGORY.get(type_)

    def default_item(self, category: str) -> Item:
        items = self.by_category.get(category)
        if not items:
            raise KeyError(category)
        return next((i for i in items if i.raw.get("default")),
                    next((i for i in items if self.realism(i) == "real"), items[0]))

    def categories_tree(self) -> Dict:
        groups = []
        for g in self.groups:
            cats = [{"id": c.id, "label": c.label, "placement": c.placement, "count": len(self.by_category.get(c.id, []))}
                    for c in self.categories.values() if c.group == g["id"]]
            groups.append({"id": g["id"], "label": g["label"], "categories": cats,
                           "count": sum(c["count"] for c in cats)})
        return {"groups": groups, "total": len(self.items)}

    # ---- natural language ----
    def interpret(self, text: str) -> Dict:
        """Reads a request like "show me a modern gray sofa" into filters.
        Only words the library knows become filters; the rest are keywords."""
        raw = (text or "").lower()
        out: Dict = {"realism": None, "category": None, "group": None, "style": None, "material": None, "color": None,
                     "size": None, "keywords": []}
        rest = f" {re.sub(r'[^a-z0-9-]+', ' ', raw)} "
        for phrase, cid in self.phrases:
            if f" {phrase} " in rest or f" {phrase}s " in rest:
                out["category"] = cid
                rest = rest.replace(f" {phrase}s ", " ").replace(f" {phrase} ", " ")
                break
        rest = rest.replace("mid century", "mid-century").replace("living room", "living")
        for tok in rest.split():
            word = tok.strip("-")
            n = _norm(word)
            if word in STYLE_WORDS and not out["style"]:
                out["style"] = STYLE_WORDS[word]
            elif word in MATERIAL_WORDS and not out["material"]:
                out["material"] = MATERIAL_WORDS[word]
            elif (COLOR_WORDS.get(word) or (word if word in self.color_names else None)) and not out["color"]:
                out["color"] = COLOR_WORDS.get(word) or word
            elif word in REALISM_WORDS and not out["realism"]:
                out["realism"] = "real"
            elif word in SIZE_WORDS and not out["size"]:
                out["size"] = SIZE_WORDS[word]
            elif word in GROUP_WORDS and not out["category"] and not out["group"]:
                out["group"] = GROUP_WORDS[word]
            elif word not in STOPWORDS and n not in STOPWORDS and word not in COLOR_WORDS:
                out["keywords"].append(n)
        return out

    # ---- search ----
    def search(self, q: str = "", category: Optional[str] = None, group: Optional[str] = None,
               style: Optional[str] = None, material: Optional[str] = None, color: Optional[str] = None,
               size: Optional[str] = None, sort: str = "relevance", page: int = 1, page_size: int = 24,
               realism: Optional[str] = None) -> Dict:
        parsed = self.interpret(q) if q else {"keywords": []}
        explicit = {"category": category, "group": group, "style": style, "material": material, "color": color,
                    "size": size, "realism": realism}
        filters = {k: explicit[k] or parsed.get(k) for k in explicit}
        if explicit["category"] or explicit["group"]:
            # an explicit category/group (the object being replaced, or the one
            # the user clicked) is not overridden by words in the query
            filters["category"] = explicit["category"]
            filters["group"] = explicit["group"]
        keywords = parsed.get("keywords", [])
        relaxed: List[str] = []

        def matches(it: Item, f: Dict, skip: str = "") -> bool:
            cat = self.categories[it.category]
            if skip != "category" and f.get("category") and it.category != f["category"]:
                return False
            if skip != "category" and f.get("group") and cat.group != f["group"]:
                return False
            if skip != "style" and f.get("style") and it.style != f["style"]:
                return False
            if skip != "material" and f.get("material") and it.material_family != f["material"]:
                return False
            if skip != "color" and f.get("color") and f["color"] not in {c["name"] for c in it.colors}:
                return False
            if skip != "size" and f.get("size") and it.size != f["size"]:
                return False
            if skip != "realism" and f.get("realism") and self.realism(it) != f["realism"]:
                return False
            return True

        def kw_score(it: Item) -> int:
            words = set(it.text.split())
            return sum(1 for k in keywords if k in words or any(w.startswith(k) for w in words if len(k) > 3))

        pool = [it for it in self.items.values() if matches(it, filters)]
        # words the user typed that ruled everything out are relaxed, least important first
        for key in ("realism", "size", "color", "style", "material"):
            if pool or not filters.get(key) or explicit.get(key):
                continue
            filters[key] = None
            relaxed.append(key)
            pool = [it for it in self.items.values() if matches(it, filters)]
        scored = [(kw_score(it), it) for it in pool]
        if keywords and any(s for s, _ in scored):
            scored = [(s, it) for s, it in scored if s > 0]
        elif keywords and scored:
            relaxed.append("keywords")
        if sort == "name":
            scored.sort(key=lambda p: p[1].name)
        elif sort == "width_asc":
            scored.sort(key=lambda p: (p[1].dimensions["width"], p[1].name))
        elif sort == "width_desc":
            scored.sort(key=lambda p: (-p[1].dimensions["width"], p[1].name))
        else:
            # real 3D models of real pieces before procedural stand-ins
            scored.sort(key=lambda p: (-p[0], self.realism(p[1]) != "real", p[1].category, p[1].name))
        page_size = max(1, min(MAX_PAGE_SIZE, int(page_size)))
        page = max(1, int(page))
        total = len(scored)
        window = scored[(page - 1) * page_size: page * page_size]

        def facet(key: str, values) -> List[Dict]:
            base = [it for it in self.items.values() if matches(it, filters, skip=key)]
            counts: Dict[str, int] = {}
            for it in base:
                for v in values(it):
                    counts[v] = counts.get(v, 0) + 1
            return [{"value": v, "label": self.facet_label(key, v), "count": n}
                    for v, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))]

        facets = {
            "style": facet("style", lambda it: [it.style] if it.style else []),
            "material": facet("material", lambda it: [it.material_family]),
            "color": facet("color", lambda it: sorted({c["name"] for c in it.colors if c["name"] != "tinted"})),
            "size": facet("size", lambda it: [it.size]),
            "realism": facet("realism", lambda it: [self.realism(it)]),
        }
        return {"items": [self.summary(it) for _, it in window], "total": total, "page": page,
                "page_size": page_size, "pages": max(1, -(-total // page_size)), "facets": facets,
                "filters": {k: v for k, v in filters.items() if v}, "interpreted": parsed if q else None,
                "relaxed": relaxed}

    def facet_label(self, key: str, value: str) -> str:
        if key == "material":
            return FAMILY_LABELS.get(value, value.title())
        if key == "realism":
            return {"real": "Real 3D model", "procedural": "Simple model"}.get(value, value)
        return value.replace("-", " ").title() if key != "color" else value.title()

    def summary(self, it: Item) -> Dict:
        cat = self.categories[it.category]
        return {
            "id": it.id, "name": it.name, "category": it.category, "category_label": cat.label,
            "group": cat.group, "subcategory": it.subcategory, "style": it.style, "material": it.material,
            "material_label": MATERIALS[it.material]["label"], "material_family": it.material_family,
            "color": it.color, "colors": it.colors, "dimensions": it.dimensions, "unit": it.unit,
            "dimensions_source": it.dimensions_source, "size": it.size, "placement": it.placement or cat.placement,
            "tags": it.tags, "model_kind": it.model["kind"], "realism": self.realism(it),
            "license": it.model.get("license"), "source_url": it.model.get("source_url"),
            "thumbnail_url": f"/api/interior/library/items/{it.id}/thumbnail.png",
            # the catalogue size is scale 1; a replacement is scaled from it to fill the old piece's space
            "default_scale": 1.0,
            "model_reference": {k: it.model[k] for k in ("kind", "source", "asset", "generator", "file")
                                if it.model.get(k) is not None},
        }

    @staticmethod
    def realism(it: Item) -> str:
        """"real" for 3D models of real pieces (photoscanned / modelled with
        PBR materials), "procedural" for parametric stand-ins."""
        return "real" if it.model["kind"] == "mesh" else "procedural"

    def detail(self, it: Item) -> Dict:
        out = self.summary(it)
        out["model"] = it.model
        out["materials_allowed"] = self.materials_for(it)
        return out

    def scene_object(self, it: Item, object_id: str, color: Optional[str] = None) -> Dict:
        """A new scene object that uses this library item. The scene keeps
        a reference to the item plus everything needed to draw it, so a saved
        design still renders if the library changes later."""
        cat = self.categories[it.category]
        model = {"width_m": it.dimensions["width"] / 100, "depth_m": it.dimensions["depth"] / 100,
                 "height_m": it.dimensions["height"] / 100, "kind": it.model["kind"]}
        if it.model["kind"] == "parametric":
            model.update(generator=it.model["generator"], params=dict(it.model.get("params") or {}))
        elif it.model["kind"] == "mesh":
            recolor = list(it.model.get("recolor") or [])
            mask = it.model.get("recolor_mask")
            model.update(generator="mesh", params={}, asset=it.model["asset"], yaw=float(it.model.get("yaw", 0.0)),
                         recolor=recolor, recolor_mask=mask, tintable=bool(recolor or mask),
                         native_color=it.model["native_color"], material=it.material)
        else:
            model.update(generator=None, params={}, file=it.model["file"])
        group_to_kind = {"lighting": "lighting", "decoration": "decor", "curtains": "decor", "rugs": "decor"}
        return {
            "id": object_id, "kind": "object", "type": it.category, "label": it.name,
            "category": group_to_kind.get(cat.group, "furniture"), "placement": it.placement or cat.placement,
            "source": "model",
            "instance": None, "confidence": None, "area": None, "color": None, "material_guess": None,
            "material_source": "library", "original": None, "model": model,
            "library_item": {"id": it.id, "name": it.name, "category": it.category, "material": it.material,
                             "dimensions": it.dimensions, "unit": it.unit,
                             "dimensions_source": it.dimensions_source, "realism": self.realism(it)},
            "transform": {"position": {"x": 0.5, "y": 0.8}, "scale": {"x": 1.0, "y": 1.0, "z": 1.0},
                          "rotation": 0.0, "flip": False},
            "appearance": {"color": (color or it.color).lower(), "material": it.material},
            "parent": None, "editable": True,
        }

    def materials_for(self, it: Item) -> List[str]:
        if it.model["kind"] == "mesh" and not (it.model.get("recolor") or it.model.get("recolor_mask")):
            return [it.material]              # a real piece keeps its real finish
        allowed = list(self.categories[it.category].materials)
        if it.material not in allowed:
            allowed.insert(0, it.material)
        return allowed


_lock = threading.Lock()
_library: Optional[Library] = None


def get_library() -> Library:
    global _library
    with _lock:
        if _library is None:
            _library = Library()
        return _library
