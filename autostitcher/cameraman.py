#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Webcam mit OpenCV:
- Zwei Trackbars: Fokus (0..255), Z-Distanz (0..200)
- Tastaturevents:
    Pfeiltasten -> prints: up / down / left / right
    h           -> print("h") und Hilfe-Overlay toggeln
    + / -       -> print("plus") / print("minus") und Z-Distanz feinjustieren
    SPACE       -> Schnappschuss speichern
    q / ESC     -> Beenden
Hinweis: Manuelle Fokuskontrolle funktioniert nur, wenn die Kamera CAP_PROP_FOCUS unterstützt.
"""

import cv2
from datetime import datetime
from pathlib import Path

from snappy import Motion

WIN = "Webcam"
TRACK_FOCUS = "Fokus"
TRACK_Z = "Z-Distanz"

FOCUS_MAX = 255  # viele UVC-Kameras nutzen 0..255
Z_MAX = 200  # rein logisch für deine Anwendung


def ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)


def put_multiline_text(img, lines, org=(10, 20), line_height=20):
    x, y = org
    for line in lines:
        cv2.putText(
            img,
            line,
            (x, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )
        y += line_height


def main():
    # Kamera öffnen (Standardgerät 0)
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Kamera konnte nicht geöffnet werden (Index 0).")
        return

    old_z = 60

    # Fenster & Trackbars
    cv2.namedWindow(WIN, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(WIN, 960, 540)
    cv2.createTrackbar(TRACK_FOCUS, WIN, 128, FOCUS_MAX, lambda v: None)
    cv2.createTrackbar(TRACK_Z, WIN, old_z, Z_MAX, lambda v: None)

    # Autofokus nach Möglichkeit deaktivieren, damit der Fokus-Slider greifen kann
    autofocus_disabled = False
    if hasattr(cv2, "CAP_PROP_AUTOFOCUS"):
        try:
            autofocus_disabled = cap.set(cv2.CAP_PROP_AUTOFOCUS, 0)
        except Exception:
            autofocus_disabled = False

    # Wird der Fokus von der Kamera unterstützt?
    focus_supported = hasattr(cv2, "CAP_PROP_FOCUS")
    last_focus_value = -1

    show_help = True
    snapshots_dir = Path("snapshots")
    ensure_dir(snapshots_dir)

    with Motion("/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0") as motion:
        motion.set_z(old_z)
        motion.home()

        print("Steuerung: Pfeiltasten, h, +, -, SPACE (Snapshot), q/ESC (Beenden)")

        while True:
            ok, frame = cap.read()
            if not ok:
                print("Kein Kamerabild empfangen.")
                break

            # Trackbar-Werte lesen
            focus_val = cv2.getTrackbarPos(TRACK_FOCUS, WIN)
            z_val = cv2.getTrackbarPos(TRACK_Z, WIN)

            # Fokus anwenden (nur wenn unterstützt & Wert geändert)
            if focus_supported and autofocus_disabled and focus_val != last_focus_value:
                try:
                    cap.set(cv2.CAP_PROP_FOCUS, float(focus_val))
                except Exception:
                    pass
                last_focus_value = focus_val

            # Overlay
            overlay_lines = [
                f"{TRACK_FOCUS}: {focus_val} {'(manuell aktiv)' if autofocus_disabled else '(AF evtl. aktiv)'}",
                f"{TRACK_Z}: {z_val}",
            ]
            if show_help:
                overlay_lines += [
                    "Tasten: Pfeile=Events | h=Hilfe an/aus | +=Z+1 | -=Z-1",
                    "SPACE=Snapshot | q/ESC=Beenden",
                ]
            put_multiline_text(frame, overlay_lines, org=(10, 20), line_height=22)

            cv2.imshow(WIN, frame)

            key = cv2.waitKey(1)
            if key == -1:
                continue

            # Beenden
            if key in (27, ord("q"), ord("Q")):  # ESC oder q
                break

            # Pfeiltasten -> Dummy-Prints
            if key == ord("w"):
                motion.move(0, +1)
            elif key == ord("a"):
                motion.move(-1, 0)
            elif key == ord("s"):
                motion.move(0, -1)
            elif key == ord("d"):
                motion.move(+1, 0)

            # h -> Hilfe-Overlay toggeln
            elif key in (ord("h"), ord("H")):
                motion.home()

            # + / - -> Dummy-Prints und Z-Distanz fein justieren
            elif key in (ord("+"), ord("=")):  # '=' oft auf derselben Taste wie '+'
                print("plus")
                new_z = min(Z_MAX, z_val + 1)
                if new_z != z_val:
                    cv2.setTrackbarPos(TRACK_Z, WIN, new_z)
            elif key in (ord("-"), ord("_")):
                print("minus")
                new_z = max(0, z_val - 1)
                if new_z != z_val:
                    cv2.setTrackbarPos(TRACK_Z, WIN, new_z)

            # SPACE -> Snapshot speichern
            elif key == 32:
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = snapshots_dir / f"snapshot_{ts}.png"
                # Achtung: 'frame' wurde bereits angezeigt – am besten nochmal lesen für geringstmögliche Latenz
                ok2, fresh = cap.read()
                img_to_save = fresh if ok2 else frame
                cv2.imwrite(str(filename), img_to_save)
                print(f"Snapshot gespeichert: {filename}")

            if z_val != old_z:
                motion.set_z(z_val)
                old_z = z_val

        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
