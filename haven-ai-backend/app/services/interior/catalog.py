"""
What the Interior Design module knows about room elements.

Maps the segmentation model's ADE20K classes to editable element types, and
lists, per type, what the user may do with it: which materials apply, what it
can be replaced with, how it may rotate, and the real-world size range used to
warn about absurd resizing. The frontend reads this through GET /catalog so
the editor offers exactly what the backend will accept.
"""
from typing import Dict, List, Optional

# Surfaces the room is made of. Recolourable/re-materialable, never moved.
SURFACE_CLASSES = {"wall": "wall", "floor": "floor", "ceiling": "ceiling"}

# ADE20K label -> element type. Classes that are not listed (sky, trees,
# people, cars seen through a window...) are ignored.
CLASS_TO_TYPE: Dict[str, str] = {
    # seating
    "sofa": "sofa", "armchair": "armchair", "chair": "chair", "seat": "chair",
    "swivel chair": "office_chair", "ottoman": "ottoman", "stool": "stool", "bench": "bench",
    # beds
    "bed": "bed",
    # tables
    "table": "table", "coffee table": "coffee_table", "desk": "desk",
    "kitchen island": "kitchen_island", "pool table": "table",
    # storage
    "cabinet": "cabinet", "wardrobe": "wardrobe", "chest of drawers": "chest_of_drawers",
    "shelf": "shelf", "bookcase": "bookshelf", "buffet": "sideboard", "case": "cabinet",
    "counter": "counter", "countertop": "counter",
    # screens
    "television receiver": "tv", "screen": "tv", "crt screen": "tv", "monitor": "tv",
    "computer": "tv",
    # lighting
    "lamp": "lamp", "light": "ceiling_light", "chandelier": "chandelier", "sconce": "sconce",
    # decor
    "plant": "plant", "flower": "plant", "vase": "vase", "painting": "painting",
    "poster": "painting", "mirror": "mirror", "rug": "rug", "curtain": "curtain",
    "blind": "curtain", "clock": "clock", "sculpture": "decor", "book": "decor",
    "pot": "plant", "basket": "decor", "box": "decor", "tray": "decor", "towel": "decor",
    "fan": "fan", "cushion": "cushion", "pillow": "cushion", "blanket": "cushion",
    # appliances and fixtures
    "refrigerator": "refrigerator", "stove": "stove", "oven": "stove",
    "microwave": "appliance", "dishwasher": "appliance", "washer": "appliance",
    "sink": "sink", "hood": "appliance", "bathtub": "bathtub", "toilet": "toilet",
    "shower": "shower", "radiator": "radiator",
    # architecture
    "windowpane": "window", "door": "door", "screen door": "door", "column": "column",
    "stairs": "stairs", "stairway": "stairs", "step": "stairs", "fireplace": "fireplace",
    "bannister": "railing", "railing": "railing",
}

# Classes that are parts of a larger piece when they touch it (a cushion on a
# sofa moves with the sofa); otherwise they are objects of their own.
SOFT_PART_TYPES = {"cushion"}
SOFT_PART_HOSTS = {"sofa", "armchair", "chair", "bed", "bench", "ottoman"}

# Classes grouped into one connected region before instances are split, so a
# sofa the model labels partly "sofa", partly "armchair" stays one object.
MERGE_GROUPS: Dict[str, str] = {
    "sofa": "seating", "armchair": "seating", "chair": "seating", "office_chair": "seating",
    "ottoman": "seating", "stool": "seating", "bench": "seating",
    "table": "table", "coffee_table": "table", "desk": "table",
    "cabinet": "storage", "wardrobe": "storage", "chest_of_drawers": "storage",
    "sideboard": "storage", "bookshelf": "storage", "shelf": "storage",
    "plant": "plant", "vase": "plant",
    "tv": "tv",
}

FABRICS = ["fabric", "velvet", "leather", "linen", "cotton"]
WOODS = ["wood_oak", "wood_walnut", "white_wood", "painted", "mdf"]
METALS = ["metal_black", "metal_brass", "metal_steel", "stainless_steel"]
STONES = ["marble_white", "marble_black", "granite", "stone"]

# Every material the renderer can draw. `tintable`: the chosen colour
# replaces the material's own colour (paint, fabric); otherwise the colour
# only tints the texture (wood, marble keep their pattern).
MATERIALS: Dict[str, Dict] = {
    "paint": {"label": "Paint", "color": "#e8e4dc", "tintable": True},
    "painted": {"label": "Painted finish", "color": "#f2f0eb", "tintable": True},
    "textured_plaster": {"label": "Textured plaster", "color": "#d9d2c5", "tintable": True},
    "brick": {"label": "Brick", "color": "#9c5a3c", "tintable": False},
    "wood_panel": {"label": "Wood panelling", "color": "#a47148", "tintable": False},
    "wallpaper_stripes": {"label": "Striped wallpaper", "color": "#c9d6cf", "tintable": True},
    "wood_oak": {"label": "Oak wood", "color": "#b98a58", "tintable": False},
    "wood_walnut": {"label": "Walnut wood", "color": "#6b4a32", "tintable": False},
    "white_wood": {"label": "White-washed wood", "color": "#e9e2d6", "tintable": False},
    "wood_planks": {"label": "Wood planks", "color": "#a97c50", "tintable": False},
    "herringbone": {"label": "Herringbone parquet", "color": "#b08256", "tintable": False},
    "marble_white": {"label": "White marble", "color": "#eceae6", "tintable": False},
    "marble_black": {"label": "Black marble", "color": "#2b2b2e", "tintable": False},
    "ceramic_tile": {"label": "Ceramic tiles", "color": "#d8d6d0", "tintable": True},
    "large_tile": {"label": "Large-format tiles", "color": "#c9c5bd", "tintable": True},
    "terracotta": {"label": "Terracotta tiles", "color": "#b8643f", "tintable": False},
    "concrete": {"label": "Polished concrete", "color": "#9a9892", "tintable": True},
    "carpet": {"label": "Carpet", "color": "#c7bba6", "tintable": True},
    "fabric": {"label": "Fabric", "color": "#b9b2a6", "tintable": True},
    "velvet": {"label": "Velvet", "color": "#2f4f4f", "tintable": True},
    "leather": {"label": "Leather", "color": "#6a3f26", "tintable": True},
    "linen": {"label": "Linen", "color": "#ddd5c7", "tintable": True},
    "metal_black": {"label": "Black metal", "color": "#232323", "tintable": False},
    "metal_brass": {"label": "Brass", "color": "#b8903e", "tintable": False},
    "metal_steel": {"label": "Brushed steel", "color": "#a7abae", "tintable": False},
    "glass": {"label": "Glass", "color": "#cfe3e8", "tintable": True},
    "rattan": {"label": "Rattan / cane", "color": "#c9a97c", "tintable": False},
    "porcelain_tile": {"label": "Porcelain tiles", "color": "#e6e3dd", "tintable": True},
    "vinyl_plank": {"label": "Vinyl planks", "color": "#b59b7c", "tintable": False},
    "slate_tile": {"label": "Slate tiles", "color": "#55575a", "tintable": False},
    "parquet_walnut": {"label": "Walnut parquet", "color": "#6f4c33", "tintable": False},
    "cotton": {"label": "Cotton", "color": "#e7e1d6", "tintable": True},
    "mdf": {"label": "Painted MDF", "color": "#efece6", "tintable": True},
    "granite": {"label": "Granite", "color": "#4b4c4e", "tintable": False},
    "stone": {"label": "Natural stone", "color": "#8e8c86", "tintable": False},
    "stainless_steel": {"label": "Stainless steel", "color": "#c2c5c7", "tintable": False},
    "plastic": {"label": "Plastic", "color": "#f0f0ee", "tintable": True},
}

SURFACE_MATERIALS = {
    "wall": ["paint", "textured_plaster", "wallpaper_stripes", "brick", "wood_panel", "marble_white"],
    "floor": ["wood_planks", "herringbone", "parquet_walnut", "vinyl_plank", "ceramic_tile", "porcelain_tile",
              "large_tile", "marble_white", "marble_black", "granite", "stone", "slate_tile", "terracotta",
              "concrete", "carpet"],
    "ceiling": ["paint", "textured_plaster", "wood_panel"],
}

SEATING = ["sofa", "sectional_sofa", "armchair", "chair", "ottoman", "bench"]
TABLES = ["coffee_table", "table", "dining_table", "side_table", "desk"]
STORAGE = ["cabinet", "sideboard", "wardrobe", "chest_of_drawers", "bookshelf", "tv_unit"]

# placement: floor (stands on the floor; moves on the floor plane and scales
# with perspective), wall (hangs on a wall), ceiling, surface (sits on other
# furniture), fixed (architecture: never moved).
# rotate: yaw (3D model: turn about the vertical axis), mirror (photo object:
# can only be flipped), tilt (flat wall item: in-plane rotation), None.
# width_m: plausible real width range, for resize warnings.
TYPES: Dict[str, Dict] = {
    "sofa": {"label": "Sofa", "category": "furniture", "placement": "floor", "materials": FABRICS,
             "replace": SEATING + ["bed"], "width_m": (1.2, 3.6), "model": True},
    "sectional_sofa": {"label": "Sectional sofa", "category": "furniture", "placement": "floor",
                       "materials": FABRICS, "replace": SEATING, "width_m": (2.0, 4.5), "model": True},
    "armchair": {"label": "Armchair", "category": "furniture", "placement": "floor", "materials": FABRICS,
                 "replace": SEATING, "width_m": (0.6, 1.3), "model": True},
    "chair": {"label": "Chair", "category": "furniture", "placement": "floor",
              "materials": FABRICS + WOODS + METALS, "replace": SEATING, "width_m": (0.35, 1.0), "model": True},
    "office_chair": {"label": "Office chair", "category": "furniture", "placement": "floor",
                     "materials": FABRICS + ["metal_black"], "replace": SEATING, "width_m": (0.5, 0.9)},
    "ottoman": {"label": "Ottoman", "category": "furniture", "placement": "floor", "materials": FABRICS,
                "replace": SEATING + TABLES, "width_m": (0.4, 1.4), "model": True},
    "stool": {"label": "Stool", "category": "furniture", "placement": "floor",
              "materials": WOODS + METALS + FABRICS, "replace": SEATING, "width_m": (0.3, 0.7)},
    "bench": {"label": "Bench", "category": "furniture", "placement": "floor", "materials": WOODS + FABRICS,
              "replace": SEATING, "width_m": (0.8, 2.4), "model": True},
    "bed": {"label": "Bed", "category": "furniture", "placement": "floor", "materials": FABRICS + WOODS,
            "replace": ["bed", "sofa"], "width_m": (0.9, 2.4), "model": True},
    "table": {"label": "Table", "category": "furniture", "placement": "floor",
              "materials": WOODS + STONES + METALS + ["glass"], "replace": TABLES, "width_m": (0.4, 3.2),
              "model": True},
    "dining_table": {"label": "Dining table", "category": "furniture", "placement": "floor",
                     "materials": WOODS + STONES + ["glass"], "replace": TABLES, "width_m": (0.8, 3.2),
                     "model": True},
    "coffee_table": {"label": "Coffee table", "category": "furniture", "placement": "floor",
                     "materials": WOODS + STONES + METALS + ["glass"], "replace": TABLES, "width_m": (0.4, 1.8),
                     "model": True},
    "side_table": {"label": "Side table", "category": "furniture", "placement": "floor",
                   "materials": WOODS + STONES + METALS, "replace": TABLES, "width_m": (0.3, 0.8), "model": True},
    "desk": {"label": "Desk", "category": "furniture", "placement": "floor", "materials": WOODS + METALS,
             "replace": TABLES, "width_m": (0.7, 2.2), "model": True},
    "kitchen_island": {"label": "Kitchen island", "category": "furniture", "placement": "floor",
                       "materials": WOODS + STONES, "replace": [], "width_m": (1.0, 4.0)},
    "cabinet": {"label": "Cabinet", "category": "furniture", "placement": "floor", "materials": WOODS + STONES,
                "replace": STORAGE, "width_m": (0.3, 4.0), "model": True},
    "sideboard": {"label": "Sideboard", "category": "furniture", "placement": "floor", "materials": WOODS,
                  "replace": STORAGE, "width_m": (0.8, 2.6), "model": True},
    "wardrobe": {"label": "Wardrobe", "category": "furniture", "placement": "floor", "materials": WOODS,
                 "replace": STORAGE, "width_m": (0.6, 3.5), "model": True},
    "chest_of_drawers": {"label": "Chest of drawers", "category": "furniture", "placement": "floor",
                         "materials": WOODS, "replace": STORAGE, "width_m": (0.5, 1.8), "model": True},
    "shelf": {"label": "Shelf", "category": "furniture", "placement": "wall", "materials": WOODS + METALS,
              "replace": [], "width_m": (0.3, 3.0)},
    "bookshelf": {"label": "Bookshelf", "category": "furniture", "placement": "floor",
                  "materials": WOODS + METALS, "replace": STORAGE, "width_m": (0.4, 3.0), "model": True},
    "tv_unit": {"label": "TV unit", "category": "furniture", "placement": "floor", "materials": WOODS + STONES,
                "replace": STORAGE, "width_m": (0.9, 3.0), "model": True},
    "counter": {"label": "Counter", "category": "furniture", "placement": "fixed", "materials": WOODS + STONES,
                "replace": []},
    "tv": {"label": "TV / screen", "category": "decor", "placement": "surface", "materials": [],
           "replace": [], "width_m": (0.4, 2.2), "model": True},
    "lamp": {"label": "Lamp", "category": "lighting", "placement": "surface", "materials": METALS + ["linen"],
             "replace": [], "width_m": (0.15, 0.8), "model": True},
    "floor_lamp": {"label": "Floor lamp", "category": "lighting", "placement": "floor",
                   "materials": METALS + ["linen"], "replace": [], "width_m": (0.2, 0.8), "model": True},
    "ceiling_light": {"label": "Ceiling light", "category": "lighting", "placement": "ceiling",
                      "materials": METALS, "replace": []},
    "chandelier": {"label": "Chandelier", "category": "lighting", "placement": "ceiling",
                   "materials": METALS, "replace": []},
    "sconce": {"label": "Wall light", "category": "lighting", "placement": "wall", "materials": METALS,
               "replace": []},
    "fan": {"label": "Fan", "category": "decor", "placement": "surface", "materials": [], "replace": []},
    "plant": {"label": "Plant", "category": "decor", "placement": "surface", "materials": [], "replace": [],
              "width_m": (0.15, 1.5), "model": True},
    "vase": {"label": "Vase", "category": "decor", "placement": "surface", "materials": [], "replace": []},
    "painting": {"label": "Painting / art", "category": "decor", "placement": "wall", "materials": [],
                 "replace": ["painting", "mirror"], "model": True},
    "mirror": {"label": "Mirror", "category": "decor", "placement": "wall", "materials": [],
               "replace": ["painting", "mirror"], "model": True},
    "clock": {"label": "Clock", "category": "decor", "placement": "wall", "materials": [], "replace": []},
    "rug": {"label": "Rug", "category": "decor", "placement": "floor_flat", "materials": ["carpet"],
            "replace": [], "width_m": (0.6, 4.5), "model": True},
    "curtain": {"label": "Curtains", "category": "decor", "placement": "wall", "materials": ["fabric", "velvet", "linen"],
                "replace": []},
    "cushion": {"label": "Cushion", "category": "decor", "placement": "surface", "materials": FABRICS,
                "replace": []},
    "decor": {"label": "Decorative object", "category": "decor", "placement": "surface", "materials": [],
              "replace": []},
    "refrigerator": {"label": "Refrigerator", "category": "appliance", "placement": "fixed", "materials": METALS,
                     "replace": []},
    "stove": {"label": "Stove / oven", "category": "appliance", "placement": "fixed", "materials": METALS,
              "replace": []},
    "appliance": {"label": "Appliance", "category": "appliance", "placement": "fixed", "materials": [],
                  "replace": []},
    "sink": {"label": "Sink", "category": "appliance", "placement": "fixed", "materials": [], "replace": []},
    "bathtub": {"label": "Bathtub", "category": "appliance", "placement": "fixed", "materials": [],
                "replace": []},
    "toilet": {"label": "Toilet", "category": "appliance", "placement": "fixed", "materials": [], "replace": []},
    "shower": {"label": "Shower", "category": "appliance", "placement": "fixed", "materials": [], "replace": []},
    "radiator": {"label": "Radiator", "category": "structure", "placement": "fixed", "materials": [],
                 "replace": []},
    "window": {"label": "Window", "category": "structure", "placement": "fixed", "materials": [], "replace": [],
               "editable": False},
    "door": {"label": "Door", "category": "structure", "placement": "fixed", "materials": WOODS,
             "replace": []},
    "column": {"label": "Column", "category": "structure", "placement": "fixed",
               "materials": ["paint", "marble_white", "concrete"], "replace": []},
    "stairs": {"label": "Stairs", "category": "structure", "placement": "fixed", "materials": [],
               "replace": [], "editable": False},
    "fireplace": {"label": "Fireplace", "category": "structure", "placement": "fixed",
                  "materials": ["brick", "marble_white", "paint"], "replace": []},
    "railing": {"label": "Railing", "category": "structure", "placement": "fixed", "materials": METALS,
                "replace": [], "editable": False},
}

# Types the user can add from the furniture library (all have a 3D model).
ADDABLE = ["sofa", "sectional_sofa", "armchair", "chair", "ottoman", "bench", "bed", "coffee_table",
           "dining_table", "side_table", "desk", "cabinet", "sideboard", "wardrobe", "chest_of_drawers",
           "bookshelf", "tv_unit", "tv", "floor_lamp", "plant", "rug", "painting", "mirror"]

# Default look of a newly added or replacement model.
MODEL_DEFAULTS: Dict[str, Dict[str, str]] = {
    "sofa": {"material": "fabric", "color": "#8c8a86"},
    "sectional_sofa": {"material": "fabric", "color": "#b7ada0"},
    "armchair": {"material": "velvet", "color": "#3f5e5a"},
    "chair": {"material": "wood_oak", "color": "#b98a58"},
    "ottoman": {"material": "leather", "color": "#6a3f26"},
    "bench": {"material": "wood_oak", "color": "#b98a58"},
    "bed": {"material": "linen", "color": "#ddd5c7"},
    "table": {"material": "wood_oak", "color": "#b98a58"},
    "dining_table": {"material": "wood_walnut", "color": "#6b4a32"},
    "coffee_table": {"material": "wood_walnut", "color": "#6b4a32"},
    "side_table": {"material": "wood_oak", "color": "#b98a58"},
    "desk": {"material": "white_wood", "color": "#e9e2d6"},
    "cabinet": {"material": "white_wood", "color": "#e9e2d6"},
    "sideboard": {"material": "wood_walnut", "color": "#6b4a32"},
    "wardrobe": {"material": "white_wood", "color": "#e9e2d6"},
    "chest_of_drawers": {"material": "wood_oak", "color": "#b98a58"},
    "bookshelf": {"material": "wood_oak", "color": "#b98a58"},
    "tv_unit": {"material": "wood_walnut", "color": "#6b4a32"},
    "tv": {"material": "metal_black", "color": "#1b1b1d"},
    "floor_lamp": {"material": "metal_brass", "color": "#b8903e"},
    "lamp": {"material": "metal_brass", "color": "#b8903e"},
    "plant": {"material": "painted", "color": "#3f7a45"},
    "rug": {"material": "carpet", "color": "#b9a88f"},
    "painting": {"material": "painted", "color": "#5b7fa6"},
    "mirror": {"material": "metal_brass", "color": "#b8903e"},
}

# Typical real widths (m), used to recover the photo's scale from the
# furniture the model found (a single photo has no scale of its own).
TYPICAL_WIDTH_M: Dict[str, float] = {
    "sofa": 2.0, "sectional_sofa": 2.8, "armchair": 0.85, "chair": 0.5, "office_chair": 0.65,
    "stool": 0.4, "bench": 1.3, "ottoman": 0.7, "bed": 1.7, "coffee_table": 1.1, "table": 1.4,
    "dining_table": 1.6, "desk": 1.3, "wardrobe": 1.5, "sideboard": 1.6, "chest_of_drawers": 1.0,
    "bookshelf": 1.0, "tv_unit": 1.6,
}

HEX_RE = r"^#[0-9a-fA-F]{6}$"


def type_info(type_: str) -> Dict:
    """What a type allows. Detected types are listed in TYPES; pieces from
    the object library use their library category's definition."""
    if type_ in TYPES:
        return TYPES[type_]
    from .library import get_library     # (library imports this module)
    cat = get_library().categories.get(type_)
    if cat is None:
        return TYPES["decor"]
    group = {"seating": "furniture", "tables": "furniture", "bedroom": "furniture", "living": "furniture",
             "lighting": "lighting", "decoration": "decor", "curtains": "decor", "rugs": "decor"}[cat.group]
    return {"label": cat.label.rstrip("s") if not cat.label.endswith("ss") else cat.label, "category": group,
            "placement": cat.placement, "materials": cat.materials, "replace": [], "model": True}


def materials_for(kind: str, type_: str) -> List[str]:
    if kind == "surface":
        return SURFACE_MATERIALS.get(type_, [])
    return list(type_info(type_).get("materials", []))


def rotate_mode(type_: str, source: str, placement: Optional[str] = None) -> Optional[str]:
    placement = placement or type_info(type_)["placement"]
    if source == "model":
        return "tilt" if placement == "wall" else "yaw"
    if placement == "wall":
        return "tilt"
    if placement in ("floor", "surface", "floor_flat"):
        return "mirror"
    return None


def public_catalog() -> Dict:
    """What the editor may offer; mirrors what operations.py validates."""
    return {
        "types": {k: {"label": v["label"], "category": v["category"], "placement": v["placement"],
                      "materials": v.get("materials", []), "replace": v.get("replace", [])}
                  for k, v in TYPES.items()},
        "addable": [{"type": t, "label": TYPES[t]["label"], "category": TYPES[t]["category"]} for t in ADDABLE],
        "materials": {k: {"label": v["label"], "color": v["color"], "tintable": v["tintable"]}
                      for k, v in MATERIALS.items()},
        "surface_materials": SURFACE_MATERIALS,
        "palette": ["#f5f3ee", "#e8e4dc", "#d8d2c8", "#b9b2a6", "#8c8a86", "#4a4a4a", "#222222",
                    "#c9d6cf", "#7d9a8c", "#3f5e5a", "#a9c1d9", "#5b7fa6", "#2c3e57", "#e9d8b4",
                    "#d4a373", "#b8643f", "#8a3b2e", "#6b4a32", "#e6c9c4", "#b5838d"],
    }
