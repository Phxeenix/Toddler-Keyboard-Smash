"""
Toddler Key Smash — parent setup, then themed keypress play.
Setup: Start Session  |  Playing: Ctrl+Shift+Q unlock  |  SETUP: Escape quits
"""

from __future__ import annotations

import atexit
import ctypes
import json
import math
import queue
import random
import os
import sys
import threading
import time
from abc import ABC, abstractmethod
from enum import Enum, auto
from pathlib import Path
from typing import Any, Callable, NamedTuple

import numpy as np
import pygame

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------

BACKGROUND_COLOR = (0, 0, 0)
SETUP_BACKGROUND_COLOR = (26, 26, 46)  # #1a1a2e deep navy
SETUP_TILE_BG = (61, 61, 92)           # #3d3d5c — lightened per user request
SETUP_TILE_BG_ACTIVE = (78, 78, 110)
SETUP_ACCENT = (124, 106, 247)        # #7c6af7
SETUP_SUBTITLE_COLOR = (185, 185, 200)
SETUP_ON_GRADIENT_TEXT_COLOR = (255, 255, 255)  # now white; set_alpha controls opacity
SETUP_TAGLINE_TEXT = "A safe keyboard playground for little ones."
SETUP_FOOTER_HINT_TEXT = "Press ESC to quit or click X in the corner"
SETUP_BG_CYCLE_SEC = 8.0
SETUP_GRADIENT_BANDS = 96
SETUP_CLOSE_HIT = 44
SETUP_BUTTON_GLOW_LAYERS = 4
SETUP_BUTTON_DISABLED_BG = (40, 40, 52)
SETUP_BUTTON_DISABLED_TEXT = (95, 95, 110)
UI_FONT_NAME = "Segoe UI"
SETUP_TILE_WIDTH = 220
SETUP_TILE_HEIGHT = 180
SETUP_TILE_GAP = 32
SETUP_TILE_BORDER = 3
SETUP_SLIDER_LABEL_WIDTH = 80
SETUP_SLIDER_TRACK_WIDTH = 300
SETUP_SLIDER_TRACK_HEIGHT = 6
SETUP_SLIDER_HANDLE_RADIUS = 9
SETUP_SLIDER_ROW_HEIGHT = 36
SETUP_SLIDER_GAP = 18
SETUP_CAT_PILL_WIDTH = 100
SETUP_CAT_PILL_HEIGHT = 32
SETUP_CAT_PILL_GAP = 10
SETUP_CAT_FADE_SEC = 0.15
_CAT_NAMES: tuple[str, ...] = ("All", "Animals", "Food", "Space", "Faces")

# Instrument selector pills (Music tile).  Slightly wider to fit "Xylophone".
SETUP_INSTR_PILL_WIDTH = 110
SETUP_INSTR_PILL_HEIGHT = 32
SETUP_INSTR_PILL_GAP = 10
_INSTRUMENT_NAMES: tuple[str, ...] = ("Piano", "Xylophone", "Synth", "Harp")
# Display name → INSTRUMENT_SOUNDS key
_INSTRUMENT_KEY: dict[str, str] = {n: n.lower() for n in _INSTRUMENT_NAMES}
SETUP_TRACK_COLOR = (45, 45, 68)
DEFAULT_VOLUME = 0.6
DEFAULT_INTENSITY = 0.7
DEFAULT_SUPPRESS_NOTIFICATIONS = True
VOLUME_HARD_CAP = 0.75
SETUP_TOGGLE_WIDTH = 52
SETUP_TOGGLE_HEIGHT = 28
SETUP_TOGGLE_ON_COLOR = (76, 175, 80)   # #4caf50
SETUP_TOGGLE_OFF_COLOR = (70, 70, 90)
SETUP_TOGGLE_HANDLE_COLOR = (255, 255, 255)
NOTIFY_TOGGLE_LABEL = "Notifications: Suppress notifications"
THEME_LABEL_DURATION = 2.0  # seconds to show theme name after switching
TARGET_FPS = 60
FOREGROUND_CHECK_INTERVAL_SEC = 0.5

# Idle animation — activates after no keypresses for IDLE_THRESHOLD_SEC.
IDLE_THRESHOLD_SEC = 30.0
IDLE_TRANSITION_SEC = 0.5          # seconds to blend in/out idle effects
IDLE_GHOST_RIPPLE_INTERVAL_SEC = 3.0
IDLE_GHOST_RIPPLE_ALPHA = int(round(255 * 0.30))   # 30 % opacity
IDLE_MUSIC_SPEED_FACTOR = 2.0      # bg transitions 2× slower when idle
IDLE_EMOJI_DRIFT_FACTOR = 0.40     # bg particles drift at 40 % speed when idle
IDLE_EMOJI_DIM_AMOUNT = 0.15       # screen dims by 15 % at full idle (= 85 % brightness)

# Stress test — developer / parent tool (F7 from SETUP only).
STRESS_TEST_DURATION_SEC = 15.0
STRESS_TEST_FLASH_LIMIT_HZ = 3.0        # WCAG 2.3.1 general-flash limit
STRESS_TEST_KEY_INTERVAL_SEC = 0.05     # 20 synthetic keys/sec (worst-case)
STRESS_TEST_THEME_INTERVAL_SEC = 0.5    # alternate themes this often
STRESS_BRIGHTNESS_THRESHOLD = 0.10      # 10 % relative-luminance change = one flash half
STRESS_RED_R_MIN = 150                  # avg red must exceed this
STRESS_RED_RATIO = 1.5                  # and dominate green/blue by this factor
STRESS_SAMPLE_SIZE = (80, 45)           # downsample target for fast luma measurement
_LOG_APP_DIR = "KeyboardMasher"
_LOG_SUBDIR = "logs"

# Per-theme caps (replace the old global MAX_SHAPES limit).
MAX_RIPPLES = 30
MAX_EMOJIS = 15

EMOJI_FONT_NAME = "Segoe UI Emoji"
EMOJI_LIFETIME = 4.0  # seconds until fully faded
EMOJI_SIZE_MIN = 48
EMOJI_SIZE_MAX = 96

EMOJI_CHARS = (
    "🐶", "🐱", "🐰", "🐻", "🐼", "🦊", "🐸", "🐵",
    "⭐", "🌟", "✨", "🎈", "🌈", "🎉",
    "🍎", "🍌", "🍕", "🍩", "🎂", "❤️",
)

EMOJI_PACKS: dict[str, list[str]] = {
    "All": [
        "🐶","🐱","🐭","🐹","🐰","🦊","🐻","🐼","🐨","🐯","🦁","🐮","🐷","🐸","🐵",
        "🦄","🐔","🐧","🦆","🦋","🐢","🐙","🦀","🐠","🐬",
        "🍎","🍌","🍓","🍒","🍕","🍔","🌮","🍩","🍪","🎂","🍦","🧁","🍫","🍿",
        "🥑","🍉","🍇",
        "⭐","🌟","💫","✨","🌙","☀️","🪐","🌈","⚡","🔥","❄️","🌊",
        "😊","😂","🥰","😎","🤩","🥳","😜","👻","👾","🤖",
    ],
    "Animals": [
        "🐶","🐱","🐭","🐹","🐰","🦊","🐻","🐼","🐨","🐯","🦁","🐮","🐷","🐸","🐵",
        "🦄","🐔","🐧","🦆","🦋","🐢","🐙","🦀","🐠","🐬","🐳","🦓","🦒","🦘","🦔",
    ],
    "Food": [
        "🍎","🍌","🍓","🍒","🍕","🍔","🌮","🍩","🍪","🎂","🍦","🧁","🍫","🍿",
        "🥑","🍉","🍇","🍑","🥝","🍋","🍊","🍍","🥭","🍆","🥕","🌽","🍄","🧀","🍳","🥞",
    ],
    "Space": [
        "⭐","🌟","💫","✨","🌙","☀️","🪐","🌈","⚡","🔥","❄️","🌊",
        "☁️","🌪️","🌤️","🌍","🌕","🌠","🌌","🛸","🚀","🌋","🏔️","💥",
    ],
    "Faces": [
        "😊","😂","🥰","😎","🤩","🥳","😜","👻","👾","🤖",
        "🥹","😇","🤗","🥸","🤡","👽","💀","🎃","🤠","🥺","😤","🤣","😍","🤑","🫶",
    ],
}

# Curated per-theme base colors (RGB). Intensity slider blends low → white, high → full.
MUSIC_THEME_PALETTE: tuple[tuple[int, int, int], ...] = (
    (168, 237, 234),  # #a8edea
    (254, 214, 227),  # #fed6e3
    (195, 207, 226),  # #c3cfe2
    (224, 195, 252),  # #e0c3fc
    (255, 236, 210),  # #ffecd2
    (161, 196, 253),  # #a1c4fd
    (212, 252, 121),  # #d4fc79
    (150, 230, 161),  # #96e6a1
)
# Per-instrument ripple palettes
SYNTH_RIPPLE_PALETTE: tuple[tuple[int, int, int], ...] = (
    (116, 192, 252),  # #74c0fc — sky blue
    (169, 227,  75),  # #a9e34b — electric lime
    (218, 119, 242),  # #da77f2 — vivid purple
)
HARP_RIPPLE_PALETTE: tuple[tuple[int, int, int], ...] = (
    (255, 212,  59),  # #ffd43b — warm gold
    (255, 169,  77),  # #ffa94d — soft amber
    (255, 135, 135),  # #ff8787 — coral pink
)
# Xylophone ping flash (small white circle at ripple origin)
XYLOPHONE_PING_DURATION = 0.08   # seconds for the flash to fade
XYLOPHONE_PING_RADIUS   = 12     # pixels
# Nighttime city skyline constants (MusicTheme background layer).
SKYLINE_SEED = 42                                   # fixed seed → same layout every run
SKYLINE_BUILD_CLR: tuple[int, int, int] = (26, 26, 42)   # #1a1a2a — charcoal
SKYLINE_AURORA_ALPHA = 153   # 60 % of 255 — aurora blended over the city
# Nighttime sky color-shifting palette (slow crossfade, same mechanic as aurora).
_SKYLINE_BG_RAW: tuple[tuple[int, int, int], ...] = (
    (13,  27,  42),   # #0d1b2a — deep navy
    (27,  42,  74),   # #1b2a4a — midnight blue
    (45,  27, 105),   # #2d1b69 — dark purple
    (26,  26,  78),   # #1a1a4e — deep indigo
    (10,  22,  40),   # #0a1628 — near-black
)
# These colors are already dark nighttime tones; leave them untouched.
_SKYLINE_BG_COLORS: tuple[tuple[int, int, int], ...] = _SKYLINE_BG_RAW
SKYLINE_WIN_W  = 6
SKYLINE_WIN_H  = 8
SKYLINE_WIN_GAP_X = 13      # horizontal spacing between window columns
SKYLINE_WIN_GAP_Y = 14      # vertical spacing between window rows
SKYLINE_WIN_LIT   = 0.30    # fraction of windows lit at spawn
SKYLINE_WIN_COLORS: tuple[tuple[int, int, int], ...] = (
    (255, 200,  80),  # warm yellow
    (255, 240, 160),  # pale cream
    (255, 170,  60),  # amber
)
SKYLINE_STAR_DIM    = 55
SKYLINE_STAR_BRIGHT = 220
SKYLINE_STAR_SPEED  = 1.6   # radians per second (twinkle frequency)

# Ordered sequence for the background color cycle (subset of palette).
MUSIC_BG_PALETTE: tuple[tuple[int, int, int], ...] = (
    (168, 237, 234),  # #a8edea
    (195, 207, 226),  # #c3cfe2
    (224, 195, 252),  # #e0c3fc
    (161, 196, 253),  # #a1c4fd
    (254, 214, 227),  # #fed6e3
    (150, 230, 161),  # #96e6a1
)
EMOJI_CONFETTI_PALETTE: tuple[tuple[int, int, int], ...] = (
    (255, 107, 107),  # #ff6b6b
    (255, 217, 61),   # #ffd93d
    (107, 203, 119),  # #6bcb77
    (77, 150, 255),   # #4d96ff
    (255, 146, 43),   # #ff922b
    (204, 93, 232),   # #cc5de8
    (240, 101, 149),  # #f06595
    (116, 192, 252),  # #74c0fc
)

# Audio — C major pentatonic across two octaves (8 notes).
SAMPLE_RATE = 44100
NOTE_DURATION = 0.6
ATTACK_SEC = 0.01
DECAY_RATE = 7.5  # exponential envelope; higher = faster fade

PENTATONIC_FREQS: tuple[float, ...] = (
    261.63,  # C4
    293.66,  # D4
    329.63,  # E4
    392.00,  # G4
    440.00,  # A4
    523.25,  # C5
    587.33,  # D5
    659.25,  # E5
)

# Physical keyboard rows (left → right). Each row maps to two note indices.
_ROW_ZXCV = (
    pygame.K_z, pygame.K_x, pygame.K_c, pygame.K_v, pygame.K_b,
    pygame.K_n, pygame.K_m, pygame.K_COMMA, pygame.K_PERIOD, pygame.K_SLASH,
)
_ROW_ASDF = (
    pygame.K_a, pygame.K_s, pygame.K_d, pygame.K_f, pygame.K_g,
    pygame.K_h, pygame.K_j, pygame.K_k, pygame.K_l,
    pygame.K_SEMICOLON, pygame.K_QUOTE,
)
_ROW_QWERTY = (
    pygame.K_q, pygame.K_w, pygame.K_e, pygame.K_r, pygame.K_t,
    pygame.K_y, pygame.K_u, pygame.K_i, pygame.K_o, pygame.K_p,
    pygame.K_LEFTBRACKET, pygame.K_RIGHTBRACKET, pygame.K_BACKSLASH,
)
_ROW_NUMBER = (
    pygame.K_BACKQUOTE,
    pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5,
    pygame.K_6, pygame.K_7, pygame.K_8, pygame.K_9, pygame.K_0,
    pygame.K_MINUS, pygame.K_EQUALS,
)
_KEYBOARD_ROWS: tuple[tuple[int, ...], ...] = (
    _ROW_ZXCV,
    _ROW_ASDF,
    _ROW_QWERTY,
    _ROW_NUMBER,
)
_ROW_NOTE_BASE = (0, 2, 4, 6)  # low → high rows

# EmojiTheme "bloop" pop (~120 ms, pitch-down chirp).
POP_DURATION = 0.12
POP_FREQ_START = 800.0
POP_FREQ_END = 200.0
PITCH_SHIFT_MIN = 0.8   # −20 %
PITCH_SHIFT_MAX = 1.2   # +20 %

# Populated at startup after mixer init.
NOTE_SOUNDS: list[pygame.mixer.Sound] = []
INSTRUMENT_SOUNDS: dict[str, list[pygame.mixer.Sound]] = {}
POP_WAVE: np.ndarray | None = None
CURRENT_PLAY_VOLUME = DEFAULT_VOLUME  # updated by apply_session_volume()


# -----------------------------------------------------------------------------
# Procedural audio
# -----------------------------------------------------------------------------


def _generate_note_sound(frequency: float) -> pygame.mixer.Sound:
    """Sine bell: 10 ms attack, exponential decay, 16-bit stereo."""
    n_samples = int(SAMPLE_RATE * NOTE_DURATION)
    t = np.linspace(0.0, NOTE_DURATION, n_samples, endpoint=False)
    wave = np.sin(2.0 * np.pi * frequency * t)

    attack_samples = int(SAMPLE_RATE * ATTACK_SEC)
    ramp = np.ones(n_samples, dtype=np.float64)
    if attack_samples > 0:
        ramp[:attack_samples] = np.linspace(0.0, 1.0, attack_samples)
    envelope = ramp * np.exp(-DECAY_RATE * t)
    wave = wave * envelope

    peak = float(np.max(np.abs(wave))) or 1.0
    mono = (wave / peak * 32767 * 0.95).astype(np.int16)
    stereo = np.column_stack([mono, mono])
    sound = pygame.sndarray.make_sound(stereo)
    sound.set_volume(1.0)
    return sound


def build_note_sounds() -> list[pygame.mixer.Sound]:
    """Generate and cache all pentatonic note samples."""
    return [_generate_note_sound(freq) for freq in PENTATONIC_FREQS]


# ---------------------------------------------------------------------------
# Multi-instrument sound generators
# ---------------------------------------------------------------------------

def _pcm_to_sound(wave: np.ndarray, attack_sec: float, decay_rate: float) -> pygame.mixer.Sound:
    """Apply attack ramp + exponential decay to a raw wave, return a Sound."""
    n = len(wave)
    t = np.arange(n, dtype=np.float64) / SAMPLE_RATE
    attack_n = int(SAMPLE_RATE * attack_sec)
    ramp = np.ones(n, dtype=np.float64)
    if attack_n > 0:
        ramp[:attack_n] = np.linspace(0.0, 1.0, attack_n)
    wave = wave * ramp * np.exp(-decay_rate * t)
    peak = float(np.max(np.abs(wave))) or 1.0
    mono = (wave / peak * 32767 * 0.95).astype(np.int16)
    stereo = np.column_stack([mono, mono])
    s = pygame.sndarray.make_sound(stereo)
    s.set_volume(1.0)
    return s


def _gen_piano(freq: float) -> pygame.mixer.Sound:
    """Sine wave — 10 ms attack, 0.6 s exp decay. Warm and familiar."""
    dur = 0.6
    n = int(SAMPLE_RATE * dur)
    t = np.linspace(0.0, dur, n, endpoint=False)
    wave = np.sin(2.0 * np.pi * freq * t)
    return _pcm_to_sound(wave, attack_sec=0.010, decay_rate=7.5)


def _gen_xylophone(freq: float) -> pygame.mixer.Sound:
    """Sine + 2nd harmonic (30 %) — 5 ms attack, 0.25 s decay. Bright and percussive."""
    dur = 0.25
    n = int(SAMPLE_RATE * dur)
    t = np.linspace(0.0, dur, n, endpoint=False)
    wave = (
        np.sin(2.0 * np.pi * freq * t)
        + 0.30 * np.sin(2.0 * np.pi * 2.0 * freq * t)
    )
    return _pcm_to_sound(wave, attack_sec=0.005, decay_rate=20.0)


def _gen_synth(freq: float) -> pygame.mixer.Sound:
    """Three detuned square waves (±3 cents) — 8 ms attack, 0.8 s decay. Fun and buzzy."""
    dur = 0.8
    n = int(SAMPLE_RATE * dur)
    t = np.linspace(0.0, dur, n, endpoint=False)
    shift = 2.0 ** (3.0 / 1200.0) - 1.0          # 3-cent ratio offset ≈ 0.001732
    sq1 = np.sign(np.sin(2.0 * np.pi * freq * t))
    sq2 = np.sign(np.sin(2.0 * np.pi * freq * (1.0 + shift) * t))
    sq3 = np.sign(np.sin(2.0 * np.pi * freq * (1.0 - shift) * t))
    wave = 0.50 * sq1 + 0.25 * sq2 + 0.25 * sq3
    return _pcm_to_sound(wave, attack_sec=0.008, decay_rate=5.5)


def _gen_harp(freq: float) -> pygame.mixer.Sound:
    """Triangle wave — 15 ms attack, 1.2 s decay. Airy and magical."""
    dur = 1.2
    n = int(SAMPLE_RATE * dur)
    t = np.linspace(0.0, dur, n, endpoint=False)
    wave = (2.0 / np.pi) * np.arcsin(np.clip(np.sin(2.0 * np.pi * freq * t), -1.0, 1.0))
    return _pcm_to_sound(wave, attack_sec=0.015, decay_rate=4.0)


_INSTRUMENT_GENERATORS: dict[str, object] = {
    "piano":     _gen_piano,
    "xylophone": _gen_xylophone,
    "synth":     _gen_synth,
    "harp":      _gen_harp,
}


def build_instrument_sounds() -> dict[str, list[pygame.mixer.Sound]]:
    """Generate all four instrument sets for every pentatonic note."""
    return {
        name: [fn(freq) for freq in PENTATONIC_FREQS]   # type: ignore[operator]
        for name, fn in _INSTRUMENT_GENERATORS.items()
    }


def _generate_pop_wave() -> np.ndarray:
    """Downward chirp with a soft envelope — short bloop, not a beep."""
    n_samples = int(SAMPLE_RATE * POP_DURATION)
    t = np.linspace(0.0, POP_DURATION, n_samples, endpoint=False)
    duration = POP_DURATION

    # Linear frequency sweep: 800 Hz → 200 Hz.
    phase = 2.0 * np.pi * (
        POP_FREQ_START * t
        + 0.5 * (POP_FREQ_END - POP_FREQ_START) * t * t / duration
    )
    wave = np.sin(phase)

    attack_samples = int(SAMPLE_RATE * 0.008)
    ramp = np.ones(n_samples, dtype=np.float64)
    if attack_samples > 0:
        ramp[:attack_samples] = np.linspace(0.0, 1.0, attack_samples)
    # Rounded body + quick tail for a bubbly pop.
    blob = np.sin(np.pi * t / duration) ** 0.7
    tail = np.exp(-20.0 * t)
    wave *= ramp * blob * tail

    peak = float(np.max(np.abs(wave))) or 1.0
    return (wave / peak).astype(np.float64)


def _resample_pitch(wave: np.ndarray, factor: float) -> np.ndarray:
    """Resample wave; factor > 1 raises pitch (shorter sample)."""
    factor = max(0.01, factor)
    old_len = len(wave)
    new_len = max(2, int(old_len / factor))
    x_old = np.arange(old_len, dtype=np.float64)
    x_new = np.linspace(0.0, old_len - 1, new_len)
    return np.interp(x_new, x_old, wave).astype(np.float64)


def build_pop_wave() -> np.ndarray:
    """Build the base pop sample (pitch-shifted per play)."""
    return _generate_pop_wave()


def play_pop_sound(pitch_factor: float | None = None) -> None:
    """Play bloop with random ±20 % pitch unless factor is given."""
    if POP_WAVE is None:
        return
    if pitch_factor is None:
        pitch_factor = random.uniform(PITCH_SHIFT_MIN, PITCH_SHIFT_MAX)

    shifted = _resample_pitch(POP_WAVE, pitch_factor)
    peak = float(np.max(np.abs(shifted))) or 1.0
    mono = (shifted / peak * 32767 * 0.95).astype(np.int16)
    stereo = np.column_stack([mono, mono])
    sound = pygame.sndarray.make_sound(stereo)
    sound.set_volume(CURRENT_PLAY_VOLUME)
    sound.play()


def effective_volume(slider_value: float) -> float:
    """Map slider 0–1 to capped playback volume (max 0.75)."""
    return min(max(0.0, slider_value), VOLUME_HARD_CAP)


def apply_session_volume(slider_value: float) -> float:
    """Apply volume to music channel and all cached Sound objects."""
    global CURRENT_PLAY_VOLUME
    vol = effective_volume(slider_value)
    CURRENT_PLAY_VOLUME = vol
    pygame.mixer.music.set_volume(vol)
    for sound in NOTE_SOUNDS:
        sound.set_volume(vol)
    return vol


def intensity_scale(intensity: float) -> float:
    """0.5 = calm, 1.0 = chaotic (intensity slider 0–1)."""
    return 0.5 + 0.5 * max(0.0, min(1.0, intensity))


def _particle_count_for_intensity(intensity: float) -> int:
    """How many sparkles/confetti to spawn per keypress: 6 (calm) → 16 (chaotic)."""
    t = max(0.0, min(1.0, intensity))
    return max(6, min(16, int(round(6 + 10 * t))))


def _apply_intensity_to_rgb(
    rgb: tuple[int, int, int], intensity: float
) -> tuple[int, int, int]:
    """
    Low intensity → blend toward white (pastel); high → full palette saturation.
    intensity is the raw session slider in [0, 1].
    """
    t = max(0.0, min(1.0, intensity))
    r, g, b = rgb
    return (
        int(round(255.0 * (1.0 - t) + float(r) * t)),
        int(round(255.0 * (1.0 - t) + float(g) * t)),
        int(round(255.0 * (1.0 - t) + float(b) * t)),
    )


def _lighter_tint(rgb: tuple[int, int, int], toward_white: float = 0.42) -> tuple[int, int, int]:
    """Push a color toward white (for sparkle accents on top of ripples)."""
    u = max(0.0, min(1.0, toward_white))
    r, g, b = rgb
    return (
        int(round(255.0 * u + float(r) * (1.0 - u))),
        int(round(255.0 * u + float(g) * (1.0 - u))),
        int(round(255.0 * u + float(b) * (1.0 - u))),
    )


def key_to_note_index(key: int) -> int:
    """
    Map a key to note 0–7 by keyboard row (ZXCV low → number row high)
    and horizontal position (left lower, right higher within the row).
    """
    for base, row in zip(_ROW_NOTE_BASE, _KEYBOARD_ROWS):
        if key not in row:
            continue
        keys = list(row)
        pos = keys.index(key)
        if len(keys) <= 1:
            offset = 0
        else:
            offset = round(pos / (len(keys) - 1))
        return min(7, base + offset)
    return 4  # middle of scale for space, arrows, etc.


# -----------------------------------------------------------------------------
# Theme base
# -----------------------------------------------------------------------------


class Theme(ABC):
    """Base class for visual themes. Subclasses own their state and rendering."""

    name: str = "Theme"

    def __init__(self, screen: pygame.Surface, intensity: float = DEFAULT_INTENSITY) -> None:
        self._screen_w, self._screen_h = screen.get_size()
        self.intensity = intensity
        self._intensity_scale = intensity_scale(intensity)
        self._time_since_keypress: float = 0.0
        self._idle_factor: float = 0.0
        self._idle_target: float = 0.0

    def clear(self) -> None:
        """Reset theme state when switching themes."""
        self._time_since_keypress = 0.0
        self._idle_factor = 0.0
        self._idle_target = 0.0
        self._on_clear()

    def _advance_idle(self, dt: float) -> None:
        """Advance the idle timer and smoothly drive _idle_factor toward its target.
        Call once at the top of update() in every subclass."""
        self._time_since_keypress += dt
        if self._time_since_keypress >= IDLE_THRESHOLD_SEC:
            self._idle_target = 1.0
        rate = 1.0 / IDLE_TRANSITION_SEC
        if self._idle_target > self._idle_factor:
            self._idle_factor = min(self._idle_target, self._idle_factor + rate * dt)
        else:
            self._idle_factor = max(self._idle_target, self._idle_factor - rate * dt)

    def _on_keypress_idle(self) -> None:
        """Reset idle state on any keypress.  Call at the top of on_keypress()."""
        self._time_since_keypress = 0.0
        self._idle_target = 0.0

    @abstractmethod
    def _on_clear(self) -> None:
        """Subclass hook to wipe lists and timers."""

    @abstractmethod
    def on_keypress(self, key: int) -> None:
        """React to a key press (non-system keys only)."""

    @abstractmethod
    def update(self, dt: float) -> None:
        """Advance animations; dt is seconds since last frame."""

    @abstractmethod
    def draw(self, screen: pygame.Surface) -> None:
        """Draw visuals (caller clears the screen to black first)."""

    def _random_position(self, margin: int = 40) -> tuple[int, int]:
        x = random.randint(margin, max(margin, self._screen_w - margin))
        y = random.randint(margin, max(margin, self._screen_h - margin))
        return x, y


# -----------------------------------------------------------------------------
# MusicTheme — expanding, fading ripples
# -----------------------------------------------------------------------------

BG_TRANSITION_DURATION_SEC = 8.0
SCALE_IN_DURATION_SEC = 0.12
EMOJI_BOUNCE_DURATION_SEC = 0.08
SPARKLE_LIFETIME_SEC = 0.4
CONFETTI_LIFETIME_SEC = 0.6
CONFETTI_GRAVITY_PPS2 = 480.0


def _ease_out_cubic(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 1.0 - (1.0 - t) ** 3


def _ripple_pop_scale(pop_age: float) -> float:
    """0→1 over SCALE_IN_DURATION_SEC (ease-out); then 1."""
    if pop_age >= SCALE_IN_DURATION_SEC:
        return 1.0
    return _ease_out_cubic(pop_age / SCALE_IN_DURATION_SEC)


def _emoji_display_scale(pop_age: float) -> float:
    """Scale-in 0→1, then bounce to 1.1 and back to 1."""
    if pop_age < SCALE_IN_DURATION_SEC:
        return _ease_out_cubic(pop_age / SCALE_IN_DURATION_SEC)
    bt = pop_age - SCALE_IN_DURATION_SEC
    if bt < EMOJI_BOUNCE_DURATION_SEC:
        u = bt / EMOJI_BOUNCE_DURATION_SEC
        return 1.0 + 0.1 * math.sin(math.pi * u)
    return 1.0


class Ripple:
    __slots__ = ("x", "y", "radius", "color", "alpha", "pop_age")

    def __init__(self, x: int, y: int, color: tuple[int, int, int]) -> None:
        self.x = x
        self.y = y
        self.radius = 8.0
        self.color = color
        self.alpha = 255.0
        self.pop_age = 0.0


class SparkleParticle:
    __slots__ = ("x", "y", "vx", "vy", "age", "size", "color")

    def __init__(
        self,
        x: float,
        y: float,
        color: tuple[int, int, int],
        vx: float,
        vy: float,
        size: float,
    ) -> None:
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.age = 0.0
        self.size = size
        self.color = color


def _desaturate(rgb: tuple[int, int, int], amount: float) -> tuple[int, int, int]:
    """Blend rgb toward its average gray by `amount` (0 = unchanged, 1 = full gray)."""
    r, g, b = rgb
    gray = (r + g + b) / 3.0
    t = max(0.0, min(1.0, amount))
    return (
        int(round(gray * t + r * (1.0 - t))),
        int(round(gray * t + g * (1.0 - t))),
        int(round(gray * t + b * (1.0 - t))),
    )


def _darken(rgb: tuple[int, int, int], amount: float) -> tuple[int, int, int]:
    """Multiply each channel by (1 - amount); amount=0.35 → 35 % darker."""
    f = max(0.0, 1.0 - max(0.0, min(1.0, amount)))
    return (
        int(round(rgb[0] * f)),
        int(round(rgb[1] * f)),
        int(round(rgb[2] * f)),
    )


# Background cycle colors: 60 % desaturated then darkened 35 % so they read as
# a faint color tint over near-black — ripples and sparkles stay the brightest
# elements on screen at all times.
_MUSIC_BG_COLORS: tuple[tuple[int, int, int], ...] = tuple(
    _darken(_desaturate(c, 0.60), 0.35) for c in MUSIC_BG_PALETTE
)


def _music_bg_transition_duration(intensity: float) -> float:
    """Map intensity 0–1 to background color-cycle duration in seconds.
    Piecewise linear: 16 s at 0.0 → 8 s at 0.5 → 5 s at 1.0.
    """
    t = max(0.0, min(1.0, intensity))
    if t <= 0.5:
        return 16.0 + (8.0 - 16.0) * (t / 0.5)
    return 8.0 + (5.0 - 8.0) * ((t - 0.5) / 0.5)


class MusicTheme(Theme):
    """Soft pastel ripples that expand and fade on each keypress."""

    name = "Music"

    RADIUS_GROWTH = 140.0  # pixels per second
    ALPHA_FADE = 100.0     # alpha per second (~2.5s full fade)
    RING_WIDTH = 7

    def __init__(
        self,
        screen: pygame.Surface,
        note_sounds: list[pygame.mixer.Sound] | None = None,
        intensity: float = DEFAULT_INTENSITY,
        active_instrument: str = "piano",
    ) -> None:
        super().__init__(screen, intensity)
        self.ripples: list[Ripple] = []
        self.sparkles: list[SparkleParticle] = []
        self._active_instrument: str = active_instrument
        self._note_sounds = (
            INSTRUMENT_SOUNDS.get(active_instrument)
            or (note_sounds if note_sounds is not None else NOTE_SOUNDS)
        )
        scale = self._intensity_scale
        self._max_ripples = max(1, int(MAX_RIPPLES * scale))
        self._ring_width = max(3, int(self.RING_WIDTH * scale))
        self._bg_idx = 0
        self._bg_t = 0.0
        self._bg_transition_sec = _music_bg_transition_duration(intensity)
        self._ghost_timer = 0.0
        # pings are (x, y, age) entries added by xylophone on each keypress
        self._pings: list[tuple[int, int, float]] = []
        self._apply_instrument_style()
        # Nighttime city skyline — built once, animated cheaply
        self._city_time: float = 0.0
        self._sky_idx: int = 0
        self._sky_t: float = 0.0
        self._sky_duration: float = _music_bg_transition_duration(intensity)
        self._city_rng = random.Random(99)      # separate RNG for runtime flickering
        self._city_bg_surf: pygame.Surface | None = None
        self._aurora_surf:  pygame.Surface | None = None
        self._stars:      list[tuple[float, float, float]] = []
        self._star_surfs: list[pygame.Surface] = []
        # Each window entry: [rect, lit, timer, interval, color]
        self._windows: list[list] = []
        self._build_skyline()

    @property
    def active_instrument(self) -> str:
        return self._active_instrument

    @active_instrument.setter
    def active_instrument(self, value: str) -> None:
        self._active_instrument = value
        sounds = INSTRUMENT_SOUNDS.get(value)
        if sounds:
            self._note_sounds = sounds
        self._apply_instrument_style()

    def _apply_instrument_style(self) -> None:
        """Derive visual parameters from the current active_instrument."""
        scale = self._intensity_scale
        instr = self._active_instrument
        # Start from piano defaults, then override per instrument
        self._radius_growth        = self.RADIUS_GROWTH * scale
        self._initial_radius       = 8.0 * scale
        self._ripple_palette: tuple[tuple[int, int, int], ...] = MUSIC_THEME_PALETTE
        self._sparkle_lifetime_sec: float = SPARKLE_LIFETIME_SEC
        self._draw_square_ripple: bool = False
        if instr == "xylophone":
            self._radius_growth  = self.RADIUS_GROWTH * scale * 1.6
            self._initial_radius = 5.0 * scale
        elif instr == "synth":
            self._ripple_palette     = SYNTH_RIPPLE_PALETTE
            self._draw_square_ripple = True
        elif instr == "harp":
            self._radius_growth        = self.RADIUS_GROWTH * scale * 0.65
            self._initial_radius       = 14.0 * scale
            self._ripple_palette       = HARP_RIPPLE_PALETTE
            self._sparkle_lifetime_sec = SPARKLE_LIFETIME_SEC * 1.5

    # ------------------------------------------------------------------
    # Skyline helpers
    # ------------------------------------------------------------------

    def _build_skyline(self) -> None:
        """Pre-bake static sky+buildings surface, generate stars and windows."""
        w, h = self._screen_w, self._screen_h
        rng = random.Random(SKYLINE_SEED)

        # ---- Building silhouette surface (SRCALPHA — sky pixels are transparent) --
        # The sky color is painted each frame as a solid fill BEFORE this blit,
        # so the transparent areas show the color-shifting sky underneath.
        self._city_bg_surf = pygame.Surface((w, h), pygame.SRCALPHA)

        # ---- Buildings + windows ----------------------------------------
        n_buildings = rng.randint(12, 18)
        spacing = w / n_buildings
        self._windows = []
        for i in range(n_buildings):
            bw = rng.randint(40, 120)
            bh = rng.randint(80, 280)
            bx = int(i * spacing + rng.uniform(-8, 8))
            bx = max(0, min(w - bw, bx))
            by = h - bh
            pygame.draw.rect(
                self._city_bg_surf, SKYLINE_BUILD_CLR,
                (bx, by, bw, bh),
            )
            # Window grid for this building
            row_y = by + SKYLINE_WIN_GAP_Y
            while row_y + SKYLINE_WIN_H < h - 4:
                col_x = bx + SKYLINE_WIN_GAP_X
                while col_x + SKYLINE_WIN_W < bx + bw - SKYLINE_WIN_GAP_X // 2:
                    lit   = rng.random() < SKYLINE_WIN_LIT
                    # Each window gets its own random phase so they never all blink together
                    timer = rng.uniform(0.0, rng.uniform(6.0, 10.0))
                    color = rng.choice(SKYLINE_WIN_COLORS)
                    self._windows.append(
                        [pygame.Rect(col_x, row_y, SKYLINE_WIN_W, SKYLINE_WIN_H),
                         lit, timer, color]
                    )
                    col_x += SKYLINE_WIN_W + SKYLINE_WIN_GAP_X
                row_y += SKYLINE_WIN_H + SKYLINE_WIN_GAP_Y

        # ---- Stars in sky area ------------------------------------------
        n_stars = rng.randint(40, 60)
        self._stars = [
            (
                rng.uniform(4.0, float(w - 4)),
                rng.uniform(4.0, float(h) * 0.65),
                rng.uniform(0.0, 2.0 * math.pi),   # per-star phase offset
            )
            for _ in range(n_stars)
        ]
        # Pre-allocate tiny 2×2 surfaces (no per-frame allocation)
        self._star_surfs = []
        for _ in self._stars:
            ss = pygame.Surface((2, 2))
            ss.fill((210, 220, 255))     # slightly blue-white
            self._star_surfs.append(ss)

        # ---- Aurora overlay surface (pre-allocated, reused each frame) --
        self._aurora_surf = pygame.Surface((w, h))
        self._aurora_surf.set_alpha(SKYLINE_AURORA_ALPHA)

    def _on_clear(self) -> None:
        self.ripples.clear()
        self.sparkles.clear()
        self._pings.clear()
        self._bg_idx = 0
        self._bg_t = 0.0
        self._ghost_timer = 0.0
        self._city_time = 0.0
        self._sky_idx = 0
        self._sky_t = 0.0

    def _spawn_sparkles(self, x: int, y: int, color: tuple[int, int, int]) -> None:
        n = _particle_count_for_intensity(self.intensity)
        t = max(0.0, min(1.0, self.intensity))
        sz_lo = 10.0 + 8.0 * t
        sz_hi = 14.0 + 8.0 * t
        for _ in range(n):
            ang = random.uniform(0.0, 2.0 * math.pi)
            spd = random.uniform(90.0, 220.0)
            vx = math.cos(ang) * spd
            vy = math.sin(ang) * spd
            sz = random.uniform(sz_lo, sz_hi)
            self.sparkles.append(SparkleParticle(float(x), float(y), color, vx, vy, sz))

    def on_keypress(self, key: int) -> None:
        self._on_keypress_idle()
        note_idx = key_to_note_index(key)
        self._note_sounds[note_idx].play()  # overlaps on separate channels

        if len(self.ripples) >= self._max_ripples:
            self.ripples.pop(0)
        x, y = self._random_position()
        base = random.choice(self._ripple_palette)
        color = _apply_intensity_to_rgb(base, self.intensity)
        ripple = Ripple(x, y, color)
        ripple.radius = self._initial_radius
        self.ripples.append(ripple)
        self._spawn_sparkles(x, y, _lighter_tint(color))
        if self._active_instrument == "xylophone":
            self._pings.append((x, y, 0.0))

    def _spawn_ghost_ripple(self) -> None:
        """Silent, low-opacity auto-ripple that appears during idle."""
        if len(self.ripples) >= self._max_ripples:
            self.ripples.pop(0)
        x, y = self._random_position()
        base = random.choice(self._ripple_palette)
        color = _apply_intensity_to_rgb(base, self.intensity)
        ripple = Ripple(x, y, color)
        ripple.radius = self._initial_radius
        ripple.alpha = IDLE_GHOST_RIPPLE_ALPHA * self._idle_factor
        self.ripples.append(ripple)

    def update(self, dt: float) -> None:
        self._advance_idle(dt)

        effective_sec = self._bg_transition_sec * (
            1.0 + (IDLE_MUSIC_SPEED_FACTOR - 1.0) * self._idle_factor
        )
        self._bg_t += dt / effective_sec
        if self._bg_t >= 1.0:
            self._bg_t -= 1.0
            self._bg_idx = (self._bg_idx + 1) % len(_MUSIC_BG_COLORS)

        if self._idle_factor > 0.0:
            self._ghost_timer += dt
            if self._ghost_timer >= IDLE_GHOST_RIPPLE_INTERVAL_SEC:
                self._ghost_timer -= IDLE_GHOST_RIPPLE_INTERVAL_SEC
                self._spawn_ghost_ripple()
        else:
            self._ghost_timer = 0.0

        alive: list[Ripple] = []
        for ripple in self.ripples:
            ripple.pop_age += dt
            ripple.radius += self._radius_growth * dt
            ripple.alpha -= self.ALPHA_FADE * dt
            if ripple.alpha > 0:
                alive.append(ripple)
        self.ripples = alive

        spark_alive: list[SparkleParticle] = []
        for sp in self.sparkles:
            sp.age += dt
            sp.x += sp.vx * dt
            sp.y += sp.vy * dt
            if sp.age < self._sparkle_lifetime_sec:
                spark_alive.append(sp)
        self.sparkles = spark_alive

        if self._pings:
            self._pings = [
                (px, py, pa + dt)
                for px, py, pa in self._pings
                if pa + dt < XYLOPHONE_PING_DURATION
            ]

        # City skyline: advance sky color cycle, star twinkle, window flicker
        self._sky_t += dt / self._sky_duration
        if self._sky_t >= 1.0:
            self._sky_t -= 1.0
            self._sky_idx = (self._sky_idx + 1) % len(_SKYLINE_BG_COLORS)
        self._city_time += dt
        for win in self._windows:
            win[2] -= dt
            if win[2] <= 0.0:
                win[1] = not win[1]          # toggle lit state
                win[2] = self._city_rng.uniform(6.0, 10.0)

    def draw(self, screen: pygame.Surface) -> None:
        # ---- Layer 1: color-shifting nighttime sky (single flat fill) ----
        sc0 = _SKYLINE_BG_COLORS[self._sky_idx]
        sc1 = _SKYLINE_BG_COLORS[(self._sky_idx + 1) % len(_SKYLINE_BG_COLORS)]
        screen.fill(_lerp_rgb(sc0, sc1, self._sky_t))

        # ---- Layer 1b: building silhouettes (transparent SRCALPHA blit) -
        if self._city_bg_surf is not None:
            screen.blit(self._city_bg_surf, (0, 0))

        # ---- Layer 2: twinkling stars -----------------------------------
        t = self._city_time
        for (sx, sy, sphase), ss in zip(self._stars, self._star_surfs):
            alpha = int(
                SKYLINE_STAR_DIM
                + (SKYLINE_STAR_BRIGHT - SKYLINE_STAR_DIM)
                * (math.sin(sphase + t * SKYLINE_STAR_SPEED) * 0.5 + 0.5)
            )
            ss.set_alpha(alpha)
            screen.blit(ss, (int(sx), int(sy)))

        # ---- Layer 3: flickering window lights --------------------------
        for win in self._windows:
            if win[1]:   # lit
                pygame.draw.rect(screen, win[3], win[0])

        # ---- Layer 4: aurora color overlay at 60 % opacity --------------
        c0 = _MUSIC_BG_COLORS[self._bg_idx]
        c1 = _MUSIC_BG_COLORS[(self._bg_idx + 1) % len(_MUSIC_BG_COLORS)]
        if self._aurora_surf is not None:
            self._aurora_surf.fill(_lerp_rgb(c0, c1, self._bg_t))
            screen.blit(self._aurora_surf, (0, 0))

        # Xylophone: bright "ping" flash at ripple origin
        for px, py, pa in self._pings:
            frac = pa / XYLOPHONE_PING_DURATION
            a = int(255 * (1.0 - frac))
            pr = max(1, int(XYLOPHONE_PING_RADIUS * (0.4 + 0.6 * frac)))
            dim = pr * 2 + 2
            psurf = pygame.Surface((dim, dim), pygame.SRCALPHA)
            pygame.draw.circle(psurf, (255, 255, 255, a), (pr + 1, pr + 1), pr)
            screen.blit(psurf, (px - pr - 1, py - pr - 1))

        for ripple in self.ripples:
            pop = _ripple_pop_scale(ripple.pop_age)
            r = max(1, int(ripple.radius * pop))
            alpha = max(0, min(255, int(ripple.alpha)))
            if alpha == 0:
                continue

            diameter = r * 2
            surf = pygame.Surface((diameter, diameter), pygame.SRCALPHA)
            rw = max(1, int(self._ring_width * pop)) if pop < 1.0 else self._ring_width
            if self._draw_square_ripple:
                # Synth: thick rounded-square outline (small corner radius = angular look)
                pygame.draw.rect(
                    surf,
                    (*ripple.color, alpha),
                    (0, 0, diameter, diameter),
                    width=rw,
                    border_radius=max(4, r // 5),
                )
            else:
                pygame.draw.circle(
                    surf,
                    (*ripple.color, alpha),
                    (r, r),
                    r,
                    width=rw,
                )
            screen.blit(surf, (ripple.x - r, ripple.y - r))

        for sp in self.sparkles:
            t = sp.age / self._sparkle_lifetime_sec
            a = int(255 * (1.0 - t))
            if a <= 0:
                continue
            sz = max(1.0, sp.size * (1.0 - 0.35 * t))
            pad = max(8, int(sz * 2.8) + 4)
            surf = pygame.Surface((pad, pad), pygame.SRCALPHA)
            cx = pad // 2
            cy = pad // 2
            pts = _star_points(float(cx), float(cy), sz)
            pygame.draw.polygon(
                surf,
                (*sp.color, a),
                [(int(p[0]), int(p[1])) for p in pts],
            )
            screen.blit(surf, (int(sp.x) - cx, int(sp.y) - cy))


def _star_points(cx: float, cy: float, radius: float) -> list[tuple[float, float]]:
    """4-point star / diamond for sparkles."""
    r = float(radius)
    return [
        (cx, cy - r),
        (cx + r * 0.55, cy),
        (cx, cy + r),
        (cx - r * 0.55, cy),
    ]


# -----------------------------------------------------------------------------
# EmojiTheme — floating emojis that fade out
# -----------------------------------------------------------------------------

BG_CONFETTI_COUNT = 35
BG_CONFETTI_RADIUS_MIN = 4.0
BG_CONFETTI_RADIUS_MAX = 8.0
BG_CONFETTI_SPEED_MIN = 20.0   # px / sec downward drift
BG_CONFETTI_SPEED_MAX = 45.0
BG_CONFETTI_SWAY_AMP_MIN = 8.0
BG_CONFETTI_SWAY_AMP_MAX = 24.0
BG_CONFETTI_SWAY_FREQ_MIN = 0.15  # Hz
BG_CONFETTI_SWAY_FREQ_MAX = 0.40
BG_CONFETTI_ALPHA = int(round(255 * 0.45))   # 45 % opacity ≈ 115
BG_CONFETTI_PALETTE: tuple[tuple[int, int, int], ...] = (
    (255, 205, 210),  # #ffcdd2
    (248, 187, 217),  # #f8bbd9
    (225, 190, 231),  # #e1bee7
    (187, 222, 251),  # #bbdefb
    (178, 223, 219),  # #b2dfdb
    (220, 237, 200),  # #dcedc8
    (255, 249, 196),  # #fff9c4
)

# Per-category solid color-shifting background palettes for EmojiTheme.
# Raw hex values defined here; processing applied below.
_EMOJI_BG_RAW: dict[str, tuple[tuple[int, int, int], ...]] = {
    "Animals": (
        (200, 230, 201),  # #c8e6c9 — soft green
        (220, 237, 200),  # #dcedc8 — light lime
        (255, 249, 196),  # #fff9c4 — warm yellow
        (255, 224, 178),  # #ffe0b2 — sandy beige
        (215, 204, 200),  # #d7ccc8 — warm gray
    ),
    "Food": (
        (255, 204, 188),  # #ffccbc — peach
        (255, 249, 196),  # #fff9c4 — cream yellow
        (248, 187, 217),  # #f8bbd9 — soft pink
        (255, 224, 178),  # #ffe0b2 — warm orange
    ),
    "Space": (
        ( 26,  26,  78),  # #1a1a4e — deep navy
        ( 45,  27, 105),  # #2d1b69 — dark purple
        ( 27,  42,  74),  # #1b2a4a — midnight blue
        ( 13,  33,  55),  # #0d2137 — near-black blue
        ( 26,  10,  46),  # #1a0a2e — deep indigo
    ),
    "Faces": (
        (255, 249, 196),  # #fff9c4 — sunny yellow
        (252, 228, 236),  # #fce4ec — soft pink
        (255, 243, 224),  # #fff3e0 — warm peach
        (243, 229, 245),  # #f3e5f5 — lavender
        (232, 245, 233),  # #e8f5e9 — mint
    ),
}

# Apply 60 % desaturation + 35 % brightness reduction (same recipe as MusicTheme).
# Space is intentionally left untouched — it is already very dark and muted.
_EMOJI_BG_PALETTES: dict[str, tuple[tuple[int, int, int], ...]] = {
    k: tuple(_darken(_desaturate(c, 0.60), 0.35) for c in v) if k != "Space" else v
    for k, v in _EMOJI_BG_RAW.items()
}
_EMOJI_BG_PALETTES["All"] = (
    _EMOJI_BG_PALETTES["Animals"]
    + _EMOJI_BG_PALETTES["Food"]
    + _EMOJI_BG_PALETTES["Space"]
    + _EMOJI_BG_PALETTES["Faces"]
)

# ---------------------------------------------------------------------------
# Sunny meadow background constants (EmojiTheme)   — all colours 20 % dimmer
# ---------------------------------------------------------------------------
MEADOW_SEED         = 7
MEADOW_HORIZON      = 0.60                       # reference fraction (clouds stay above)
# Sun — 30 % larger than original design, 20 % dimmer colour
MEADOW_SUN_CLR      = (204, 172,   0)            # #ffd700 × 0.80
MEADOW_SUN_R        = 78                         # 60 × 1.30
MEADOW_RAY_LEN      = 36                         # 28 × 1.30 — scaled proportionally
MEADOW_RAY_W        = 4
MEADOW_SUN_SPEED    = math.radians(10.0)         # radians per second
# Clouds — 20 % dimmer
MEADOW_CLOUD_CLR    = (192, 192, 192)            # #f0f0f0 × 0.80
MEADOW_CLOUD_ALPHA  = 204                        # ≈80 % of 255
MEADOW_CLOUD_SPEED  = 8.0                        # px/s leftward drift
# Rolling hills — 3 layers, already 20 % dimmed from the spec colours
MEADOW_HILL_BACK    = ( 98, 146,  58)            # #7ab648 × 0.80
MEADOW_HILL_MID     = ( 85, 138,  49)            # #6aad3d × 0.80
MEADOW_HILL_FRONT   = ( 72, 126,  38)            # #5a9e30 × 0.80
# Daytime sky colour-shift palette — 20 % dimmer, subtle & desaturated
_MEADOW_SKY_COLORS: tuple[tuple[int, int, int], ...] = (
    (108, 165, 188),  # #87ceeb × 0.80
    (141, 179, 204),  # #b0e0ff × 0.80
    (161, 186, 204),  # #c9e8ff × 0.80
    (134, 173, 187),  # #a8d8ea × 0.80
    (108, 165, 188),  # loop back
)
MEADOW_SKY_DURATION = 8.0                        # seconds per colour step


class _BgConfettiParticle:
    __slots__ = ("base_x", "y", "radius", "color", "speed", "sway_amp", "sway_freq", "phase")

    def __init__(
        self,
        base_x: float,
        y: float,
        radius: float,
        color: tuple[int, int, int],
        speed: float,
        sway_amp: float,
        sway_freq: float,
        phase: float,
    ) -> None:
        self.base_x = base_x
        self.y = y
        self.radius = radius
        self.color = color
        self.speed = speed
        self.sway_amp = sway_amp
        self.sway_freq = sway_freq
        self.phase = phase


class ConfettiParticle:
    __slots__ = ("x", "y", "vx", "vy", "age", "radius", "color")

    def __init__(
        self,
        x: float,
        y: float,
        vx: float,
        vy: float,
        radius: float,
        color: tuple[int, int, int],
    ) -> None:
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.age = 0.0
        self.radius = radius
        self.color = color


class EmojiSprite:
    __slots__ = ("x", "y", "char", "size", "age", "pop_age")

    def __init__(self, x: int, y: int, char: str, size: int) -> None:
        self.x = x
        self.y = y
        self.char = char
        self.size = size
        self.age = 0.0
        self.pop_age = 0.0


class EmojiTheme(Theme):
    """Random emojis on keypress; fade over ~3 seconds (FIFO cap)."""

    name = "Emoji"

    def __init__(
        self,
        screen: pygame.Surface,
        intensity: float = DEFAULT_INTENSITY,
        active_pack: str = "All",
    ) -> None:
        super().__init__(screen, intensity)
        self.emojis: list[EmojiSprite] = []
        self.confetti: list[ConfettiParticle] = []
        self._font_cache: dict[int, pygame.font.Font] = {}
        scale = self._intensity_scale
        self._max_emojis = max(1, int(MAX_EMOJIS * scale))
        self._size_min = max(16, int(EMOJI_SIZE_MIN * scale))
        self._size_max = max(self._size_min, int(EMOJI_SIZE_MAX * scale))
        self.active_pack: str = active_pack
        # Solid color-shifting background (same mechanic as MusicTheme)
        self._bg_pal_colors = _EMOJI_BG_PALETTES.get(active_pack, _EMOJI_BG_PALETTES["All"])
        self._bg_pal_idx: int = 0
        self._bg_pal_t: float = 0.0
        self._bg_pal_duration: float = _music_bg_transition_duration(intensity)
        # Background confetti particles
        self._bg_time = 0.0
        self._bg_particles: list[_BgConfettiParticle] = []
        _it = max(0.0, min(1.0, intensity))
        self._bg_count    = max(1, round(15 + 40 * _it))              # 15 → 35 → 55
        self._bg_speed_min = 15.0 + 25.0 * _it                        # 15 → 27.5 → 40
        self._bg_speed_max = 25.0 + 40.0 * _it                        # 25 → 45 → 65
        self._bg_radius_min = 4.0 + 2.0 * _it                         # 4 → 5 → 6
        self._bg_radius_max = 8.0 + 4.0 * _it                         # 8 → 10 → 12
        self._dim_overlay = pygame.Surface((self._screen_w, self._screen_h))
        self._dim_overlay.fill((0, 0, 0))
        self._init_bg_confetti(spread=True)
        # Sunny meadow background (built once at init)
        self._meadow_ground_surf: pygame.Surface | None = None
        self._meadow_time:    float = 0.0
        self._sun_angle:      float = 0.0
        self._sun_pos:        tuple[int, int] = (0, 0)
        self._meadow_sky_idx: int   = 0
        self._meadow_sky_t:   float = 0.0
        # Each cloud: [x, y, surf, blit_ox, blit_oy]
        self._clouds: list[list] = []
        self._build_meadow()

    def _init_bg_confetti(self, spread: bool = False) -> None:
        """Populate the background particle pool.  spread=True scatters
        particles across the full screen height so there is no empty-screen
        flash when the theme first loads."""
        self._bg_particles.clear()
        for _ in range(self._bg_count):
            y = (
                random.uniform(0.0, self._screen_h)
                if spread
                else -random.uniform(0.0, self._screen_h * 0.5)
            )
            self._bg_particles.append(self._make_bg_particle(
                x=random.uniform(0.0, float(self._screen_w)),
                y=y,
            ))

    def _make_bg_particle(self, x: float, y: float) -> _BgConfettiParticle:
        return _BgConfettiParticle(
            base_x=x,
            y=y,
            radius=random.uniform(self._bg_radius_min, self._bg_radius_max),
            color=random.choice(BG_CONFETTI_PALETTE),
            speed=random.uniform(self._bg_speed_min, self._bg_speed_max),
            sway_amp=random.uniform(BG_CONFETTI_SWAY_AMP_MIN, BG_CONFETTI_SWAY_AMP_MAX),
            sway_freq=random.uniform(BG_CONFETTI_SWAY_FREQ_MIN, BG_CONFETTI_SWAY_FREQ_MAX),
            phase=random.uniform(0.0, 2.0 * math.pi),
        )

    # ------------------------------------------------------------------
    # Meadow helpers
    # ------------------------------------------------------------------

    def _build_meadow(self) -> None:
        """Pre-bake rolling hills surface and generate clouds + sun position."""
        w, h = self._screen_w, self._screen_h
        rng = random.Random(MEADOW_SEED)

        # ---- Rolling hills (SRCALPHA — dynamic sky shows through above) -
        self._meadow_ground_surf = pygame.Surface((w, h), pygame.SRCALPHA)
        hill_specs = [
            # (color,           crest_frac, amplitude, freq,  phase)
            (MEADOW_HILL_BACK,  0.48,       55.0,      1.25,  0.0),
            (MEADOW_HILL_MID,   0.56,       42.0,      1.70,  0.9),
            (MEADOW_HILL_FRONT, 0.63,       32.0,      1.05,  1.7),
        ]
        n_pts = max(24, w // 3)
        for color, crest_frac, amp, freq, phase in hill_specs:
            crest_y = int(h * crest_frac)
            pts = []
            for i in range(n_pts + 1):
                x = int(i * w / n_pts)
                y = crest_y + int(amp * math.sin(freq * 2.0 * math.pi * i / n_pts + phase))
                pts.append((x, y))
            pts.append((w, h))
            pts.append((0, h))
            pygame.draw.polygon(self._meadow_ground_surf, color, pts)

        # ---- Sun position (upper-right quadrant) ------------------------
        self._sun_pos = (int(w * 0.82), int(h * 0.14))

        # ---- 8 clouds evenly spread across the sky, varied sizes --------
        self._clouds = []
        n_clouds = 8
        size_profiles = [40, 32, 50, 36, 46, 28, 44, 38]   # max_r per cloud
        for i in range(n_clouds):
            # Evenly space anchor within each screen slice, with small jitter
            slot_w = float(w) / n_clouds
            cx = rng.uniform(i * slot_w, (i + 1) * slot_w)
            cy = rng.uniform(h * 0.05, h * 0.38)
            max_r = size_profiles[i % len(size_profiles)] + rng.randint(-4, 4)
            n_circ = rng.randint(4, 7)
            circles: list[tuple[int, int, int]] = []
            x_off = 0
            for _ in range(n_circ):
                r = rng.randint(max(8, max_r - 12), max_r)
                circles.append((x_off + rng.randint(-8, 8), rng.randint(-10, 6), r))
                x_off += rng.randint(22, 38)
            xs_lo = [rx - r for rx, ry, r in circles]
            xs_hi = [rx + r for rx, ry, r in circles]
            ys_lo = [ry - r for rx, ry, r in circles]
            ys_hi = [ry + r for rx, ry, r in circles]
            min_x, max_x = min(xs_lo), max(xs_hi)
            min_y, max_y = min(ys_lo), max(ys_hi)
            sw = max(1, max_x - min_x + 4)
            sh = max(1, max_y - min_y + 4)
            csurf = pygame.Surface((sw, sh), pygame.SRCALPHA)
            for rx, ry, r in circles:
                pygame.draw.circle(
                    csurf,
                    (*MEADOW_CLOUD_CLR, MEADOW_CLOUD_ALPHA),
                    (rx - min_x + 2, ry - min_y + 2), r,
                )
            # cloud entry: [x, y, surf, blit_ox, blit_oy]
            self._clouds.append([cx, cy, csurf, min_x - 2, min_y - 2])

    def _draw_meadow(self, screen: pygame.Surface) -> None:
        """Draw the sunny meadow: colour-shifting sky, rolling hills, sun, clouds."""
        # 1. Sky — dynamic flat colour fill (crossfades through daytime palette)
        c0 = _MEADOW_SKY_COLORS[self._meadow_sky_idx]
        c1 = _MEADOW_SKY_COLORS[(self._meadow_sky_idx + 1) % len(_MEADOW_SKY_COLORS)]
        screen.fill(_lerp_rgb(c0, c1, self._meadow_sky_t))

        # 2. Sun + rotating rays (drawn before clouds so clouds can overlap)
        sx, sy = self._sun_pos
        pygame.draw.circle(screen, MEADOW_SUN_CLR, (sx, sy), MEADOW_SUN_R)
        for i in range(8):
            ang = self._sun_angle + (math.pi / 4) * i
            cos_a, sin_a = math.cos(ang), math.sin(ang)
            x1 = int(sx + cos_a * (MEADOW_SUN_R + 6))
            y1 = int(sy + sin_a * (MEADOW_SUN_R + 6))
            x2 = int(sx + cos_a * (MEADOW_SUN_R + MEADOW_RAY_LEN))
            y2 = int(sy + sin_a * (MEADOW_SUN_R + MEADOW_RAY_LEN))
            pygame.draw.line(screen, MEADOW_SUN_CLR, (x1, y1), (x2, y2), MEADOW_RAY_W)
            pygame.draw.circle(screen, MEADOW_SUN_CLR, (x2, y2), MEADOW_RAY_W // 2)

        # 3. Clouds (pre-rendered SRCALPHA surfs, drifting left)
        for cloud in self._clouds:
            screen.blit(
                cloud[2],
                (int(cloud[0]) + cloud[3], int(cloud[1]) + cloud[4]),
            )

        # 4. Rolling hills (SRCALPHA blit — transparent sky area shows fill above)
        if self._meadow_ground_surf is not None:
            screen.blit(self._meadow_ground_surf, (0, 0))

    def _on_clear(self) -> None:
        self.emojis.clear()
        self.confetti.clear()
        self._bg_time = 0.0
        self._bg_pal_idx = 0
        self._bg_pal_t = 0.0
        self._meadow_time = 0.0
        self._sun_angle = 0.0
        self._meadow_sky_idx = 0
        self._meadow_sky_t = 0.0
        self._init_bg_confetti(spread=True)

    def _font_for_size(self, size: int) -> pygame.font.Font:
        if size not in self._font_cache:
            self._font_cache[size] = pygame.font.SysFont(EMOJI_FONT_NAME, int(size * 1.3))
        return self._font_cache[size]

    def _spawn_confetti(self, cx: int, cy: int) -> None:
        n = _particle_count_for_intensity(self.intensity)
        t = max(0.0, min(1.0, self.intensity))
        r_lo = 12.0 + 4.0 * t
        r_hi = 16.0 + 4.0 * t
        for _ in range(n):
            ang = random.uniform(-math.pi * 0.35, math.pi * 0.35) - math.pi / 2
            spd = random.uniform(140.0, 320.0)
            vx = math.cos(ang) * spd
            vy = math.sin(ang) * spd
            r = random.uniform(r_lo, r_hi)
            base = random.choice(EMOJI_CONFETTI_PALETTE)
            dot_color = _apply_intensity_to_rgb(base, self.intensity)
            self.confetti.append(
                ConfettiParticle(float(cx), float(cy), vx, vy, r, dot_color)
            )

    def on_keypress(self, key: int) -> None:
        self._on_keypress_idle()
        del key
        play_pop_sound()

        if len(self.emojis) >= self._max_emojis:
            self.emojis.pop(0)
        x, y = self._random_position(margin=60)
        size = random.randint(self._size_min, self._size_max)
        self.emojis.append(EmojiSprite(x, y, random.choice(EMOJI_PACKS[self.active_pack]), size))
        self._spawn_confetti(x, y)

    def update(self, dt: float) -> None:
        self._advance_idle(dt)
        self._bg_time += dt

        # Meadow animation: sky colour cycle, sun rotation, cloud drift
        self._meadow_time += dt
        self._sun_angle += MEADOW_SUN_SPEED * dt
        self._meadow_sky_t += dt / MEADOW_SKY_DURATION
        if self._meadow_sky_t >= 1.0:
            self._meadow_sky_t -= 1.0
            self._meadow_sky_idx = (self._meadow_sky_idx + 1) % len(_MEADOW_SKY_COLORS)
        for cloud in self._clouds:
            cloud[0] -= MEADOW_CLOUD_SPEED * dt
            # Wrap when the cloud surface has fully exited the left edge
            surf_w = cloud[2].get_width()
            if int(cloud[0]) + cloud[3] + surf_w < 0:
                cloud[0] = float(self._screen_w - cloud[3])

        drift_mult = 1.0 - (1.0 - IDLE_EMOJI_DRIFT_FACTOR) * self._idle_factor
        for p in self._bg_particles:
            p.y += p.speed * drift_mult * dt
            if p.y > self._screen_h + p.radius:
                p.base_x = random.uniform(0.0, float(self._screen_w))
                p.y = -p.radius
                p.phase = random.uniform(0.0, 2.0 * math.pi)

        alive: list[EmojiSprite] = []
        for emoji in self.emojis:
            emoji.age += dt
            emoji.pop_age += dt
            if emoji.age < EMOJI_LIFETIME:
                alive.append(emoji)
        self.emojis = alive

        conf_alive: list[ConfettiParticle] = []
        for c in self.confetti:
            c.age += dt
            c.vy += CONFETTI_GRAVITY_PPS2 * dt
            c.x += c.vx * dt
            c.y += c.vy * dt
            if c.age < CONFETTI_LIFETIME_SEC:
                conf_alive.append(c)
        self.confetti = conf_alive

    def draw(self, screen: pygame.Surface) -> None:
        # Meadow background (drawn first, everything on top)
        self._draw_meadow(screen)

        for p in self._bg_particles:
            draw_x = p.base_x + p.sway_amp * math.sin(
                2.0 * math.pi * p.sway_freq * self._bg_time + p.phase
            )
            rad = max(1, int(p.radius))
            dim = rad * 2 + 2
            surf = pygame.Surface((dim, dim), pygame.SRCALPHA)
            pygame.draw.circle(surf, (*p.color, BG_CONFETTI_ALPHA), (rad + 1, rad + 1), rad)
            screen.blit(surf, (int(draw_x) - rad - 1, int(p.y) - rad - 1))

        if self._idle_factor > 0.0:
            self._dim_overlay.set_alpha(
                int(round(255 * IDLE_EMOJI_DIM_AMOUNT * self._idle_factor))
            )
            screen.blit(self._dim_overlay, (0, 0))

        for emoji in self.emojis:
            t = emoji.age / EMOJI_LIFETIME
            alpha = int(255 * (1.0 - t))
            if alpha <= 0:
                continue

            disp_scale = _emoji_display_scale(emoji.pop_age)
            disp_scale = max(0.05, disp_scale)

            font = self._font_for_size(emoji.size)
            text = font.render(emoji.char, True, (255, 255, 255))
            tw, th = text.get_size()
            nw = max(1, int(tw * disp_scale))
            nh = max(1, int(th * disp_scale))
            if nw != tw or nh != th:
                text = pygame.transform.smoothscale(text, (nw, nh))
            text.set_alpha(alpha)
            rect = text.get_rect(center=(emoji.x, emoji.y))
            screen.blit(text, rect)

        for c in self.confetti:
            u = c.age / CONFETTI_LIFETIME_SEC
            a = int(255 * (1.0 - u))
            if a <= 0:
                continue
            rad = max(1, int(c.radius))
            dim = rad * 2 + 2
            surf = pygame.Surface((dim, dim), pygame.SRCALPHA)
            pygame.draw.circle(surf, (*c.color, a), (rad + 1, rad + 1), rad)
            screen.blit(surf, (int(c.x) - rad - 1, int(c.y) - rad - 1))


# -----------------------------------------------------------------------------
# Theme switching
# -----------------------------------------------------------------------------

THEME_FACTORIES: dict[int, type[Theme]] = {
    pygame.K_F1: MusicTheme,
    pygame.K_F2: EmojiTheme,
}


def switch_theme(
    factory: type[Theme],
    screen: pygame.Surface,
    current: Theme | None,
) -> Theme:
    """Leave the old theme, instantiate a fresh one (empty state)."""
    intensity = current.intensity if current is not None else DEFAULT_INTENSITY
    if current is not None:
        current.clear()
    if factory is MusicTheme:
        return MusicTheme(screen, NOTE_SOUNDS, intensity)
    pack = current.active_pack if isinstance(current, EmojiTheme) else "All"
    return EmojiTheme(screen, intensity, pack)


def draw_theme_label(
    screen: pygame.Surface,
    label: str,
    hud_font: pygame.font.Font,
) -> None:
    text = hud_font.render(label, True, (180, 180, 180))
    screen.blit(text, (16, 12))


def draw_mode_pill(
    screen: pygame.Surface,
    theme: "Theme",
    font: pygame.font.Font,
) -> None:
    """Top-left corner indicator: current theme and sub-selection."""
    if isinstance(theme, MusicTheme):
        _instr_display = {
            "piano":     "Piano",
            "xylophone": "Xylophone",
            "synth":     "Synth",
            "harp":      "Harp",
        }
        label = "\u2669 " + _instr_display.get(theme.active_instrument, theme.active_instrument.title())
    elif isinstance(theme, EmojiTheme):
        _cat_display = {
            "All":     "All Emojis",
            "Animals": "Animals",
            "Food":    "Food",
            "Space":   "Space",
            "Faces":   "Faces",
        }
        label = _cat_display.get(theme.active_pack, theme.active_pack)
    else:
        return

    text_surf = font.render(label, True, (255, 255, 255))
    pad_x, pad_y = 11, 6
    # Use glyph height (ascent+|descent|) so pill height is tight to the text
    glyph_h = font.get_ascent() + abs(font.get_descent())
    pill_w   = text_surf.get_width() + pad_x * 2
    pill_h   = glyph_h + pad_y * 2
    pill     = pygame.Surface((pill_w, pill_h), pygame.SRCALPHA)
    _aa_rounded_rect(pill, (26, 26, 46, 179), pill.get_rect(), pill_h // 2)
    # Vertical: centre glyph, not the larger line-spacing surface
    ty = (pill_h - text_surf.get_height()) // 2
    pill.blit(text_surf, (pad_x, ty))
    screen.blit(pill, (16, 16))


# -----------------------------------------------------------------------------
# Windows notification suppression
# -----------------------------------------------------------------------------


class NotificationSuppressor:
    """
    Disable global toast notifications via registry while playing.
    Restores the previous value on leave_playing_state() / restore().
    """

    _REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Notifications\Settings"
    _REG_VALUE = "NOC_GLOBAL_SETTING_TOASTS_ENABLED"

    def __init__(self) -> None:
        self._original_value: int | None = None
        self._active = False

    def enable(self) -> bool:
        """Return True if suppression was applied."""
        if self._active:
            return True
        if sys.platform != "win32":
            return False
        try:
            import winreg

            access = winreg.KEY_READ | winreg.KEY_WRITE
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, self._REG_PATH, 0, access
            ) as key:
                try:
                    self._original_value, _ = winreg.QueryValueEx(
                        key, self._REG_VALUE
                    )
                except FileNotFoundError:
                    self._original_value = 1
                winreg.SetValueEx(key, self._REG_VALUE, 0, winreg.REG_DWORD, 0)
            self._active = True
            return True
        except OSError:
            self._original_value = None
            return False

    def restore(self) -> None:
        """Restore the registry value captured at enable()."""
        if not self._active or self._original_value is None:
            self._active = False
            return
        if sys.platform != "win32":
            self._active = False
            return
        try:
            import winreg

            access = winreg.KEY_READ | winreg.KEY_WRITE
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, self._REG_PATH, 0, access
            ) as key:
                winreg.SetValueEx(
                    key,
                    self._REG_VALUE,
                    0,
                    winreg.REG_DWORD,
                    int(self._original_value),
                )
        except OSError:
            pass
        finally:
            self._original_value = None
            self._active = False


def _broadcast_setting_change() -> None:
    """Tell Windows to reload policy settings after a registry change."""
    if sys.platform != "win32":
        return
    try:
        HWND_BROADCAST = 0xFFFF
        WM_SETTINGCHANGE = 0x001A
        SMTO_ABORTIFHUNG = 0x0002
        result = ctypes.c_ulong(0)
        ctypes.windll.user32.SendMessageTimeoutW(
            HWND_BROADCAST,
            WM_SETTINGCHANGE,
            0,
            "Policy",
            SMTO_ABORTIFHUNG,
            1000,
            ctypes.byref(result),
        )
    except OSError:
        pass


class WinKeySuppressor:
    """
    Registry safety net: NoWinKeys=1 disables Windows-key shortcuts in Explorer.
    Works alongside the keyboard hook; fails silently if the write is denied.
    """

    _REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Policies\Explorer"
    _REG_VALUE = "NoWinKeys"

    def __init__(self) -> None:
        self._original_value: int | None = None
        self._value_existed = False
        self._active = False

    def enable(self) -> bool:
        """Return True if NoWinKeys was set."""
        if self._active:
            return True
        if sys.platform != "win32":
            return False
        try:
            import winreg

            access = winreg.KEY_READ | winreg.KEY_WRITE
            with winreg.CreateKeyEx(
                winreg.HKEY_CURRENT_USER, self._REG_PATH, 0, access
            ) as key:
                try:
                    self._original_value, _ = winreg.QueryValueEx(
                        key, self._REG_VALUE
                    )
                    self._value_existed = True
                except FileNotFoundError:
                    self._original_value = None
                    self._value_existed = False
                winreg.SetValueEx(key, self._REG_VALUE, 0, winreg.REG_DWORD, 1)
            _broadcast_setting_change()
            self._active = True
            return True
        except OSError:
            self._original_value = None
            self._value_existed = False
            return False

    def restore(self) -> None:
        """Restore or delete NoWinKeys to match pre-session state."""
        if not self._active:
            return
        if sys.platform != "win32":
            self._active = False
            return
        try:
            import winreg

            access = winreg.KEY_READ | winreg.KEY_WRITE
            with winreg.CreateKeyEx(
                winreg.HKEY_CURRENT_USER, self._REG_PATH, 0, access
            ) as key:
                if self._value_existed and self._original_value is not None:
                    winreg.SetValueEx(
                        key,
                        self._REG_VALUE,
                        0,
                        winreg.REG_DWORD,
                        int(self._original_value),
                    )
                else:
                    try:
                        winreg.DeleteValue(key, self._REG_VALUE)
                    except FileNotFoundError:
                        pass
            _broadcast_setting_change()
        except OSError:
            pass
        finally:
            self._original_value = None
            self._value_existed = False
            self._active = False


class DisableLockWorkstationSuppressor:
    """
    Registry tweak: DisableLockWorkstation=1 blocks Win+L from locking the workstation.
    Applied during PLAYING alongside NoWinKeys; restored on unlock/exit.
    """

    _REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Policies\System"
    _REG_VALUE = "DisableLockWorkstation"

    def __init__(self) -> None:
        self._original_value: int | None = None
        self._value_existed = False
        self._active = False

    def enable(self) -> bool:
        if self._active:
            return True
        if sys.platform != "win32":
            return False
        try:
            import winreg

            access = winreg.KEY_READ | winreg.KEY_WRITE
            with winreg.CreateKeyEx(
                winreg.HKEY_CURRENT_USER, self._REG_PATH, 0, access
            ) as key:
                try:
                    self._original_value, _ = winreg.QueryValueEx(
                        key, self._REG_VALUE
                    )
                    self._value_existed = True
                except FileNotFoundError:
                    self._original_value = None
                    self._value_existed = False
                winreg.SetValueEx(key, self._REG_VALUE, 0, winreg.REG_DWORD, 1)
            _broadcast_setting_change()
            self._active = True
            return True
        except OSError:
            self._original_value = None
            self._value_existed = False
            return False

    def restore(self) -> None:
        if not self._active:
            return
        if sys.platform != "win32":
            self._active = False
            return
        try:
            import winreg

            access = winreg.KEY_READ | winreg.KEY_WRITE
            with winreg.CreateKeyEx(
                winreg.HKEY_CURRENT_USER, self._REG_PATH, 0, access
            ) as key:
                if self._value_existed and self._original_value is not None:
                    winreg.SetValueEx(
                        key,
                        self._REG_VALUE,
                        0,
                        winreg.REG_DWORD,
                        int(self._original_value),
                    )
                else:
                    try:
                        winreg.DeleteValue(key, self._REG_VALUE)
                    except FileNotFoundError:
                        pass
            _broadcast_setting_change()
        except OSError:
            pass
        finally:
            self._original_value = None
            self._value_existed = False
            self._active = False


# SystemParametersInfo: accessibility hotkeys (Sticky / Filter / Toggle Keys)
SPI_GETFILTERKEYS = 0x0032
SPI_SETFILTERKEYS = 0x0031
SPI_GETSTICKYKEYS = 0x003E
SPI_SETSTICKYKEYS = 0x003D
SPI_GETTOGGLEKEYS = 0x0034
SPI_SETTOGGLEKEYS = 0x0033
SPIF_UPDATEINIFILE = 0x01
SPIF_SENDCHANGE = 0x02
_SPIF_ACCESSIBILITY = SPIF_UPDATEINIFILE | SPIF_SENDCHANGE


class _FILTERKEYS(ctypes.Structure):
    _fields_ = (
        ("cbSize", ctypes.c_uint),
        ("dwFlags", ctypes.c_uint32),
        ("iWaitMSec", ctypes.c_uint32),
        ("iDelayMSec", ctypes.c_uint32),
        ("iRepeatMSec", ctypes.c_uint32),
        ("iBounceMSec", ctypes.c_uint32),
    )


class _STICKYKEYS(ctypes.Structure):
    _fields_ = (
        ("cbSize", ctypes.c_uint),
        ("dwFlags", ctypes.c_uint32),
    )


class _TOGGLEKEYS(ctypes.Structure):
    _fields_ = (
        ("cbSize", ctypes.c_uint),
        ("dwFlags", ctypes.c_uint32),
    )


class AccessibilityKeysSuppressor:
    """
    Temporarily clear FilterKeys / StickyKeys / ToggleKeys dwFlags (hotkeys off)
    during PLAYING via SystemParametersInfo; restores prior structs on exit.
    """

    def __init__(self) -> None:
        self._filter_saved: _FILTERKEYS | None = None
        self._sticky_saved: _STICKYKEYS | None = None
        self._toggle_saved: _TOGGLEKEYS | None = None
        self._filter_applied = False
        self._sticky_applied = False
        self._toggle_applied = False

    def enable(self) -> None:
        if self._filter_applied or self._sticky_applied or self._toggle_applied:
            return
        if sys.platform != "win32":
            return
        try:
            spi = ctypes.windll.user32.SystemParametersInfoW
        except (AttributeError, OSError):
            return
        try:
            fk = _FILTERKEYS()
            fk.cbSize = ctypes.sizeof(_FILTERKEYS)
            if spi(SPI_GETFILTERKEYS, 0, ctypes.byref(fk), 0):
                fk_off = _FILTERKEYS()
                ctypes.memmove(
                    ctypes.byref(fk_off),
                    ctypes.byref(fk),
                    ctypes.sizeof(_FILTERKEYS),
                )
                fk_off.dwFlags = 0
                if spi(
                    SPI_SETFILTERKEYS,
                    ctypes.sizeof(_FILTERKEYS),
                    ctypes.byref(fk_off),
                    _SPIF_ACCESSIBILITY,
                ):
                    snap = _FILTERKEYS()
                    ctypes.memmove(
                        ctypes.byref(snap),
                        ctypes.byref(fk),
                        ctypes.sizeof(_FILTERKEYS),
                    )
                    self._filter_saved = snap
                    self._filter_applied = True

            sk = _STICKYKEYS()
            sk.cbSize = ctypes.sizeof(_STICKYKEYS)
            if spi(SPI_GETSTICKYKEYS, 0, ctypes.byref(sk), 0):
                sk_off = _STICKYKEYS()
                ctypes.memmove(
                    ctypes.byref(sk_off),
                    ctypes.byref(sk),
                    ctypes.sizeof(_STICKYKEYS),
                )
                sk_off.dwFlags = 0
                if spi(
                    SPI_SETSTICKYKEYS,
                    ctypes.sizeof(_STICKYKEYS),
                    ctypes.byref(sk_off),
                    _SPIF_ACCESSIBILITY,
                ):
                    snap = _STICKYKEYS()
                    ctypes.memmove(
                        ctypes.byref(snap),
                        ctypes.byref(sk),
                        ctypes.sizeof(_STICKYKEYS),
                    )
                    self._sticky_saved = snap
                    self._sticky_applied = True

            tk = _TOGGLEKEYS()
            tk.cbSize = ctypes.sizeof(_TOGGLEKEYS)
            if spi(SPI_GETTOGGLEKEYS, 0, ctypes.byref(tk), 0):
                tk_off = _TOGGLEKEYS()
                ctypes.memmove(
                    ctypes.byref(tk_off),
                    ctypes.byref(tk),
                    ctypes.sizeof(_TOGGLEKEYS),
                )
                tk_off.dwFlags = 0
                if spi(
                    SPI_SETTOGGLEKEYS,
                    ctypes.sizeof(_TOGGLEKEYS),
                    ctypes.byref(tk_off),
                    _SPIF_ACCESSIBILITY,
                ):
                    snap = _TOGGLEKEYS()
                    ctypes.memmove(
                        ctypes.byref(snap),
                        ctypes.byref(tk),
                        ctypes.sizeof(_TOGGLEKEYS),
                    )
                    self._toggle_saved = snap
                    self._toggle_applied = True
        except OSError:
            pass

    def restore(self) -> None:
        if not (
            self._filter_applied
            or self._sticky_applied
            or self._toggle_applied
        ):
            self._reset_tracking()
            return
        if sys.platform != "win32":
            return
        try:
            spi = ctypes.windll.user32.SystemParametersInfoW
        except (AttributeError, OSError):
            self._reset_tracking()
            return
        try:
            if self._filter_applied and self._filter_saved is not None:
                spi(
                    SPI_SETFILTERKEYS,
                    ctypes.sizeof(_FILTERKEYS),
                    ctypes.byref(self._filter_saved),
                    _SPIF_ACCESSIBILITY,
                )
            if self._sticky_applied and self._sticky_saved is not None:
                spi(
                    SPI_SETSTICKYKEYS,
                    ctypes.sizeof(_STICKYKEYS),
                    ctypes.byref(self._sticky_saved),
                    _SPIF_ACCESSIBILITY,
                )
            if self._toggle_applied and self._toggle_saved is not None:
                spi(
                    SPI_SETTOGGLEKEYS,
                    ctypes.sizeof(_TOGGLEKEYS),
                    ctypes.byref(self._toggle_saved),
                    _SPIF_ACCESSIBILITY,
                )
        except OSError:
            pass
        finally:
            self._reset_tracking()

    def _reset_tracking(self) -> None:
        self._filter_saved = None
        self._sticky_saved = None
        self._toggle_saved = None
        self._filter_applied = False
        self._sticky_applied = False
        self._toggle_applied = False


# Extra block list for system shortcuts (hook suppress=True catches the rest).
# Ctrl+Alt+Del is a Secure Attention Sequence — it cannot be blocked by user-mode hooks.
_EXTRA_BLOCKED_KEYS: tuple[str, ...] = (
    "windows",
    "left windows",
    "right windows",
    "left alt",
    "right alt",
    "alt",
    "tab",
    "f4",
    "left ctrl",
    "right ctrl",
    "ctrl",
    "d",
    "l",
)

# Release these (and blocked keys) before unhook so held chords do not replay to Windows.
_HOOK_PRE_UNHOOK_RELEASE_SEC = 0.15
_KEYS_TO_RELEASE_BEFORE_UNHOOK: tuple[str, ...] = tuple(
    dict.fromkeys(
        (
            "ctrl",
            "left ctrl",
            "right ctrl",
            "shift",
            "left shift",
            "right shift",
            "alt",
            "left alt",
            "right alt",
            "windows",
            "left windows",
            "right windows",
            "q",
            "escape",
            "esc",
            "return",
            "enter",
        )
        + _EXTRA_BLOCKED_KEYS
    )
)

WM_CANCELMODE = 0x001F
HWND_BROADCAST = 0xFFFF

UNLOCK_HOLD_SECONDS = 2.0


def _is_ctrl_key_name(name: str) -> bool:
    return name in ("left ctrl", "right ctrl", "ctrl")


def _is_shift_key_name(name: str) -> bool:
    return name in ("left shift", "right shift", "shift")


def _is_unlock_combo_key_name(name: str) -> bool:
    """Keys that must not fire theme effects while Ctrl+Shift+Q is fully held."""
    return _is_ctrl_key_name(name) or _is_shift_key_name(name) or name == "q"


def _pygame_key_aliases() -> dict[str, int]:
    """Build name aliases once pygame constants are available."""
    aliases: dict[str, int] = {
        "escape": pygame.K_ESCAPE,
        "esc": pygame.K_ESCAPE,
        "return": pygame.K_RETURN,
        "enter": pygame.K_RETURN,
    }
    left = getattr(pygame, "K_LWIN", getattr(pygame, "K_LGUI", getattr(pygame, "K_LMETA", None)))
    right = getattr(pygame, "K_RWIN", getattr(pygame, "K_RGUI", getattr(pygame, "K_RMETA", None)))
    if left is not None:
        aliases["windows"] = left
        aliases["left windows"] = left
    if right is not None:
        aliases["right windows"] = right
    return aliases


class KeyboardLockdown:
    """
    Global keyboard hook: swallow keys so Windows/other apps never see them,
    queue KEY_DOWN events for the main thread to dispatch to the active theme.
    Tracks Ctrl+Shift+Q held 2s for parent unlock (no theme events for those keys).
    """

    def __init__(self) -> None:
        self._hook: Callable[..., Any] | None = None
        self._queue: queue.SimpleQueue[int] = queue.SimpleQueue()
        self._installed = False
        self._blocked: list[str] = []
        self._combo_lock = threading.Lock()
        self._held_key_names: set[str] = set()
        self._combo_start_mono: float | None = None
        self._unlock_requested = False

    def install(self) -> None:
        if self._installed:
            return
        with self._combo_lock:
            self._held_key_names.clear()
            self._combo_start_mono = None
            self._unlock_requested = False
        import keyboard

        self._hook = keyboard.hook(self._on_key_event, suppress=True)
        for key_name in _EXTRA_BLOCKED_KEYS:
            try:
                keyboard.block_key(key_name)
                self._blocked.append(key_name)
            except (ValueError, OSError):
                pass
        self._installed = True

    def remove(self) -> None:
        """Tear down hook: flush held keys, wait, unhook, then WM_CANCELMODE (Windows)."""
        try:
            import keyboard
        except ImportError:
            keyboard = None  # type: ignore[assignment]

        had_hook_activity = (
            self._installed
            or self._hook is not None
            or len(self._blocked) > 0
        )

        if keyboard is not None and had_hook_activity:
            try:
                for key_name in _KEYS_TO_RELEASE_BEFORE_UNHOOK:
                    try:
                        keyboard.release(key_name)
                    except (ValueError, OSError, RuntimeError):
                        pass
                time.sleep(_HOOK_PRE_UNHOOK_RELEASE_SEC)
            except Exception:
                pass

        try:
            if keyboard is not None:
                if self._hook is not None:
                    try:
                        keyboard.unhook(self._hook)
                    except (RuntimeError, ValueError, OSError):
                        pass
                    self._hook = None
                try:
                    keyboard.unhook_all()
                except (RuntimeError, ValueError, OSError, AttributeError):
                    pass
                for key_name in list(self._blocked):
                    with suppress_key_errors():
                        keyboard.unblock_key(key_name)
        except Exception:
            pass
        self._blocked.clear()
        while True:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break
        with self._combo_lock:
            self._held_key_names.clear()
            self._combo_start_mono = None
            self._unlock_requested = False
        self._installed = False

        if sys.platform == "win32":
            try:
                ctypes.windll.user32.PostMessageW(
                    HWND_BROADCAST, WM_CANCELMODE, 0, 0
                )
            except OSError:
                pass

    def drain(self) -> list[int]:
        keys: list[int] = []
        while True:
            try:
                keys.append(self._queue.get_nowait())
            except queue.Empty:
                break
        return keys

    def consume_unlock_request(self) -> bool:
        with self._combo_lock:
            if self._unlock_requested:
                self._unlock_requested = False
                return True
            return False

    def get_unlock_overlay(self) -> tuple[str, str] | None:
        """
        While Ctrl+Shift+Q is fully held: ('Unlocking...', '2s' | '1s').
        None if not held or hold completed (about to unlock).
        """
        with self._combo_lock:
            if not self._unlock_combo_held_locked():
                return None
            if self._combo_start_mono is None:
                return ("Unlocking...", "2s")
            elapsed = time.monotonic() - self._combo_start_mono
            if elapsed >= UNLOCK_HOLD_SECONDS:
                return None
            remaining = max(1, math.ceil(UNLOCK_HOLD_SECONDS - elapsed))
            return ("Unlocking...", f"{remaining}s")

    def _unlock_combo_held_locked(self) -> bool:
        h = self._held_key_names
        ctrl = bool(
            h & {"left ctrl", "right ctrl", "ctrl"}
        )
        shift = bool(
            h & {"left shift", "right shift", "shift"}
        )
        q_down = "q" in h
        return ctrl and shift and q_down

    def _update_unlock_combo_state_locked(self) -> None:
        if self._unlock_combo_held_locked():
            if self._combo_start_mono is None:
                self._combo_start_mono = time.monotonic()
            elif (
                time.monotonic() - self._combo_start_mono >= UNLOCK_HOLD_SECONDS
                and not self._unlock_requested
            ):
                self._unlock_requested = True
        else:
            self._combo_start_mono = None

    def _on_key_event(self, event: Any) -> None:
        import keyboard

        name = (event.name or "").strip().lower()
        with self._combo_lock:
            if event.event_type == keyboard.KEY_DOWN:
                if name:
                    self._held_key_names.add(name)
            elif event.event_type == keyboard.KEY_UP:
                if name:
                    self._held_key_names.discard(name)
            self._update_unlock_combo_state_locked()
            combo_held = self._unlock_combo_held_locked()

        if event.event_type != keyboard.KEY_DOWN:
            return
        pygame_key = keyboard_event_to_pygame_key(event)
        if pygame_key is None:
            return
        if pygame_key == pygame.K_ESCAPE:
            return
        if combo_held and _is_unlock_combo_key_name(name):
            return
        self._queue.put(pygame_key)


class suppress_key_errors:
    """Context manager to ignore keyboard library errors during cleanup."""

    def __enter__(self) -> None:
        return None

    def __exit__(self, *args: object) -> bool:
        return True


def keyboard_event_to_pygame_key(event: Any) -> int | None:
    """Map a keyboard library event to a pygame key constant."""
    name = (event.name or "").strip().lower()
    if not name:
        return None
    aliases = _pygame_key_aliases()
    if name in aliases:
        return aliases[name]
    try:
        return pygame.key.key_code(name)
    except ValueError:
        return None


def leave_playing_state(
    notification_suppressor: NotificationSuppressor,
    keyboard_lockdown: KeyboardLockdown,
    win_key_suppressor: WinKeySuppressor,
    lock_workstation_suppressor: DisableLockWorkstationSuppressor,
    accessibility_keys_suppressor: AccessibilityKeysSuppressor,
) -> None:
    """Call when exiting PLAYING (return to setup or quit)."""
    keyboard_lockdown.remove()
    win_key_suppressor.restore()
    lock_workstation_suppressor.restore()
    accessibility_keys_suppressor.restore()
    notification_suppressor.restore()


# Populated in main(); used by try/finally and atexit (idempotent cleanup).
_SESSION_CLEANUP_ARGS: tuple[Any, ...] | None = None
_ATEXIT_SESSION_CLEANUP_REGISTERED = False


def _run_full_session_cleanup() -> None:
    """
    Remove keyboard hook, restore NoWinKeys / DisableLockWorkstation,
    restore accessibility SPI, restore notification policy.
    Safe to call multiple times (e.g. unlock + finally + atexit).
    """
    global _SESSION_CLEANUP_ARGS
    if _SESSION_CLEANUP_ARGS is None:
        return
    try:
        leave_playing_state(*_SESSION_CLEANUP_ARGS)
    except Exception:
        pass


def enter_playing_state(
    notification_suppressor: NotificationSuppressor,
    keyboard_lockdown: KeyboardLockdown,
    win_key_suppressor: WinKeySuppressor,
    lock_workstation_suppressor: DisableLockWorkstationSuppressor,
    accessibility_keys_suppressor: AccessibilityKeysSuppressor,
    suppress: bool,
) -> None:
    """Install keyboard lockdown, registry blocks, accessibility SPI, optional toast mute."""
    keyboard_lockdown.install()
    win_key_suppressor.enable()
    lock_workstation_suppressor.enable()
    accessibility_keys_suppressor.enable()
    if suppress:
        notification_suppressor.enable()


# -----------------------------------------------------------------------------
# Settings persistence (settings.json beside main.py)
# -----------------------------------------------------------------------------

SETTINGS_PATH = Path(__file__).resolve().parent / "settings.json"


class AppSettings(NamedTuple):
    volume: float
    intensity: float
    suppress_notifications: bool
    emoji_category: str
    music_instrument: str


def default_settings() -> AppSettings:
    return AppSettings(
        DEFAULT_VOLUME,
        DEFAULT_INTENSITY,
        DEFAULT_SUPPRESS_NOTIFICATIONS,
        "All",
        "piano",
    )


def _clamp_unit_float(value: Any, fallback: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return fallback
    return max(0.0, min(1.0, number))


def _parse_bool(value: Any, fallback: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    return fallback


def save_settings(settings: AppSettings) -> None:
    try:
        payload = {
            "volume": settings.volume,
            "intensity": settings.intensity,
            "suppress_notifications": settings.suppress_notifications,
            "emoji_category": settings.emoji_category,
            "music_instrument": settings.music_instrument,
        }
        with SETTINGS_PATH.open("w", encoding="utf-8") as file:
            json.dump(payload, file, indent=2)
            file.write("\n")
    except OSError:
        pass


def load_settings() -> AppSettings:
    """Load settings or write defaults if missing / invalid."""
    defaults = default_settings()
    try:
        if SETTINGS_PATH.exists():
            with SETTINGS_PATH.open(encoding="utf-8") as file:
                data = json.load(file)
            if isinstance(data, dict):
                raw_cat = str(data.get("emoji_category", "All"))
                emoji_cat = raw_cat if raw_cat in EMOJI_PACKS else "All"
                raw_instr = str(data.get("music_instrument", "piano"))
                music_instr = raw_instr if raw_instr in _INSTRUMENT_KEY.values() else "piano"
                settings = AppSettings(
                    _clamp_unit_float(data.get("volume"), defaults.volume),
                    _clamp_unit_float(data.get("intensity"), defaults.intensity),
                    _parse_bool(
                        data.get("suppress_notifications"),
                        defaults.suppress_notifications,
                    ),
                    emoji_cat,
                    music_instr,
                )
                save_settings(settings)
                return settings
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        pass
    save_settings(defaults)
    return defaults


# -----------------------------------------------------------------------------
# Stress test (developer / parent tool — F7 from SETUP)
# -----------------------------------------------------------------------------


class StressTestResult(NamedTuple):
    flash_rate_hz: float
    avg_fps: float
    min_fps: float
    max_fps: float
    peak_brightness_delta: float
    red_spike_count: int
    passed: bool
    timestamp: str
    theme_label: str


class FlashRateTracker:
    """
    WCAG 2.3.1 general-flash detector.
    A flash = a pair of opposing relative-luminance changes >= threshold.
    Reports the maximum number of such events in any 1-second window.
    """

    def __init__(self, threshold: float = STRESS_BRIGHTNESS_THRESHOLD) -> None:
        self._threshold = threshold
        self._last_significant: float | None = None
        self._last_direction: int = 0   # +1 rising, -1 falling, 0 unknown
        self._flash_times: list[float] = []

    def update(self, luma: float, t: float) -> None:
        if self._last_significant is None:
            self._last_significant = luma
            return
        delta = luma - self._last_significant
        if abs(delta) >= self._threshold:
            direction = 1 if delta > 0 else -1
            if self._last_direction != 0 and direction != self._last_direction:
                self._flash_times.append(t)
            self._last_direction = direction
            self._last_significant = luma

    def peak_hz(self) -> float:
        """Maximum flash count in any 1-second window."""
        if len(self._flash_times) < 2:
            return 0.0
        best = 0
        for i, t0 in enumerate(self._flash_times):
            count = sum(1 for ts in self._flash_times[i:] if ts < t0 + 1.0)
            best = max(best, count)
        return float(best)


def _measure_screen(screen: pygame.Surface) -> tuple[float, bool]:
    """
    Downsample surface to STRESS_SAMPLE_SIZE, return (avg_luma_0_1, red_spike).
    Red spike: avg R > STRESS_RED_R_MIN and dominates G and B by STRESS_RED_RATIO.
    """
    small = pygame.transform.scale(screen, STRESS_SAMPLE_SIZE)
    arr = pygame.surfarray.array3d(small).astype(np.float32)
    avg_r = float(arr[:, :, 0].mean())
    avg_g = float(arr[:, :, 1].mean())
    avg_b = float(arr[:, :, 2].mean())
    luma = (avg_r * 0.299 + avg_g * 0.587 + avg_b * 0.114) / 255.0
    red_spike = (
        avg_r > STRESS_RED_R_MIN
        and avg_g > 0
        and avg_b > 0
        and avg_r > avg_g * STRESS_RED_RATIO
        and avg_r > avg_b * STRESS_RED_RATIO
    )
    return luma, red_spike


def _make_stress_theme(factory: type[Theme], screen: pygame.Surface) -> Theme:
    """Construct a max-intensity theme for stress testing."""
    if factory is MusicTheme:
        return MusicTheme(screen, NOTE_SOUNDS, 1.0)
    return factory(screen, 1.0)


class StressTestRunner:
    """
    Drives the 15-second developer stress test: synthetic keypresses at maximum
    rate, rapid theme cycling, intensity = 1.0.  Records brightness / FPS /
    flash / red-spike data each frame.  Audio is silenced for the duration.

    Pass theme_factory to test a single theme; pass None to cycle both.
    """

    _ALL_KEYS: tuple[int, ...] = tuple(range(pygame.K_a, pygame.K_z + 1)) + (
        pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5,
    )

    def __init__(
        self,
        screen: pygame.Surface,
        theme_factory: type[Theme] | None = None,
    ) -> None:
        self._saved_volume = CURRENT_PLAY_VOLUME
        apply_session_volume(0.0)
        self._elapsed = 0.0
        self._key_timer = 0.0
        self._theme_timer = 0.0
        self._theme_idx = 0
        if theme_factory is not None:
            self._themes: list[Theme] = [_make_stress_theme(theme_factory, screen)]
            self._theme_label = theme_factory.name if hasattr(theme_factory, "name") else "Custom"
        else:
            self._themes = [
                MusicTheme(screen, NOTE_SOUNDS, 1.0),
                EmojiTheme(screen, 1.0),
            ]
            self._theme_label = "Music + Emoji"
        self._flash = FlashRateTracker()
        self._fps_samples: list[float] = []
        self._peak_delta = 0.0
        self._red_spikes = 0
        self._last_luma: float | None = None

    @property
    def elapsed(self) -> float:
        return self._elapsed

    @property
    def done(self) -> bool:
        return self._elapsed >= STRESS_TEST_DURATION_SEC

    @property
    def progress(self) -> float:
        return min(1.0, self._elapsed / STRESS_TEST_DURATION_SEC)

    def _current_theme(self) -> Theme:
        return self._themes[self._theme_idx]

    def update(self, dt: float) -> None:
        self._elapsed = min(self._elapsed + dt, STRESS_TEST_DURATION_SEC)

        self._key_timer += dt
        while self._key_timer >= STRESS_TEST_KEY_INTERVAL_SEC:
            self._key_timer -= STRESS_TEST_KEY_INTERVAL_SEC
            self._current_theme().on_keypress(random.choice(self._ALL_KEYS))

        self._theme_timer += dt
        if self._theme_timer >= STRESS_TEST_THEME_INTERVAL_SEC:
            self._theme_timer -= STRESS_TEST_THEME_INTERVAL_SEC
            self._theme_idx = (self._theme_idx + 1) % len(self._themes)

        self._current_theme().update(dt)

        if dt > 0:
            self._fps_samples.append(min(1.0 / dt, 9999.0))

    def draw(self, screen: pygame.Surface) -> None:
        screen.fill(BACKGROUND_COLOR)
        self._current_theme().draw(screen)

    def measure(self, screen: pygame.Surface) -> None:
        """Capture per-frame brightness metrics; call after draw(), before flip()."""
        luma, red_spike = _measure_screen(screen)
        self._flash.update(luma, self._elapsed)
        if self._last_luma is not None:
            delta = abs(luma - self._last_luma)
            self._peak_delta = max(self._peak_delta, delta)
        self._last_luma = luma
        if red_spike:
            self._red_spikes += 1

    def finish(self) -> StressTestResult:
        apply_session_volume(self._saved_volume)
        samples = self._fps_samples or [0.0]
        flash_hz = self._flash.peak_hz()
        return StressTestResult(
            flash_rate_hz=flash_hz,
            avg_fps=sum(samples) / len(samples),
            min_fps=min(samples),
            max_fps=max(samples),
            peak_brightness_delta=self._peak_delta,
            red_spike_count=self._red_spikes,
            passed=flash_hz <= STRESS_TEST_FLASH_LIMIT_HZ,
            timestamp=time.strftime("%Y-%m-%dT%H-%M-%S"),
            theme_label=self._theme_label,
        )


def _stress_log_path() -> Path:
    local_appdata = os.environ.get("LOCALAPPDATA", "")
    base = Path(local_appdata) if local_appdata else Path.home() / "AppData" / "Local"
    return base / _LOG_APP_DIR / _LOG_SUBDIR


def write_stress_log(result: StressTestResult) -> Path | None:
    """Write results to %LOCALAPPDATA%\\KeyboardMasher\\logs\\stress_<ts>.log."""
    try:
        log_dir = _stress_log_path()
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"stress_{result.timestamp}.log"
        flash_pass = result.flash_rate_hz <= STRESS_TEST_FLASH_LIMIT_HZ
        lines = [
            f"KeyboardMasher Stress Test  {result.timestamp}",
            f"Theme: {result.theme_label}",
            "=" * 52,
            f"Overall result: {'PASS' if result.passed else 'FAIL'}",
            "",
            (
                f"  Flash rate        {result.flash_rate_hz:.2f} Hz"
                f"  (limit {STRESS_TEST_FLASH_LIMIT_HZ:.1f} Hz)"
                f"  {'PASS' if flash_pass else 'FAIL'}"
            ),
            f"  Avg FPS           {result.avg_fps:.1f}",
            f"  Min FPS           {result.min_fps:.1f}",
            f"  Max FPS           {result.max_fps:.1f}",
            f"  Peak brightness \u0394 {result.peak_brightness_delta:.4f}",
            f"  Red spike frames  {result.red_spike_count}",
            "",
            "Safe to ship." if result.passed else "Review flagged items before shipping.",
        ]
        log_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return log_file
    except OSError:
        return None


def draw_stress_test_hud(
    screen: pygame.Surface,
    runner: StressTestRunner,
    font: pygame.font.Font,
) -> None:
    """Progress bar + countdown label rendered over the stress-test visuals."""
    w, h = screen.get_size()
    bar_h = 8
    pygame.draw.rect(screen, (40, 40, 40), (0, h - bar_h, w, bar_h))
    fill_w = int(w * runner.progress)
    pygame.draw.rect(screen, SETUP_ACCENT, (0, h - bar_h, fill_w, bar_h))
    remaining = max(0.0, STRESS_TEST_DURATION_SEC - runner.elapsed)
    label = font.render(
        f"Stress Test  \u2014  {remaining:.1f}s remaining", True, (220, 220, 220)
    )
    screen.blit(label, (12, h - bar_h - label.get_height() - 8))


def draw_stress_results(
    screen: pygame.Surface,
    result: StressTestResult,
    big_font: pygame.font.Font,
    med_font: pygame.font.Font,
    sm_font: pygame.font.Font,
) -> None:
    """Full-screen overlay showing the stress test report."""
    w, h = screen.get_size()

    dim = pygame.Surface((w, h), pygame.SRCALPHA)
    dim.fill((12, 12, 20, 220))
    screen.blit(dim, (0, 0))

    panel_w = min(660, w - 80)
    panel_h = 460
    panel_rect = pygame.Rect(0, 0, panel_w, panel_h)
    panel_rect.center = (w // 2, h // 2)
    panel_surf = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
    pygame.draw.rect(
        panel_surf, (28, 28, 42, 245), panel_surf.get_rect(), border_radius=20
    )
    pygame.draw.rect(
        panel_surf,
        (80, 80, 120, 180),
        panel_surf.get_rect(),
        width=2,
        border_radius=20,
    )
    screen.blit(panel_surf, panel_rect.topleft)

    cx = panel_rect.centerx
    y = panel_rect.top + 28

    hdr_surf = med_font.render("STRESS TEST RESULTS", True, (180, 180, 220))
    screen.blit(hdr_surf, hdr_surf.get_rect(centerx=cx, top=y))
    y += hdr_surf.get_height() + 4

    theme_surf = sm_font.render(f"Theme: {result.theme_label}", True, (140, 140, 170))
    screen.blit(theme_surf, theme_surf.get_rect(centerx=cx, top=y))
    y += theme_surf.get_height() + 8

    verdict_text = "PASS" if result.passed else "FAIL"
    verdict_color = (80, 220, 100) if result.passed else (230, 60, 60)
    verdict_surf = big_font.render(verdict_text, True, verdict_color)
    screen.blit(verdict_surf, verdict_surf.get_rect(centerx=cx, top=y))
    y += verdict_surf.get_height() + 14

    flash_pass = result.flash_rate_hz <= STRESS_TEST_FLASH_LIMIT_HZ
    detail_rows: list[tuple[str, tuple[int, int, int]]] = [
        (
            (
                f"Flash rate:  {result.flash_rate_hz:.2f} Hz"
                f"  (limit: {STRESS_TEST_FLASH_LIMIT_HZ:.1f} Hz)"
                f"  \u2014  {'PASS' if flash_pass else 'FAIL'}"
            ),
            (80, 220, 100) if flash_pass else (230, 60, 60),
        ),
        (
            f"Avg FPS: {result.avg_fps:.1f}   Min FPS: {result.min_fps:.1f}",
            (200, 200, 200),
        ),
        (
            f"Peak brightness \u0394: {result.peak_brightness_delta:.3f}",
            (200, 200, 200),
        ),
        (
            f"Red spike frames: {result.red_spike_count}",
            (230, 130, 60) if result.red_spike_count > 0 else (200, 200, 200),
        ),
    ]
    for text, color in detail_rows:
        s = med_font.render(text, True, color)
        screen.blit(s, s.get_rect(centerx=cx, top=y))
        y += s.get_height() + 10

    y += 8
    note_text = (
        "Safe to ship."
        if result.passed
        else "Review flagged items before shipping."
    )
    note_color = (80, 210, 100) if result.passed else (240, 180, 60)
    note_surf = med_font.render(note_text, True, note_color)
    screen.blit(note_surf, note_surf.get_rect(centerx=cx, top=y))
    y += note_surf.get_height() + 14

    hint = sm_font.render("Press any key to return to setup.", True, (110, 110, 135))
    screen.blit(hint, hint.get_rect(centerx=cx, top=y))


# -----------------------------------------------------------------------------
# App state
# -----------------------------------------------------------------------------


class AppState(Enum):
    SETUP = auto()
    PLAYING = auto()
    STRESS_TEST = auto()
    STRESS_RESULTS = auto()


class _ThemeTile:
    __slots__ = ("emoji", "label", "subtitle", "factory", "emoji_color")

    def __init__(
        self,
        emoji: str,
        label: str,
        subtitle: str,
        factory: type[Theme],
        emoji_color: tuple[int, int, int] = (255, 255, 255),
    ) -> None:
        self.emoji = emoji
        self.label = label
        self.subtitle = subtitle
        self.factory = factory
        self.emoji_color = emoji_color


_THEME_TILES: tuple[_ThemeTile, ...] = (
    _ThemeTile("🎵", "Music", "Notes", MusicTheme, (204, 204, 204)),  # #cccccc
    _ThemeTile("🎊", "Emoji", "Fun emojis", EmojiTheme),
)


class SessionConfig(NamedTuple):
    theme_factory: type[Theme]
    volume: float
    intensity: float
    suppress_notifications: bool
    emoji_category: str
    music_instrument: str


def _lerp_rgb(
    a: tuple[int, int, int], b: tuple[int, int, int], t: float
) -> tuple[int, int, int]:
    t = max(0.0, min(1.0, t))
    return (
        int(round(float(a[0]) + (float(b[0]) - float(a[0])) * t)),
        int(round(float(a[1]) + (float(b[1]) - float(a[1])) * t)),
        int(round(float(a[2]) + (float(b[2]) - float(a[2])) * t)),
    )


def _aa_rounded_rect(
    surf: pygame.Surface,
    color: tuple,
    rect,
    radius: int,
) -> None:
    """Anti-aliased filled rounded rectangle via 4× supersampling + smoothscale."""
    if isinstance(rect, pygame.Rect):
        x, y, w, h = rect.x, rect.y, rect.w, rect.h
    else:
        x, y, w, h = int(rect[0]), int(rect[1]), int(rect[2]), int(rect[3])
    if w <= 0 or h <= 0:
        return
    scale = 4
    big = pygame.Surface((w * scale, h * scale), pygame.SRCALPHA)
    pygame.draw.rect(big, color, big.get_rect(), border_radius=radius * scale)
    small = pygame.transform.smoothscale(big, (w, h))
    surf.blit(small, (x, y))


# Setup screen animated background — dark navy with visible blue tones
_SETUP_BG_COLORS: tuple[tuple[int, int, int], ...] = (
    (26,  26,  46),  # #1a1a2e
    (22,  33,  62),  # #16213e
    (31,  43,  94),  # #1f2b5e
    (45,  45,  94),  # #2d2d5e
    (26,  26,  62),  # #1a1a3e
    (26,  26,  46),  # loop back
)
_SETUP_BG_DURATION = 8.0   # seconds per colour step


class SetupNotificationToggle:
    """Mobile-style ON/OFF pill toggle for notification suppression."""

    def __init__(
        self,
        center_x: int,
        top: int,
        label_font: pygame.font.Font,
        *,
        enabled: bool = DEFAULT_SUPPRESS_NOTIFICATIONS,
    ) -> None:
        self.enabled = enabled
        self._label_font = label_font
        self._center_x = center_x
        self._top = top
        self.label_rect = pygame.Rect(0, 0, 0, 0)
        self.pill_rect = pygame.Rect(0, 0, 0, 0)
        self.hit_rect = pygame.Rect(0, 0, 0, 0)
        self._layout()

    def _layout(self) -> None:
        label_surf = self._label_font.render(NOTIFY_TOGGLE_LABEL, True, (255, 255, 255))
        gap = 16
        row_w = label_surf.get_width() + gap + SETUP_TOGGLE_WIDTH
        left = self._center_x - row_w // 2
        self.label_rect = label_surf.get_rect(topleft=(left, self._top))
        self.pill_rect = pygame.Rect(
            self.label_rect.right + gap,
            self._top + (self.label_rect.height - SETUP_TOGGLE_HEIGHT) // 2,
            SETUP_TOGGLE_WIDTH,
            SETUP_TOGGLE_HEIGHT,
        )
        self.hit_rect = self.label_rect.union(self.pill_rect).inflate(10, 10)

    def contains_point(self, pos: tuple[int, int]) -> bool:
        return self.hit_rect.collidepoint(pos)

    def toggle(self) -> None:
        self.enabled = not self.enabled

    def draw(self, screen: pygame.Surface) -> None:
        label_surf = self._label_font.render(NOTIFY_TOGGLE_LABEL, True, (255, 255, 255))
        screen.blit(label_surf, self.label_rect)

        pill_color = (
            SETUP_TOGGLE_ON_COLOR if self.enabled else SETUP_TOGGLE_OFF_COLOR
        )
        pygame.draw.rect(
            screen,
            pill_color,
            self.pill_rect,
            border_radius=SETUP_TOGGLE_HEIGHT // 2,
        )

        margin = 3
        handle_radius = (SETUP_TOGGLE_HEIGHT - margin * 2) // 2
        handle_x = (
            self.pill_rect.right - margin - handle_radius
            if self.enabled
            else self.pill_rect.left + margin + handle_radius
        )
        pygame.draw.circle(
            screen,
            SETUP_TOGGLE_HANDLE_COLOR,
            (handle_x, self.pill_rect.centery),
            handle_radius,
        )


class SetupSlider:
    """Horizontal slider: label | track | percentage."""

    def __init__(
        self,
        label: str,
        value: float,
        center_x: int,
        top: int,
        label_font: pygame.font.Font,
        value_font: pygame.font.Font,
    ) -> None:
        self.label = label
        self.value = max(0.0, min(1.0, value))
        self._label_font = label_font
        self._value_font = value_font
        self._center_x = center_x
        self._top = top
        self._layout()

    def _layout(self) -> None:
        row_w = (
            SETUP_SLIDER_LABEL_WIDTH
            + SETUP_SLIDER_TRACK_WIDTH
            + 56
        )
        left = self._center_x - row_w // 2
        self.label_rect = pygame.Rect(
            left,
            self._top,
            SETUP_SLIDER_LABEL_WIDTH,
            SETUP_SLIDER_ROW_HEIGHT,
        )
        track_top = self._top + (SETUP_SLIDER_ROW_HEIGHT - SETUP_SLIDER_TRACK_HEIGHT) // 2
        self.track_rect = pygame.Rect(
            left + SETUP_SLIDER_LABEL_WIDTH,
            track_top,
            SETUP_SLIDER_TRACK_WIDTH,
            SETUP_SLIDER_TRACK_HEIGHT,
        )
        self.percent_rect = pygame.Rect(
            self.track_rect.right + 8,
            self._top,
            48,
            SETUP_SLIDER_ROW_HEIGHT,
        )
        self.hit_rect = self.track_rect.inflate(0, 24)

    @property
    def handle_center(self) -> tuple[int, int]:
        x = self.track_rect.left + int(self.value * self.track_rect.width)
        return x, self.track_rect.centery

    def set_from_mouse_x(self, mouse_x: int) -> None:
        if self.track_rect.width <= 0:
            return
        t = (mouse_x - self.track_rect.left) / self.track_rect.width
        self.value = max(0.0, min(1.0, t))

    def contains_point(self, pos: tuple[int, int]) -> bool:
        handle = pygame.Rect(0, 0, SETUP_SLIDER_HANDLE_RADIUS * 2, SETUP_SLIDER_HANDLE_RADIUS * 2)
        handle.center = self.handle_center
        return handle.collidepoint(pos) or self.hit_rect.collidepoint(pos)

    def draw(self, screen: pygame.Surface) -> None:
        label_surf = self._label_font.render(self.label, True, (255, 255, 255))
        label_pos = label_surf.get_rect(
            midleft=(self.label_rect.left + 4, self.label_rect.centery),
        )
        screen.blit(label_surf, label_pos)

        pygame.draw.rect(
            screen,
            SETUP_TRACK_COLOR,
            self.track_rect,
            border_radius=SETUP_SLIDER_TRACK_HEIGHT // 2,
        )

        hx, hy = self.handle_center
        pygame.draw.circle(
            screen,
            SETUP_ACCENT,
            (hx, hy),
            SETUP_SLIDER_HANDLE_RADIUS,
        )

        pct = f"{int(round(self.value * 100))}%"
        pct_surf = self._value_font.render(pct, True, (255, 255, 255))
        pct_pos = pct_surf.get_rect(midleft=(self.percent_rect.left, self.percent_rect.centery))
        screen.blit(pct_surf, pct_pos)


class SetupScreen:
    """Parent-facing setup UI before a play session."""

    TITLE_TEXT = "Keyboard Masher"
    BUTTON_TEXT = "START SESSION"

    def __init__(self, screen: pygame.Surface) -> None:
        self._screen = screen
        self._title_font = pygame.font.SysFont(UI_FONT_NAME, 56)
        self._tagline_font = pygame.font.SysFont(UI_FONT_NAME, 16)
        self._footer_font = pygame.font.SysFont(UI_FONT_NAME, 24)
        self._tile_emoji_font = pygame.font.SysFont(EMOJI_FONT_NAME, 60)
        self._tile_label_font = pygame.font.SysFont(UI_FONT_NAME, 24, bold=True)
        self._tile_subtitle_font = pygame.font.SysFont(UI_FONT_NAME, 14)
        self._button_font = pygame.font.SysFont(UI_FONT_NAME, 32, bold=True)
        self._slider_label_font = pygame.font.SysFont(UI_FONT_NAME, 18)
        self._slider_value_font = pygame.font.SysFont(UI_FONT_NAME, 16)
        self._cat_font = pygame.font.SysFont(UI_FONT_NAME, 14, bold=True)

        self._selected_index: int | None = None
        self._hovered_index: int | None = None
        self._dragging_slider: SetupSlider | None = None
        self._tile_rects: list[pygame.Rect] = []
        self._cat_pill_rects: list[pygame.Rect] = []
        self._cat_alpha_factor: float = 0.0
        self._cat_target_alpha: float = 0.0
        self._instr_pill_rects: list[pygame.Rect] = []
        self._instr_alpha_factor: float = 0.0
        self._instr_target_alpha: float = 0.0
        self._title_rect = pygame.Rect(0, 0, 0, 0)
        self._tagline_rect = pygame.Rect(0, 0, 0, 0)
        self._button_rect = pygame.Rect(0, 0, 0, 0)
        self._close_rect = pygame.Rect(0, 0, 0, 0)
        self._footer_hint_y = 0
        self._close_hover = False
        self._button_hover = False
        self._bg_time = 0.0
        self._setup_bg_idx: int   = 0
        self._setup_bg_t:   float = 0.0
        self._tile_surf_normal: pygame.Surface | None = None
        self._tile_surf_active: pygame.Surface | None = None
        self._sliders: list[SetupSlider] = []
        self._settings = load_settings()
        self._selected_category: str = self._settings.emoji_category
        self._selected_instrument: str = self._settings.music_instrument
        self._layout()
        apply_session_volume(self.volume)

    def sync_to_display(self, new_screen: pygame.Surface) -> None:
        """After set_mode(), keep layout in sync with the current display surface."""
        self._screen = new_screen
        self._layout()

    @property
    def volume(self) -> float:
        return self._sliders[0].value

    @property
    def intensity(self) -> float:
        return self._sliders[1].value

    @property
    def suppress_notifications(self) -> bool:
        return self._notification_toggle.enabled

    @property
    def selected_theme_factory(self) -> type[Theme] | None:
        """Return the currently highlighted theme factory, or None if none selected."""
        if self._selected_index is not None:
            return _THEME_TILES[self._selected_index].factory
        return None

    def _persist_settings(self) -> None:
        save_settings(
            AppSettings(
                self.volume, self.intensity,
                self.suppress_notifications, self._selected_category,
                self._selected_instrument,
            )
        )

    def tick(self, dt: float) -> None:
        """Advance setup-only animations (background, pill fade)."""
        self._bg_time += dt
        self._setup_bg_t += dt / _SETUP_BG_DURATION
        if self._setup_bg_t >= 1.0:
            self._setup_bg_t -= 1.0
            self._setup_bg_idx = (self._setup_bg_idx + 1) % len(_SETUP_BG_COLORS)
        rate = 1.0 / SETUP_CAT_FADE_SEC
        if self._cat_target_alpha > self._cat_alpha_factor:
            self._cat_alpha_factor = min(
                self._cat_target_alpha, self._cat_alpha_factor + rate * dt
            )
        else:
            self._cat_alpha_factor = max(
                self._cat_target_alpha, self._cat_alpha_factor - rate * dt
            )
        if self._instr_target_alpha > self._instr_alpha_factor:
            self._instr_alpha_factor = min(
                self._instr_target_alpha, self._instr_alpha_factor + rate * dt
            )
        else:
            self._instr_alpha_factor = max(
                self._instr_target_alpha, self._instr_alpha_factor - rate * dt
            )

    def _draw_animated_background(self, screen: pygame.Surface) -> None:
        c0 = _SETUP_BG_COLORS[self._setup_bg_idx]
        c1 = _SETUP_BG_COLORS[(self._setup_bg_idx + 1) % len(_SETUP_BG_COLORS)]
        screen.fill(_lerp_rgb(c0, c1, self._setup_bg_t))

    def _layout(self) -> None:
        w, h = self._screen.get_size()
        margin_x = max(24, min(80, w // 48))

        self._close_rect = pygame.Rect(
            w - margin_x - SETUP_CLOSE_HIT,
            margin_x,
            SETUP_CLOSE_HIT,
            SETUP_CLOSE_HIT,
        )

        title_surf = self._title_font.render(self.TITLE_TEXT, True, (255, 255, 255))
        self._title_rect = title_surf.get_rect(center=(w // 2, int(h * 0.10)))

        tag_surf = self._tagline_font.render(
            SETUP_TAGLINE_TEXT, True, SETUP_ON_GRADIENT_TEXT_COLOR
        )
        self._tagline_rect = tag_surf.get_rect(
            center=(w // 2, self._title_rect.bottom + 14),
        )

        row_width = SETUP_TILE_WIDTH * 2 + SETUP_TILE_GAP
        tiles_left = (w - row_width) // 2
        gap_below_tagline = max(28, int(h * 0.045))
        tiles_top = self._tagline_rect.bottom + gap_below_tagline
        self._tile_rects = [
            pygame.Rect(
                tiles_left,
                tiles_top,
                SETUP_TILE_WIDTH,
                SETUP_TILE_HEIGHT,
            ),
            pygame.Rect(
                tiles_left + SETUP_TILE_WIDTH + SETUP_TILE_GAP,
                tiles_top,
                SETUP_TILE_WIDTH,
                SETUP_TILE_HEIGHT,
            ),
        ]

        cat_gap = max(14, int(h * 0.018))
        cat_row_top = tiles_top + SETUP_TILE_HEIGHT + cat_gap
        n_cats = len(_CAT_NAMES)
        total_pill_w = n_cats * SETUP_CAT_PILL_WIDTH + (n_cats - 1) * SETUP_CAT_PILL_GAP
        pill_left = w // 2 - total_pill_w // 2
        self._cat_pill_rects = [
            pygame.Rect(
                pill_left + i * (SETUP_CAT_PILL_WIDTH + SETUP_CAT_PILL_GAP),
                cat_row_top,
                SETUP_CAT_PILL_WIDTH,
                SETUP_CAT_PILL_HEIGHT,
            )
            for i in range(n_cats)
        ]
        n_instrs = len(_INSTRUMENT_NAMES)
        total_instr_w = n_instrs * SETUP_INSTR_PILL_WIDTH + (n_instrs - 1) * SETUP_INSTR_PILL_GAP
        instr_left = w // 2 - total_instr_w // 2
        self._instr_pill_rects = [
            pygame.Rect(
                instr_left + i * (SETUP_INSTR_PILL_WIDTH + SETUP_INSTR_PILL_GAP),
                cat_row_top,           # same Y — mutually exclusive with cat row
                SETUP_INSTR_PILL_WIDTH,
                SETUP_INSTR_PILL_HEIGHT,
            )
            for i in range(n_instrs)
        ]
        sliders_top = cat_row_top + SETUP_CAT_PILL_HEIGHT + cat_gap
        self._sliders = [
            SetupSlider(
                "Volume",
                self._settings.volume,
                w // 2,
                sliders_top,
                self._slider_label_font,
                self._slider_value_font,
            ),
            SetupSlider(
                "Intensity",
                self._settings.intensity,
                w // 2,
                sliders_top + SETUP_SLIDER_ROW_HEIGHT + SETUP_SLIDER_GAP,
                self._slider_label_font,
                self._slider_value_font,
            ),
        ]

        toggle_top = (
            self._sliders[-1].label_rect.bottom + SETUP_SLIDER_GAP
        )
        self._notification_toggle = SetupNotificationToggle(
            w // 2,
            toggle_top,
            self._slider_label_font,
            enabled=self._settings.suppress_notifications,
        )

        button_surf = self._button_font.render(self.BUTTON_TEXT, True, (255, 255, 255))
        pad_x, pad_y = 48, 20
        toggle_bottom = self._notification_toggle.hit_rect.bottom
        gap_above_button = max(32, int(h * 0.038))
        btn_inner_w, btn_inner_h = button_surf.get_size()
        btn_w = btn_inner_w + pad_x * 2
        btn_h = btn_inner_h + pad_y * 2
        btn_cy = toggle_bottom + gap_above_button + btn_h // 2
        self._button_rect = pygame.Rect(0, 0, btn_w, btn_h)
        self._button_rect.center = (w // 2, btn_cy)

        self._footer_hint_y = h - max(18, int(h * 0.022))

        # Pre-bake tile background surfaces (4× AA; avoids per-frame supersampling)
        tw, th = SETUP_TILE_WIDTH, SETUP_TILE_HEIGHT
        self._tile_surf_normal = pygame.Surface((tw, th), pygame.SRCALPHA)
        _aa_rounded_rect(self._tile_surf_normal, SETUP_TILE_BG, (0, 0, tw, th), 16)
        self._tile_surf_active = pygame.Surface((tw, th), pygame.SRCALPHA)
        _aa_rounded_rect(self._tile_surf_active, SETUP_ACCENT, (0, 0, tw, th), 16)
        inner_r = max(1, 16 - SETUP_TILE_BORDER)
        _aa_rounded_rect(
            self._tile_surf_active,
            SETUP_TILE_BG_ACTIVE,
            (SETUP_TILE_BORDER, SETUP_TILE_BORDER,
             tw - 2 * SETUP_TILE_BORDER, th - 2 * SETUP_TILE_BORDER),
            inner_r,
        )

    def _slider_at(self, pos: tuple[int, int]) -> SetupSlider | None:
        for slider in self._sliders:
            if slider.contains_point(pos):
                return slider
        return None

    def _tile_index_at(self, pos: tuple[int, int]) -> int | None:
        for i, rect in enumerate(self._tile_rects):
            if rect.collidepoint(pos):
                return i
        return None

    def handle_event(self, event: pygame.event.Event) -> SessionConfig | None:
        """Return session settings when Start Session is confirmed."""
        if event.type == pygame.MOUSEMOTION:
            if self._dragging_slider is not None:
                self._dragging_slider.set_from_mouse_x(event.pos[0])
                if self._dragging_slider.label == "Volume":
                    apply_session_volume(self._dragging_slider.value)
                self._persist_settings()
            else:
                self._hovered_index = self._tile_index_at(event.pos)

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._close_rect.collidepoint(event.pos):
                pygame.event.post(pygame.event.Event(pygame.QUIT))
                return None

            slider_hit = self._slider_at(event.pos)
            if slider_hit is not None:
                self._dragging_slider = slider_hit
                slider_hit.set_from_mouse_x(event.pos[0])
                if slider_hit.label == "Volume":
                    apply_session_volume(slider_hit.value)
                self._persist_settings()
                return None

            if self._notification_toggle.contains_point(event.pos):
                self._notification_toggle.toggle()
                self._persist_settings()
                return None

            tile_hit = self._tile_index_at(event.pos)
            if tile_hit is not None:
                self._selected_index = tile_hit
                # tile 0 = Music → show instrument pills; tile 1 = Emoji → show category pills
                self._instr_target_alpha = 1.0 if tile_hit == 0 else 0.0
                self._cat_target_alpha   = 1.0 if tile_hit == 1 else 0.0
                return None

            if self._instr_alpha_factor > 0.05:
                for i, rect in enumerate(self._instr_pill_rects):
                    if rect.collidepoint(event.pos):
                        self._selected_instrument = _INSTRUMENT_KEY[_INSTRUMENT_NAMES[i]]
                        self._persist_settings()
                        # Preview: play middle C on the selected instrument
                        sounds = INSTRUMENT_SOUNDS.get(self._selected_instrument)
                        if sounds:
                            sounds[0].set_volume(CURRENT_PLAY_VOLUME)
                            sounds[0].play()
                        return None

            if self._cat_alpha_factor > 0.05:
                for i, rect in enumerate(self._cat_pill_rects):
                    if rect.collidepoint(event.pos):
                        self._selected_category = _CAT_NAMES[i]
                        self._persist_settings()
                        return None

            if (
                self._selected_index is not None
                and self._button_rect.collidepoint(event.pos)
            ):
                return SessionConfig(
                    _THEME_TILES[self._selected_index].factory,
                    self.volume,
                    self.intensity,
                    self.suppress_notifications,
                    self._selected_category,
                    self._selected_instrument,
                )

        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self._dragging_slider is not None:
                self._persist_settings()
            self._dragging_slider = None

        return None

    def _pill_blit_label(
        self,
        pill: pygame.Surface,
        text: str,
        color: tuple[int, int, int],
        alpha: int,
    ) -> None:
        """Render text centred in pill using font ascent/descent for pixel-perfect V-centre."""
        label = self._cat_font.render(text, True, color)
        label.set_alpha(alpha)
        pw, ph = pill.get_size()
        # Horizontal: true centre
        lx = (pw - label.get_width()) // 2
        # Vertical: centre by actual glyph height, not line-spacing height
        glyph_h = self._cat_font.get_ascent() + abs(self._cat_font.get_descent())
        ly = (ph - glyph_h) // 2
        pill.blit(label, (lx, ly))

    def _draw_category_pills(self, screen: pygame.Surface) -> None:
        if self._cat_alpha_factor <= 0.01:
            return
        alpha = int(round(255 * self._cat_alpha_factor))
        for rect, name in zip(self._cat_pill_rects, _CAT_NAMES):
            selected = name == self._selected_category
            bg = SETUP_ACCENT if selected else SETUP_TILE_BG
            txt_color = (255, 255, 255) if selected else (140, 140, 155)
            radius = rect.height // 2
            pill = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
            _aa_rounded_rect(pill, (*bg, alpha), pill.get_rect(), radius)
            self._pill_blit_label(pill, name, txt_color, alpha)
            screen.blit(pill, rect.topleft)

    def _draw_instrument_pills(self, screen: pygame.Surface) -> None:
        if self._instr_alpha_factor <= 0.01:
            return
        alpha = int(round(255 * self._instr_alpha_factor))
        for rect, name in zip(self._instr_pill_rects, _INSTRUMENT_NAMES):
            key = _INSTRUMENT_KEY[name]
            selected = key == self._selected_instrument
            bg = SETUP_ACCENT if selected else SETUP_TILE_BG
            txt_color = (255, 255, 255) if selected else (140, 140, 155)
            radius = rect.height // 2
            pill = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
            _aa_rounded_rect(pill, (*bg, alpha), pill.get_rect(), radius)
            self._pill_blit_label(pill, name, txt_color, alpha)
            screen.blit(pill, rect.topleft)

    def _draw_tile(
        self,
        screen: pygame.Surface,
        tile: _ThemeTile,
        rect: pygame.Rect,
        *,
        highlighted: bool,
    ) -> None:
        bg_surf = self._tile_surf_active if highlighted else self._tile_surf_normal
        if bg_surf is not None:
            screen.blit(bg_surf, rect.topleft)
        else:
            bg = SETUP_TILE_BG_ACTIVE if highlighted else SETUP_TILE_BG
            pygame.draw.rect(screen, bg, rect, border_radius=16)

        emoji_surf = self._tile_emoji_font.render(tile.emoji, True, tile.emoji_color)
        label_surf = self._tile_label_font.render(tile.label, True, (255, 255, 255))
        subtitle_surf = self._tile_subtitle_font.render(
            tile.subtitle, True, SETUP_SUBTITLE_COLOR
        )

        emoji_rect = emoji_surf.get_rect(center=(rect.centerx, rect.top + 52))
        label_rect = label_surf.get_rect(center=(rect.centerx, rect.top + 108))
        subtitle_rect = subtitle_surf.get_rect(center=(rect.centerx, rect.top + 138))

        screen.blit(emoji_surf, emoji_rect)
        screen.blit(label_surf, label_rect)
        screen.blit(subtitle_surf, subtitle_rect)

    def _draw_close_button(self, screen: pygame.Surface) -> None:
        """Two diagonal lines — avoids missing-glyph boxes for Unicode close marks."""
        r = self._close_rect
        surf = pygame.Surface((max(1, r.width), max(1, r.height)), pygame.SRCALPHA)
        w, h = surf.get_size()
        m = min(w, h)
        inset = max(10, m // 3 - 1)
        inset = min(inset, m // 2 - 4)
        lw = 3
        alpha = 255 if self._close_hover else 115
        col = (255, 255, 255, alpha)
        x0, y0 = inset, inset
        x1, y1 = w - 1 - inset, h - 1 - inset
        pygame.draw.line(surf, col, (x0, y0), (x1, y1), lw)
        pygame.draw.line(surf, col, (x1, y0), (x0, y1), lw)
        screen.blit(surf, r.topleft)

    def draw(self, screen: pygame.Surface) -> None:
        mp = pygame.mouse.get_pos()
        self._close_hover = self._close_rect.collidepoint(mp)
        self._button_hover = (
            self._selected_index is not None
            and self._button_rect.collidepoint(mp)
        )

        self._draw_animated_background(screen)

        title_surf = self._title_font.render(self.TITLE_TEXT, True, (255, 255, 255))
        screen.blit(title_surf, self._title_rect)

        tag_surf = self._tagline_font.render(
            SETUP_TAGLINE_TEXT, True, (255, 255, 255)
        )
        tag_surf.set_alpha(216)   # 85 % opacity
        screen.blit(tag_surf, self._tagline_rect)

        for i, (tile, rect) in enumerate(zip(_THEME_TILES, self._tile_rects)):
            highlighted = i == self._selected_index or i == self._hovered_index
            self._draw_tile(screen, tile, rect, highlighted=highlighted)

        self._draw_category_pills(screen)
        self._draw_instrument_pills(screen)

        for slider in self._sliders:
            slider.draw(screen)

        self._notification_toggle.draw(screen)

        enabled = self._selected_index is not None
        if enabled:
            if self._button_hover:
                pad = 36
                glow = pygame.Surface(
                    (
                        self._button_rect.width + pad * 2,
                        self._button_rect.height + pad * 2,
                    ),
                    pygame.SRCALPHA,
                )
                ox = self._button_rect.left - pad
                oy = self._button_rect.top - pad
                for i in range(SETUP_BUTTON_GLOW_LAYERS - 1, -1, -1):
                    inflate = 6 + i * 10
                    alpha = 14 + (SETUP_BUTTON_GLOW_LAYERS - 1 - i) * 10
                    gr = self._button_rect.inflate(inflate * 2, inflate * 2)
                    pygame.draw.rect(
                        glow,
                        (*SETUP_ACCENT, min(95, alpha)),
                        (gr.x - ox, gr.y - oy, gr.w, gr.h),
                        border_radius=16 + i * 3,
                    )
                screen.blit(glow, (ox, oy))

            pygame.draw.rect(
                screen, SETUP_ACCENT, self._button_rect, border_radius=14
            )
            button_color = (255, 255, 255)
        else:
            pygame.draw.rect(
                screen, SETUP_BUTTON_DISABLED_BG, self._button_rect, border_radius=12
            )
            pygame.draw.rect(
                screen, (70, 70, 95), self._button_rect, width=2, border_radius=12
            )
            button_color = SETUP_BUTTON_DISABLED_TEXT

        button_surf = self._button_font.render(self.BUTTON_TEXT, True, button_color)
        label_rect = button_surf.get_rect(center=self._button_rect.center)
        screen.blit(button_surf, label_rect)

        self._draw_close_button(screen)

        hint_surf = self._footer_font.render(
            SETUP_FOOTER_HINT_TEXT, True, (255, 255, 255)
        )
        hint_surf.set_alpha(216)   # 85 % opacity
        hint_rect = hint_surf.get_rect(
            midbottom=(screen.get_width() // 2, self._footer_hint_y)
        )
        screen.blit(hint_surf, hint_rect)


def _draw_unlock_overlay_pill(
    screen: pygame.Surface,
    keyboard_lockdown: KeyboardLockdown,
    font: pygame.font.Font,
) -> None:
    """Top-right subtle pill while parent holds Ctrl+Shift+Q."""
    overlay = keyboard_lockdown.get_unlock_overlay()
    if overlay is None:
        return
    title, countdown = overlay
    line1 = font.render(title, True, (255, 255, 255))
    line2 = font.render(countdown, True, (255, 255, 255))
    pad_x, pad_y = 12, 10
    gap = 4
    inner_w = max(line1.get_width(), line2.get_width())
    inner_h = line1.get_height() + gap + line2.get_height()
    pill_w = inner_w + pad_x * 2
    pill_h = inner_h + pad_y * 2
    pill = pygame.Surface((pill_w, pill_h), pygame.SRCALPHA)
    pill_alpha = int(255 * 0.7)
    pygame.draw.rect(
        pill,
        (18, 18, 28, pill_alpha),
        pill.get_rect(),
        border_radius=14,
    )
    pill.blit(line1, (pad_x, pad_y))
    pill.blit(line2, (pad_x, pad_y + line1.get_height() + gap))
    sw, _ = screen.get_size()
    dest = pill.get_rect(topright=(sw - 14, 14))
    screen.blit(pill, dest)


def begin_play_session(
    screen: pygame.Surface,
    config: SessionConfig,
) -> tuple[Theme, str, float]:
    """Create the parent-selected theme and HUD label state."""
    apply_session_volume(config.volume)
    if config.theme_factory is MusicTheme:
        theme = MusicTheme(screen, intensity=config.intensity, active_instrument=config.music_instrument)
    else:
        theme = EmojiTheme(screen, config.intensity, config.emoji_category)
    return theme, theme.name, THEME_LABEL_DURATION


def run_playing_frame(
    screen: pygame.Surface,
    current_theme: Theme,
    label_text: str,
    label_timer: float,
    hud_font: pygame.font.Font,
    keyboard_lockdown: KeyboardLockdown,
    unlock_overlay_font: pygame.font.Font,
    dt: float,
    mode_pill_font: pygame.font.Font | None = None,
) -> tuple[Theme, str, float]:
    """Update and draw one playing frame; returns possibly updated theme/label."""
    current_theme.update(dt)

    screen.fill(BACKGROUND_COLOR)
    current_theme.draw(screen)

    if label_timer > 0:
        draw_theme_label(screen, label_text, hud_font)
        label_timer -= dt

    # Top-left mode indicator (always visible, drawn on top of all effects)
    if mode_pill_font is not None:
        draw_mode_pill(screen, current_theme, mode_pill_font)

    _draw_unlock_overlay_pill(screen, keyboard_lockdown, unlock_overlay_font)

    return current_theme, label_text, label_timer


def handle_playing_key(
    key: int,
    screen: pygame.Surface,
    current_theme: Theme,
    label_text: str,
    label_timer: float,
) -> tuple[Theme, str, float]:
    """Handle one key from the lockdown hook queue."""
    if key in THEME_FACTORIES:
        current_theme = switch_theme(
            THEME_FACTORIES[key], screen, current_theme
        )
        label_text = current_theme.name
        label_timer = THEME_LABEL_DURATION
    else:
        current_theme.on_keypress(key)

    return current_theme, label_text, label_timer


def _pygame_window_hwnd() -> int | None:
    """SDL window handle on Windows; None if unavailable."""
    if sys.platform != "win32":
        return None
    try:
        info = pygame.display.get_wm_info()
        hwnd = info.get("window")
        if hwnd is None:
            return None
        return int(hwnd)
    except (KeyError, TypeError, ValueError, pygame.error):
        return None


def _reclaim_fullscreen_focus(screen: pygame.Surface, setup_screen: SetupScreen) -> pygame.Surface:
    """Re-enter fullscreen and ask Windows to foreground our window."""
    if sys.platform != "win32":
        return screen
    try:
        new_screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        setup_screen.sync_to_display(new_screen)
        hwnd = _pygame_window_hwnd()
        if hwnd:
            ctypes.windll.user32.SetForegroundWindow(hwnd)
        return new_screen
    except (OSError, AttributeError, pygame.error):
        return screen


# -----------------------------------------------------------------------------
# Main loop
# -----------------------------------------------------------------------------


def main() -> None:
    global NOTE_SOUNDS, INSTRUMENT_SOUNDS, POP_WAVE, _SESSION_CLEANUP_ARGS, _ATEXIT_SESSION_CLEANUP_REGISTERED

    pygame.mixer.pre_init(SAMPLE_RATE, -16, 2, 512)

    notification_suppressor = NotificationSuppressor()
    keyboard_lockdown = KeyboardLockdown()
    win_key_suppressor = WinKeySuppressor()
    lock_workstation_suppressor = DisableLockWorkstationSuppressor()
    accessibility_keys_suppressor = AccessibilityKeysSuppressor()

    _SESSION_CLEANUP_ARGS = (
        notification_suppressor,
        keyboard_lockdown,
        win_key_suppressor,
        lock_workstation_suppressor,
        accessibility_keys_suppressor,
    )
    if not _ATEXIT_SESSION_CLEANUP_REGISTERED:
        atexit.register(_run_full_session_cleanup)
        _ATEXIT_SESSION_CLEANUP_REGISTERED = True

    try:
        pygame.init()

        NOTE_SOUNDS = build_note_sounds()
        INSTRUMENT_SOUNDS.update(build_instrument_sounds())
        POP_WAVE = build_pop_wave()

        screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        pygame.display.set_caption("Keyboard Masher")
        # Set the window/taskbar icon from icon.png if it exists next to main.py
        _icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.png")
        if os.path.isfile(_icon_path):
            _icon_surf = pygame.image.load(_icon_path).convert_alpha()
            pygame.display.set_icon(_icon_surf)
        clock = pygame.time.Clock()
        hud_font = pygame.font.SysFont(UI_FONT_NAME, 28)
        mode_pill_font = pygame.font.SysFont(UI_FONT_NAME, 15)
        unlock_overlay_font = pygame.font.SysFont(UI_FONT_NAME, 18)
        stress_hud_font = pygame.font.SysFont(UI_FONT_NAME, 22)
        stress_big_font = pygame.font.SysFont(UI_FONT_NAME, 72, bold=True)
        stress_med_font = pygame.font.SysFont(UI_FONT_NAME, 28)
        stress_sm_font = pygame.font.SysFont(UI_FONT_NAME, 20)

        app_state = AppState.SETUP
        setup_screen = SetupScreen(screen)
        current_theme: Theme | None = None
        label_text = ""
        label_timer = 0.0
        foreground_check_accumulator = 0.0
        stress_runner: StressTestRunner | None = None
        stress_result: StressTestResult | None = None

        running = True
        while running:
            dt = clock.tick(TARGET_FPS) / 1000.0

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

                elif (
                    event.type == pygame.KEYDOWN
                    and event.key == pygame.K_ESCAPE
                    and app_state == AppState.SETUP
                ):
                    running = False

                elif (
                    event.type == pygame.KEYDOWN
                    and event.key == pygame.K_F7
                    and app_state == AppState.SETUP
                ):
                    stress_runner = StressTestRunner(
                        screen, setup_screen.selected_theme_factory
                    )
                    app_state = AppState.STRESS_TEST

                elif (
                    event.type == pygame.KEYDOWN
                    and app_state == AppState.STRESS_RESULTS
                ):
                    app_state = AppState.SETUP
                    stress_result = None

                elif app_state == AppState.SETUP:
                    session = setup_screen.handle_event(event)
                    if session is not None:
                        app_state = AppState.PLAYING
                        current_theme, label_text, label_timer = begin_play_session(
                            screen, session
                        )
                        enter_playing_state(
                            notification_suppressor,
                            keyboard_lockdown,
                            win_key_suppressor,
                            lock_workstation_suppressor,
                            accessibility_keys_suppressor,
                            session.suppress_notifications,
                        )

            if app_state == AppState.PLAYING and current_theme is not None:
                if keyboard_lockdown.consume_unlock_request():
                    current_theme.clear()
                    leave_playing_state(
                        notification_suppressor,
                        keyboard_lockdown,
                        win_key_suppressor,
                        lock_workstation_suppressor,
                        accessibility_keys_suppressor,
                    )
                    app_state = AppState.SETUP
                    current_theme = None
                    label_text = ""
                    label_timer = 0.0
                else:
                    for key in keyboard_lockdown.drain():
                        if key == pygame.K_F7:
                            leave_playing_state(
                                notification_suppressor,
                                keyboard_lockdown,
                                win_key_suppressor,
                                lock_workstation_suppressor,
                                accessibility_keys_suppressor,
                            )
                            factory = type(current_theme)
                            current_theme.clear()
                            current_theme = None
                            label_text = ""
                            label_timer = 0.0
                            stress_runner = StressTestRunner(screen, factory)
                            app_state = AppState.STRESS_TEST
                            break
                        current_theme, label_text, label_timer = handle_playing_key(
                            key, screen, current_theme, label_text, label_timer
                        )

                    foreground_check_accumulator += dt
                    if (
                        foreground_check_accumulator
                        >= FOREGROUND_CHECK_INTERVAL_SEC
                    ):
                        foreground_check_accumulator = 0.0
                        try:
                            hwnd = _pygame_window_hwnd()
                            if (
                                hwnd is not None
                                and ctypes.windll.user32.GetForegroundWindow()
                                != hwnd
                            ):
                                screen = _reclaim_fullscreen_focus(
                                    screen, setup_screen
                                )
                        except OSError:
                            pass

            if app_state == AppState.STRESS_TEST and stress_runner is not None:
                stress_runner.update(dt)
                stress_runner.draw(screen)
                draw_stress_test_hud(screen, stress_runner, stress_hud_font)
                stress_runner.measure(screen)
                if stress_runner.done:
                    stress_result = stress_runner.finish()
                    write_stress_log(stress_result)
                    stress_runner = None
                    app_state = AppState.STRESS_RESULTS
            elif app_state == AppState.STRESS_RESULTS and stress_result is not None:
                screen.fill(BACKGROUND_COLOR)
                draw_stress_results(
                    screen, stress_result,
                    stress_big_font, stress_med_font, stress_sm_font,
                )
            elif app_state == AppState.SETUP:
                setup_screen.tick(dt)
                setup_screen.draw(screen)
            elif current_theme is not None:
                current_theme, label_text, label_timer = run_playing_frame(
                    screen,
                    current_theme,
                    label_text,
                    label_timer,
                    hud_font,
                    keyboard_lockdown,
                    unlock_overlay_font,
                    dt,
                    mode_pill_font,
                )

            pygame.display.flip()
    finally:
        _run_full_session_cleanup()
        try:
            pygame.quit()
        except Exception:
            pass

    sys.exit(0)


if __name__ == "__main__":
    main()
