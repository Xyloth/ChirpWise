from __future__ import annotations

import socket
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.trainer_server import run


def runtime_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    return ROOT


def choose_port(preferred: int = 8765) -> int:
    for port in range(preferred, preferred + 25):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.25)
            if sock.connect_ex(("127.0.0.1", port)) != 0:
                return port
    raise RuntimeError("No free local port found")


def main() -> int:
    if server_is_alive(8765):
        webbrowser.open("http://127.0.0.1:8765")
        return 0
    port = choose_port()
    url = f"http://127.0.0.1:{port}"
    opener = threading.Thread(target=open_browser_later, args=(url,), daemon=True)
    opener.start()
    run("127.0.0.1", port, root_override=runtime_root())
    return 0


def open_browser_later(url: str) -> None:
    time.sleep(1.2)
    webbrowser.open(url)


def server_is_alive(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=0.8) as response:
            return response.status == 200
    except Exception:
        return False


if __name__ == "__main__":
    raise SystemExit(main())
