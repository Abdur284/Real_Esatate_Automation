"""
Reading the text printed on a floor plan: room names and dimensions.

OCR is RapidOCR (PP-OCR models run on onnxruntime, CPU only, bundled with
the package, so no download, GPU or external AI service). It is optional: if
the package is missing the analysis still works and reports that text was
not read, exactly as before OCR existed.

The OCR only reads strings and where they are. What they mean is decided
here by plain rules: a known room word names the room the text sits in, and
"12' x 14'" style strings are dimensions. Nothing is invented: a string that
matches neither is ignored, and unreadable text simply leaves a room unnamed.
"""
import logging
import re
import threading
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

MIN_TEXT_SCORE = 0.6

_engine = None
_engine_lock = threading.Lock()
_engine_failed = False


def _get_engine():
    global _engine, _engine_failed
    if _engine is not None or _engine_failed:
        return _engine
    with _engine_lock:
        if _engine is None and not _engine_failed:
            try:
                from rapidocr_onnxruntime import RapidOCR
                _engine = RapidOCR()
            except Exception:  # missing package or model: text is simply not read
                logger.warning("RapidOCR unavailable; floor-plan text will not be read.", exc_info=True)
                _engine_failed = True
    return _engine


def ocr_available() -> bool:
    return _get_engine() is not None


def read_text(bgr: np.ndarray) -> Optional[List[Dict[str, Any]]]:
    """Returns [{text, score, box: (x0, y0, x1, y1)}] in the image's pixels, or
    None when OCR is not available."""
    engine = _get_engine()
    if engine is None:
        return None
    try:
        result, _ = engine(bgr)
    except Exception:
        logger.exception("OCR failed on a floor plan")
        return None
    out = []
    for quad, text, score in result or []:
        if not text or float(score) < MIN_TEXT_SCORE:
            continue
        xs = [float(p[0]) for p in quad]
        ys = [float(p[1]) for p in quad]
        out.append({"text": str(text).strip(), "score": round(float(score), 2),
                    "box": (min(xs), min(ys), max(xs), max(ys))})
    return out


def rotate_boxes(items: List[Dict[str, Any]], front: str, w: int, h: int) -> List[Dict[str, Any]]:
    """Maps boxes read on the original image into the frame rotated by
    image_io.rotate_front_to_bottom (w, h = original size)."""
    def pt(x, y):
        if front == "top":
            return w - x, h - y
        if front == "left":      # 90 deg counter-clockwise
            return y, w - x
        if front == "right":     # 90 deg clockwise
            return h - y, x
        return x, y

    out = []
    for it in items:
        x0, y0, x1, y1 = it["box"]
        a, b = pt(x0, y0), pt(x1, y1)
        out.append({**it, "box": (min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1]))})
    return out


# ── Room names ──────────────────────────────────────────────────────────────
# Matched against the text lower-cased with spaces and punctuation removed
# (OCR often drops the space in "LIVING ROOM"). Longer keys are tried first.
ROOM_WORDS: List[Tuple[str, str]] = sorted([
    ("masterbed", "master_bedroom"), ("masterbedroom", "master_bedroom"), ("mbr", "master_bedroom"),
    ("guestroom", "guest_room"), ("guestbed", "guest_room"),
    ("servantroom", "servant_room"), ("servantquarter", "servant_room"), ("servant", "servant_room"),
    ("bedroom", "bedroom"), ("bedrm", "bedroom"), ("bed", "bedroom"), ("br", "bedroom"),
    ("bathroom", "bathroom"), ("bath", "bathroom"), ("toilet", "bathroom"), ("tollet", "bathroom"), ("washroom", "bathroom"),
    ("wc", "bathroom"), ("powder", "bathroom"), ("ensuite", "bathroom"), ("restroom", "bathroom"),
    ("kitchen", "kitchen"), ("kit", "kitchen"), ("pantry", "kitchen"),
    ("dining", "dining_room"), ("dinning", "dining_room"),
    ("livingroom", "living_room"), ("living", "living_room"), ("sitting", "living_room"),
    ("familyroom", "living_room"), ("family", "living_room"), ("hall", "living_room"),
    ("great room", "living_room"),
    ("tvlounge", "tv_lounge"), ("lounge", "tv_lounge"), ("tvroom", "tv_lounge"),
    ("drawingroom", "drawing_room"), ("drawing", "drawing_room"), ("guestsitting", "drawing_room"),
    ("study", "study"), ("office", "study"), ("library", "study"),
    ("prayer", "prayer_room"), ("pooja", "prayer_room"), ("puja", "prayer_room"),
    ("store", "store"), ("storage", "store"), ("closet", "store"), ("dress", "store"), ("wardrobe", "store"),
    ("laundry", "laundry"), ("utility", "laundry"),
    ("stair", "staircase"), ("stairs", "staircase"), ("staircase", "staircase"), ("up", "staircase"),
    ("hallway", "corridor"), ("corridor", "corridor"), ("passage", "corridor"), ("gallery", "corridor"),
    ("lobby", "lobby"), ("foyer", "lobby"), ("entrance", "entrance"), ("entry", "entrance"),
    ("carporch", "parking"), ("porch", "parking"), ("parking", "parking"), ("carport", "parking"),
    ("garage", "garage"),
    ("courtyard", "courtyard"), ("lawn", "lawn"), ("garden", "lawn"),
    ("terrace", "terrace"), ("veranda", "terrace"), ("verandah", "terrace"), ("patio", "terrace"),
    ("sitout", "terrace"), ("portico", "parking"),
    ("balcony", "balcony"),
], key=lambda kv: -len(kv[0]))
SHORT_WORDS = {"br", "wc", "up", "kit", "bed", "mbr"}  # only as a whole word


def _squash(text: str) -> str:
    return re.sub(r"[^a-z]", "", text.lower())


def room_type_for(text: str) -> Optional[str]:
    words = re.findall(r"[a-z]+", text.lower())
    squashed = _squash(text)
    if not squashed:
        return None
    for key, rtype in ROOM_WORDS:
        key = key.replace(" ", "")
        if key in SHORT_WORDS:
            if key in words or squashed == key or re.fullmatch(key + r"\d*", squashed):
                return rtype
        elif key in squashed:
            return rtype
    return None


def clean_name(text: str) -> str:
    """Display name for a label as printed: 'LIVINGROOM' -> 'Living Room'."""
    t = re.sub(r"\s+", " ", text).strip(" -:.")
    squashed = _squash(t)
    for joined, spaced in (("livingroom", "living room"), ("drawingroom", "drawing room"),
                           ("bedroom", "bedroom"), ("tvlounge", "TV lounge"), ("carporch", "car porch"),
                           ("diningroom", "dining room"), ("guestroom", "guest room"),
                           ("masterbedroom", "master bedroom"), ("familyroom", "family room")):
        if squashed.startswith(joined) and " " not in t:
            rest = re.sub(r"^[A-Za-z]+", "", t)
            t = spaced + rest
            break
    # Short upper-case words are abbreviations (TV, WC, W.C.); keep them.
    return " ".join(w if w.isupper() and len(re.sub(r"[^A-Za-z]", "", w)) <= 2 else w.title()
                    for w in t.split(" "))[:40]


# ── Dimensions ──────────────────────────────────────────────────────────────
# One length: 12' | 12'-6" | 12'6" | 12.5' | 12 ft | 3.6m | 360cm | bare 12
_LEN = (r"(\d{1,3}(?:\.\d{1,2})?)\s*(?:(['’′`]|ft\.?|feet)\s*-?\s*(?:(\d{1,2}(?:\.\d)?)\s*(?:[\"”″]|''|in\.?)?)?"
        r"|(m|cm|mm)\b)?")
_PAIR = re.compile(_LEN + r"\s*(?:[xX×*]|[^\w\s.'\"]|\s[xX]?\s?)\s*" + _LEN)
_SINGLE = re.compile(r"^\s*" + _LEN + r"\s*$")


def _feet(num: str, foot_mark: Optional[str], inches: Optional[str], metric: Optional[str]) -> Optional[float]:
    v = float(num)
    if metric:
        v = v / {"m": 0.3048, "cm": 30.48, "mm": 304.8}[metric]
    elif inches:
        v += float(inches) / 12.0
    return v if 2.0 <= v <= 400.0 else None


def parse_pair(text: str) -> Optional[Tuple[float, float, bool]]:
    """'12' x 14'' -> (12.0, 14.0, has_unit). None if not a dimension pair."""
    t = text.replace("’", "'").replace("”", '"')
    m = _PAIR.search(t)
    if not m:
        return None
    g = m.groups()
    a = _feet(g[0], g[1], g[2], g[3])
    b = _feet(g[4], g[5], g[6], g[7])
    if a is None or b is None:
        return None
    unit = bool(g[1] or g[3] or g[5] or g[7])
    # A bare "12 14" is too ambiguous: it needs a unit or an "x".
    if not unit and not re.search(r"[xX×*]", t[m.start():m.end()]):
        return None
    a, b = _dropped_marks(a, b, g)
    return round(a, 2), round(b, 2), unit


def _dropped_marks(a: float, b: float, g) -> Tuple[float, float]:
    """OCR often loses the foot and inch marks of 11'0" x 16'6", giving
    "110 x 166". A room side over 40 ft written without inches is read that
    way (110 -> 11'0", 166 -> 16'6", 50 -> 5'0"), unless both numbers carry
    a foot mark (a real "30' x 60'" plot) or the result is implausibly small."""
    if max(a, b) <= 40 or (g[1] and g[5] and not g[2] and not g[6]):
        return a, b
    # A small partner written plainly ("30x60") means plain feet, not lost marks.
    if any(v <= 40 and not inches for v, inches in ((a, g[2]), (b, g[6]))):
        return a, b
    out = []
    for value, (num, _mark, inches, metric) in ((a, g[0:4]), (b, g[4:8])):
        if value > 40 and not inches and not metric and "." not in num and len(num) >= 2:
            feet, inch = (num[:-2], num[-2:]) if len(num) == 4 and int(num[-2:]) <= 11 else (num[:-1], num[-1])
            value = int(feet) + int(inch) / 12.0
        out.append(value)
    return (a, b) if min(out) < 4 else (out[0], out[1])


def parse_single(text: str) -> Optional[float]:
    """An overall dimension such as 26'-0" (a unit is required)."""
    t = text.replace("’", "'").replace("”", '"')
    m = _SINGLE.match(t)
    if not m or not (m.group(2) or m.group(4)):
        return None
    return _feet(m.group(1), m.group(2), m.group(3), m.group(4))


def classify(items: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Splits OCR items into room labels, dimension pairs and single lengths."""
    labels, pairs, singles, other = [], [], [], []
    for it in items:
        text = it["text"]
        pair = parse_pair(text)
        if pair:
            pairs.append({**it, "a": pair[0], "b": pair[1]})
            # "BEDROOM 12'x14'" in one string is a name and a size.
            words = re.sub(r"[\d'\"’”xX×*.,\-]+", " ", text).strip()
            rtype = room_type_for(words) if re.search(r"[A-Za-z]{3,}", words) else None
            if rtype:
                labels.append({**it, "type": rtype, "name": clean_name(words)})
            continue
        single = parse_single(text)
        if single:
            singles.append({**it, "value": single})
            continue
        rtype = room_type_for(text)
        if rtype and re.search(r"[A-Za-z]{2,}", text):
            labels.append({**it, "type": rtype, "name": clean_name(text)})
        else:
            other.append(it)
    return {"labels": labels, "pairs": pairs, "singles": singles, "other": other}


def centre(box) -> Tuple[float, float]:
    return (box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0


def region_at(labels: np.ndarray, box, room_ids: set, fixtures: Optional[Dict[int, int]] = None
              ) -> Optional[int]:
    """The room region a text box sits in: its centre, else the room most of
    a small grid of points over the box falls in. Text printed inside a piece
    of furniture (a bed outline) belongs to the room around it."""
    H, W = labels.shape
    fixtures = fixtures or {}
    cx, cy = centre(box)
    lab = int(labels[min(H - 1, max(0, int(cy))), min(W - 1, max(0, int(cx)))])
    lab = fixtures.get(lab, lab)
    if lab in room_ids:
        return lab
    votes: Dict[int, int] = {}
    for fx in (0.1, 0.3, 0.5, 0.7, 0.9):
        for fy in (0.2, 0.5, 0.8):
            x = int(box[0] + fx * (box[2] - box[0]))
            y = int(box[1] + fy * (box[3] - box[1]))
            if 0 <= x < W and 0 <= y < H:
                v = int(labels[y, x])
                v = fixtures.get(v, v)
                if v in room_ids:
                    votes[v] = votes.get(v, 0) + 1
    return max(votes, key=votes.get) if votes else None


def scale_from_rooms(pairs: List[Dict[str, Any]], rooms: List[Dict[str, Any]], labels: np.ndarray,
                     wall_px: float, fixtures: Optional[Dict[int, int]] = None) -> Optional[Dict[str, Any]]:
    """Pixels per foot (x and y) from room-size strings printed inside rooms.

    A printed room size may be the clear (inside) size or the centre-line size;
    they differ by one wall thickness, so the room's pixel size is taken
    halfway between the two (an error of about 2% either way). The two numbers
    are matched to the room's sides by whichever order fits its proportions."""
    by_label = {r["label"]: r for r in rooms if len(r["parts"]) == 1}
    sx_list, sy_list, used = [], [], []
    for p in pairs:
        lab = region_at(labels, p["box"], set(by_label), fixtures)
        if lab is None:
            continue
        x0, y0, x1, y1 = by_label[lab]["bbox"]
        pw, ph = (x1 - x0) + 0.5 * wall_px, (y1 - y0) + 0.5 * wall_px
        best = None
        for fw, fh in ((p["a"], p["b"]), (p["b"], p["a"])):
            sx, sy = pw / fw, ph / fh
            err = abs(sx / sy - 1)
            if best is None or err < best[0]:
                best = (err, sx, sy, fw, fh)
        err, sx, sy, fw, fh = best
        if err > 0.12:  # the string does not describe this room's shape
            continue
        sx_list.append(sx)
        sy_list.append(sy)
        used.append({"text": p["text"], "room_label": lab, "width_ft": fw, "length_ft": fh})
    if not used:
        return None
    sx, sy = float(np.median(sx_list)), float(np.median(sy_list))
    spread = max(max(abs(v / sx - 1) for v in sx_list), max(abs(v / sy - 1) for v in sy_list))
    # One string is weak evidence; agreeing strings are strong.
    conf = 0.65 if len(used) == 1 else (0.9 if spread < 0.06 else 0.75 if spread < 0.12 else 0.5)
    return {"sx": sx, "sy": sy, "used": used, "spread": round(spread, 3), "confidence": conf}


def overall_from_singles(singles: List[Dict[str, Any]], bbox, pairs: List[Dict[str, Any]]
                         ) -> Dict[str, Optional[float]]:
    """Overall width/depth printed on dimension lines outside the building:
    the largest length below/above the plan is its width, the largest one
    left/right of it is its depth. A 'W x D' plot string anywhere outside the
    building is used too."""
    bx, by, bw, bh = bbox
    width = depth = None
    for s in singles:
        cx, cy = centre(s["box"])
        within_x = bx <= cx <= bx + bw
        within_y = by <= cy <= by + bh
        if within_x and not within_y:      # on a dimension line above/below the plan
            width = max(width or 0, s["value"])
        elif within_y and not within_x:    # left/right of the plan
            depth = max(depth or 0, s["value"])
    for p in pairs:
        cx, cy = centre(p["box"])
        if bx <= cx <= bx + bw and by <= cy <= by + bh:
            continue  # a room size, not the plot
        a, b = p["a"], p["b"]
        aspect = bw / bh
        if abs((a / b) / aspect - 1) <= abs((b / a) / aspect - 1):
            width, depth = width or a, depth or b
        else:
            width, depth = width or b, depth or a
    return {"width_ft": width, "depth_ft": depth}
