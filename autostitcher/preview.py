#!/usr/bin/env python3
"""
Planar Mosaic Viewer — grid preview with adjustable spacing

Loads images named like:  img_{px}_{py}.png  (e.g., img_0_0.png, img_15_6.png)
Shows a live window where you can adjust horizontal/vertical spacing between tiles
using sliders, so you can visually verify your grid and overlap.

Controls:
  - Trackbars:
      * step_x: horizontal step (pixels between image origins)
      * step_y: vertical step (pixels between image origins)
      * grid:   0/1 to toggle tile rectangles
      * scale%: display scale (does not affect saved output)
  - Keys:
      * q or ESC: quit
      * s:        save current mosaic view to mosaic_preview.png

Dependencies:  pip install opencv-python numpy

Note: This is a viewer/previewer — it pastes tiles directly without geometric warping.
If overlaps exist, later tiles simply overwrite earlier ones in those regions.
"""

import os
import re
import glob
import cv2
import numpy as np

# --- Configuration ---------------------------------------------------------
# Directory to scan ("." means current folder)
IMAGE_DIR = "/home/felix/projects/experiments/wtf-leiterplattenkram/stitch_store"
# Regex pattern for filenames. Capturing groups must be px, py in this order.
# Example matches: img_0_0.png, img_12_3.png, img_-1_2.png
FILENAME_RE = re.compile(r"^img_(-?\d+)_(-?\d+)\.png$", re.IGNORECASE)
# --------------------------------------------------------------------------


def discover_tiles(image_dir: str):
    files = [os.path.basename(p) for p in glob.glob(os.path.join(image_dir, "*.png"))]
    tiles = []  # list of ((px, py), image, filename)
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
    # Ensure all tiles same size
    h0, w0 = tiles[0][1].shape[:2]
    for (px, py), im, fname in tiles:
        if im.shape[:2] != (h0, w0):
            raise SystemExit(f"All tiles must have the same size. {fname} is {im.shape[1]}x{im.shape[0]}, expected {w0}x{h0}.")
    return tiles, w0, h0


def bounds_from_tiles(tiles):
    xs = [px for (px, py), _, _ in tiles]
    ys = [py for (px, py), _, _ in tiles]
    return min(xs), max(xs), min(ys), max(ys)


def build_canvas(tiles, img_w, img_h, step_x, step_y, min_px, min_py, max_px, max_py, draw_grid=False):
    # Compute canvas size
    width = (max_px - min_px) * step_x + img_w
    height = (max_py - min_py) * step_y + img_h
    if width <= 0 or height <= 0:
        width = max(img_w, 1)
        height = max(img_h, 1)
    canvas = np.zeros((height, width, 3), dtype=np.uint8)

    # Paste tiles
    for (px, py), im, _fname in tiles:
        x = (px - min_px) * step_x
        y = (py - min_py) * step_y
        y2 = y + img_h
        x2 = x + img_w
        # Safety in case of small steps
        if x < 0 or y < 0:
            continue
        if y2 > canvas.shape[0] or x2 > canvas.shape[1]:
            # Expand canvas if needed (rare if steps decrease beyond initial size)
            new_h = max(canvas.shape[0], y2)
            new_w = max(canvas.shape[1], x2)
            bigger = np.zeros((new_h, new_w, 3), dtype=np.uint8)
            bigger[: canvas.shape[0], : canvas.shape[1]] = canvas
            canvas = bigger
        canvas[y:y2, x:x2] = im
        if draw_grid:
            cv2.rectangle(canvas, (x, y), (x2 - 1, y2 - 1), (255, 255, 255), 1)
    return canvas


def main():
    tiles, img_w, img_h = discover_tiles(IMAGE_DIR)
    min_px, max_px, min_py, max_py = bounds_from_tiles(tiles)

    # Window + trackbars
    win = "Mosaic Viewer"
    cv2.namedWindow(win, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(win, 1280, 800)

    def _noop(v):
        pass

    # Trackbar maxima allow up to 2× tile size; you can adjust if needed
    cv2.createTrackbar("step_x", win, img_w, max(1, img_w * 2), _noop)
    cv2.createTrackbar("step_y", win, img_h, max(1, img_h * 2), _noop)
    cv2.createTrackbar("grid", win, 1, 1, _noop)
    cv2.createTrackbar("scale%", win, 100, 400, _noop)

    # If you expect ~30% overlap, initial steps ~ 70% of tile dims
    sx_init = max(1, int(round(img_w * 0.70)))
    sy_init = max(1, int(round(img_h * 0.70)))
    cv2.setTrackbarPos("step_x", win, sx_init)
    cv2.setTrackbarPos("step_y", win, sy_init)

    prev = (-1, -1, -1, -1)
    canvas = None

    print("Loaded", len(tiles), "tiles;", f"tile size = {img_w}x{img_h}")
    print("Use sliders to set step_x/step_y; press 's' to save, 'q' or ESC to quit.")

    while True:
        step_x = max(1, cv2.getTrackbarPos("step_x", win))
        step_y = max(1, cv2.getTrackbarPos("step_y", win))
        grid_on = cv2.getTrackbarPos("grid", win) == 1
        scale = max(10, cv2.getTrackbarPos("scale%", win))

        if (step_x, step_y, grid_on, scale) != prev:
            canvas = build_canvas(
                tiles, img_w, img_h, step_x, step_y, min_px, min_py, max_px, max_py, draw_grid=grid_on
            )
            disp = canvas
            if scale != 100:
                fx = fy = scale / 100.0
                disp = cv2.resize(canvas, None, fx=fx, fy=fy, interpolation=cv2.INTER_NEAREST)

            # HUD overlay
            hud = disp.copy()
            text = f"tiles: {len(tiles)} | step_x={step_x}px step_y={step_y}px | scale={scale}%"
            cv2.putText(hud, text, (10, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)
            cv2.imshow(win, hud)
            prev = (step_x, step_y, grid_on, scale)

        k = cv2.waitKey(50) & 0xFF
        if k in (27, ord('q')):
            break
        if k == ord('s') and canvas is not None:
            out_path = "mosaic_preview.png"
            cv2.imwrite(out_path, canvas)
            print(f"Saved {out_path}")

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
