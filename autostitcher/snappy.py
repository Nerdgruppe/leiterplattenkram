import time
import math
from pathlib import Path

import serial
import cv2
import pygame
import pygame.camera

# TOP LEFT
# >>> M114
# SENDING:M114
# X:88.00 Y:109.00 Z:51.50 E:0.00 Count X:7040 Y:8720 Z:20600

IMG_STORE = Path("/home/felix/projects/experiments/wtf-leiterplattenkram/stitch_store")

# Boundary:
# Top Left: X:87.30 Y:109.90 Z:51.50 E:0.00 Count X:6984 Y:8792 Z:20600
# Bottom Right: X:166.30 Y:85.90 Z:51.50 E:0.00 Count X:13304 Y:6872 Z:20600

pcb_left = 87.30
pcb_right = 166.30

pcb_top = 109.90
pcb_bottom = 85.90


# "horizontal"
# Border at right: X:83.70 Y:105.90 Z:51.50 E:0.00 Count X:6696 Y:8472 Z:20600
# Border at left: X:91.30 Y:105.90 Z:51.50 E:0.00 Count X:7304 Y:8472 Z:20600
delta_x = 91.30 - 83.70

# "vertical"
# Border at bottom: X:91.90 Y:111.70 Z:51.50 E:0.00 Count X:7352 Y:8936 Z:20600
# border at top: X:91.90 Y:105.90 Z:51.50 E:0.00 Count X:7352 Y:8472 Z:20600
delta_y = 111.70 - 105.90

overlap = 0.7  # 30% overlap

width = max(pcb_left, pcb_right) - min(pcb_left, pcb_right)
height = max(pcb_top, pcb_bottom) - min(pcb_top, pcb_bottom)

steps_x = int(math.ceil(width / (delta_x * overlap)))
steps_y = int(math.ceil(height / (delta_y * overlap)))

print(width, height)
print(delta_x, delta_y)
print(steps_x, steps_y)


def slerp(low: float, high: float, f: float) -> float:
    return low + (high - low) * f


print(slerp(pcb_top, pcb_bottom, 0.0))
print(slerp(pcb_top, pcb_bottom, 0.5))
print(slerp(pcb_top, pcb_bottom, 1.0))

def fmt_val(x: int |float) -> str:
    if isinstance(x, int):
        return str(x)
    elif isinstance(x, float):
        return f"{x:.1f}"
    else:
        assert False 

class Motion:
    port: serial.Serial
    x: float
    y: float
    z: float 

    def __init__(self, port: str) -> None:
        self.port = serial.Serial(port, 115200)
        self.x = 100
        self.y = 100

    def __enter__(self):
        return self

    def __exit__(self, *argv) -> None:
        self.port.close()

    def move_to(self, x: float, y: float, speed: int = 3000) -> None:
        self.execute_g1(x = x,y=y,F=speed)
        self.x = x
        self.y = y

    def move(self, dx: float, dy: float, speed: int = 3000) -> None:
        self.move_to(self.x + dx, self.y + dy, speed)

    def set_z(self, z: float) -> None:
        self.execute_g1(z=z)
        self.z = z 

    def rel_z(self, dz: float) -> None:
        self.set_z(z=self.z + dz)

    def home(self):
        self.move_to(100, 100)

    def execute_g1(self, **kwargs) -> None:

        cmd = "G1 " + " ".join(f"{key.upper()}{fmt_val(value)}" for key, value in  kwargs.items() ) + "\r\n"

        print(f"> {cmd!r}")
        self.port.write(cmd.encode())
        self.port.flush()


def main() -> None:
    pygame.camera.init()
    cams = pygame.camera.list_cameras()
    if len(cams) == 0:
        print("no cameras")
        return

    cam = pygame.camera.Camera("/dev/video1", (640, 480))
    try:
        cam.start()
        with Motion("/dev/ttyUSB0") as motion:
            print("Homing...")
            motion.move_to(pcb_left, pcb_top)
            time.sleep(5.0)  # center

            for dy in range(steps_y + 1):
                is_even_row = (dy % 2) == 0
                for dx in range(steps_x + 1):
                    fx = dx / steps_x
                    fy = dy / steps_y

                    px = dx
                    py = dy
                    if not is_even_row:
                        # we move in a snake pattern instead of "scanlines",
                        # as it's much faster and requires less movement
                        fx = 1 - fx
                        px = steps_x - px

                    print(f"Move to ({px},{py})...")
                    motion.move_to(
                        slerp(pcb_left, pcb_right, fx),
                        slerp(pcb_top, pcb_bottom, fy),
                    )

                    # Capture one frame
                    img_path = IMG_STORE / f"img_{px}_{py}.png"
                    print(f"Capture ({px},{py})...")

                    # let the camera settle and reduce jitter
                    start = time.monotonic()
                    img = None
                    while time.monotonic() < start + 1.5:
                        img = cam.get_image()
                    assert img is not None

                    pygame.image.save(img, img_path)

                    print()
    finally:
        cam.stop()


if __name__ == "__main__":
    main()
