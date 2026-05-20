# Toddler Keyboard Smash

## Download

**[Download the latest .exe from Releases](https://github.com/Phxeenix/Toddler-Keyboard-Smash/releases/latest)** — no Python required, just download and run.

> **Windows SmartScreen note:** Because the app isn't signed, Windows may show a "Windows protected your PC" warning. Click **More info** then **Run anyway** to proceed — this is normal for indie apps.

A safe, fullscreen keyboard playground for toddlers. Every keypress triggers satisfying sounds and colorful visuals — no risk of accidentally closing windows, opening apps, or messing with system settings.

---

## Features

- **Fullscreen lockdown** — takes over the screen while a session is active; keypresses are intercepted before they reach Windows
- **Two visual themes**, switchable with F1 / F2 during play:
  - **Music** — pastel ripples expand across the screen, each keypress plays a note from a C major pentatonic scale, sparkle particles burst from every ripple
  - **Emoji** — bright emoji characters pop onto the screen with a bounce animation and colorful confetti bursts
- **Procedural audio** — all sounds are generated at runtime (no audio files needed): bell-like tones for Music mode, a downward "bloop" chirp for Emoji mode
- **Parent setup screen** — configure volume, intensity, and notification suppression before handing the keyboard to your toddler
- **Safe unlock** — hold **Ctrl+Shift+Q** for 2 seconds to exit play mode; toddlers cannot accidentally quit
- **Intensity slider** — controls how many particles spawn, how large they are, and how saturated the colors are
- **Settings persistence** — volume, intensity, and notification preferences are saved between sessions

---

## Requirements

- Windows 10 / 11
- Python 3.10+
- Dependencies listed in `requirements.txt`:

```
pygame>=2.5.0
numpy>=1.24.0
keyboard>=0.13.5
```

---

## Installation

```bash
# Clone the repo
git clone https://github.com/Phxeenix/Toddler-Keyboard-Smash.git
cd Toddler-Keyboard-Smash

# Create and activate a virtual environment (recommended)
python -m venv venv
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

---

## Running

```bash
python main.py
```

The app must be run with **administrator privileges** (or at least elevated enough for the global keyboard hook to work). Right-click and "Run as administrator" if keys aren't being captured.

---

## Usage

1. The **setup screen** appears first — pick a theme, adjust volume and intensity, then click **START SESSION**
2. Hand the keyboard to your toddler and let them smash away
3. To exit, hold **Ctrl+Shift+Q** for 2 seconds — a countdown pill appears in the top-right corner
4. Press **ESC** on the setup screen (or click the **X** in the corner) to quit the app entirely

---

## Controls (during play)

| Input | Action |
|---|---|
| Any key | Triggers a sound and visual effect |
| F1 | Switch to Music theme |
| F2 | Switch to Emoji theme |
| Ctrl+Shift+Q (hold 2s) | Return to setup screen |

---

## Notes

- The `keyboard` library requires Windows and elevated privileges for the global hook
- The `venv` folder and `settings.json` are not included in the repo; `settings.json` is created automatically on first run
- All audio is synthesized with `numpy` — no external sound files required
