"""
Dota 2 Overlay — Launcher (main.py)
════════════════════════════════════
Run this file to start the overlay.

Features:
  • Dependency checker & auto-installer
  • Settings manager (config.json)
  • System tray icon with controls
  • Global hotkeys (F9 toggle, F10 opacity)
  • First-run setup wizard
  • Auto-launch with Dota 2 (optional)
"""

import os
import sys
import json
import subprocess
import threading
import time

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
OVERLAY_PY  = os.path.join(BASE_DIR, "overlay.py")
WS_PORT     = 3001   # must match overlay.py

# ══════════════════════════════════════════════════════════════════════════════
#  DEFAULT CONFIG
# ══════════════════════════════════════════════════════════════════════════════
DEFAULT_CONFIG = {
    "window": {
        "x":             20,
        "y":             20,
        "width":         290,
        "height":        640,
        "opacity":       50,
        "always_on_top": True,
    },
    "hotkeys": {
        "toggle_overlay": "f9",
        "toggle_opacity":  "f10",
    },
    "auto_start_with_dota": False,
    "show_tray_icon":        True,
    "first_run":             True,
}

# ══════════════════════════════════════════════════════════════════════════════
#  CONSOLE COLORS
# ══════════════════════════════════════════════════════════════════════════════
class C:
    RESET  = "\033[0m";  BOLD   = "\033[1m";  DIM    = "\033[2m"
    RED    = "\033[91m"; GREEN  = "\033[92m";  YELLOW = "\033[93m"
    BLUE   = "\033[94m"; CYAN   = "\033[96m";  WHITE  = "\033[97m"

def ok(m):   print(f"  {C.GREEN}✔{C.RESET}  {m}")
def err(m):  print(f"  {C.RED}✘{C.RESET}  {m}")
def warn(m): print(f"  {C.YELLOW}⚠{C.RESET}  {m}")
def info(m): print(f"  {C.CYAN}●{C.RESET}  {m}")
def head(m): print(f"\n{C.BOLD}{C.WHITE}{m}{C.RESET}")

# ══════════════════════════════════════════════════════════════════════════════
#  CONFIG
# ══════════════════════════════════════════════════════════════════════════════
def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE) as f:
                saved = json.load(f)
            cfg = json.loads(json.dumps(DEFAULT_CONFIG))
            deep_merge(cfg, saved)
            return cfg
        except Exception as e:
            warn(f"Config error ({e}) — using defaults")
    return json.loads(json.dumps(DEFAULT_CONFIG))

def save_config(cfg):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)

def deep_merge(base, override):
    for k, v in override.items():
        if k in base and isinstance(base[k], dict) and isinstance(v, dict):
            deep_merge(base[k], v)
        else:
            base[k] = v

# ══════════════════════════════════════════════════════════════════════════════
#  DEPENDENCY CHECK
# ══════════════════════════════════════════════════════════════════════════════
REQUIRED = {"PyQt6": "PyQt6", "PyQt6.QtWebEngineWidgets": "PyQt6-WebEngine", "websockets": "websockets"}
OPTIONAL = {"pystray": "pystray", "PIL": "Pillow", "keyboard": "keyboard"}

def check_import(m):
    try: __import__(m); return True
    except ImportError: return False

def pip_install(pkg):
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", pkg, "-q"],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except: return False

def check_dependencies():
    head("  Checking dependencies...")
    all_ok = True
    for mod, pkg in REQUIRED.items():
        if check_import(mod): ok(pkg)
        else:
            warn(f"{pkg} missing — installing...")
            if pip_install(pkg): ok(f"{pkg} installed")
            else: err(f"Could not install {pkg}  →  pip install {pkg}"); all_ok = False
    for mod, pkg in OPTIONAL.items():
        if check_import(mod): ok(f"{pkg} {C.DIM}(optional){C.RESET}")
        else:
            if pip_install(pkg): ok(f"{pkg} installed")
            else: warn(f"{pkg} unavailable — some features disabled")
    return all_ok

# ══════════════════════════════════════════════════════════════════════════════
#  SEND COMMAND TO OVERLAY
#  Connects to the WS server that lives inside overlay.py and sends a command.
#  Waits up to 8 seconds for the server to be ready (overlay takes time to start).
# ══════════════════════════════════════════════════════════════════════════════
def send_ws_command(cmd, retries=8, delay=1.0):
    """Send a command to the overlay. Retries until the WS server is up."""
    def _run():
        import asyncio
        try:
            import websockets as _ws
        except ImportError:
            return

        async def _send():
            for attempt in range(retries):
                try:
                    async with _ws.connect(f"ws://127.0.0.1:{WS_PORT}",
                                           open_timeout=2) as ws:
                        await ws.send(json.dumps({"command": cmd}))
                        await asyncio.sleep(0.15)   # let server broadcast it
                        return  # success
                except Exception:
                    if attempt < retries - 1:
                        await asyncio.sleep(delay)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:    loop.run_until_complete(_send())
        finally: loop.close()

    threading.Thread(target=_run, daemon=True).start()

# ══════════════════════════════════════════════════════════════════════════════
#  GLOBAL HOTKEYS
#  Uses the `keyboard` library which works globally on Windows.
#  Must be set up AFTER the overlay process is launched so the WS server exists.
# ══════════════════════════════════════════════════════════════════════════════
def setup_hotkeys(config):
    try:
        import keyboard

        toggle_key  = config["hotkeys"].get("toggle_overlay", "f9").lower()
        opacity_key = config["hotkeys"].get("toggle_opacity",  "f10").lower()

        # suppress=True: prevent the keypress reaching other apps
        keyboard.add_hotkey(toggle_key,  lambda: send_ws_command("toggle"),          suppress=True)
        keyboard.add_hotkey(opacity_key, lambda: send_ws_command("opacity:toggle"),  suppress=True)

        ok(f"Hotkeys  {C.CYAN}{toggle_key.upper()}{C.RESET} toggle  |  "
           f"{C.CYAN}{opacity_key.upper()}{C.RESET} opacity")
        return True
    except ImportError:
        warn("keyboard module not found — hotkeys disabled")
    except Exception as e:
        warn(f"Hotkey setup failed: {e}")
    return False

# ══════════════════════════════════════════════════════════════════════════════
#  SYSTEM TRAY
# ══════════════════════════════════════════════════════════════════════════════
def build_tray_icon(config):
    try:
        import pystray
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return None

    # Draw icon
    size = 64
    img  = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d    = ImageDraw.Draw(img)
    d.ellipse([2, 2, 61, 61], fill=(15, 15, 15, 230))
    d.ellipse([2, 2, 61, 61], outline=(80, 180, 80, 255), width=3)
    d.ellipse([18, 18, 45, 45], fill=(80, 180, 80, 200))

    def on_toggle(*_):   send_ws_command("toggle")
    def on_op50(*_):     send_ws_command("opacity:50")
    def on_op100(*_):    send_ws_command("opacity:100")
    def on_settings(*_): open_settings_editor()
    def on_quit(*_):
        icon.stop()
        if overlay_process and overlay_process.poll() is None:
            overlay_process.terminate()
        os._exit(0)

    icon = pystray.Icon(
        "dota2-overlay", img, "Dota 2 Overlay",
        menu=pystray.Menu(
            pystray.MenuItem("🎮  Dota 2 Overlay", None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(f"👁   Toggle  (F9)",           on_toggle),
            pystray.MenuItem("🔆  Opacity 100%",             on_op100),
            pystray.MenuItem("🔅  Opacity 50%",              on_op50),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("⚙   Settings",                on_settings),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("✕   Quit",                    on_quit),
        )
    )
    return icon

# ══════════════════════════════════════════════════════════════════════════════
#  SETTINGS EDITOR
# ══════════════════════════════════════════════════════════════════════════════
def open_settings_editor():
    cfg = load_config()
    head("  ⚙  Settings")
    items = [
        ("Window X",       "window.x"),
        ("Window Y",       "window.y"),
        ("Width",          "window.width"),
        ("Height",         "window.height"),
        ("Opacity %",      "window.opacity"),
        ("Always on top",  "window.always_on_top"),
        ("Toggle hotkey",  "hotkeys.toggle_overlay"),
        ("Opacity hotkey", "hotkeys.toggle_opacity"),
    ]
    print()
    for i, (label, path) in enumerate(items):
        keys = path.split(".")
        v = cfg
        for k in keys: v = v[k]
        print(f"  {C.CYAN}[{i+1}]{C.RESET} {label:<20} = {C.WHITE}{v}{C.RESET}")

    print(f"\n  {C.CYAN}[s]{C.RESET} Save   {C.CYAN}[q]{C.RESET} Cancel\n")
    try:
        choice = input("  Edit number (or s/q): ").strip().lower()
        if choice == "q": return
        if choice == "s":
            save_config(cfg); patch_overlay_config(cfg)
            ok("Saved — restart to apply window changes"); return
        idx = int(choice) - 1
        if 0 <= idx < len(items):
            label, path = items[idx]
            keys = path.split(".")
            node = cfg
            for k in keys[:-1]: node = node[k]
            cur = node[keys[-1]]
            new = input(f"  {label} [{cur}]: ").strip()
            if new:
                if isinstance(cur, bool):  node[keys[-1]] = new.lower() in ("true","1","yes")
                elif isinstance(cur, int): node[keys[-1]] = int(new)
                else:                      node[keys[-1]] = new
                save_config(cfg); patch_overlay_config(cfg)
                ok(f"Updated. Restart to apply.")
    except (ValueError, KeyboardInterrupt):
        warn("Cancelled.")

# ══════════════════════════════════════════════════════════════════════════════
#  PATCH overlay.py CONSTANTS FROM CONFIG
# ══════════════════════════════════════════════════════════════════════════════
def patch_overlay_config(config):
    w = config["window"]
    patches = {
        "WINDOW_W":      w["width"],
        "WINDOW_H":      w["height"],
        "WINDOW_X":      w["x"],
        "WINDOW_Y":      w["y"],
        "ALWAYS_ON_TOP": w["always_on_top"],
    }
    with open(OVERLAY_PY) as f: lines = f.readlines()
    new = []
    for line in lines:
        replaced = False
        for key, val in patches.items():
            stripped = line.lstrip()
            if stripped.startswith(f"{key} ") or stripped.startswith(f"{key}="):
                indent = len(line) - len(stripped)
                new.append(f"{' '*indent}{key:<14}= {repr(val)}\n")
                replaced = True; break
        if not replaced: new.append(line)
    with open(OVERLAY_PY, "w") as f: f.writelines(new)

# ══════════════════════════════════════════════════════════════════════════════
#  FIRST RUN WIZARD
# ══════════════════════════════════════════════════════════════════════════════
def first_run_wizard(config):
    print(f"\n  {C.BOLD}{C.YELLOW}╔══════════════════════════════════════╗")
    print(f"  ║   Welcome to Dota 2 Overlay Setup   ║")
    print(f"  ╚══════════════════════════════════════╝{C.RESET}\n")
    info("Press Enter to keep default values.\n")
    try:
        for key, label, typ in [
            ("window.x",             "Overlay X position", int),
            ("window.y",             "Overlay Y position", int),
            ("window.opacity",       "Opacity % (0-100)",  int),
            ("hotkeys.toggle_overlay","Toggle hotkey",     str),
            ("hotkeys.toggle_opacity","Opacity hotkey",    str),
        ]:
            keys = key.split(".")
            node = config
            for k in keys[:-1]: node = node[k]
            cur = node[keys[-1]]
            val = input(f"  {label} [{cur}]: ").strip()
            if val:
                node[keys[-1]] = typ(val) if typ != str else val.lower()
    except (ValueError, KeyboardInterrupt):
        warn("Using defaults.")
    config["first_run"] = False
    save_config(config)
    ok("Config saved!\n")

# ══════════════════════════════════════════════════════════════════════════════
#  DOTA 2 WATCHER
# ══════════════════════════════════════════════════════════════════════════════
overlay_process = None

def watch_for_dota(on_start):
    def _watch():
        was_running = False
        while True:
            try:
                r = subprocess.run(["tasklist","/FI","IMAGENAME eq dota2.exe","/NH"],
                                   capture_output=True, text=True)
                running = "dota2.exe" in r.stdout
                if running and not was_running:
                    was_running = True
                    info("Dota 2 detected — launching overlay!")
                    on_start()
                elif not running and was_running:
                    was_running = False
                    info("Dota 2 closed.")
            except: pass
            time.sleep(5)
    threading.Thread(target=_watch, daemon=True).start()

# ══════════════════════════════════════════════════════════════════════════════
#  LAUNCH OVERLAY
# ══════════════════════════════════════════════════════════════════════════════
def launch_overlay():
    global overlay_process
    if not os.path.exists(OVERLAY_PY):
        err(f"overlay.py not found"); sys.exit(1)
    info("Starting overlay...")
    overlay_process = subprocess.Popen([sys.executable, OVERLAY_PY], cwd=BASE_DIR)
    return overlay_process

# ══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════════════
def main():
    if sys.platform == "win32":
        os.system("color")  # enable ANSI colors

    config = load_config()

    # Banner
    print(f"\n  {C.BOLD}{C.YELLOW}╔═══════════════════════════════════════════╗")
    print(f"  ║       🎮  DOTA 2 OVERLAY  v1.0           ║")
    print(f"  ╚═══════════════════════════════════════════╝{C.RESET}\n")
    w = config["window"]; h = config["hotkeys"]
    info(f"Position   {C.WHITE}{w['x']}, {w['y']}{C.RESET}  |  "
         f"Size {C.WHITE}{w['width']}×{w['height']}{C.RESET}  |  "
         f"Opacity {C.WHITE}{w['opacity']}%{C.RESET}")
    info(f"Hotkeys    {C.CYAN}{h['toggle_overlay'].upper()}{C.RESET} toggle  |  "
         f"{C.CYAN}{h['toggle_opacity'].upper()}{C.RESET} opacity\n")

    # First run
    if config.get("first_run", True):
        first_run_wizard(config)
        config = load_config()

    # Dependencies
    if not check_dependencies():
        err("Missing required packages.")
        input("\n  Press Enter to exit...")
        sys.exit(1)

    print()

    # Apply config to overlay.py
    try:
        patch_overlay_config(config)
        ok("Config applied to overlay.py")
    except Exception as e:
        warn(f"Could not patch overlay.py: {e}")

    # ── Launch overlay FIRST so WS server starts ──────────────────────────────
    proc = launch_overlay()
    ok(f"Overlay launched (PID {proc.pid})")

    # Wait a moment for the WebSocket server inside overlay.py to be ready
    info("Waiting for overlay WebSocket server...")
    time.sleep(3)

    # ── Setup hotkeys AFTER overlay is running ────────────────────────────────
    setup_hotkeys(config)

    # ── System tray ───────────────────────────────────────────────────────────
    tray = None
    if config.get("show_tray_icon"):
        tray = build_tray_icon(config)
        if tray:
            threading.Thread(target=tray.run, daemon=True).start()
            ok("System tray active — right-click for controls")
        else:
            warn("Tray unavailable (pip install pystray Pillow)")

    # ── Dota auto-start ───────────────────────────────────────────────────────
    if config.get("auto_start_with_dota"):
        watch_for_dota(launch_overlay)

    print()
    info(f"{C.DIM}Running. Press Ctrl+C to stop.{C.RESET}\n")

    # Keep alive — watch overlay process
    try:
        while True:
            if proc.poll() is not None:
                warn(f"Overlay exited (code {proc.returncode})")
                break
            time.sleep(1)
    except KeyboardInterrupt:
        print()
        info("Shutting down...")
        if proc.poll() is None:
            proc.terminate()
        if tray:
            try: tray.stop()
            except: pass

    print(); ok("Goodbye!")


if __name__ == "__main__":
    main()