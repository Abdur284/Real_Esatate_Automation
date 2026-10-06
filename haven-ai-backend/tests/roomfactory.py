"""
A synthetic room photo with a known segmentation, for testing the scene,
operations and renderer without the ML model.

The photo has a pale wall, a wooden floor whose boards recede to a known
vanishing point, a green sofa on the floor, a dark painting on the wall and a
brown table with a vase standing on it. `FakeSegmenter` returns the exact
class map for it (a test double for the ONNX model, used only in tests).
"""
import math

import cv2
import numpy as np

# ADE20K ids of the classes used (same ids as the real model's config.json).
LABELS = {0: "wall", 3: "floor", 5: "ceiling", 15: "table", 22: "painting", 23: "sofa", 28: "rug",
          135: "vase"}
WALL, FLOOR, TABLE, PAINTING, SOFA, VASE = 0, 3, 15, 22, 23, 135

W, H = 640, 480
SEAM_Y = 300                      # wall/floor seam
VP = (320, 150)                   # vanishing point of the floor boards
SOFA_BOX = (150, 215, 450, 330)   # x0, y0, x1, y1 (bottom on the floor)
PAINTING_BOX = (470, 60, 580, 150)
TABLE_BOX = (470, 290, 610, 370)
VASE_BOX = (525, 250, 555, 291)   # stands on the table top

WALL_BGR = (205, 200, 196)
FLOOR_BGR = (80, 120, 165)
SOFA_BGR = (45, 110, 40)
PAINTING_BGR = (90, 40, 30)
TABLE_BGR = (30, 60, 110)
VASE_BGR = (180, 180, 40)


def room_image() -> np.ndarray:
    rng = np.random.default_rng(3)
    img = np.zeros((H, W, 3), np.float32)
    img[:SEAM_Y] = WALL_BGR
    img[SEAM_Y:] = FLOOR_BGR
    # soft light from the left, like a window
    img *= (1.05 - 0.15 * np.linspace(0, 1, W))[None, :, None]
    # floor boards converging to the vanishing point
    for x_bottom in np.linspace(-900, 1540, 36):
        x_seam = VP[0] + (x_bottom - VP[0]) * (SEAM_Y - VP[1]) / (H - VP[1])
        cv2.line(img, (int(x_seam), SEAM_Y), (int(x_bottom), H), (50, 80, 115), 2, cv2.LINE_AA)
    img += rng.normal(0, 3, img.shape).astype(np.float32)
    for (x0, y0, x1, y1), c in ((SOFA_BOX, SOFA_BGR), (PAINTING_BOX, PAINTING_BGR), (TABLE_BOX, TABLE_BGR),
                                (VASE_BOX, VASE_BGR)):
        img[y0:y1, x0:x1] = c
        img[y0:y1, x0:x1] *= np.linspace(1.1, 0.85, y1 - y0)[:, None, None]   # shading
    return np.clip(img, 0, 255).astype(np.uint8)


def class_map() -> np.ndarray:
    cls = np.full((H, W), WALL, np.int16)
    cls[SEAM_Y:] = FLOOR
    for (x0, y0, x1, y1), c in ((SOFA_BOX, SOFA), (PAINTING_BOX, PAINTING), (TABLE_BOX, TABLE), (VASE_BOX, VASE)):
        cls[y0:y1, x0:x1] = c
    return cls


def png_bytes(img: np.ndarray = None) -> bytes:
    ok, buf = cv2.imencode(".png", room_image() if img is None else img)
    return buf.tobytes()


class FakeSegmenter:
    """Stands in for the ONNX model: returns the known class map."""
    labels = LABELS

    def segment(self, img):
        assert img.shape[:2] == (H, W)
        return class_map(), np.full((H, W), 0.9, np.float32)


def mean_color(img: np.ndarray, box) -> np.ndarray:
    x0, y0, x1, y1 = box
    return img[y0:y1, x0:x1].reshape(-1, 3).mean(0)


def color_distance(a, b) -> float:
    return float(math.dist([float(v) for v in a], [float(v) for v in b]))
