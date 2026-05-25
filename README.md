# Keyboard Masher

A safe, fullscreen keyboard playground for toddlers. Every keypress triggers satisfying sounds and colorful visuals — no risk of accidentally closing windows, opening apps, or messing with system settings.

---

## What's New in v2.0

- **Dynamic animated backgrounds** — Music theme gets a nighttime city skyline with a slow color-shifting aurora sky; Emoji theme gets a sunny meadow with rolling hills, drifting clouds, and an animated sky
- **4 instrument choices** for the Music theme — Piano, Xylophone, Synth, and Harp, each with a distinct sound and matching visual style
- **Emoji category packs** — choose Animals, Food, Space, Faces, or All from the setup screen so the theme matches your toddler's current obsession
- **Sound-reactive background** — the background color and transition speed respond to the intensity slider, making high-intensity sessions feel more alive
- **Smoother transitions and visual polish** — anti-aliased rounded corners, a color-shifting setup screen, per-mode indicator pill during play, and improved text legibility throughout

---

## Download

**[Download the latest release](https://github.com/Phxeenix/Toddler-Keyboard-Smash/releases/latest)**

1. Download **ToddlerKeyboardSmash.exe**
2. Double-click to run — no installation required

> **Windows SmartScreen:** You may see a "Windows protected your PC" warning since the app isn't code-signed. Click **More info → Run anyway** to proceed. This is normal for indie apps.

---

## Features

- **Fullscreen lockdown** — the screen is taken over during play; keypresses go to the app, not Windows
- **Two visual themes** switchable with F1 / F2:
  - **Music** — animated city skyline, ripples, pentatonic notes, sparkle particles, and 4 selectable instruments (Piano, Xylophone, Synth, Harp)
  - **Emoji** — sunny meadow background, emoji pops with bounce animations, confetti bursts, and 5 emoji category packs
- **Procedural audio** — all sounds are generated on the fly, no audio files needed
- **Intensity slider** — controls particle count, size, color saturation, and background animation speed
- **Settings are saved** between sessions — theme, instrument, emoji category, volume, and intensity all persist

---

## How to Use

1. Launch the app — a setup screen appears for the parent
2. Pick a theme, choose an instrument or emoji category, adjust volume and intensity, click **START SESSION**
3. Hand the keyboard to your toddler
4. To exit, hold **Ctrl+Shift+Q** for 2 seconds

---

## For Developers

Want to run from source or contribute?

**Requirements:** Python 3.10+, Windows 10/11

```bash
git clone https://github.com/Phxeenix/Toddler-Keyboard-Smash.git
cd Toddler-Keyboard-Smash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

> The `keyboard` library requires administrator privileges for its global hook. Run as administrator if keypresses aren't being captured.
