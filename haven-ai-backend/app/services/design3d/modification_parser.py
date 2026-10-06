"""
Rule-based reading of a redesign request ("modern elevation, add a balcony on
the first floor, contemporary colours, keep the structure").

Deterministic keyword rules, so the same text always gives the same design.
Anything structural that a photo cannot confirm (adding a storey, removing or
moving walls/columns, extensions) is returned as a blocking clarification
instead of being applied.
"""
import re
from typing import Any, Dict, List, Optional

# Palettes per style: walls, facade (road-facing accent), trim, roof, frames, door.
STYLE_PRESETS = {
    "modern pakistani": {"label": "Modern Pakistani", "cladding": "stone", "windows_upper": "full_height",
                         "windows_ground": "large", "railing": "glass",
                         "colors": {"walls": "#ecebe7", "facade": "#4a4a4f", "trim": "#27272a", "roof": "#d4d4d8",
                                    "window_frames": "#18181b", "door": "#5b4331"}},
    "modern": {"label": "Modern", "cladding": "tile", "windows_upper": "large", "windows_ground": "large",
               "railing": "glass",
               "colors": {"walls": "#f4f4f5", "facade": "#52525b", "trim": "#27272a", "roof": "#e4e4e7",
                          "window_frames": "#18181b", "door": "#3f3f46"}},
    "minimal": {"label": "Minimalist", "cladding": "concrete", "windows_upper": "large", "windows_ground": "large",
                "railing": "glass",
                "colors": {"walls": "#fafafa", "facade": "#d4d4d4", "trim": "#737373", "roof": "#e5e5e5",
                           "window_frames": "#262626", "door": "#a3a3a3"}},
    "industrial": {"label": "Industrial", "cladding": "brick", "windows_upper": "large", "windows_ground": "large",
                   "railing": "solid",
                   "colors": {"walls": "#d6d3d1", "facade": "#9a4a32", "trim": "#1c1917", "roof": "#57534e",
                              "window_frames": "#0c0a09", "door": "#292524"}},
    "classic": {"label": "Classic", "cladding": "none", "windows_upper": "standard", "windows_ground": "standard",
                "railing": "solid",
                "colors": {"walls": "#efe4cf", "facade": "#e2cfaa", "trim": "#8b6b4a", "roof": "#c9b89a",
                           "window_frames": "#6b4a2e", "door": "#6b3f22"}},
    "traditional": {"label": "Traditional", "cladding": "brick", "windows_upper": "standard",
                    "windows_ground": "standard", "railing": "solid",
                    "colors": {"walls": "#e9dcc3", "facade": "#b5653e", "trim": "#7c4a2d", "roof": "#c7b08b",
                               "window_frames": "#5a3a22", "door": "#5a3a22"}},
    "spanish": {"label": "Spanish", "cladding": "none", "windows_upper": "standard", "windows_ground": "standard",
                "railing": "solid",
                "colors": {"walls": "#f3ead8", "facade": "#ecdcbc", "trim": "#9a5b34", "roof": "#b5543a",
                           "window_frames": "#4a2c1a", "door": "#7a3e1d"}},
}
STYLE_PATTERNS = [
    ("modern pakistani", r"modern\s+pakistani|pakistani\s+modern"),
    ("minimal", r"minimal(ist|istic)?"),
    ("industrial", r"industrial"),
    ("spanish", r"spanish|mediterranean"),
    ("traditional", r"traditional|mughal|old[- ]style"),
    ("classic", r"classic(al)?|colonial"),
    ("modern", r"modern|contemporary"),
]
NAMED_COLORS = {
    "white": "#f5f5f4", "off-white": "#eeebe3", "cream": "#efe6d2", "beige": "#e3d5b8", "ivory": "#f3eee1",
    "grey": "#9ca3af", "gray": "#9ca3af", "light grey": "#d1d5db", "light gray": "#d1d5db",
    "dark grey": "#4b5563", "dark gray": "#4b5563", "charcoal": "#36393f", "black": "#1f1f1f",
    "brown": "#7a5236", "wooden": "#8b5e34", "terracotta": "#b5543a", "red": "#a33b2f", "maroon": "#6d2530",
    "blue": "#3b6ea5", "navy": "#1e3a5f", "green": "#4d7c55", "olive": "#6b7040", "yellow": "#e7c65b",
    "sand": "#d8c39a", "peach": "#f2c6a0", "pink": "#e8b4b8",
}
CLADDING_WORDS = [("stone", r"stone"), ("brick", r"brick|tuff ?tile|gutka"), ("wood", r"wood(en)?|timber"),
                  ("tile", r"\btiles?\b|ceramic|porcelain"), ("glass", r"glass (facade|front|elevation)|glazing|curtain wall"),
                  ("concrete", r"concrete|exposed cement")]
STRUCTURAL = [
    (r"\b(add|build|construct)\w*\s+(an?\s+|one\s+|another\s+|a\s+second\s+|extra\s+)?(floor|storey|story)\b|\bextra\s+(floor|storey|story)\b",
     "adding a storey"),
    (r"\b(remove|demolish|knock\s+down|break|move|shift)\w*\s+(the\s+|a\s+|an\s+)?(\w+\s+)?(wall|column|beam|pillar|stair)",
     "removing or moving walls, columns, beams or stairs"),
    (r"\b(extend|extension|enlarge)\w*\b.*\b(house|building|room|front|back|side|footprint)|\bbasement\b",
     "extending the building or adding a basement"),
]
LEVEL_WORDS = {"ground": 1, "first": 2, "upper": 2, "top": 2, "second": 2}


def _find_color(text: str, target: str) -> Optional[str]:
    names = "|".join(sorted((re.escape(n) for n in NAMED_COLORS), key=len, reverse=True))
    m = re.search(rf"\b({names})\b[\w\s-]{{0,20}}\b{target}", text) or \
        re.search(rf"\b{target}\w*\b[\w\s-]{{0,20}}\b({names})\b", text)
    return NAMED_COLORS[m.group(1)] if m else None


def parse_modifications(prompt: str, observed_colors: Dict[str, str], floors: int,
                        existing: Dict[str, Any]) -> Dict[str, Any]:
    """Returns {"request", "proposed", "clarifications", "assumptions"} in the
    same shape the photo analysis response uses."""
    text = (prompt or "").lower()
    mods: List[Dict[str, str]] = []
    preserve: List[str] = []
    structural: List[str] = []
    clarifications: List[Dict[str, Any]] = []
    assumptions: List[str] = []

    for pattern, label in STRUCTURAL:
        if re.search(pattern, text):
            structural.append(label)
    for label in structural:
        clarifications.append({
            "question": f"Your request involves {label}. Can you confirm it with drawings or an engineer's "
                        f"assessment, or remove it from the request?",
            "reason": "A photo cannot show whether the structure can take this change.",
            "blocking": True})

    style_key = next((k for k, pat in STYLE_PATTERNS if re.search(rf"\b({pat})\b", text)), None)
    preset = STYLE_PRESETS.get(style_key) if style_key else None
    if preset:
        mods.append({"element": "front elevation", "change": f"{preset['label']} style"})

    wants_scheme = bool(re.search(r"colou?r\s*(scheme|palette)|repaint|paint", text))
    colors = dict(observed_colors)
    colors.setdefault("facade", colors.get("walls", "#e2e8f0"))
    if preset and (wants_scheme or not re.search(r"keep\w*\s+(the\s+)?(existing\s+|current\s+)?colou?rs?", text)):
        colors.update(preset["colors"])
        if wants_scheme:
            mods.append({"element": "colour scheme", "change": f"{preset['label'].lower()} palette"})
    elif wants_scheme and not preset:
        assumptions.append("No style was named, so the existing colours were kept apart from colours you named.")
    for target, key in (("wall", "walls"), ("(facade|front|elevation)", "facade"), ("(door|gate)", "door"),
                        ("(window|frame)", "window_frames"), ("(trim|border|band)", "trim")):
        c = _find_color(text, target)
        if c:
            colors[key] = c
            mods.append({"element": key.replace("_", " "), "change": f"colour {c}"})

    cladding = next((k for k, pat in CLADDING_WORDS if re.search(pat, text)), None)
    if cladding:
        mods.append({"element": "facade finish", "change": f"{cladding} cladding"})
    else:
        cladding = preset["cladding"] if preset else "none"

    window_style_upper = preset["windows_upper"] if preset else "standard"
    window_style_ground = preset["windows_ground"] if preset else "standard"
    if re.search(r"full[- ]height|floor[- ]to[- ]ceiling", text):
        window_style_upper = window_style_ground = "full_height"
        mods.append({"element": "windows", "change": "full-height windows"})
    elif re.search(r"(large|big|bigger|wide|wider)\s+windows", text):
        window_style_upper = window_style_ground = "large"
        mods.append({"element": "windows", "change": "larger windows"})

    balconies = []
    if existing.get("balcony") and not re.search(r"remove\w*\s+(the\s+)?balcon", text):
        balconies.append({"level": 2, "position": "center", "width_fraction": 0.4})
        preserve.append("existing first-floor balcony")
    m = re.search(r"\badd\w*\s+(an?\s+|one\s+)?(full[- ]width\s+|wide\s+|small\s+)?balcon\w*(.{0,40})", text)
    if m:
        where = m.group(3) or ""
        level_word = re.search(r"(ground|first|upper|top|second)\s+(floor|storey|story|level)", where)
        level = LEVEL_WORDS[level_word.group(1)] if level_word else 2
        position = "full_width" if (m.group(2) or "").startswith(("full", "wide")) or "full width" in where else \
            "left" if "left" in where else "right" if "right" in where else "center"
        balconies = [b for b in balconies if b["level"] != level]
        balconies.append({"level": level, "position": position,
                          "width_fraction": 1.0 if position == "full_width" else 0.45})
        mods.append({"element": f"level {level}", "change": "add a balcony"})
        if level == 1:
            clarifications.append({"question": "A balcony needs an upper floor. Did you mean the first floor?",
                                   "reason": "The request puts the balcony on the ground floor.", "blocking": True})
        elif level > floors:
            clarifications.append({"question": f"The balcony is on level {level}, but the property has {floors} "
                                               f"floor(s). Which floor should it go on?",
                                   "reason": "There is no floor to attach it to.", "blocking": True})
    if re.search(r"remove\w*\s+(the\s+)?balcon", text):
        balconies = []
        mods.append({"element": "balcony", "change": "remove"})

    garage = bool(existing.get("garage_door"))
    if re.search(r"\badd\w*\s+(a\s+)?(garage|car\s*porch|gate)", text):
        garage = True
        mods.append({"element": "ground floor", "change": "garage door at the front"})

    if re.search(r"keep\w*\s+(the\s+)?(existing\s+)?(structure|building|shape|layout)|as much as possible|same structure", text):
        preserve.append("existing structure, floors and opening positions")
    preserve.append(f"{floors} floor(s) as in the existing property")

    windows = existing.get("front_windows")
    front = [{"level": 1, "doors": 1, "windows": windows if windows is not None else 2,
              "garage_door": garage, "window_style": window_style_ground}]
    if floors >= 2:
        front.append({"level": 2, "doors": 0, "windows": windows if windows is not None else 3,
                      "garage_door": False, "window_style": window_style_upper})
    if windows is None:
        assumptions.append("Front windows per floor were not given, so a typical count was used "
                           "(2 on the ground floor, 3 above). Enter the number you see for a closer match.")

    text_left = re.sub(r"[^a-z]", "", text)
    if text_left and not mods and not structural and not re.search(r"keep|same|as it is|existing", text):
        clarifications.append({
            "question": "Which changes do you want? For example: \"modern elevation, add a balcony on the first "
                        "floor, stone cladding, grey and white colour scheme\".",
            "reason": "No recognisable design change was found in the description.",
            "blocking": True})

    intent = "modify_existing" if mods else "no_changes"
    return {
        "request": {"intent": intent, "modifications": mods, "preserve": preserve,
                    "unreliable_structural_requests": structural},
        "proposed": {"floors": floors, "style": preset["label"] if preset else "Existing style",
                     "colors": colors, "facade_cladding": cladding, "front_elevation": front,
                     "balconies": balconies, "top_terrace": False},
        "clarifications": clarifications,
        "assumptions": assumptions,
        "railing": preset["railing"] if preset else "solid",
    }
