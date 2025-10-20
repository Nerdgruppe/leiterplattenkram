#!/usr/bin/env python3
"""
Mosaic Viewer — adjustable spacing + slopes (Python + OpenCV)

Loads images named: img_{px}_{py}.png (e.g., img_0_0.png ...)
Shows a live window where you can adjust:
  - step_x (horizontal spacing between tile origins)
  - step_y (vertical spacing between tile origins)
  - h_slope (extra X pixels per row — horizontal drift downwards)
  - v_slope (extra Y pixels per column — vertical drift rightwards)
  - grid (draw tile outlines)
  - scale% (display zoom only)

Formulas (px, py are the integer indices taken from filenames):
  x = (px - min_px) * step_x + (py - min_py) * h_slope
  y = (py - min_py) * step_y + (px - min_px) * v_slope

This implements an affine shear-like correction so you can compensate for
accumulated stage drift or non-orthogonality in your acquisition.

Controls:
  - q or ESC: quit
  - s: save current full-resolution mosaic to mosaic_preview.png
  - r: reset slopes (h_slope, v_slope) to 0

Dependencies:  pip install opencv-python numpy
"""

import os
import re
import glob
import cv2
import numpy as np
from typing import List, Tuple

# --- Configuration ---------------------------------------------------------
IMAGE_DIR = "/home/felix/projects/experiments/wtf-leiterplattenkram/stitch_store"
FILENAME_RE = re.compile(r"^img_(-?\d+)_(-?\d+)\.png$", re.IGNORECASE)
# --------------------------------------------------------------------------

Tile = Tuple[Tuple[int, int], np.ndarray, str]


def discover_tiles(image_dir: str) -> Tuple[List[Tile], int, int, int, int]:
    files = [os.path.basename(p) for p in glob.glob(os.path.join(image_dir, "*.png"))]
    tiles: List[Tile] = []
    for fname in files:
        m = FILENAME_RE.match(fname)
        if not m:
            continue
        px, py = int(m.group(1)), int(m.group(2))
        path = os.path.join(image_dir, fname)
        img = cv2.imread(path, cv2.IMREAD_COLOR)
        if img is None:
            print(f"Warning: failed to read {path}")
            continue
        tiles.append(((px, py), img, fname))

    if not tiles:
        raise SystemExit("No images found matching pattern img_{px}_{py}.png in the specified directory.")

    # Ensure all tiles have identical size
    h0, w0 = tiles[0][1].shape[:2]
    for (_px, _py), im, fname in tiles:
        if im.shape[:2] != (h0, w0):
            raise SystemExit(
                f"All tiles must be the same size. {fname} is {im.shape[1]}x{im.shape[0]}, expected {w0}x{h0}."
            )

    # Sort tiles for deterministic layering (top->bottom, left->right)
    tiles.sort(key=lambda t: (t[0][1], t[0][0]))  # by (py, px)

    xs = [t[0][0] for t in tiles]
    ys = [t[0][1] for t in tiles]
    return tiles, w0, h0, min(xs), min(ys)


def compute_positions(tiles: List[Tile], img_w: int, img_h: int,
                      step_x: int, step_y: int,
                      h_slope: int, v_slope: int,
                      min_px: int, min_py: int):
    """Compute integer top-left placement for every tile and the bounding box."""
    positions = []  # (x, y) per tile, same order as tiles
    min_x = 10**9
    min_y = 10**9
    max_x2 = -10**9
    max_y2 = -10**9

    for (px, py), _im, _fn in tiles:
        x = (px - min_px) * step_x + (py - min_py) * h_slope
        y = (py - min_py) * step_y + (px - min_px) * v_slope
        positions.append((int(x), int(y)))
        if x < min_x:
            min_x = x
        if y < min_y:
            min_y = y
        if x + img_w > max_x2:
            max_x2 = x + img_w
        if y + img_h > max_y2:
            max_y2 = y + img_h

    width = int(max(1, round(max_x2 - min_x)))
    height = int(max(1, round(max_y2 - min_y)))
    return positions, min_x, min_y, width, height


def build_canvas(tiles: List[Tile], img_w: int, img_h: int,
                 step_x: int, step_y: int,
                 h_slope: int, v_slope: int,
                 min_px: int, min_py: int,
                 draw_grid: bool):
    positions, min_x, min_y, width, height = compute_positions(
        tiles, img_w, img_h, step_x, step_y, h_slope, v_slope, min_px, min_py
    )

    # Offset positions so the minimum is at (0,0)
    off_x = int(round(-min_x))
    off_y = int(round(-min_y))

    canvas = np.zeros((height, width, 3), dtype=np.uint8)

    for (x, y), tile in zip(positions, tiles):
        (px, py), im, _fn = tile
        xi = int(x + off_x)
        yi = int(y + off_y)
        y2 = yi + img_h
        x2 = xi + img_w
        # Clip if necessary (shouldn't happen if bounds computed correctly)
        if xi < 0 or yi < 0:
            continue
        if y2 > canvas.shape[0] or x2 > canvas.shape[1]:
            continue
        canvas[yi:y2, xi:x2] = im
        if draw_grid:
            cv2.rectangle(canvas, (xi, yi), (x2 - 1, y2 - 1), (255, 255, 255), 1)

    return canvas


def main():
    tiles, img_w, img_h, min_px, min_py = discover_tiles(IMAGE_DIR)

    win = "Mosaic Viewer (spacing + slopes)"
    cv2.namedWindow(win, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(win, 1280, 800)

    def _noop(v):
        pass

    # Trackbars
    # steps default to ~70% of tile size (good starting point for ~30% overlap)
    sx_init = max(1, int(round(img_w * 0.70)))
    sy_init = max(1, int(round(img_h * 0.70)))

    cv2.createTrackbar("step_x", win, sx_init, max(1, img_w * 2), _noop)
    cv2.createTrackbar("step_y", win, sy_init, max(1, img_h * 2), _noop)

    # Slopes are signed; map 0..400 -> -200..+200 pixels per row/col
    cv2.createTrackbar("h_slope", win, 200, 400, _noop)  # horizontal drift per row
    cv2.createTrackbar("v_slope", win, 200, 400, _noop)  # vertical drift per column

    cv2.createTrackbar("grid", win, 1, 1, _noop)
    cv2.createTrackbar("scale%", win, 100, 400, _noop)

    prev = None
    cached_disp = None

    print(f"Loaded {len(tiles)} tiles; each {img_w}x{img_h} px")
    print("Use sliders. Press 's' to save, 'r' to reset slopes, 'q'/ESC to quit.")

    while True:
        step_x = max(1, cv2.getTrackbarPos("step_x", win))
        step_y = max(1, cv2.getTrackbarPos("step_y", win))
        h_slope = cv2.getTrackbarPos("h_slope", win) - 200
        v_slope = cv2.getTrackbarPos("v_slope", win) - 200
        grid_on = cv2.getTrackbarPos("grid", win) == 1
        scale = max(10, cv2.getTrackbarPos("scale%", win))

        state = (step_x, step_y, h_slope, v_slope, grid_on, scale)
        if state != prev:
            mosaic = build_canvas(
                tiles, img_w, img_h,
                step_x, step_y,
                h_slope, v_slope,
                min_px, min_py,
                draw_grid=grid_on,
            )

            disp = mosaic
            if scale != 100:
                fx = fy = scale / 100.0
                disp = cv2.resize(mosaic, None, fx=fx, fy=fy, interpolation=cv2.INTER_NEAREST)

            # HUD overlay
            hud = disp.copy()
            txt1 = f"tiles={len(tiles)}  step_x={step_x}px  step_y={step_y}px  scale={scale}%"
            txt2 = f"h_slope={h_slope}px/row  v_slope={v_slope}px/col"
            cv2.putText(hud, txt1, (10, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)
            cv2.putText(hud, txt2, (10, 52), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)

            cv2.imshow(win, hud)
            cached_disp = mosaic
            prev = state

        k = cv2.waitKey(30) & 0xFF
        if k in (27, ord('q')):
            break
        if k == ord('s') and cached_disp is not None:
            out_path = "mosaic_preview.png"
            cv2.imwrite(out_path, cached_disp)
            print(f"Saved {out_path}")
        if k == ord('r'):
            cv2.setTrackbarPos("h_slope", win, 200)
            cv2.setTrackbarPos("v_slope", win, 200)

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
