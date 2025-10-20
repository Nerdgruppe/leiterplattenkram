#!/usr/bin/env python3
"""
Mosaic Viewer — spacing + slopes + global alpha + global rotation
+ Einzel-Export pro Kachel (für enblend/enfuse)
+ **Bugfix**: AxisError bei der Normalisierung behoben

Wichtigster Fix:
  • Die Vorschau-Normalisierung ist jetzt robust:
        out = (acc / max(wsum, eps))  mit Broadcast
    und die Zuweisung auf gültige Pixel erfolgt mit einem 2D-Boolean-Masken-Index,
    um den früheren AxisError zu vermeiden.
  • Das Grid wird **nach** der Normalisierung gezeichnet (auf "out"),
    damit keine Artefakte durch Division entstehen.

Steuerung/Export wie gehabt:
  step_x, step_y, h_slope, v_slope, alpha%, rot(°x0.1), grid, scale%
  fmt (PNG/TIFF), depth16 (8/16-bit)
  Tasten: s (Preview speichern), e/x (Einzel-Export), r/t/a, q/ESC

Abhängigkeiten:  pip install opencv-python numpy
"""

import os
import re
import glob
import cv2
import numpy as np
import argparse
from typing import List, Tuple

# ---- Default-Konfiguration -----------------------------------------------
DEFAULT_IMAGE_DIR = "."
DEFAULT_EXPORT_DIR = os.environ.get("EXPORT_DIR", "export_layers")
FILENAME_RE = re.compile(r"^img_(-?\d+)_(-?\d+)\.png$", re.IGNORECASE)
# --------------------------------------------------------------------------

Tile = Tuple[Tuple[int, int], np.ndarray, str]

def parse_args():
    ap = argparse.ArgumentParser(description="Mosaic Viewer mit Einzel-Export (Bugfix)")
    ap.add_argument("--images", default=DEFAULT_IMAGE_DIR, help="Bildverzeichnis (Default: .)")
    ap.add_argument("--out", default=DEFAULT_EXPORT_DIR, help="Export-Verzeichnis (Default: export_layers oder $EXPORT_DIR)")
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

    # Einheitliche Größe erzwingen
    h0, w0 = tiles[0][1].shape[:2]
    for (_px, _py), im, fname in tiles:
        if im.shape[:2] != (h0, w0):
            raise SystemExit(
                f"Alle Kacheln müssen gleich groß sein. {fname} ist {im.shape[1]}x{im.shape[0]}, erwartet {w0}x{h0}."
            )

    tiles.sort(key=lambda t: (t[0][1], t[0][0]))  # stabil: nach (py, px)

    xs = [t[0][0] for t in tiles]
    ys = [t[0][1] for t in tiles]
    return tiles, w0, h0, min(xs), min(ys)


def rot_bbox_size(w: int, h: int, angle_deg: float):
    a = np.deg2rad(angle_deg)
    c, s = abs(np.cos(a)), abs(np.sin(a))
    new_w = int(round(w * c + h * s))
    new_h = int(round(w * s + h * c))
    return new_w, new_h


def rotation_matrix_for_expand(w: int, h: int, angle_deg: float):
    rot_w, rot_h = rot_bbox_size(w, h, angle_deg)
    M = cv2.getRotationMatrix2D((w / 2.0, h / 2.0), angle_deg, 1.0)
    # Translation so, dass das Zentrum in der neuen Leinwand mittig liegt
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
        if x0 < min_x:
            min_x = x0
        if y0 < min_y:
            min_y = y0
        if x0 + rot_w > max_x2:
            max_x2 = x0 + rot_w
        if y0 + rot_h > max_y2:
            max_y2 = y0 + rot_h
    width = int(max(1, round(max_x2 - min_x)))
    height = int(max(1, round(max_y2 - min_y)))
    return min_x, min_y, width, height


def build_preview(tiles: List[Tile], img_w: int, img_h: int,
                  step_x: int, step_y: int,
                  h_slope: int, v_slope: int,
                  min_px: int, min_py: int,
                  angle_deg: float,
                  alpha: float,
                  draw_grid: bool):
    centers = compute_centers(tiles, img_w, img_h, step_x, step_y, h_slope, v_slope, min_px, min_py)
    M, rot_w, rot_h = rotation_matrix_for_expand(img_w, img_h, angle_deg)
    min_x, min_y, width, height = layout_bounds(centers, rot_w, rot_h)

    acc = np.zeros((height, width, 3), dtype=np.float32)
    wsum = np.zeros((height, width, 1), dtype=np.float32)

    base_mask = np.full((img_h, img_w), 255, dtype=np.uint8)

    rects = []  # für Grid

    for (cx, cy), tile in zip(centers, tiles):
        (_px, _py), im, _fn = tile
        img_rot = cv2.warpAffine(im, M, (rot_w, rot_h), flags=cv2.INTER_LINEAR, borderValue=(0, 0, 0))
        m_rot = cv2.warpAffine(base_mask, M, (rot_w, rot_h), flags=cv2.INTER_NEAREST, borderValue=0)
        m = (m_rot.astype(np.float32) / 255.0)[..., None]

        x0 = int(round(cx - rot_w / 2.0 - min_x))
        y0 = int(round(cy - rot_h / 2.0 - min_y))
        y2 = y0 + rot_h
        x2 = x0 + rot_w

        tile_rgb = img_rot.astype(np.float32)
        a = alpha * m
        acc[y0:y2, x0:x2] += tile_rgb * a
        wsum[y0:y2, x0:x2] += a

        rects.append((x0, y0, x2, y2))

    # Robuste Normalisierung mit Broadcast — vermeidet AxisError
    eps = 1e-6
    norm = acc / np.maximum(wsum, eps)  # (H,W,3) / (H,W,1)

    out = np.zeros_like(acc, dtype=np.uint8)
    mask2d = (wsum[..., 0] > eps)
    out[mask2d] = np.clip(norm[mask2d], 0, 255).astype(np.uint8)

    if draw_grid:
        for (x0, y0, x2, y2) in rects:
            cv2.rectangle(out, (x0, y0), (min(x2 - 1, out.shape[1] - 1), min(y2 - 1, out.shape[0] - 1)), (255, 255, 255), 1)

    layout_info = (M, rot_w, rot_h, centers, min_x, min_y, width, height)
    return out, layout_info


def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


def export_layers(tiles: List[Tile], layout_info, export_dir: str, use_tiff: bool, depth16: bool):
    """Exportiert pro Kachel eine Datei in voller Canvasgröße, RGBA mit Alpha-Maske."""
    M, rot_w, rot_h, centers, min_x, min_y, width, height = layout_info
    ensure_dir(export_dir)

    with open(os.path.join(export_dir, "manifest.txt"), "w", encoding="utf-8") as f:
        f.write(f"canvas_width={width}\ncanvas_height={height}\nmin_x={min_x}\nmin_y={min_y}\n")

    base_mask = np.full((tiles[0][1].shape[0], tiles[0][1].shape[1]), 255, dtype=np.uint8)

    for idx, ((px, py), im, fname) in enumerate(tiles):
        img_rot = cv2.warpAffine(im, M, (rot_w, rot_h), flags=cv2.INTER_LINEAR, borderValue=(0, 0, 0))
        # leichte Kanten-Glättung für Alpha beim Export: INTER_LINEAR
        m_rot = cv2.warpAffine(base_mask, M, (rot_w, rot_h), flags=cv2.INTER_LINEAR, borderValue=0)

        if depth16:
            canvas = np.zeros((height, width, 4), dtype=np.uint16)
            img16 = (img_rot.astype(np.uint16) * 257)
            a16 = (m_rot.astype(np.uint16) * 257)
            cx, cy = centers[idx]
            x0 = int(round(cx - rot_w / 2.0 - min_x))
            y0 = int(round(cy - rot_h / 2.0 - min_y))
            canvas[y0:y0+rot_h, x0:x0+rot_w, 0:3] = img16  # BGR
            canvas[y0:y0+rot_h, x0:x0+rot_w, 3] = a16      # A
        else:
            canvas = np.zeros((height, width, 4), dtype=np.uint8)
            cx, cy = centers[idx]
            x0 = int(round(cx - rot_w / 2.0 - min_x))
            y0 = int(round(cy - rot_h / 2.0 - min_y))
            canvas[y0:y0+rot_h, x0:x0+rot_w, 0:3] = img_rot  # BGR
            canvas[y0:y0+rot_h, x0:x0+rot_w, 3] = m_rot      # A

        base = f"layer_{idx:04d}_px{px}_py{py}"
        ext = ".tif" if use_tiff else ".png"
        out_path = os.path.join(export_dir, base + ext)
        ok = cv2.imwrite(out_path, canvas)
        if not ok:
            print(f"Fehler beim Schreiben: {out_path}")
        else:
            print(f"geschrieben: {out_path}")


def main():
    args = parse_args()
    image_dir = args.images
    export_dir = args.out

    tiles, img_w, img_h, min_px, min_py = discover_tiles(image_dir)

    win = "Mosaic Viewer (Bugfix + Export)"
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
    cv2.createTrackbar("rot(°x0.1)", win, 300, 600, _noop)  # -30..+30°

    cv2.createTrackbar("grid", win, 0, 1, _noop)
    cv2.createTrackbar("scale%", win, 100, 400, _noop)

    cv2.createTrackbar("fmt", win, 1, 1, _noop)       # 0=PNG, 1=TIFF
    cv2.createTrackbar("depth16", win, 1, 1, _noop)   # 0=8-bit, 1=16-bit

    prev = None
    last_preview = None
    last_layout_info = None

    print(f"Geladen: {len(tiles)} Kacheln; Tilegröße = {img_w}x{img_h} px")
    print("'e' oder 'x' exportiert Einzeldateien nach:", export_dir)

    while True:
        step_x = max(1, cv2.getTrackbarPos("step_x", win))
        step_y = max(1, cv2.getTrackbarPos("step_y", win))
        h_slope = cv2.getTrackbarPos("h_slope", win) - 200
        v_slope = cv2.getTrackbarPos("v_slope", win) - 200
        alpha = cv2.getTrackbarPos("alpha%", win) / 100.0
        rot_tenths = cv2.getTrackbarPos("rot(°x0.1)", win)
        angle = (rot_tenths - 300) / 10.0
        grid_on = cv2.getTrackbarPos("grid", win) == 1
        scale = max(10, cv2.getTrackbarPos("scale%", win))

        state = (step_x, step_y, h_slope, v_slope, alpha, angle, grid_on, scale)
        if state != prev:
            preview, layout_info = build_preview(
                tiles, img_w, img_h,
                step_x, step_y,
                h_slope, v_slope,
                min_px, min_py,
                angle,
                alpha,
                draw_grid=grid_on,
            )

            disp = preview
            if scale != 100:
                fx = fy = scale / 100.0
                disp = cv2.resize(preview, None, fx=fx, fy=fy, interpolation=cv2.INTER_NEAREST)

            hud = disp.copy()
            txt1 = f"tiles={len(tiles)}  step_x={step_x}px  step_y={step_y}px  scale={scale}%"
            txt2 = f"h_slope={h_slope}px/row  v_slope={v_slope}px/col  alpha={int(alpha*100)}%  rot={angle:.1f}°"
            txt3 = f"export: fmt={'TIFF' if cv2.getTrackbarPos('fmt', win)==1 else 'PNG'}  depth={'16b' if cv2.getTrackbarPos('depth16', win)==1 else '8b'}"
            cv2.putText(hud, txt1, (10, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)
            cv2.putText(hud, txt2, (10, 52), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)
            cv2.putText(hud, txt3, (10, 78), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)

            cv2.imshow(win, hud)
            last_preview = preview
            last_layout_info = layout_info
            prev = state

        k = cv2.waitKey(15) & 0xFF
        if k in (27, ord('q')):
            break
        if k == ord('s') and last_preview is not None:
            out_path = "mosaic_preview.png"
            cv2.imwrite(out_path, last_preview)
            print(f"Gespeichert: {out_path}")
        if k == ord('r'):
            cv2.setTrackbarPos("h_slope", win, 200)
            cv2.setTrackbarPos("v_slope", win, 200)
        if k == ord('t'):
            cv2.setTrackbarPos("rot(°x0.1)", win, 300)
        if k == ord('a'):
            cv2.setTrackbarPos("alpha%", win, 50)
        if k in (ord('e'), ord('x')) and last_layout_info is not None:
            use_tiff = cv2.getTrackbarPos("fmt", win) == 1
            depth16 = cv2.getTrackbarPos("depth16", win) == 1
            print("Export starte… ->", export_dir)
            export_layers(tiles, last_layout_info, export_dir, use_tiff, depth16)
            print("Export fertig.")

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
