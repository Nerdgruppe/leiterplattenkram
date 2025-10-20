from dataclasses import dataclass
import logging
import json

import serial

from websocket_server import WebsocketServer

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

    home_x: float
    home_y: float

    def __init__(self, port: str) -> None:
        self.port = serial.Serial(port, 115200)
        self.home_x = 137
        self.home_y = 120
        self.x = self.home_x
        self.y = self.home_y
        self.z = 51.5

    def __enter__(self):
        return self

    def __exit__(self, *argv) -> None:
        self.port.close()

    def move_to(self, x: float, y: float, speed: int = 3000) -> None:
        self.execute_g1(x=x, y=y, F=speed)
        self.x = x
        self.y = y

    def move(self, dx: float, dy: float, speed: int = 3000) -> None:
        self.move_to(self.x + dx, self.y + dy, speed)

    def set_z(self, z: float) -> None:
        self.execute_g1(z=z, f=3000)
        self.z = z

    def rel_z(self, dz: float) -> None:
        self.set_z(z=self.z + dz)

    def home(self):
        self.move_to(self.home_x, self.home_y)

    def wait(self) -> None:
        self._execute("M400")

    def execute_g1(self, **kwargs) -> None:
        cmd = (
            "G1 "
            + " ".join(
                f"{key.upper()}{fmt_val(value)}" for key, value in kwargs.items()
            )
        )
        self._execute(cmd)

    def _execute(self, cmd: str) -> None:

        cmd += "\r\n"

        print(f"> {cmd!r}")
        self.port.write(cmd.encode())
        
        while True:

            line = self.port.readline()
            print(f"< {line!r}")

            if line.startswith(b"echo:"):
                continue 

            assert line == b"ok\n", f"unexpected response: {line!r}"
            return 

@dataclass
class Service:

    motion: Motion

    def send_update(self, server, client):

        server.send_message(
            client,
            json.dumps(
                {
                    "status": "ok",
                    "properties": [
                        {"key": "X", "value": self.motion.x},
                        {"key": "Y", "value": self.motion.y},
                        {"key": "Z", "value": self.motion.z},
                    ],
                }
            ),
        )

    # Called for every client connecting (after handshake)
    def on_new_client(self, client, server):
        print(f"[server] client #{client['id']} connected: {client['address']}")

        self.send_update(server, client)


    # Called for every client disconnecting
    def on_client_left(self, client, server):
        print(f"[server] client #{client['id']} disconnected")


    # Called when a client sends a message
    def on_message(self, client, server, message):
        msg = json.loads( message)

        if "rel-move" in msg:
            dest = msg["rel-move"]
            match dest:
                case "left":
                    self.motion.move(-1,0)
                case "right":
                    self.motion.move(+1,0)
                case "up":
                    self.motion.move(0,+1)
                case "down":
                    self.motion.move(0,-1)
        elif "action" in msg:
            dest = msg["action"]
            match dest:
                case "home":
                    self.motion.home()
                    self.motion.wait()
                case "z-up":
                    self.motion.rel_z(0.5)
                    self.motion.wait()
                case "z-down":
                    self.motion.rel_z(-0.5)
                    self.motion.wait()

        else:
            print(f"[server] got from #{client['id']}: {message!r}")

        self.send_update(server, client)

def main():  # Bind to localhost:8765
    logging.basicConfig(level=logging.INFO)

    motion = Motion("/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0")

    motion.set_z(51.5)
    motion.wait()
    motion.home()

    service = Service(motion)

    server = WebsocketServer(host="0.0.0.0", port=8765, loglevel=logging.INFO)
    server.set_fn_new_client(service.on_new_client)
    server.set_fn_client_left(service.on_client_left)
    server.set_fn_message_received(service.on_message)
    print("[server] listening on ws://127.0.0.1:8765")
    server.run_forever()


if __name__ == "__main__":
    main()
