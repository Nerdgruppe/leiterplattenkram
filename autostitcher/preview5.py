#!/usr/bin/env python3
"""
Mosaic Viewer — super‑flüssige Preview (OpenCV) + Offsets (x/y) + Export

Neu:
  • Zwei neue Slider **off_x** / **off_y** (signiert), um die gesamte
    Kachel‑Anordnung auf der Canvas zu verschieben. Damit kannst du links/oben
    zusätzlichen Rand schaffen ("weiter nach links").
  • Offsets wirken sowohl in der Preview als auch im Einzel‑Export (volle Canvas).

Vorhanden:
  • OpenCV‑Preview (Overwrite / Alpha‑Blend) + Rotations/Scale‑Caching
  • Export einzelner Layer als RGBA‑Canvas (TIFF/PNG, 8/16‑Bit) für enblend/enfuse

Steuerung (Trackbars):
  step_x, step_y        – Abstand zwischen Kachel‑Ursprüngen (px)
  h_slope, v_slope      – Drift (px/Zeile bzw. px/Spalte)
  alpha%                – Transparenz in Preview (0..100)
  rot(°x0.1)            – globale Rotation in Zehntelgrad (−30..+30°)
  mode                  – Preview‑Modus: 0=Overwrite (schnell), 1=Alpha‑Blend
  off_x, off_y          – globale Offsets (±2000 px) für die gesamte Anordnung
  grid                  – Kachelrahmen an/aus
  scale%                – Anzeige‑Skalierung (Preview)
  fmt, depth16          – Exportformat (PNG/TIFF) und Bit‑Tiefe (8/16)

Tasten:
  q/ESC  – beenden
  s      – Previewbild speichern (mosaic_preview.png)
  e/x    – Einzel‑Export nach EXPORT_DIR (oder --out Pfad)
  r      – Slopes auf 0
  t      – Rotation 0°
  a      – Alpha 50%

Beispiel enblend:
  enblend -o mosaic.tif export_layers/*.tif

Abhängigkeiten:
  pip install opencv-python numpy
"""

import os
import re
import glob
import cv2
import numpy as np
import argparse
from typing import List, Tuple

# ---- Defaults -------------------------------------------------------------
DEFAULT_IMAGE_DIR = "."
DEFAULT_EXPORT_DIR = os.environ.get("EXPORT_DIR", "export_layers")
FILENAME_RE = re.compile(r"^img_(-?\d+)_(-?\d+)\.png$", re.IGNORECASE)

Tile = Tuple[Tuple[int, int], np.ndarray, str]

# ---- I/O ------------------------------------------------------------------

def parse_args():
    ap = argparse.ArgumentParser(description="Fast OpenCV Mosaic Viewer mit Offsets")
    ap.add_argument("--images", default=DEFAULT_IMAGE_DIR, help="Bildverzeichnis (Default: .)")
    ap.add_argument("--out", default=DEFAULT_EXPORT_DIR, help="Export‑Verzeichnis (Default: export_layers oder $EXPORT_DIR)")
    return ap.parse_args()


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
            print(f"Warnung: Konnte {path} nicht lesen")
            continue
        tiles.append(((px, py), img, fname))

    if not tiles:
        raise SystemExit("Keine Dateien im Muster img_{px}_{py}.png gefunden.")

    h0, w0 = tiles[0][1].shape[:2]
    for (_px, _py), im, fname in tiles:
        if im.shape[:2] != (h0, w0):
            raise SystemExit(f"Alle Kacheln müssen gleich groß sein. {fname} ist {im.shape[1]}x{im.shape[0]}, erwartet {w0}x{h0}.")

    tiles.sort(key=lambda t: (t[0][1], t[0][0]))  # stabil: (py, px)

    xs = [t[0][0] for t in tiles]
    ys = [t[0][1] for t in tiles]
    return tiles, w0, h0, min(xs), min(ys)

# ---- Geometrie ------------------------------------------------------------

def rot_bbox_size(w: int, h: int, angle_deg: float):
    a = np.deg2rad(angle_deg)
    c, s = abs(np.cos(a)), abs(np.sin(a))
    return int(round(w * c + h * s)), int(round(w * s + h * c))


def rotation_matrix_for_expand(w: int, h: int, angle_deg: float):
    rot_w, rot_h = rot_bbox_size(w, h, angle_deg)
    M = cv2.getRotationMatrix2D((w / 2.0, h / 2.0), angle_deg, 1.0)
    M[0, 2] += (rot_w / 2.0) - (w / 2.0)
    M[1, 2] += (rot_h / 2.0) - (h / 2.0)
    return M, rot_w, rot_h


def compute_centers(tiles: List[Tile], img_w: int, img_h: int,
                    step_x: int, step_y: int,
                    h_slope: int, v_slope: int,
                    min_px: int, min_py: int):
    centers = []
    for (px, py), _im, _fn in tiles:
        cx = (px - min_px) * step_x + (py - min_py) * h_slope + img_w / 2.0
        cy = (py - min_py) * step_y + (px - min_px) * v_slope + img_h / 2.0
        centers.append((cx, cy))
    return centers


def layout_bounds(centers, rot_w, rot_h):
    min_x = 1e18
    min_y = 1e18
    max_x2 = -1e18
    max_y2 = -1e18
    for (cx, cy) in centers:
        x0 = int(np.floor(cx - rot_w / 2.0))
        y0 = int(np.floor(cy - rot_h / 2.0))
        if x0 < min_x: min_x = x0
        if y0 < min_y: min_y = y0
        if x0 + rot_w > max_x2: max_x2 = x0 + rot_w
        if y0 + rot_h > max_y2: max_y2 = y0 + rot_h
    return min_x, min_y, max_x2, max_y2

# ---- Caches ---------------------------------------------------------------
class Cache:
    def __init__(self):
        self.angle = None
        self.M = None
        self.rot_w = 0
        self.rot_h = 0
        self.rot_imgs = None   # List[np.ndarray]
        self.rot_mask = None   # np.ndarray (H,W), 8‑bit
        self.scale = None
        self.scaled_imgs = None
        self.scaled_mask = None

    def invalidate_angle(self):
        self.angle = None
        self.M = None
        self.rot_imgs = None
        self.rot_mask = None
        self.scaled_imgs = None
        self.scaled_mask = None

    def invalidate_scale(self):
        self.scale = None
        self.scaled_imgs = None
        self.scaled_mask = None

# ---- Preview Rendering (OpenCV‑only) -------------------------------------

def ensure_rotated_cache(cache: Cache, tiles: List[Tile], img_w: int, img_h: int, angle_deg: float):
    if cache.angle == angle_deg and cache.rot_imgs is not None:
        return
    cache.angle = angle_deg
    cache.M, cache.rot_w, cache.rot_h = rotation_matrix_for_expand(img_w, img_h, angle_deg)
    base_mask = np.full((img_h, img_w), 255, dtype=np.uint8)
    cache.rot_imgs = []
    for (_p, im, _fn) in tiles:
        img_rot = cv2.warpAffine(im, cache.M, (cache.rot_w, cache.rot_h), flags=cv2.INTER_LINEAR, borderValue=(0, 0, 0))
        cache.rot_imgs.append(img_rot)
    cache.rot_mask = cv2.warpAffine(base_mask, cache.M, (cache.rot_w, cache.rot_h), flags=cv2.INTER_NEAREST, borderValue=0)
    cache.invalidate_scale()


def ensure_scaled_cache(cache: Cache, scale: float):
    if abs((cache.scale or -1) - scale) < 1e-6 and cache.scaled_imgs is not None:
        return
    cache.scale = scale
    if scale == 1.0:
        cache.scaled_imgs = cache.rot_imgs
        cache.scaled_mask = cache.rot_mask
    else:
        w = max(1, int(round(cache.rot_w * scale)))
        h = max(1, int(round(cache.rot_h * scale)))
        cache.scaled_imgs = [cv2.resize(im, (w, h), interpolation=cv2.INTER_AREA) for im in cache.rot_imgs]
        cache.scaled_mask = cv2.resize(cache.rot_mask, (w, h), interpolation=cv2.INTER_NEAREST)


def render_preview_opencv(tiles: List[Tile], centers, left: int, top: int,
                          cache: Cache, scale: float, alpha: float,
                          mode: int, draw_grid: bool,
                          width: int, height: int):
    # Canvas in Anzeigegröße anlegen
    W = max(1, int(round(width * scale)))
    H = max(1, int(round(height * scale)))
    disp = np.zeros((H, W, 3), dtype=np.uint8)

    th, tw = cache.scaled_mask.shape[:2]

    # pro Tile rendern
    for idx, ((px, py), _orig, _fn) in enumerate(tiles):
        cx, cy = centers[idx]
        x0 = int(round((cx - cache.rot_w / 2.0 - left) * scale))
        y0 = int(round((cy - cache.rot_h / 2.0 - top) * scale))
        tile = cache.scaled_imgs[idx]
        mask = cache.scaled_mask

        # ROI clippen
        x_start = max(0, x0)
        y_start = max(0, y0)
        x_end = min(W, x0 + tw)
        y_end = min(H, y0 + th)
        if x_start >= x_end or y_start >= y_end:
            continue
        rx0 = x_start - x0
        ry0 = y_start - y0
        rw = x_end - x_start
        rh = y_end - y_start

        roi = disp[y_start:y_end, x_start:x_end]
        src = tile[ry0:ry0+rh, rx0:rx0+rw]
        msk = mask[ry0:ry0+rh, rx0:rx0+rw]

        if mode == 0:
            cv2.copyTo(src, msk, roi)
        else:
            blended = cv2.addWeighted(roi, 1.0 - alpha, src, alpha, 0.0)
            cv2.copyTo(blended, msk, roi)

        if draw_grid:
            # Grid‑Rechteck um die (ggf. geclippte) Tile‑BBox zeichnen
            gx0 = max(0, x0)
            gy0 = max(0, y0)
            gx1 = min(W - 1, x0 + tw - 1)
            gy1 = min(H - 1, y0 + th - 1)
            if gx0 < gx1 and gy0 < gy1:
                cv2.rectangle(disp, (gx0, gy0), (gx1, gy1), (255, 255, 255), 1)

    return disp

# ---- Export (Layer, volle Canvas) ----------------------------------------

def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


def export_layers(tiles: List[Tile], img_w: int, img_h: int,
                  step_x: int, step_y: int, h_slope: int, v_slope: int,
                  min_px: int, min_py: int, angle_deg: float,
                  off_x: int, off_y: int,
                  export_dir: str, use_tiff: bool, depth16: bool):
    # Rotations‑Cache für Export (volle Auflösung)
    M, rot_w, rot_h = rotation_matrix_for_expand(img_w, img_h, angle_deg)
    centers = compute_centers(tiles, img_w, img_h, step_x, step_y, h_slope, v_slope, min_px, min_py)
    min_x, min_y, max_x2, max_y2 = layout_bounds(centers, rot_w, rot_h)

    # Offsets auf die Canvas‑Grenzen anwenden (positiv = mehr Rand links/oben)
    left  = int(min_x - max(0, off_x))
    top   = int(min_y - max(0, off_y))
    right = int(max_x2 + max(0, -off_x))
    bottom= int(max_y2 + max(0, -off_y))
    width = max(1, right - left)
    height= max(1, bottom - top)

    ensure_dir(export_dir)
    with open(os.path.join(export_dir, "manifest.txt"), "w", encoding="utf-8") as f:
        f.write(f"canvas_width={width}\ncanvas_height={height}\nleft={left}\ntop={top}\noff_x={off_x}\noff_y={off_y}\n")

    base_mask = np.full((img_h, img_w), 255, dtype=np.uint8)

    for idx, ((px, py), im, fname) in enumerate(tiles):
        img_rot = cv2.warpAffine(im, M, (rot_w, rot_h), flags=cv2.INTER_LINEAR, borderValue=(0, 0, 0))
        m_rot = cv2.warpAffine(base_mask, M, (rot_w, rot_h), flags=cv2.INTER_LINEAR, borderValue=0)
        cx, cy = centers[idx]
        x0 = int(round(cx - rot_w / 2.0 - left))
        y0 = int(round(cy - rot_h / 2.0 - top))

        if depth16:
            canvas = np.zeros((height, width, 4), dtype=np.uint16)
            img16 = (img_rot.astype(np.uint16) * 257)
            a16   = (m_rot.astype(np.uint16) * 257)
            canvas[y0:y0+rot_h, x0:x0+rot_w, 0:3] = img16
            canvas[y0:y0+rot_h, x0:x0+rot_w, 3]   = a16
        else:
            canvas = np.zeros((height, width, 4), dtype=np.uint8)
            canvas[y0:y0+rot_h, x0:x0+rot_w, 0:3] = img_rot
            canvas[y0:y0+rot_h, x0:x0+rot_w, 3]   = m_rot

        base = f"layer_{idx:04d}_px{px}_py{py}"
        ext = ".tif" if use_tiff else ".png"
        out_path = os.path.join(export_dir, base + ext)
        ok = cv2.imwrite(out_path, canvas)
        if not ok:
            print(f"Fehler beim Schreiben: {out_path}")
        else:
            print(f"geschrieben: {out_path}")

# ---- Main Loop ------------------------------------------------------------

def main():
    args = parse_args()
    image_dir = args.images
    export_dir = args.out

    tiles, img_w, img_h, min_px, min_py = discover_tiles(image_dir)

    win = "Mosaic Viewer (fast OpenCV + Offsets)"
    cv2.namedWindow(win, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(win, 1280, 800)

    def _noop(v):
        pass

    # Startwerte
    sx_init = max(1, int(round(img_w * 0.70)))
    sy_init = max(1, int(round(img_h * 0.70)))

    cv2.createTrackbar("step_x", win, sx_init, max(1, img_w * 2), _noop)
    cv2.createTrackbar("step_y", win, sy_init, max(1, img_h * 2), _noop)

    cv2.createTrackbar("h_slope", win, 200, 400, _noop)  # -200..+200
    cv2.createTrackbar("v_slope", win, 200, 400, _noop)

    cv2.createTrackbar("alpha%", win, 50, 100, _noop)
    cv2.createTrackbar("rot(°x0.1)", win, 300, 600, _noop)

    cv2.createTrackbar("mode", win, 0, 1, _noop)         # 0=Overwrite, 1=Alpha‑Blend
    cv2.createTrackbar("grid", win, 0, 1, _noop)
    cv2.createTrackbar("scale%", win, 75, 300, _noop)    # 75% als guter Startwert

    # Offsets: 0..4000 -> -2000..+2000 px
    cv2.createTrackbar("off_x", win, 2000, 4000, _noop)
    cv2.createTrackbar("off_y", win, 2000, 4000, _noop)

    cv2.createTrackbar("fmt", win, 1, 1, _noop)          # 0=PNG, 1=TIFF
    cv2.createTrackbar("depth16", win, 1, 1, _noop)      # 0=8‑bit, 1=16‑bit

    cache = Cache()

    prev_state = None
    last_disp = None

    print(f"Geladen: {len(tiles)} Kacheln; Tilegröße = {img_w}x{img_h} px")
    print("Nutze 'off_x/off_y' für zusätzlichen Rand links/oben bzw. Verschiebung des Startpunkts.")

    while True:
        step_x = max(1, cv2.getTrackbarPos("step_x", win))
        step_y = max(1, cv2.getTrackbarPos("step_y", win))
        h_slope = cv2.getTrackbarPos("h_slope", win) - 200
        v_slope = cv2.getTrackbarPos("v_slope", win) - 200
        alpha = cv2.getTrackbarPos("alpha%", win) / 100.0
        angle = (cv2.getTrackbarPos("rot(°x0.1)", win) - 300) / 10.0
        mode = cv2.getTrackbarPos("mode", win)
        grid_on = cv2.getTrackbarPos("grid", win) == 1
        scale = max(10, cv2.getTrackbarPos("scale%", win)) / 100.0
        off_x = cv2.getTrackbarPos("off_x", win) - 2000
        off_y = cv2.getTrackbarPos("off_y", win) - 2000

        state = (step_x, step_y, h_slope, v_slope, alpha, angle, mode, grid_on, scale, off_x, off_y)
        if state != prev_state:
            # Caches aktualisieren
            ensure_rotated_cache(cache, tiles, img_w, img_h, angle)
            ensure_scaled_cache(cache, scale)

            centers = compute_centers(tiles, img_w, img_h, step_x, step_y, h_slope, v_slope, min_px, min_py)
            min_x, min_y, max_x2, max_y2 = layout_bounds(centers, cache.rot_w, cache.rot_h)

            # Offsets anwenden (positiv = mehr Rand links/oben)
            left  = int(min_x - max(0, off_x))
            top   = int(min_y - max(0, off_y))
            right = int(max_x2 + max(0, -off_x))
            bottom= int(max_y2 + max(0, -off_y))
            width = max(1, right - left)
            height= max(1, bottom - top)

            disp = render_preview_opencv(tiles, centers, left, top, cache, scale, alpha, mode, grid_on, width, height)

            # HUD
            hud = disp.copy()
            txt1 = f"tiles={len(tiles)}  step_x={step_x}px  step_y={step_y}px  scale={int(scale*100)}%  mode={'OW' if mode==0 else 'ALPHA'}"
            txt2 = f"h_slope={h_slope}px/row  v_slope={v_slope}px/col  alpha={int(alpha*100)}%  rot={angle:.1f}°"
            txt3 = f"off_x={off_x}px  off_y={off_y}px  canvas={width}x{height}"
            cv2.putText(hud, txt1, (10, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255,255,255), 2, cv2.LINE_AA)
            cv2.putText(hud, txt2, (10, 52), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255,255,255), 2, cv2.LINE_AA)
            cv2.putText(hud, txt3, (10, 78), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255,255,255), 2, cv2.LINE_AA)

            cv2.imshow(win, hud)
            last_disp = disp
            prev_state = state

        k = cv2.waitKey(10) & 0xFF
        if k in (27, ord('q')):
            break
        if k == ord('s') and last_disp is not None:
            cv2.imwrite("mosaic_preview.png", last_disp)
            print("Gespeichert: mosaic_preview.png")
        if k == ord('r'):
            cv2.setTrackbarPos("h_slope", win, 200)
            cv2.setTrackbarPos("v_slope", win, 200)
        if k == ord('t'):
            cv2.setTrackbarPos("rot(°x0.1)", win, 300)
        if k == ord('a'):
            cv2.setTrackbarPos("alpha%", win, 50)
        if k in (ord('e'), ord('x')):
            use_tiff = cv2.getTrackbarPos("fmt", win) == 1
            depth16 = cv2.getTrackbarPos("depth16", win) == 1
            print("Export starte… ->", export_dir)
            export_layers(tiles, img_w, img_h, step_x, step_y, h_slope, v_slope, min_px, min_py, angle, off_x, off_y, export_dir, use_tiff, depth16)
            print("Export fertig.")

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
