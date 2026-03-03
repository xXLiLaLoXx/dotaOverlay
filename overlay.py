"""
Dota 2 Overlay — GSI + WebSocket + PyQt6
─────────────────────────────────────────
Uses PyQt6 (built-in Chromium, no .NET/pythonnet needed)
  Port 8765 → serves overlay HTML/CSS/JS files
  Port 3000 → receives Dota 2 GSI JSON
  Port 3001 → WebSocket pushes clock to overlay
"""

import os
import sys
import json
import asyncio
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler, SimpleHTTPRequestHandler

# ── Config ───────────────────────────────────────────────────────────────────
BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
OVERLAY_FILE = os.path.join(BASE_DIR, "overlay_content", "overlay.html")
STATIC_PORT  = 8765
GSI_PORT     = 3000
WS_PORT      = 3001
WINDOW_W      = 640
WINDOW_H      = 300
WINDOW_X      = 40
WINDOW_Y      = 40
ALWAYS_ON_TOP = True
# ─────────────────────────────────────────────────────────────────────────────

game_state = {
    "clock_time": -90,
    "game_state": "DOTA_GAMERULES_STATE_WAIT_FOR_PLAYERS_TO_LOAD",
    "connected":  False,
}
ws_clients = set()


# ── 1. Static file server ─────────────────────────────────────────────────────
class StaticHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=os.path.join(BASE_DIR, "overlay_content"), **kwargs)
    def log_message(self, *a): pass

def start_static_server():
    srv = HTTPServer(("127.0.0.1", STATIC_PORT), StaticHandler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    print(f"  📂  Static server  → http://127.0.0.1:{STATIC_PORT}")


# ── 2. GSI receiver ───────────────────────────────────────────────────────────
class GSIHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body   = self.rfile.read(length)
        self.send_response(200)
        self.end_headers()
        try:
            data  = json.loads(body)
            clock = (data.get("map") or {}).get("clock_time")
            state = (data.get("map") or {}).get("game_state", "")
            if clock is not None:
                game_state["clock_time"] = int(clock)
                game_state["game_state"] = state
                game_state["connected"]  = True
        except Exception as e:
            print(f"  ⚠  GSI parse error: {e}")

    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, *a): pass

def start_gsi_server():
    srv = HTTPServer(("127.0.0.1", GSI_PORT), GSIHandler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    print(f"  🎮  GSI receiver   → http://127.0.0.1:{GSI_PORT}")


# ── 3. WebSocket server ───────────────────────────────────────────────────────
async def ws_handler(websocket):
    ws_clients.add(websocket)
    try:
        # Listen for any incoming messages (commands from main.py)
        async for message in websocket:
            try:
                data = json.loads(message)
                cmd  = data.get("command")
                if cmd:
                    # Broadcast command to all OTHER connected overlays
                    dead = set()
                    for client in list(ws_clients):
                        if client is websocket:
                            continue  # don't echo back to sender
                        try:
                            await client.send(json.dumps({"command": cmd}))
                        except Exception:
                            dead.add(client)
                    ws_clients.difference_update(dead)
            except Exception:
                pass
    finally:
        ws_clients.discard(websocket)

async def ws_broadcast_loop():
    while True:
        await asyncio.sleep(0.5)
        if not ws_clients:
            continue
        msg  = json.dumps(game_state)
        dead = set()
        for ws in list(ws_clients):
            try:
                await ws.send(msg)
            except Exception:
                dead.add(ws)
        ws_clients.difference_update(dead)

async def ws_main():
    import websockets
    async with websockets.serve(ws_handler, "127.0.0.1", WS_PORT):
        print(f"  📡  WebSocket      → ws://127.0.0.1:{WS_PORT}")
        await ws_broadcast_loop()

def start_ws_server():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(ws_main())


# ── 4. GSI config writer ──────────────────────────────────────────────────────
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")

def get_all_drives():
    """Return list of all available drive letters on Windows."""
    drives = []
    try:
        import string
        from ctypes import windll
        bitmask = windll.kernel32.GetLogicalDrives()
        for letter in string.ascii_uppercase:
            if bitmask & 1:
                drives.append(f"{letter}:\\")
            bitmask >>= 1
    except Exception:
        drives = ["C:\\", "D:\\", "E:\\", "F:\\"]
    return drives

def find_steam_path():
    """Search everywhere for Steam installation."""
    candidates = []

    if sys.platform == "win32":
        # 1. Registry — most reliable
        import winreg
        for reg_path in [
            r"SOFTWARE\WOW6432Node\Valve\Steam",
            r"SOFTWARE\Valve\Steam",
        ]:
            for hive in [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]:
                try:
                    key = winreg.OpenKey(hive, reg_path)
                    path = winreg.QueryValueEx(key, "InstallPath")[0]
                    candidates.append(path)
                except Exception:
                    pass

        # 2. Common install locations on ALL drives
        drives = get_all_drives()
        for drive in drives:
            candidates += [
                os.path.join(drive, "Steam"),
                os.path.join(drive, "Program Files", "Steam"),
                os.path.join(drive, "Program Files (x86)", "Steam"),
                os.path.join(drive, "Games", "Steam"),
                os.path.join(drive, "SteamLibrary"),
            ]

        # 3. User profile
        candidates += [
            os.path.expanduser(r"~\Steam"),
            os.path.expanduser(r"~\AppData\Local\Steam"),
        ]

        # 4. Steam library folders from libraryfolders.vdf
        for candidate in list(candidates):
            vdf = os.path.join(candidate, "steamapps", "libraryfolders.vdf")
            if os.path.isfile(vdf):
                try:
                    with open(vdf, encoding="utf-8", errors="ignore") as f:
                        for line in f:
                            line = line.strip()
                            if '"path"' in line.lower():
                                parts = line.split('"')
                                if len(parts) >= 4:
                                    candidates.append(parts[3])
                except Exception:
                    pass

    # Check which candidates actually have Dota 2
    for steam in candidates:
        gsi_dir = os.path.join(steam, "steamapps", "common",
                               "dota 2 beta", "game", "dota",
                               "cfg", "gamestate_integration")
        if os.path.isdir(gsi_dir):
            return steam, gsi_dir

    return None, None


def write_gsi_cfg():
    cfg_content = (
        '"dota2-overlay"\n{\n'
        f'    "uri"       "http://127.0.0.1:{GSI_PORT}/"\n'
        '    "timeout"   "5.0"\n    "heartbeat" "2.0"\n'
        '    "buffer"    "0.1"\n    "throttle"  "0.1"\n'
        '    "data"\n    {\n        "map"   "1"\n    }\n}\n'
    )

    # Check if we already have a saved Steam path in config
    saved_steam = None
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE) as f:
                saved_steam = json.load(f).get("steam_path")
        except Exception:
            pass

    # Try saved path first, then auto-detect
    steam_path, gsi_dir = None, None

    if saved_steam:
        candidate_gsi = os.path.join(saved_steam, "steamapps", "common",
                                     "dota 2 beta", "game", "dota",
                                     "cfg", "gamestate_integration")
        if os.path.isdir(candidate_gsi):
            steam_path, gsi_dir = saved_steam, candidate_gsi

    if not gsi_dir:
        steam_path, gsi_dir = find_steam_path()

    if gsi_dir:
        # Create folder if needed
        os.makedirs(gsi_dir, exist_ok=True)
        cfg_path = os.path.join(gsi_dir, "gamestate_integration_overlay.cfg")
        try:
            with open(cfg_path, "w") as f:
                f.write(cfg_content)
            print(f"  ✅  GSI cfg written → {cfg_path}")

            # Save the found Steam path to config so we don't search again
            if os.path.exists(CONFIG_FILE):
                try:
                    with open(CONFIG_FILE) as f:
                        config_data = json.load(f)
                    config_data["steam_path"] = steam_path
                    with open(CONFIG_FILE, "w") as f:
                        json.dump(config_data, f, indent=2)
                except Exception:
                    pass
            return
        except Exception as e:
            print(f"  ⚠  Could not write GSI cfg: {e}")

    # Nothing worked — write fallback and show clear instructions
    fallback = os.path.join(BASE_DIR, "gamestate_integration_overlay.cfg")
    with open(fallback, "w") as f:
        f.write(cfg_content)

    print(f"\n  ⚠  Could not find Dota 2 automatically.")
    print(f"  👉  Where is Steam installed? (e.g. D:\\Steam or E:\\Games\\Steam)")
    print(f"      Leave empty to copy manually.\n")

    try:
        user_path = input("  Steam path: ").strip().strip('"')
        if user_path:
            gsi_dir = os.path.join(user_path, "steamapps", "common",
                                   "dota 2 beta", "game", "dota",
                                   "cfg", "gamestate_integration")
            os.makedirs(gsi_dir, exist_ok=True)
            cfg_path = os.path.join(gsi_dir, "gamestate_integration_overlay.cfg")
            with open(cfg_path, "w") as f:
                f.write(cfg_content)
            print(f"  ✅  GSI cfg written → {cfg_path}")

            # Save to config
            if os.path.exists(CONFIG_FILE):
                try:
                    with open(CONFIG_FILE) as f:
                        config_data = json.load(f)
                    config_data["steam_path"] = user_path
                    with open(CONFIG_FILE, "w") as f:
                        json.dump(config_data, f, indent=2)
                    print(f"  ✅  Steam path saved to config.json")
                except Exception:
                    pass
        else:
            print(f"\n  Copy manually:")
            print(f"    FROM: {fallback}")
            print(f"    TO:   <Steam>\\steamapps\\common\\dota 2 beta\\game\\dota\\cfg\\gamestate_integration\\\n")
    except (KeyboardInterrupt, EOFError):
        print(f"\n  Copy manually:")
        print(f"    FROM: {fallback}")
        print(f"    TO:   <Steam>\\steamapps\\common\\dota 2 beta\\game\\dota\\cfg\\gamestate_integration\\\n")


# ── 5. File watcher ───────────────────────────────────────────────────────────
class FileWatcher:
    def __init__(self, path, on_change):
        self.path      = path
        self.on_change = on_change
        self._mtime    = self._get()

    def _get(self):
        try:    return os.path.getmtime(self.path)
        except: return 0

    def watch(self):
        while True:
            time.sleep(0.6)
            m = self._get()
            if m != self._mtime:
                self._mtime = m
                print("🔄  overlay.html changed — reloading...")
                self.on_change()


# ── 6. PyQt6 Window ───────────────────────────────────────────────────────────
def run_qt_window():
    from PyQt6.QtWidgets  import QApplication, QMainWindow
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    from PyQt6.QtWebEngineCore    import QWebEngineSettings
    from PyQt6.QtCore    import Qt, QUrl, QTimer, pyqtSignal, QObject
    from PyQt6.QtGui     import QColor

    os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS",
        "--disable-gpu-compositing --disable-software-rasterizer "
        "--log-level=3 --disable-logging"
    )

    app = QApplication(sys.argv)
    app.setApplicationName("Dota 2 Overlay")

    # ── Signal bridge: lets background threads talk to Qt main thread ──────────
    class Bridge(QObject):
        command_received = pyqtSignal(str)   # emitted from any thread

    bridge = Bridge()

    class OverlayWindow(QMainWindow):
        def __init__(self):
            super().__init__()

            self._visible  = True
            self._opacity  = 50          # current opacity %
            self._drag_pos = None

            self.setWindowFlags(
                Qt.WindowType.FramelessWindowHint   |
                Qt.WindowType.WindowStaysOnTopHint  |
                Qt.WindowType.Tool                   # hides from taskbar
            )
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            self.setGeometry(WINDOW_X, WINDOW_Y, WINDOW_W, WINDOW_H)

            self.view = QWebEngineView(self)
            self.view.setGeometry(0, 0, WINDOW_W, WINDOW_H)
            self.view.page().setBackgroundColor(QColor(0, 0, 0, 0))

            s = self.view.page().settings()
            s.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
            s.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
            s.setAttribute(QWebEngineSettings.WebAttribute.PlaybackRequiresUserGesture, False)
            s.setAttribute(QWebEngineSettings.WebAttribute.AllowRunningInsecureContent, True)

            self.load_overlay()

            # File watcher hot-reload
            self.watcher = FileWatcher(OVERLAY_FILE, self.reload)
            threading.Thread(target=self.watcher.watch, daemon=True).start()

            # Connect signal from bridge → handle_command (runs on Qt thread)
            bridge.command_received.connect(self.handle_command)

        # ── Load / reload ──────────────────────────────────────────────────────
        def load_overlay(self):
            self.view.setUrl(QUrl(f"http://127.0.0.1:{STATIC_PORT}/overlay.html"))
            # After page loads, force-resume AudioContext via Qt
            self.view.loadFinished.connect(self._on_load_finished)

        def _on_load_finished(self, ok):
            # Inject JS to unlock AudioContext — Qt won't block this
            self.view.page().runJavaScript("""
                (function() {
                    var ctx = new (window.AudioContext || window.webkitAudioContext)();
                    ctx.resume().then(function() {
                        window._ac = ctx;
                        console.log('AudioContext unlocked by Qt injection');
                    });
                })();
            """)

        def reload(self):
            QTimer.singleShot(0, self.load_overlay)

        # ── Command handler (always runs on Qt main thread via signal) ─────────
        def handle_command(self, cmd):
            if cmd == "toggle":
                self.set_visible(not self._visible)

            elif cmd == "show":
                self.set_visible(True)

            elif cmd == "hide":
                self.set_visible(False)

            elif cmd == "opacity:toggle":
                self.set_opacity(50 if self._opacity >= 90 else 100)

            elif cmd == "opacity:100":
                self.set_opacity(100)

            elif cmd == "opacity:50":
                self.set_opacity(50)

            elif cmd.startswith("opacity:"):
                try:
                    n = int(cmd.split(":")[1])
                    self.set_opacity(max(0, min(100, n)))
                except ValueError:
                    pass

        def set_visible(self, visible: bool):
            self._visible = visible
            if visible:
                # Restore normal interactive window
                self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
                self.setWindowOpacity(self._opacity / 100)
            else:
                # Make completely invisible AND click-through
                # so mouse events pass straight to Dota 2
                self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
                self.setWindowOpacity(0.0)

        def set_opacity(self, pct: int):
            self._opacity = pct
            if self._visible:
                self.setWindowOpacity(pct / 100)
            # Also tell the HTML so its internal opacity var stays in sync
            self.view.page().runJavaScript(
                f"if(typeof setOpacity==='function') setOpacity({pct});"
            )

        # ── Drag to move ───────────────────────────────────────────────────────
        def mousePressEvent(self, event):
            if event.button() == Qt.MouseButton.LeftButton:
                self._drag_pos = (event.globalPosition().toPoint()
                                  - self.frameGeometry().topLeft())

        def mouseMoveEvent(self, event):
            if self._drag_pos and event.buttons() == Qt.MouseButton.LeftButton:
                self.move(event.globalPosition().toPoint() - self._drag_pos)

        def mouseReleaseEvent(self, event):
            self._drag_pos = None

    window = OverlayWindow()
    window.show()

    # ── Background thread: listen for WS commands and emit signal ─────────────
    def ws_command_listener():
        """Separate WS client that listens for commands sent to the overlay."""
        import asyncio
        try:
            import websockets as _ws
        except ImportError:
            return

        async def _listen():
            while True:
                try:
                    async with _ws.connect(f"ws://127.0.0.1:{WS_PORT}",
                                           open_timeout=3) as ws:
                        print("  🎮  Command listener connected")
                        async for msg in ws:
                            try:
                                data = json.loads(msg)
                                cmd  = data.get("command")
                                if cmd:
                                    # Emit signal → Qt main thread handles it
                                    bridge.command_received.emit(cmd)
                            except Exception:
                                pass
                except Exception:
                    await asyncio.sleep(2)   # reconnect

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(_listen())

    threading.Thread(target=ws_command_listener, daemon=True).start()

    print(f"  🪟  Overlay window opened")
    print("=" * 55)

    sys.exit(app.exec())


# ── 7. Main ───────────────────────────────────────────────────────────────────
def main():
    print("=" * 55)
    print("  🎮  Dota 2 Overlay")
    print("=" * 55)

    write_gsi_cfg()
    start_static_server()
    start_gsi_server()
    threading.Thread(target=start_ws_server, daemon=True).start()
    time.sleep(0.5)

    if not os.path.exists(OVERLAY_FILE):
        print(f"❌  overlay.html not found at: {OVERLAY_FILE}")
        sys.exit(1)

    print(f"  ✅  overlay.html found")

    # Check PyQt6
    try:
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtWebEngineWidgets import QWebEngineView
    except ImportError:
        print("\n❌  PyQt6 not installed. Run:")
        print("    pip install PyQt6 PyQt6-WebEngine\n")
        sys.exit(1)

    run_qt_window()


if __name__ == "__main__":
    main()