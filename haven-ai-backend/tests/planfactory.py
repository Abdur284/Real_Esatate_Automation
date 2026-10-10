"""
Draws synthetic floor-plan images with known ground truth, so Layer 1 can be
tested for measured accuracy rather than "it returned something".

Rooms are given as wall-centreline rectangles in feet (the same convention the
analyser outputs). The drawing has thick exterior walls, thinner partitions,
door gaps with swing arcs, windows as a gap with two thin lines, room labels
and optional stair treads and colour fills, with the road at the bottom.
"""
import json
import struct
import zlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

EXT_T = 0.75
INT_T = 0.375


@dataclass
class Room:
    name: str
    x0: float
    y0: float
    x1: float
    y1: float
    fill: Optional[Tuple[int, int, int]] = None  # RGB
    stairs: bool = False
    group: Optional[str] = None


@dataclass
class Opening:
    kind: str           # door | window
    horizontal: bool    # wall runs along x
    line: float         # y (horizontal) or x (vertical) of the wall centreline, ft
    a: float            # start along the wall, ft
    b: float            # end along the wall, ft


@dataclass
class Layout:
    width: float
    depth: float
    rooms: List[Room]
    openings: List[Opening] = field(default_factory=list)


def simple_house() -> Layout:
    """25 x 40 ft, six rooms, six doors (one to the road), three windows."""
    h = EXT_T / 2
    W, D = 25.0, 40.0
    rooms = [
        Room("LIVING", h, h, 14, 16),
        Room("KITCHEN", 14, h, W - h, 10),
        Room("BATH", 14, 10, W - h, 16),
        Room("BED 1", h, 16, 12, D - h),
        Room("BED 2", 12, 16, W - h, 30),
        Room("STORE", 12, 30, W - h, D - h),
    ]
    openings = [
        Opening("door", True, h, 5, 8.5),        # main entrance from the road
        Opening("door", True, 16, 4, 7),         # living -> bed 1
        Opening("door", False, 14, 3, 6),        # living -> kitchen
        Opening("door", True, 10, 18, 21),       # kitchen -> bath
        Opening("door", False, 12, 20, 23),      # bed 1 -> bed 2
        Opening("door", True, 30, 16, 19),       # bed 2 -> store
        Opening("window", False, h, 25, 29),     # bed 1, west
        Opening("window", False, W - h, 3, 7),   # kitchen, east
        Opening("window", False, W - h, 20, 24), # bed 2, east
    ]
    return Layout(W, D, rooms, openings)


def l_shaped_house() -> Layout:
    """30 x 30 ft with an L-shaped lounge wrapping a bedroom."""
    h = EXT_T / 2
    W = D = 30.0
    rooms = [
        Room("LOUNGE", h, h, W - h, 12, group="L"),
        Room("LOUNGE", h, 12, 12, D - h, group="L"),
        Room("BED", 12, 12, W - h, D - h),
    ]
    openings = [
        Opening("door", True, h, 10, 13.5),
        Opening("door", True, 12, 18, 21),
    ]
    return Layout(W, D, rooms, openings)


def draw(layout: Layout, ppf: float = 20.0, margin: int = 60, text: bool = True,
         sizes: bool = False, hollow: bool = False, overall: bool = False) -> np.ndarray:
    """sizes: print each room's size ("12' x 14'") under its name; hollow:
    draw walls as outlines (two parallel lines); overall: print the overall
    width on a dimension line below the plan."""
    W, D = layout.width, layout.depth
    w_px, h_px = int(round(W * ppf)) + 2 * margin, int(round(D * ppf)) + 2 * margin
    img = np.full((h_px, w_px, 3), 255, np.uint8)
    X = lambda x: margin + x * ppf                # noqa: E731
    Y = lambda y: margin + (D - y) * ppf          # noqa: E731
    h = EXT_T / 2

    def on_boundary(v, lo, hi):
        return abs(v - lo) < 1e-6 or abs(v - hi) < 1e-6

    for r in layout.rooms:
        if r.fill:
            cv2.rectangle(img, (int(X(r.x0)), int(Y(r.y1))), (int(X(r.x1)), int(Y(r.y0))), r.fill[::-1], -1)
    walls = np.zeros((h_px, w_px), np.uint8)
    for r in layout.rooms:
        for horizontal, line, a, b in ((True, r.y0, r.x0, r.x1), (True, r.y1, r.x0, r.x1),
                                       (False, r.x0, r.y0, r.y1), (False, r.x1, r.y0, r.y1)):
            same_group = r.group and any(
                o is not r and o.group == r.group and (
                    (horizontal and (abs(o.y0 - line) < 1e-6 or abs(o.y1 - line) < 1e-6)
                     and min(o.x1, b) - max(o.x0, a) > 0)
                    or (not horizontal and (abs(o.x0 - line) < 1e-6 or abs(o.x1 - line) < 1e-6)
                        and min(o.y1, b) - max(o.y0, a) > 0))
                for o in layout.rooms)
            if same_group:
                continue
            ext = on_boundary(line, h, (D if horizontal else W) - h)
            t = EXT_T if ext else INT_T
            if horizontal:
                p0, p1 = (X(a - t / 2), Y(line + t / 2)), (X(b + t / 2), Y(line - t / 2))
            else:
                p0, p1 = (X(line - t / 2), Y(b + t / 2)), (X(line + t / 2), Y(a - t / 2))
            cv2.rectangle(walls, (int(round(p0[0])), int(round(p0[1]))), (int(round(p1[0])), int(round(p1[1]))), 1, -1)

    for op in layout.openings:
        ext = on_boundary(op.line, h, (D if op.horizontal else W) - h)
        t = (EXT_T if ext else INT_T) + 0.2
        if op.horizontal:
            walls[int(Y(op.line + t / 2)):int(Y(op.line - t / 2)) + 1, int(X(op.a)):int(X(op.b))] = 0
        else:
            walls[int(Y(op.b)):int(Y(op.a)), int(X(op.line - t / 2)):int(X(op.line + t / 2)) + 1] = 0
    if hollow:
        walls = walls - cv2.erode(walls, np.ones((3, 3), np.uint8))
    img[walls > 0] = (30, 30, 30)

    for op in layout.openings:
        if op.kind == "window":
            for off in (-0.15, 0.15):
                if op.horizontal:
                    y = int(Y(op.line + off))
                    cv2.line(img, (int(X(op.a)), y), (int(X(op.b)), y), (40, 40, 40), 1)
                else:
                    x = int(X(op.line + off))
                    cv2.line(img, (x, int(Y(op.a))), (x, int(Y(op.b))), (40, 40, 40), 1)
        else:
            r = int((op.b - op.a) * ppf)
            if op.horizontal:
                cv2.ellipse(img, (int(X(op.a)), int(Y(op.line))), (r, r), 0, 270, 360, (90, 90, 90), 1)
            else:
                cv2.ellipse(img, (int(X(op.line)), int(Y(op.a))), (r, r), 0, 180, 270, (90, 90, 90), 1)

    seen = set()
    for r in layout.rooms:
        if r.stairs:
            y = r.y0 + 1
            while y < r.y1 - 0.5:
                cv2.line(img, (int(X(r.x0 + 0.4)), int(Y(y))), (int(X(r.x1 - 0.4)), int(Y(y))), (60, 60, 60), 1)
                y += 1
        if text and r.name not in seen:
            seen.add(r.name)
            cx, cy = X((r.x0 + r.x1) / 2), Y((r.y0 + r.y1) / 2)
            cv2.putText(img, r.name, (int(cx) - 30, int(cy)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (20, 20, 20), 1, cv2.LINE_AA)
            if sizes:
                size = f"{r.x1 - r.x0:.0f}' x {r.y1 - r.y0:.0f}'"
                cv2.putText(img, size, (int(cx) - 30, int(cy) + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (20, 20, 20), 1,
                            cv2.LINE_AA)
    if overall:
        y = int(Y(0)) + 30
        cv2.line(img, (int(X(0)), y), (int(X(W)), y), (0, 0, 0), 1)
        for x in (0, W):
            cv2.line(img, (int(X(x)), y - 6), (int(X(x)), y + 6), (0, 0, 0), 1)
        cv2.putText(img, f"{W:.0f}'-0\"", (int(X(W / 2)) - 25, y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1,
                    cv2.LINE_AA)
    return img


def png_bytes(img: np.ndarray) -> bytes:
    ok, buf = cv2.imencode(".png", img)
    assert ok
    return buf.tobytes()


def with_itxt(png: bytes, keyword: str, text: str) -> bytes:
    """Inserts an iTXt chunk before IEND, as the frontend's PNG export does."""
    body = keyword.encode() + b"\x00\x00\x00\x00\x00" + text.encode("utf-8")
    chunk = struct.pack(">I", len(body)) + b"iTXt" + body + struct.pack(">I", zlib.crc32(b"iTXt" + body) & 0xFFFFFFFF)
    return png[:-12] + chunk + png[-12:]


def truth_rects(layout: Layout) -> Dict[str, List[Tuple[float, float, float, float]]]:
    out: Dict[str, List] = {}
    for r in layout.rooms:
        out.setdefault(r.name, []).append((r.x0, r.y0, r.x1 - r.x0, r.y1 - r.y0))
    return out


def dumps(plan) -> str:
    return json.dumps(plan)
