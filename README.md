# 🎮 Dota 2 Overlay

A transparent, always-on-top overlay for Dota 2 with auto-synced timers using Game State Integration (GSI).  
Built with Python + PyQt6. No .NET or pythonnet required.

---

## ✨ Features

- ⏱ **Roshan timer** — tracks kill time, min/max respawn window, plays sound alerts
- ✨ **Rune timers** — Bounty, Power, Wisdom, Lotus — all auto-synced to the in-game clock
- 📖 **Wisdom rune** — unique sound alert with purple visual flash
- 🛡 **Aegis countdown** — tracks 5-minute expiry after Roshan kill
- 🧀 **Cheese tracker** — dots light up from kill #2 onward
- 📡 **GSI sync** — reads the real Dota 2 clock automatically, no manual input
- 🔊 **Sound alerts** — synthesized via Web Audio API (no audio files needed)
- 🪟 **50% opacity** — overlay is semi-transparent, goes to 95% on hover
- 🖱 **Draggable** — grab anywhere on the overlay to reposition it
- 🔄 **Hot-reload** — edit `overlay.html` and it reloads live without restarting
- ⚙ **Config file** — `config.json` for position, opacity, hotkeys
- 🖥 **System tray icon** — right-click for quick controls
- ⌨ **Global hotkeys** — F9 toggle, F10 opacity swap

---

## 📁 Project Structure

```
Overlay/
├── main.py                          ← Run this to start
├── overlay.py                       ← Core overlay engine
├── requirements.txt                 ← Python dependencies
├── config.json                      ← Auto-created on first run
├── gamestate_integration_overlay.cfg ← Auto-created, copy to Dota 2
└── overlay_content/
    └── overlay.html                 ← The overlay UI (edit freely)
```

---

## 🚀 Installation

### 1. Install Python
Download Python 3.10–3.12 from https://python.org  
> ⚠️ **Avoid Python 3.14** — some packages don't support it yet. Use 3.11 or 3.12.

### 2. Install dependencies
Open a terminal in the project folder and run:
```bash
pip install PyQt6 PyQt6-WebEngine websockets pystray Pillow keyboard
```

### 3. Set up Dota 2 GSI
Run the overlay once — it will auto-create the GSI config file.  
If Dota 2 is not found automatically, copy the file manually:

**From:**
```
<project folder>\gamestate_integration_overlay.cfg
```
**To:**
```
C:\Program Files (x86)\Steam\steamapps\common\dota 2 beta\game\dota\cfg\gamestate_integration\
```
> Create the `gamestate_integration` folder if it doesn't exist.

### 4. Run
```bash
python main.py
```

---

## ⚙️ Configuration (`config.json`)

Auto-created on first run. Edit any time — restart the overlay to apply changes.

```json
{
  "window": {
    "x": 20,
    "y": 20,
    "width": 290,
    "height": 640,
    "opacity": 50,
    "always_on_top": true
  },
  "hotkeys": {
    "toggle_overlay": "F9",
    "toggle_opacity": "F10"
  },
  "auto_start_with_dota": false,
  "show_tray_icon": true
}
```

| Setting | Description |
|---|---|
| `x`, `y` | Overlay position in pixels from top-left of screen |
| `width`, `height` | Overlay window size in pixels |
| `opacity` | Transparency 0–100% (50 = half transparent) |
| `always_on_top` | Keep overlay above all other windows |
| `toggle_overlay` | Hotkey to show/hide overlay |
| `toggle_opacity` | Hotkey to swap between 50% and 100% opacity |
| `auto_start_with_dota` | Launch overlay automatically when Dota 2 starts |

---

## ⌨️ Hotkeys

| Key | Action |
|---|---|
| `F9` | Show / hide overlay |
| `F10` | Toggle opacity between 50% and 100% |

Change these in `config.json` or via the in-app settings editor.

---

## 🎮 How to Use In-Game

### Rune Timers
Once GSI connects (shows `● GSI LIVE` in the overlay), all rune timers start automatically — no button presses needed.

| Rune | Spawns |
|---|---|
| 💰 Bounty | Every 3 min from 0:00 |
| ⚡ Power | Every 2 min from 2:00 |
| 🌸 Lotus | Every 3 min from 3:00 |
| 📖 Wisdom | 7:00, 14:00, 21:00... |

Each rune shows:
- ⏱ Countdown timer
- 🟠 Orange warning 30–45s before spawn
- 🔊 Sound alert when it spawns
- 🟦/🟣 Glowing card when ready

### Roshan Timer
GSI does **not** expose when Roshan dies — you must press the button manually:

1. When Roshan dies → click **☠ ROSH DIED**
2. Timer counts down to minimum spawn (8 min)
3. At 8 min → warning sound, window opens (8–11 min)
4. At 11 min → spawn sound + border flash

---

## 🖥️ System Tray

When running, a tray icon appears in the bottom-right taskbar.  
Right-click it for:
- 👁 Toggle overlay visibility
- 🔆 Set opacity to 100%
- 🔅 Set opacity to 50%
- ⚙ Open settings editor
- ✕ Quit

---

## ✏️ Customizing the Overlay

Edit `overlay_content/overlay.html` freely — it auto-reloads when saved.

**Important rules to keep:**
```css
/* Keep background transparent */
html, body { background: transparent !important; }
```

You can use any HTML, CSS, JavaScript, Google Fonts, or fetch() calls.

---

## 🏗️ Architecture

```
Dota 2 game
    │
    │  POST JSON (every 0.1s)
    ▼
Python GSI server          (port 3000)
    │
    │  updates game_state dict
    ▼
Python WebSocket server    (port 3001)
    │
    │  broadcasts clock every 0.5s
    ▼
overlay.html (WebSocket client)
    │
    │  calculates all timers from clock
    ▼
Rune alerts + Roshan timer + sounds
```

---

## 🐛 Troubleshooting

### `ModuleNotFoundError: No module named 'clr'`
You have the wrong version of pywebview. This project uses **PyQt6** instead:
```bash
pip uninstall pywebview -y
pip install PyQt6 PyQt6-WebEngine
```

### `overlay.html not found`
Make sure your folder structure is correct:
```
Overlay/
├── overlay.py       ← here
└── overlay_content/
    └── overlay.html ← here
```

### `NO GSI` showing in overlay
1. Make sure the `.cfg` file is in the right Dota 2 folder (see Installation step 3)
2. Restart Dota 2 after copying the file
3. GSI only sends data during an active game — it won't connect in the main menu

### Overlay not visible / behind game
Make sure `always_on_top` is `true` in `config.json`.  
If Dota 2 runs in **fullscreen** mode, switch to **Fullscreen Windowed (Borderless)** in Dota 2 video settings.

### Sound not playing
Click anywhere on the overlay first — browsers require a user interaction before playing audio.

---

## 📦 Dependencies

| Package | Purpose |
|---|---|
| `PyQt6` | Window framework |
| `PyQt6-WebEngine` | Chromium web renderer |
| `websockets` | Real-time clock sync |
| `pystray` | System tray icon (optional) |
| `Pillow` | Tray icon image (optional) |
| `keyboard` | Global hotkeys (optional) |

---

## 📄 License

MIT — do whatever you want with it.