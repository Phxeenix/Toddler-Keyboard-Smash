# Toddler Keyboard Smash

A safe, fullscreen keyboard playground for toddlers. Every keypress triggers satisfying sounds and colorful visuals — no risk of accidentally closing windows, opening apps, or messing with system settings.

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
  - **Music** — pastel ripples, pentatonic piano notes, and sparkle particles on every keypress
  - **Emoji** — colorful emoji pop onto the screen with bounce animations and confetti bursts
- **Procedural audio** — all sounds are generated on the fly, no audio files needed
- **Intensity slider** — controls particle size, count, and color saturation
- **Settings are saved** between sessions

---

## How to Use

1. Launch the app — a setup screen appears for the parent
2. Pick a theme, adjust volume and intensity, click **START SESSION**
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
