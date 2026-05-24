"""
Toddler Key Smash — parent setup, then themed keypress play.
Setup: Start Session  |  Playing: Ctrl+Shift+Q unlock  |  SETUP: Escape quits
"""

from __future__ import annotations

import atexit
import collections
import ctypes
import json
import math
import os
import queue
import random
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
# Dev mode — measurement & instrumentation gate
# -----------------------------------------------------------------------------
#
# Dev mode unlocks the luminance HUD, frame-time histogram, palette hot-reload,
# and synthetic stress test. Enabled only when KEYBOARD_MASHER_DEV=1 is set in
# the environment AND the process is not a frozen (PyInstaller) build. This
# guarantees the shipped .exe can never expose dev surfaces, even if the env
# var leaks into a parent's session.

IS_FROZEN = bool(getattr(sys, "frozen", False))
IS_DEV_MODE = (os.environ.get("KEYBOARD_MASHER_DEV") == "1") and not IS_FROZEN

# Persistent dev-mode log. Each PLAYING session writes to its own theme file
# under ./logs/ (e.g. logs/music.log, logs/emoji.log). Events outside a
# session go to logs/general.log. _dev_log writes safety- and test-critical
# events to the active file; _dev_trace is stderr-only chatter for live
# debugging and does NOT persist. Keeping the file lean is the point — when
# the owner shares a log we want to scan it in seconds, not minutes.
DEV_LOG_DIR = Path(__file__).resolve().parent / "logs"
DEV_GENERAL_LOG_PATH = DEV_LOG_DIR / "general.log"


def _active_dev_log_path() -> Path:
    if DEV_STATE is not None and DEV_STATE.active_log_path is not None:
        return DEV_STATE.active_log_path
    return DEV_GENERAL_LOG_PATH


def _dev_trace(message: str) -> None:
    """Stderr-only chatter (HUD toggles, redundant rejections). Not persisted."""
    if not IS_DEV_MODE:
        return
    try:
        sys.stderr.write(f"[trace] {message}\n")
        sys.stderr.flush()
    except OSError:
        pass


def _dev_log(message: str) -> None:
    """
    Persist a safety- or test-critical event to the active session log file
    (or general.log outside a session) AND stderr. No-op in release.
    """
    if not IS_DEV_MODE:
        return
    line = f"[{time.strftime('%H:%M:%S')}] {message}\n"
    try:
        sys.stderr.write(f"[dev] {line}")
        sys.stderr.flush()
    except OSError:
        pass
    target = _active_dev_log_path()
    try:
        DEV_LOG_DIR.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as file:
            file.write(line)
    except OSError:
        pass


def dev_session_start(theme_name: str, volume: float, intensity: float) -> None:
    """Switch the active log file to this theme and write a session header."""
    if not IS_DEV_MODE or DEV_STATE is None:
        return
    safe = "".join(c for c in theme_name.lower() if c.isalnum()) or "session"
    DEV_STATE.active_log_path = DEV_LOG_DIR / f"{safe}.log"
    DEV_STATE.session_started_at = time.monotonic()
    DEV_STATE.session_breach_count = 0
    DEV_STATE.session_drop_count = 0
    header = (
        f"\n=== session start {time.strftime('%Y-%m-%dT%H:%M:%S')} "
        f"theme={theme_name} volume={volume:.2f} intensity={intensity:.2f} ===\n"
    )
    try:
        DEV_LOG_DIR.mkdir(parents=True, exist_ok=True)
        with DEV_STATE.active_log_path.open("a", encoding="utf-8") as file:
            file.write(header)
    except OSError:
        pass


def dev_session_end() -> None:
    """
    Write the per-session summary footer. The active log path stays attached
    so any straggler drop / breach that fires during the unlock + cleanup
    work in the same tick still attributes to the session that owned it.
    The next dev_session_start overwrites the path before its own header.
    """
    if not IS_DEV_MODE or DEV_STATE is None:
        return
    if DEV_STATE.active_log_path is None:
        return
    duration = time.monotonic() - DEV_STATE.session_started_at
    footer = (
        f"=== session end   {time.strftime('%Y-%m-%dT%H:%M:%S')} "
        f"duration={duration:.1f}s "
        f"luminance_breaches={DEV_STATE.session_breach_count} "
        f"frame_drop_bursts={DEV_STATE.session_drop_count} ===\n"
    )
    try:
        with DEV_STATE.active_log_path.open("a", encoding="utf-8") as file:
            file.write(footer)
    except OSError:
        pass


class DevState:
    """
    Container for dev-mode runtime state (HUD toggles, probes, stress test).
    All fields default to 'off' so flipping IS_DEV_MODE to False leaves the
    container inert. Later Phase 0 sub-plans populate the per-feature fields.
    """

    __slots__ = (
        "hud_visible",
        "frame_hist_visible",
        "palette_overrides",
        "palette_mtime",
        "stress_test",
        "luminance_probe",
        "frame_histogram",
        "stress_result_text",
        "stress_result_until",
        "stress_result_pass",
        "last_lum_breach_log",
        "last_drop_log",
        "active_log_path",
        "session_started_at",
        "session_breach_count",
        "session_drop_count",
    )

    def __init__(self) -> None:
        # HUD + histogram default ON in dev mode so a fresh launch shows them
        # immediately; F8/F9 still toggle individually.
        self.hud_visible: bool = True
        self.frame_hist_visible: bool = True
        self.palette_overrides: dict[str, Any] = {}
        self.palette_mtime: float = 0.0
        self.stress_test: StressTest | None = None
        self.luminance_probe: LuminanceProbe | None = None
        self.frame_histogram: FrameHistogram | None = None
        # Last finished stress-test result, surfaced as a 5 s overlay.
        self.stress_result_text: str = ""
        self.stress_result_until: float = 0.0
        self.stress_result_pass: bool = True
        # Throttle timestamps so a sustained breach logs once per second,
        # not every frame.
        self.last_lum_breach_log: float = 0.0
        self.last_drop_log: float = 0.0
        # Per-session log routing + counters (set by dev_session_start).
        self.active_log_path: Path | None = None
        self.session_started_at: float = 0.0
        self.session_breach_count: int = 0
        self.session_drop_count: int = 0


# Probe constants — chosen to align with Harding-style photosensitivity rules.
# Threshold of 25 in 0–255 RGB luminance approximates the 10 cd/m² flash floor
# used by W3C WCAG 2.3.1 detection tooling.
LUM_PROBE_POSITIONS: tuple[tuple[float, float], ...] = (
    (0.10, 0.10), (0.50, 0.10), (0.90, 0.10),
    (0.10, 0.50),                 (0.90, 0.50),
    (0.10, 0.90), (0.50, 0.90), (0.90, 0.90),
)
LUM_PROBE_WINDOW_SEC = 1.0
LUM_PROBE_DELTA_THRESHOLD = 25.0   # 0–255 luminance units per transition
LUM_PROBE_HZ_BREACH = 3.0          # CLAUDE.md hard cap: > 3 Hz is unsafe


class LuminanceProbe:
    """
    Samples Rec.709 luminance at 8 fixed screen positions each frame. Holds a
    1-second rolling history per probe and reports the worst-pixel transition
    rate (Hz). Used as the empirical photosensitivity check that backs the
    'no luminance changes > 3 Hz' constraint in CLAUDE.md.
    """

    __slots__ = ("positions", "_history", "_anchor", "_direction", "_last_hz")

    def __init__(self, screen_size: tuple[int, int]) -> None:
        w, h = screen_size
        self.positions: list[tuple[int, int]] = [
            (
                max(0, min(w - 1, int(round(px * w)))),
                max(0, min(h - 1, int(round(py * h)))),
            )
            for px, py in LUM_PROBE_POSITIONS
        ]
        n = len(self.positions)
        self._history: list[collections.deque[tuple[float, float]]] = [
            collections.deque() for _ in range(n)
        ]
        self._anchor: list[float] = [0.0] * n
        self._direction: list[int] = [0] * n
        self._last_hz: float = 0.0

    def resize(self, screen_size: tuple[int, int]) -> None:
        """Rebuild probe positions if the display size changed."""
        w, h = screen_size
        self.positions = [
            (
                max(0, min(w - 1, int(round(px * w)))),
                max(0, min(h - 1, int(round(py * h)))),
            )
            for px, py in LUM_PROBE_POSITIONS
        ]

    @staticmethod
    def _rec709(r: int, g: int, b: int) -> float:
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    def sample(self, screen: pygame.Surface, now: float) -> None:
        """Read each probe pixel; expire entries older than the window."""
        cutoff = now - LUM_PROBE_WINDOW_SEC
        for i, (x, y) in enumerate(self.positions):
            try:
                color = screen.get_at((x, y))
            except (IndexError, ValueError):
                continue
            lum = self._rec709(color[0], color[1], color[2])
            hist = self._history[i]
            hist.append((now, lum))
            while hist and hist[0][0] < cutoff:
                hist.popleft()

    def hz(self) -> float:
        """
        Return the worst-pixel transition rate over the rolling 1 s window.
        A 'transition' is a luminance reversal that has moved at least
        LUM_PROBE_DELTA_THRESHOLD units from the last anchor — i.e., one
        leg of a flash. A 3 Hz flash registers as ~6 transitions/sec.
        """
        worst = 0.0
        for i, hist in enumerate(self._history):
            if len(hist) < 2:
                continue
            anchor = hist[0][1]
            direction = 0
            transitions = 0
            for _, lum in hist:
                delta = lum - anchor
                if abs(delta) < LUM_PROBE_DELTA_THRESHOLD:
                    continue
                new_dir = 1 if delta > 0 else -1
                if new_dir != direction:
                    transitions += 1
                    direction = new_dir
                anchor = lum
            self._anchor[i] = anchor
            self._direction[i] = direction
            # Each full flash cycle ≈ 2 transitions, so Hz = transitions / 2.
            hz = transitions / 2.0
            if hz > worst:
                worst = hz
        self._last_hz = worst
        return worst

    def avg_luminance(self) -> float:
        total = 0.0
        n = 0
        for hist in self._history:
            if hist:
                total += hist[-1][1]
                n += 1
        return total / n if n else 0.0


# Frame-time histogram bins (seconds). 16.67 ms ≈ 60 fps cap; the >20 ms bin
# represents dropped frames the toddler would actually perceive.
FRAME_HIST_BINS: tuple[tuple[float, float], ...] = (
    (0.000, 0.008),
    (0.008, 0.012),
    (0.012, 0.016),
    (0.016, 0.020),
    (0.020, float("inf")),
)
FRAME_HIST_LABELS: tuple[str, ...] = ("≤8", "≤12", "≤16", "≤20", ">20")
FRAME_HIST_BAR_COLORS: tuple[tuple[int, int, int], ...] = (
    (150, 220, 150),  # generous
    (190, 220, 150),
    (220, 220, 150),
    (220, 180, 100),  # near miss
    (240, 110, 110),  # dropped frame
)
FRAME_HIST_WINDOW_SEC = 1.0


class FrameHistogram:
    """
    1-second rolling tally of frame deltas, bucketed into five bins. Used by
    the dev HUD to show whether the render loop is meeting its 60 fps budget.
    """

    __slots__ = ("_samples", "_bin_counts")

    def __init__(self) -> None:
        self._samples: collections.deque[tuple[float, float]] = collections.deque()
        self._bin_counts: list[int] = [0] * len(FRAME_HIST_BINS)

    @staticmethod
    def _bin_for(dt: float) -> int:
        for i, (lo, hi) in enumerate(FRAME_HIST_BINS):
            if lo <= dt < hi:
                return i
        return len(FRAME_HIST_BINS) - 1

    def push(self, dt: float, now: float) -> None:
        self._samples.append((now, dt))
        self._bin_counts[self._bin_for(dt)] += 1
        cutoff = now - FRAME_HIST_WINDOW_SEC
        while self._samples and self._samples[0][0] < cutoff:
            _, old_dt = self._samples.popleft()
            self._bin_counts[self._bin_for(old_dt)] -= 1

    def counts(self) -> tuple[int, ...]:
        return tuple(self._bin_counts)


# Stress-test parameters: 30 Hz key emission, 10 s cycle through Q-Y, then
# 5 s on a single key (Q). Modeled after the worst-case toddler input — six
# fingers slapping the keyboard row at fast cadence.
STRESS_CYCLE_KEYS: tuple[int, ...] = (
    pygame.K_q, pygame.K_w, pygame.K_e,
    pygame.K_r, pygame.K_t, pygame.K_y,
)
STRESS_RATE_HZ = 30.0
STRESS_CYCLE_SEC = 10.0
STRESS_HOLD_SEC = 5.0
STRESS_TOTAL_SEC = STRESS_CYCLE_SEC + STRESS_HOLD_SEC


class StressTest:
    """
    Drives 15 s of synthetic key events into the active theme to validate the
    safety/perf budget under worst-case toddler input. PASS criteria: probe
    Hz never exceeds LUM_PROBE_HZ_BREACH and no >20 ms frames are recorded.
    """

    __slots__ = (
        "active",
        "_started_at",
        "_next_emit_at",
        "_emit_count",
        "_peak_hz",
        "_peak_dropped",
    )

    def __init__(self) -> None:
        self.active: bool = False
        self._started_at: float = 0.0
        self._next_emit_at: float = 0.0
        self._emit_count: int = 0
        self._peak_hz: float = 0.0
        self._peak_dropped: int = 0

    def start(self, now: float) -> None:
        self.active = True
        self._started_at = now
        self._next_emit_at = now
        self._emit_count = 0
        self._peak_hz = 0.0
        self._peak_dropped = 0

    def tick(
        self,
        now: float,
        theme: Theme | None,
        probe: LuminanceProbe | None,
        histogram: FrameHistogram | None,
    ) -> tuple[bool, str] | None:
        """
        Advance one frame of the test. Returns (pass, summary) once finished;
        None while running. Emits synthetic keys into `theme` directly so the
        keyboard hook stays uninvolved.
        """
        if not self.active:
            return None
        elapsed = now - self._started_at
        period = 1.0 / STRESS_RATE_HZ
        while now >= self._next_emit_at and elapsed < STRESS_TOTAL_SEC:
            if elapsed < STRESS_CYCLE_SEC:
                key = STRESS_CYCLE_KEYS[self._emit_count % len(STRESS_CYCLE_KEYS)]
            else:
                key = STRESS_CYCLE_KEYS[0]  # held single key
            if theme is not None:
                try:
                    theme.on_keypress(key)
                except Exception:  # noqa: BLE001 — stress test must not crash app
                    pass
            self._emit_count += 1
            self._next_emit_at += period
        if probe is not None:
            hz = probe.hz()
            if hz > self._peak_hz:
                self._peak_hz = hz
        if histogram is not None:
            dropped = histogram.counts()[4]
            if dropped > self._peak_dropped:
                self._peak_dropped = dropped
        if elapsed < STRESS_TOTAL_SEC:
            return None
        self.active = False
        passed = (
            self._peak_hz <= LUM_PROBE_HZ_BREACH
            and self._peak_dropped == 0
        )
        summary = (
            f"emits={self._emit_count}  "
            f"peak_hz={self._peak_hz:.1f} (cap {LUM_PROBE_HZ_BREACH:.1f})  "
            f"dropped_frames={self._peak_dropped}"
        )
        return passed, summary


def draw_stress_overlay(
    screen: pygame.Surface, font: pygame.font.Font
) -> None:
    """Center overlay shown briefly when a stress test completes."""
    if not IS_DEV_MODE or DEV_STATE is None:
        return
    now = time.monotonic()
    if now >= DEV_STATE.stress_result_until or not DEV_STATE.stress_result_text:
        return
    color = (150, 230, 150) if DEV_STATE.stress_result_pass else (240, 110, 110)
    label = "STRESS PASS" if DEV_STATE.stress_result_pass else "STRESS FAIL"
    surf_label = font.render(label, True, color)
    surf_detail = font.render(DEV_STATE.stress_result_text, True, (220, 220, 220))
    pad = 12
    inner_w = max(surf_label.get_width(), surf_detail.get_width())
    inner_h = surf_label.get_height() + 4 + surf_detail.get_height()
    bg = pygame.Surface((inner_w + pad * 2, inner_h + pad * 2), pygame.SRCALPHA)
    bg.fill((0, 0, 0, 200))
    sw, sh = screen.get_size()
    bx = (sw - bg.get_width()) // 2
    by = sh - bg.get_height() - 60
    screen.blit(bg, (bx, by))
    screen.blit(surf_label, (bx + pad, by + pad))
    screen.blit(
        surf_detail,
        (bx + pad, by + pad + surf_label.get_height() + 4),
    )


def draw_frame_histogram(
    screen: pygame.Surface, font: pygame.font.Font
) -> None:
    """Top-right HUD: per-bin frame counts over the last second."""
    if (
        not IS_DEV_MODE
        or DEV_STATE is None
        or not DEV_STATE.frame_hist_visible
    ):
        return
    hist = DEV_STATE.frame_histogram
    if hist is None:
        return
    counts = hist.counts()
    total = sum(counts) or 1
    parts: list[tuple[str, tuple[int, int, int]]] = []
    parts.append(("FPS ", (220, 220, 220)))
    for label, count, color in zip(
        FRAME_HIST_LABELS, counts, FRAME_HIST_BAR_COLORS
    ):
        parts.append((f"{label}:{count:>2} ", color))
    # Worst-bin indicator: red if any drops, yellow if any near-miss.
    if counts[4] > 0:
        flag_color = (240, 110, 110)
        flag = "DROP"
    elif counts[3] > 0:
        flag_color = (220, 180, 100)
        flag = "NEAR"
    else:
        flag_color = (170, 230, 170)
        flag = "OK"
    parts.append((f"[{flag}]", flag_color))

    rendered = [font.render(text, True, color) for text, color in parts]
    pad = 6
    total_w = sum(s.get_width() for s in rendered)
    h = max(s.get_height() for s in rendered)
    bg = pygame.Surface((total_w + pad * 2, h + pad * 2), pygame.SRCALPHA)
    bg.fill((0, 0, 0, 160))
    sw = screen.get_width()
    bg_x = sw - bg.get_width() - 8
    bg_y = 8
    screen.blit(bg, (bg_x, bg_y))
    cursor = bg_x + pad
    for surf in rendered:
        screen.blit(surf, (cursor, bg_y + pad))
        cursor += surf.get_width()
    del total


def draw_luminance_hud(
    screen: pygame.Surface, font: pygame.font.Font
) -> None:
    """Top-left HUD: avg luminance, Hz, breach indicator. Dev mode only."""
    if not IS_DEV_MODE or DEV_STATE is None or not DEV_STATE.hud_visible:
        return
    probe = DEV_STATE.luminance_probe
    if probe is None:
        return
    hz = probe.hz()
    lum = probe.avg_luminance()
    breach = hz > LUM_PROBE_HZ_BREACH
    color = (255, 90, 90) if breach else (170, 230, 170)
    flag = "BREACH" if breach else "OK"
    text = f"LUM L:{lum:5.1f}  Hz:{hz:4.1f}  [{flag}]"
    surf = font.render(text, True, color)
    pad = 6
    bg = pygame.Surface(
        (surf.get_width() + pad * 2, surf.get_height() + pad * 2),
        pygame.SRCALPHA,
    )
    bg.fill((0, 0, 0, 160))
    screen.blit(bg, (8, 8))
    screen.blit(surf, (8 + pad, 8 + pad))


# Module-level singleton; populated in main() only when IS_DEV_MODE is True.
DEV_STATE: DevState | None = None

# Palette hot-reload — written to and read from ./dev_palette.json. Allows
# live tuning of aurora, music ripple, and emoji confetti colors without
# restarting. mtime is polled at most once every DEV_PALETTE_POLL_SEC.
DEV_PALETTE_PATH = Path(__file__).resolve().parent / "dev_palette.json"
DEV_PALETTE_POLL_SEC = 0.5


# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------

BACKGROUND_COLOR = (0, 0, 0)
SETUP_BACKGROUND_COLOR = (26, 26, 46)  # #1a1a2e deep navy
# Emoji play background — muted Montessori-calm neutral (slightly cooler
# than the setup screen so the two spaces feel distinct without competing
# with the colorful emojis or the Phase 2.03 drifting confetti layer).
EMOJI_BG_COLOR = (26, 26, 36)  # #1a1a24
SETUP_TILE_BG = (45, 45, 68)          # #2d2d44
SETUP_TILE_BG_ACTIVE = (58, 58, 88)
SETUP_ACCENT = (124, 106, 247)        # #7c6af7
SETUP_SUBTITLE_COLOR = (150, 150, 165)
SETUP_ON_GRADIENT_TEXT_COLOR = (74, 74, 106)  # #4a4a6a — tagline & footer on animated bg
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

# Per-theme caps (replace the old global MAX_SHAPES limit).
MAX_RIPPLES = 30
MAX_EMOJIS = 15

EMOJI_FONT_NAME = "Segoe UI Emoji"
EMOJI_LIFETIME = 3.0  # seconds until fully faded
EMOJI_SIZE_MIN = 48
EMOJI_SIZE_MAX = 96

EMOJI_CHARS = (
    "🐶", "🐱", "🐰", "🐻", "🐼", "🦊", "🐸", "🐵",
    "⭐", "🌟", "✨", "🎈", "🌈", "🎉",
    "🍎", "🍌", "🍕", "🍩", "🎂", "❤️",
)

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

# Aurora background — three music-palette hues desaturated 40 % toward luminance.
_AURORA_RAW: tuple[tuple[int, int, int], ...] = (
    (168, 237, 234),  # #a8edea
    (195, 207, 226),  # #c3cfe2
    (224, 195, 252),  # #e0c3fc
)

def _desaturate_rgb(
    rgb: tuple[int, int, int], amount: float = 0.40
) -> tuple[int, int, int]:
    r, g, b = rgb
    lum = 0.299 * r + 0.587 * g + 0.114 * b
    u = max(0.0, min(1.0, amount))
    return (
        int(round(r * (1.0 - u) + lum * u)),
        int(round(g * (1.0 - u) + lum * u)),
        int(round(b * (1.0 - u) + lum * u)),
    )

AURORA_COLORS: tuple[tuple[int, int, int], ...] = tuple(
    _desaturate_rgb(c) for c in _AURORA_RAW
)
AURORA_CYCLE_SEC = 12.0
# Retained for back-compat in dev tooling but no longer used by the render
# path — aurora is now drawn per-pixel via numpy for a smooth gradient.
AURORA_STRIPS = 24

# Sound-reactive pulse overlay constants.
PULSE_DURATION_SEC = 0.35     # how long one pulse lasts
PULSE_PER_KEY = 0.15          # opacity contribution per keypress (0-1)
PULSE_MAX_OPACITY = 0.35      # hard cap so screen never washes out

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
POP_WAVE: np.ndarray | None = None
CURRENT_PLAY_VOLUME = DEFAULT_VOLUME  # updated by apply_session_volume()


# -----------------------------------------------------------------------------
# Dev palette hot-reload (dev mode only)
# -----------------------------------------------------------------------------


def _coerce_rgb_list(
    raw: Any, fallback: tuple[tuple[int, int, int], ...]
) -> tuple[tuple[int, int, int], ...]:
    """Validate raw → tuple of (r,g,b); fall back if any entry is malformed."""
    if not isinstance(raw, list) or not raw:
        return fallback
    out: list[tuple[int, int, int]] = []
    for entry in raw:
        if not isinstance(entry, (list, tuple)) or len(entry) != 3:
            return fallback
        try:
            r, g, b = (int(entry[0]), int(entry[1]), int(entry[2]))
        except (TypeError, ValueError):
            return fallback
        if not (0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255):
            return fallback
        out.append((r, g, b))
    return tuple(out)


def _default_dev_palette_payload() -> dict[str, Any]:
    """Seed JSON values from the current Montessori-tuned constants."""
    return {
        "_comment": (
            "Edit RGB triplets and save; changes apply within ~1s. "
            "Delete this file to regenerate defaults."
        ),
        "aurora": [list(c) for c in AURORA_COLORS],
        "music_palette": [list(c) for c in MUSIC_THEME_PALETTE],
        "emoji_confetti": [list(c) for c in EMOJI_CONFETTI_PALETTE],
    }


def _write_dev_palette_atomic(payload: dict[str, Any]) -> None:
    """Write JSON via temp file + os.replace so a torn write never sticks."""
    tmp = DEV_PALETTE_PATH.with_suffix(".json.tmp")
    try:
        with tmp.open("w", encoding="utf-8") as file:
            json.dump(payload, file, indent=2)
            file.write("\n")
        os.replace(tmp, DEV_PALETTE_PATH)
    except OSError:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass


def _read_dev_palette() -> dict[str, tuple[tuple[int, int, int], ...]] | None:
    """Read the palette file; return None on missing/corrupt."""
    try:
        with DEV_PALETTE_PATH.open(encoding="utf-8") as file:
            data = json.load(file)
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    return {
        "aurora": _coerce_rgb_list(data.get("aurora"), AURORA_COLORS),
        "music_palette": _coerce_rgb_list(
            data.get("music_palette"), MUSIC_THEME_PALETTE
        ),
        "emoji_confetti": _coerce_rgb_list(
            data.get("emoji_confetti"), EMOJI_CONFETTI_PALETTE
        ),
    }


def poll_dev_palette(dt: float) -> None:
    """
    Called once per frame from the game loop. Polls the palette file's mtime
    at most every DEV_PALETTE_POLL_SEC; on change, reloads into DEV_STATE.
    No-op outside dev mode.
    """
    if not IS_DEV_MODE or DEV_STATE is None:
        return
    # The accumulator lives on DEV_STATE so we don't add a global.
    acc = DEV_STATE.palette_overrides.get("_acc", 0.0)
    if not isinstance(acc, float):
        acc = 0.0
    acc += dt
    if acc < DEV_PALETTE_POLL_SEC:
        DEV_STATE.palette_overrides["_acc"] = acc
        return
    DEV_STATE.palette_overrides["_acc"] = 0.0

    try:
        mtime = DEV_PALETTE_PATH.stat().st_mtime
    except OSError:
        mtime = 0.0
    if mtime == DEV_STATE.palette_mtime:
        return
    parsed = _read_dev_palette()
    if parsed is None:
        return
    DEV_STATE.palette_overrides.update(parsed)
    DEV_STATE.palette_mtime = mtime
    _dev_trace(f"palette reloaded from {DEV_PALETTE_PATH.name}")


def init_dev_palette() -> None:
    """First-run: write defaults if file missing, then load into DEV_STATE."""
    if not IS_DEV_MODE or DEV_STATE is None:
        return
    if not DEV_PALETTE_PATH.exists():
        _write_dev_palette_atomic(_default_dev_palette_payload())
        _dev_trace(f"wrote default palette to {DEV_PALETTE_PATH.name}")
    parsed = _read_dev_palette()
    if parsed is None:
        return
    DEV_STATE.palette_overrides.update(parsed)
    try:
        DEV_STATE.palette_mtime = DEV_PALETTE_PATH.stat().st_mtime
    except OSError:
        DEV_STATE.palette_mtime = 0.0


def get_aurora_colors() -> tuple[tuple[int, int, int], ...]:
    """Live aurora colors (dev override falls through to baked constant)."""
    if IS_DEV_MODE and DEV_STATE is not None:
        override = DEV_STATE.palette_overrides.get("aurora")
        if isinstance(override, tuple) and override:
            return override  # type: ignore[return-value]
    return AURORA_COLORS


def get_music_palette() -> tuple[tuple[int, int, int], ...]:
    """Live music ripple palette."""
    if IS_DEV_MODE and DEV_STATE is not None:
        override = DEV_STATE.palette_overrides.get("music_palette")
        if isinstance(override, tuple) and override:
            return override  # type: ignore[return-value]
    return MUSIC_THEME_PALETTE


def get_emoji_confetti_palette() -> tuple[tuple[int, int, int], ...]:
    """Live emoji confetti palette."""
    if IS_DEV_MODE and DEV_STATE is not None:
        override = DEV_STATE.palette_overrides.get("emoji_confetti")
        if isinstance(override, tuple) and override:
            return override  # type: ignore[return-value]
    return EMOJI_CONFETTI_PALETTE


# -----------------------------------------------------------------------------
# Procedural audio
# -----------------------------------------------------------------------------


def _shape_for_mixer(mono_samples: np.ndarray) -> np.ndarray:
    """
    Reshape a mono int16 array to match the active mixer's channel count.
    pygame.mixer.init can silently fall back to mono if the audio driver
    doesn't accept the requested stereo format (AUDIO_ALLOW_CHANNELS_CHANGE
    is on by default). pygame.sndarray.make_sound requires the array's
    dimensionality to match the mixer exactly — 1D for mono, 2D for stereo
    — or it raises ValueError. Returning the right shape keeps audio
    working on machines where stereo wasn't negotiated.
    """
    init = pygame.mixer.get_init()
    if init is None:
        return mono_samples
    channels = init[2]
    if channels >= 2:
        return np.column_stack([mono_samples] * channels)
    return mono_samples


def _generate_note_sound(frequency: float) -> pygame.mixer.Sound:
    """Sine bell: 10 ms attack, exponential decay. Shape adapts to mixer."""
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
    samples = _shape_for_mixer(mono)
    sound = pygame.sndarray.make_sound(samples)
    sound.set_volume(1.0)
    return sound


def build_note_sounds() -> list[pygame.mixer.Sound]:
    """Generate and cache all pentatonic note samples."""
    return [_generate_note_sound(freq) for freq in PENTATONIC_FREQS]


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
    samples = _shape_for_mixer(mono)
    sound = pygame.sndarray.make_sound(samples)
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

    def clear(self) -> None:
        """Reset theme state when switching themes."""
        self._on_clear()

    @abstractmethod
    def _on_clear(self) -> None:
        """Subclass hook to wipe lists and timers."""

    @abstractmethod
    def on_keypress(self, key: int) -> None:
        """React to a key press (non-system keys only)."""

    @abstractmethod
    def update(self, dt: float) -> None:
        """Advance animations; dt is seconds since last frame."""

    def draw_background(self, screen: pygame.Surface) -> None:
        """Fill the screen before drawing theme visuals. Override for custom backgrounds."""
        screen.fill(BACKGROUND_COLOR)

    @abstractmethod
    def draw(self, screen: pygame.Surface) -> None:
        """Draw visuals on top of the already-filled background."""

    def _random_position(self, margin: int = 40) -> tuple[int, int]:
        x = random.randint(margin, max(margin, self._screen_w - margin))
        y = random.randint(margin, max(margin, self._screen_h - margin))
        return x, y


# -----------------------------------------------------------------------------
# Background composition — per-theme background layer owned by each Theme.
# Themes delegate to their background for the bottom-most visual layer so
# later phases (Phase 2 confetti drift, Phase 5 illustrated scenes) can layer
# additional content into a clean seam without rewriting the theme classes.
# -----------------------------------------------------------------------------


class Background:
    """Base class for theme background layers. Subclasses own all state."""

    def __init__(self, screen: pygame.Surface) -> None:
        self._screen_w, self._screen_h = screen.get_size()

    def clear(self) -> None:
        """Reset background state (called from Theme.clear)."""

    def update(self, dt: float) -> None:
        """Advance background animations; default no-op."""

    def draw(self, screen: pygame.Surface) -> None:
        """Paint the background. Default: solid BACKGROUND_COLOR fill."""
        screen.fill(BACKGROUND_COLOR)


class MusicBackground(Background):
    """Aurora gradient with sound-reactive white pulse overlay."""

    def __init__(self, screen: pygame.Surface) -> None:
        super().__init__(screen)
        self._aurora_time: float = 0.0
        self._pulses: list[float] = []
        self._pulse_surf: pygame.Surface | None = None

    def clear(self) -> None:
        self._pulses.clear()

    def on_pulse_trigger(self) -> None:
        """Called by MusicTheme.on_keypress to register a new pulse."""
        self._pulses.append(0.0)

    def update(self, dt: float) -> None:
        self._aurora_time += dt
        self._pulses = [
            age + dt for age in self._pulses
            if age + dt < PULSE_DURATION_SEC
        ]

    def draw(self, screen: pygame.Surface) -> None:
        w, h = screen.get_size()
        aurora = get_aurora_colors()
        if len(aurora) >= 3:
            c0, c1, c2 = aurora[0], aurora[1], aurora[2]
        else:
            c0, c1, c2 = AURORA_COLORS
        tau_inv = self._aurora_time / AURORA_CYCLE_SEC
        pix = _aurora_column_pixels(tau_inv, h, c0, c1, c2)
        col_surf = pygame.surfarray.make_surface(pix)
        pygame.transform.scale(col_surf, (w, h), screen)

        if self._pulses:
            total = 0.0
            for age in self._pulses:
                t = age / PULSE_DURATION_SEC
                fade = 1.0 - _ease_out_cubic(t)
                total += fade * PULSE_PER_KEY
            total = min(total, PULSE_MAX_OPACITY)
            overlay_alpha = int(round(total * 255))
            if overlay_alpha > 0:
                if (
                    self._pulse_surf is None
                    or self._pulse_surf.get_size() != (w, h)
                ):
                    self._pulse_surf = pygame.Surface((w, h), pygame.SRCALPHA)
                    self._pulse_surf.fill((255, 255, 255, 0))
                self._pulse_surf.set_alpha(overlay_alpha)
                self._pulse_surf.fill((255, 255, 255))
                screen.blit(self._pulse_surf, (0, 0))


class EmojiBackground(Background):
    """
    Calm Montessori-neutral base for the Emoji theme. Replaces the previous
    pure-black BACKGROUND_COLOR fill so the emojis feel like they're sitting
    on a soft dark canvas rather than a void. Phase 2.03 layers drifting
    confetti on top of this fill.
    """

    def draw(self, screen: pygame.Surface) -> None:
        screen.fill(EMOJI_BG_COLOR)


# -----------------------------------------------------------------------------
# MusicTheme — expanding, fading ripples
# -----------------------------------------------------------------------------

SCALE_IN_DURATION_SEC = 0.12
EMOJI_BOUNCE_DURATION_SEC = 0.08
SPARKLE_LIFETIME_SEC = 0.4
CONFETTI_LIFETIME_SEC = 0.6
CONFETTI_GRAVITY_PPS2 = 480.0


def _ease_out_cubic(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 1.0 - (1.0 - t) ** 3


def _aurora_column_pixels(
    t_norm: float,
    height: int,
    c0: tuple[int, int, int],
    c1: tuple[int, int, int],
    c2: tuple[int, int, int],
) -> np.ndarray:
    """
    Build a (1, height, 3) uint8 column where every row's color comes from
    the per-pixel aurora wave. The result is a 1-pixel-wide image suitable
    for pygame.surfarray.make_surface + transform.scale to fill the screen.
    Smooths the previous 24-strip render by sampling at the row resolution
    of the display, killing the visible horizontal banding.
    """
    fy = (np.arange(height, dtype=np.float32) + 0.5) / float(height)
    two_pi = 2.0 * math.pi
    wave = (
        np.sin(two_pi * (fy * 1.4 + t_norm)) * 0.6
        + np.sin(two_pi * (fy * 0.7 - t_norm * 0.55 + 0.3)) * 0.4
    )
    p = (wave + 1.0) * 0.5
    c0a = np.asarray(c0, dtype=np.float32)
    c1a = np.asarray(c1, dtype=np.float32)
    c2a = np.asarray(c2, dtype=np.float32)
    mask_low = (p < 0.5).reshape(-1, 1)
    p_low = (p * 2.0).reshape(-1, 1)
    p_high = ((p - 0.5) * 2.0).reshape(-1, 1)
    low = c0a * (1.0 - p_low) + c1a * p_low
    high = c1a * (1.0 - p_high) + c2a * p_high
    colors = np.where(mask_low, low, high)
    pix = np.empty((1, height, 3), dtype=np.uint8)
    pix[0] = colors.clip(0.0, 255.0).astype(np.uint8)
    return pix


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
    ) -> None:
        super().__init__(screen, intensity)
        self.ripples: list[Ripple] = []
        self.sparkles: list[SparkleParticle] = []
        self._note_sounds = note_sounds if note_sounds is not None else NOTE_SOUNDS
        scale = self._intensity_scale
        self._max_ripples = max(1, int(MAX_RIPPLES * scale))
        self._radius_growth = self.RADIUS_GROWTH * scale
        self._ring_width = max(3, int(self.RING_WIDTH * scale))
        self._initial_radius = 8.0 * scale
        self._background = MusicBackground(screen)

    def _on_clear(self) -> None:
        self.ripples.clear()
        self.sparkles.clear()
        self._background.clear()

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
        note_idx = key_to_note_index(key)
        self._note_sounds[note_idx].play()  # overlaps on separate channels

        if len(self.ripples) >= self._max_ripples:
            self.ripples.pop(0)
        x, y = self._random_position()
        base = random.choice(get_music_palette())
        color = _apply_intensity_to_rgb(base, self.intensity)
        ripple = Ripple(x, y, color)
        ripple.radius = self._initial_radius
        self.ripples.append(ripple)
        self._spawn_sparkles(x, y, _lighter_tint(color))
        self._background.on_pulse_trigger()

    def draw_background(self, screen: pygame.Surface) -> None:
        self._background.draw(screen)

    def update(self, dt: float) -> None:
        self._background.update(dt)
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
            if sp.age < SPARKLE_LIFETIME_SEC:
                spark_alive.append(sp)
        self.sparkles = spark_alive

    def draw(self, screen: pygame.Surface) -> None:
        for ripple in self.ripples:
            pop = _ripple_pop_scale(ripple.pop_age)
            r = max(1, int(ripple.radius * pop))
            alpha = max(0, min(255, int(ripple.alpha)))
            if alpha == 0:
                continue

            diameter = r * 2
            surf = pygame.Surface((diameter, diameter), pygame.SRCALPHA)
            rw = max(1, int(self._ring_width * pop)) if pop < 1.0 else self._ring_width
            pygame.draw.circle(
                surf,
                (*ripple.color, alpha),
                (r, r),
                r,
                width=rw,
            )
            screen.blit(surf, (ripple.x - r, ripple.y - r))

        for sp in self.sparkles:
            t = sp.age / SPARKLE_LIFETIME_SEC
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
    ) -> None:
        super().__init__(screen, intensity)
        self.emojis: list[EmojiSprite] = []
        self.confetti: list[ConfettiParticle] = []
        self._font_cache: dict[int, pygame.font.Font] = {}
        scale = self._intensity_scale
        self._max_emojis = max(1, int(MAX_EMOJIS * scale))
        self._size_min = max(16, int(EMOJI_SIZE_MIN * scale))
        self._size_max = max(self._size_min, int(EMOJI_SIZE_MAX * scale))
        self._background = EmojiBackground(screen)

    def _on_clear(self) -> None:
        self.emojis.clear()
        self.confetti.clear()
        self._background.clear()

    def draw_background(self, screen: pygame.Surface) -> None:
        self._background.draw(screen)

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
            base = random.choice(get_emoji_confetti_palette())
            dot_color = _apply_intensity_to_rgb(base, self.intensity)
            self.confetti.append(
                ConfettiParticle(float(cx), float(cy), vx, vy, r, dot_color)
            )

    def on_keypress(self, key: int) -> None:
        del key
        play_pop_sound()

        if len(self.emojis) >= self._max_emojis:
            self.emojis.pop(0)
        x, y = self._random_position(margin=60)
        size = random.randint(self._size_min, self._size_max)
        self.emojis.append(EmojiSprite(x, y, random.choice(EMOJI_CHARS), size))
        self._spawn_confetti(x, y)

    def update(self, dt: float) -> None:
        self._background.update(dt)
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
    return EmojiTheme(screen, intensity)


def draw_theme_label(
    screen: pygame.Surface,
    label: str,
    hud_font: pygame.font.Font,
) -> None:
    text = hud_font.render(label, True, (180, 180, 180))
    screen.blit(text, (16, 12))


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
        # Dev-mode HUD / stress-test keys bypass the theme queue and are
        # surfaced directly to pygame's event queue so the main loop's
        # KEYDOWN handlers fire as they would in SETUP.
        if IS_DEV_MODE and pygame_key in (pygame.K_F7, pygame.K_F8, pygame.K_F9):
            try:
                pygame.event.post(
                    pygame.event.Event(pygame.KEYDOWN, {"key": pygame_key})
                )
            except pygame.error:
                pass
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


# --- Hard-kill recovery -----------------------------------------------------
#
# atexit only fires on graceful interpreter shutdown. If the user kills the
# process via Task Manager (or the OS does, e.g. on power loss), the
# registry / SPI suppressions remain in place: the Win key stays blocked,
# Win+L stays disabled, toast notifications stay muted, FilterKeys etc.
# stay zeroed. These can leave the parent locked out of normal shortcuts.
#
# Mitigation: a marker file is written when a session begins and deleted
# when it ends cleanly. If the marker is present at next startup, the
# previous session did not clean up — we then best-effort delete our three
# registry values. (Accessibility SPI originals can't be recovered because
# we never persisted them; the user would need to re-enable FilterKeys
# manually if they had it on. Documented in Phase 1.05.)

SESSION_DIRTY_PATH = Path(__file__).resolve().parent / ".session_dirty"

_RECOVERY_REGISTRY_KEYS: tuple[tuple[str, str], ...] = (
    (r"Software\Microsoft\Windows\CurrentVersion\Policies\Explorer", "NoWinKeys"),
    (r"Software\Microsoft\Windows\CurrentVersion\Policies\System", "DisableLockWorkstation"),
    (
        r"Software\Microsoft\Windows\CurrentVersion\Notifications\Settings",
        "NOC_GLOBAL_SETTING_TOASTS_ENABLED",
    ),
)


def _mark_session_dirty() -> None:
    try:
        SESSION_DIRTY_PATH.touch()
    except OSError:
        pass


def _clear_session_dirty() -> None:
    try:
        SESSION_DIRTY_PATH.unlink(missing_ok=True)
    except OSError:
        pass


def recover_dirty_session() -> bool:
    """
    If a marker from a hard-killed prior session is present, best-effort
    delete our three registry values so the Win key / Win+L / notifications
    return to their default (Windows-managed) behavior. Returns True if
    recovery ran, False if no marker was present. Safe to call on
    non-Windows or with no admin rights — failures are silent.
    """
    if not SESSION_DIRTY_PATH.exists():
        return False
    if sys.platform == "win32":
        try:
            import winreg

            for path, value_name in _RECOVERY_REGISTRY_KEYS:
                try:
                    with winreg.OpenKey(
                        winreg.HKEY_CURRENT_USER,
                        path,
                        0,
                        winreg.KEY_WRITE,
                    ) as key:
                        try:
                            winreg.DeleteValue(key, value_name)
                        except FileNotFoundError:
                            pass
                except OSError:
                    pass
            _broadcast_setting_change()
        except ImportError:
            pass
    _clear_session_dirty()
    _dev_log("recovered stale session: cleared NoWinKeys / DisableLockWorkstation / toast policy")
    return True


def leave_playing_state(
    notification_suppressor: NotificationSuppressor,
    keyboard_lockdown: KeyboardLockdown,
    win_key_suppressor: WinKeySuppressor,
    lock_workstation_suppressor: DisableLockWorkstationSuppressor,
    accessibility_keys_suppressor: AccessibilityKeysSuppressor,
) -> None:
    """Call when exiting PLAYING (return to setup or quit)."""
    dev_session_end()
    keyboard_lockdown.remove()
    win_key_suppressor.restore()
    lock_workstation_suppressor.restore()
    accessibility_keys_suppressor.restore()
    notification_suppressor.restore()
    _clear_session_dirty()


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
    # Drop a marker so we can detect a hard-kill (Task Manager) on the next
    # launch and undo the registry suppressions even though atexit did not
    # get a chance to run.
    _mark_session_dirty()


# -----------------------------------------------------------------------------
# Settings persistence (settings.json beside main.py)
# -----------------------------------------------------------------------------

SETTINGS_PATH = Path(__file__).resolve().parent / "settings.json"


class AppSettings(NamedTuple):
    volume: float
    intensity: float
    suppress_notifications: bool


def default_settings() -> AppSettings:
    return AppSettings(
        DEFAULT_VOLUME,
        DEFAULT_INTENSITY,
        DEFAULT_SUPPRESS_NOTIFICATIONS,
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
                settings = AppSettings(
                    _clamp_unit_float(data.get("volume"), defaults.volume),
                    _clamp_unit_float(data.get("intensity"), defaults.intensity),
                    _parse_bool(
                        data.get("suppress_notifications"),
                        defaults.suppress_notifications,
                    ),
                )
                save_settings(settings)
                return settings
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        pass
    save_settings(defaults)
    return defaults


# -----------------------------------------------------------------------------
# App state
# -----------------------------------------------------------------------------


class AppState(Enum):
    SETUP = auto()
    PLAYING = auto()


class _ThemeTile:
    __slots__ = ("emoji", "label", "subtitle", "factory")

    def __init__(
        self,
        emoji: str,
        label: str,
        subtitle: str,
        factory: type[Theme],
    ) -> None:
        self.emoji = emoji
        self.label = label
        self.subtitle = subtitle
        self.factory = factory


_THEME_TILES: tuple[_ThemeTile, ...] = (
    _ThemeTile("🎵", "Music", "Piano notes", MusicTheme),
    _ThemeTile("🎊", "Emoji", "Fun emojis", EmojiTheme),
)


class SessionConfig(NamedTuple):
    theme_factory: type[Theme]
    volume: float
    intensity: float
    suppress_notifications: bool


def _lerp_rgb(
    a: tuple[int, int, int], b: tuple[int, int, int], t: float
) -> tuple[int, int, int]:
    t = max(0.0, min(1.0, t))
    return (
        int(round(float(a[0]) + (float(b[0]) - float(a[0])) * t)),
        int(round(float(a[1]) + (float(b[1]) - float(a[1])) * t)),
        int(round(float(a[2]) + (float(b[2]) - float(a[2])) * t)),
    )


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

        self._selected_index: int | None = None
        self._hovered_index: int | None = None
        self._dragging_slider: SetupSlider | None = None
        self._tile_rects: list[pygame.Rect] = []
        self._title_rect = pygame.Rect(0, 0, 0, 0)
        self._tagline_rect = pygame.Rect(0, 0, 0, 0)
        self._button_rect = pygame.Rect(0, 0, 0, 0)
        self._close_rect = pygame.Rect(0, 0, 0, 0)
        self._footer_hint_y = 0
        self._close_hover = False
        self._button_hover = False
        self._bg_time = 0.0
        self._sliders: list[SetupSlider] = []
        self._settings = load_settings()
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

    def _persist_settings(self) -> None:
        save_settings(
            AppSettings(self.volume, self.intensity, self.suppress_notifications)
        )

    def tick(self, dt: float) -> None:
        """Advance setup-only animation (background gradient)."""
        self._bg_time += dt

    def _draw_animated_background(self, screen: pygame.Surface) -> None:
        w, h = screen.get_size()
        phase = (math.sin(self._bg_time * (2.0 * math.pi / SETUP_BG_CYCLE_SEC)) + 1.0) * 0.5
        pal = get_music_palette()
        if len(pal) < 8:
            pal = MUSIC_THEME_PALETTE
        # Morph gradient endpoints through palette pairs; blend toward base so UI stays legible.
        c_top = _lerp_rgb(_lerp_rgb(pal[0], pal[5], phase), SETUP_BACKGROUND_COLOR, 0.32)
        c_bot = _lerp_rgb(_lerp_rgb(pal[3], pal[7], phase), SETUP_BACKGROUND_COLOR, 0.32)
        bands = SETUP_GRADIENT_BANDS
        for i in range(bands):
            y0 = (i * h) // bands
            y1 = ((i + 1) * h) // bands
            if y1 <= y0:
                y1 = y0 + 1
            t = (i + 0.5) / float(bands)
            c = _lerp_rgb(c_top, c_bot, t)
            pygame.draw.rect(screen, c, (0, y0, w, y1 - y0))

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

        sliders_top = tiles_top + SETUP_TILE_HEIGHT + max(22, int(h * 0.028))
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
                )

        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self._dragging_slider is not None:
                self._persist_settings()
            self._dragging_slider = None

        return None

    def _draw_tile(
        self,
        screen: pygame.Surface,
        tile: _ThemeTile,
        rect: pygame.Rect,
        *,
        highlighted: bool,
    ) -> None:
        bg = SETUP_TILE_BG_ACTIVE if highlighted else SETUP_TILE_BG
        pygame.draw.rect(screen, bg, rect, border_radius=16)
        if highlighted:
            pygame.draw.rect(
                screen,
                SETUP_ACCENT,
                rect,
                width=SETUP_TILE_BORDER,
                border_radius=16,
            )

        emoji_surf = self._tile_emoji_font.render(tile.emoji, True, (255, 255, 255))
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
            SETUP_TAGLINE_TEXT, True, SETUP_ON_GRADIENT_TEXT_COLOR
        )
        screen.blit(tag_surf, self._tagline_rect)

        for i, (tile, rect) in enumerate(zip(_THEME_TILES, self._tile_rects)):
            highlighted = i == self._selected_index or i == self._hovered_index
            self._draw_tile(screen, tile, rect, highlighted=highlighted)

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
            SETUP_FOOTER_HINT_TEXT, True, SETUP_ON_GRADIENT_TEXT_COLOR
        )
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
        theme = MusicTheme(screen, NOTE_SOUNDS, config.intensity)
    else:
        theme = EmojiTheme(screen, config.intensity)
    dev_session_start(theme.name, config.volume, config.intensity)
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
) -> tuple[Theme, str, float]:
    """Update and draw one playing frame; returns possibly updated theme/label."""
    current_theme.update(dt)

    current_theme.draw_background(screen)
    current_theme.draw(screen)

    if label_timer > 0:
        draw_theme_label(screen, label_text, hud_font)
        label_timer -= dt

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
    global NOTE_SOUNDS, POP_WAVE, _SESSION_CLEANUP_ARGS, _ATEXIT_SESSION_CLEANUP_REGISTERED
    global DEV_STATE

    if IS_DEV_MODE:
        DEV_STATE = DevState()
        init_dev_palette()
        _dev_trace("dev mode active")

    # If the previous run was hard-killed, undo any registry suppressions
    # before we construct new ones (otherwise their enable() would capture
    # the stale-suppressed value as the 'original' to restore).
    recover_dirty_session()

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
        # Allocate generously so Music's 0.6 s notes don't cut each other off
        # under rapid input. At 30 Hz keypresses (worst case via F7 stress
        # test) up to ~18 notes can overlap. Default 8 channels would steal
        # older notes mid-decay, producing audible chops; 32 covers the
        # overlap with headroom for EmojiTheme's 0.12 s pops too.
        pygame.mixer.set_num_channels(32)

        NOTE_SOUNDS = build_note_sounds()
        POP_WAVE = build_pop_wave()

        screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        pygame.display.set_caption("Toddler Key Smash")
        clock = pygame.time.Clock()
        hud_font = pygame.font.SysFont(UI_FONT_NAME, 28)
        unlock_overlay_font = pygame.font.SysFont(UI_FONT_NAME, 18)

        dev_hud_font: pygame.font.Font | None = None
        dev_overlay_font: pygame.font.Font | None = None
        if IS_DEV_MODE and DEV_STATE is not None:
            DEV_STATE.luminance_probe = LuminanceProbe(screen.get_size())
            DEV_STATE.frame_histogram = FrameHistogram()
            DEV_STATE.stress_test = StressTest()
            dev_hud_font = pygame.font.SysFont(UI_FONT_NAME, 16)
            dev_overlay_font = pygame.font.SysFont(UI_FONT_NAME, 22)

        app_state = AppState.SETUP
        setup_screen = SetupScreen(screen)
        current_theme: Theme | None = None
        label_text = ""
        label_timer = 0.0
        foreground_check_accumulator = 0.0

        running = True
        while running:
            dt = clock.tick(TARGET_FPS) / 1000.0

            poll_dev_palette(dt)

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
                    IS_DEV_MODE
                    and DEV_STATE is not None
                    and event.type == pygame.KEYDOWN
                    and event.key == pygame.K_F8
                ):
                    DEV_STATE.hud_visible = not DEV_STATE.hud_visible
                    _dev_trace(
                        f"luminance HUD {'on' if DEV_STATE.hud_visible else 'off'}"
                    )

                elif (
                    IS_DEV_MODE
                    and DEV_STATE is not None
                    and event.type == pygame.KEYDOWN
                    and event.key == pygame.K_F9
                ):
                    DEV_STATE.frame_hist_visible = not DEV_STATE.frame_hist_visible
                    _dev_trace(
                        f"frame histogram "
                        f"{'on' if DEV_STATE.frame_hist_visible else 'off'}"
                    )

                elif (
                    IS_DEV_MODE
                    and DEV_STATE is not None
                    and DEV_STATE.stress_test is not None
                    and event.type == pygame.KEYDOWN
                    and event.key == pygame.K_F7
                ):
                    if app_state == AppState.PLAYING and current_theme is not None:
                        DEV_STATE.stress_test.start(time.monotonic())
                        _dev_log("stress test started (15 s)")
                    else:
                        _dev_trace("stress test requires PLAYING state")

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

            if app_state == AppState.SETUP:
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
                )

            if IS_DEV_MODE and DEV_STATE is not None:
                now_mono = time.monotonic()
                probe = DEV_STATE.luminance_probe
                if probe is not None:
                    if probe.positions and (
                        probe.positions[-1][0] >= screen.get_width()
                        or probe.positions[-1][1] >= screen.get_height()
                    ):
                        probe.resize(screen.get_size())
                    probe.sample(screen, now_mono)
                    breach_hz = probe.hz()
                    if (
                        breach_hz > LUM_PROBE_HZ_BREACH
                        and now_mono - DEV_STATE.last_lum_breach_log >= 1.0
                    ):
                        _dev_log(
                            f"luminance breach hz={breach_hz:.2f} "
                            f"(cap {LUM_PROBE_HZ_BREACH:.1f})"
                        )
                        DEV_STATE.last_lum_breach_log = now_mono
                        DEV_STATE.session_breach_count += 1
                if DEV_STATE.frame_histogram is not None:
                    DEV_STATE.frame_histogram.push(dt, now_mono)
                    dropped = DEV_STATE.frame_histogram.counts()[4]
                    if (
                        dropped > 0
                        and now_mono - DEV_STATE.last_drop_log >= 1.0
                    ):
                        _dev_log(
                            f"frame drops in last 1s: {dropped} frames >20ms"
                        )
                        DEV_STATE.last_drop_log = now_mono
                        DEV_STATE.session_drop_count += 1
                stress = DEV_STATE.stress_test
                if (
                    stress is not None
                    and stress.active
                    and app_state == AppState.PLAYING
                ):
                    result = stress.tick(
                        now_mono,
                        current_theme,
                        DEV_STATE.luminance_probe,
                        DEV_STATE.frame_histogram,
                    )
                    if result is not None:
                        passed, summary = result
                        DEV_STATE.stress_result_pass = passed
                        DEV_STATE.stress_result_text = summary
                        DEV_STATE.stress_result_until = now_mono + 5.0
                        verdict = "PASS" if passed else "FAIL"
                        _dev_log(f"stress test {verdict}: {summary}")
                if dev_hud_font is not None:
                    draw_luminance_hud(screen, dev_hud_font)
                    draw_frame_histogram(screen, dev_hud_font)
                if dev_overlay_font is not None:
                    draw_stress_overlay(screen, dev_overlay_font)

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
