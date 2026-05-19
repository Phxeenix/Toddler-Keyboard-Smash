"""
Toddler Key Smash — parent setup, then themed keypress play.
Setup: Start Session  |  Playing: F1/F2 themes  |  Escape: quit
"""

from __future__ import annotations

import json
import random
import sys
from abc import ABC, abstractmethod
from enum import Enum, auto
from pathlib import Path
from typing import Any, NamedTuple

import numpy as np
import pygame

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------

BACKGROUND_COLOR = (0, 0, 0)
SETUP_BACKGROUND_COLOR = (26, 26, 46)  # #1a1a2e deep navy
SETUP_TILE_BG = (45, 45, 68)          # #2d2d44
SETUP_TILE_BG_ACTIVE = (58, 58, 88)
SETUP_ACCENT = (124, 106, 247)        # #7c6af7
SETUP_SUBTITLE_COLOR = (150, 150, 165)
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
NOTIFY_TOGGLE_LABEL = "🔔 Suppress notifications"
THEME_LABEL_DURATION = 2.0  # seconds to show theme name after switching
TARGET_FPS = 60

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

# Soft pastels for MusicTheme ripples.
PASTEL_PALETTE: tuple[tuple[int, int, int], ...] = (
    (255, 182, 193),
    (255, 218, 185),
    (255, 255, 186),
    (186, 255, 201),
    (186, 225, 255),
    (220, 198, 255),
    (255, 204, 229),
    (200, 240, 220),
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


class Ripple:
    __slots__ = ("x", "y", "radius", "color", "alpha")

    def __init__(self, x: int, y: int, color: tuple[int, int, int]) -> None:
        self.x = x
        self.y = y
        self.radius = 8.0
        self.color = color
        self.alpha = 255.0


class MusicTheme(Theme):
    """Soft pastel ripples that expand and fade on each keypress."""

    name = "Music"

    RADIUS_GROWTH = 140.0  # pixels per second
    ALPHA_FADE = 100.0     # alpha per second (~2.5s full fade)
    RING_WIDTH = 5

    def __init__(
        self,
        screen: pygame.Surface,
        note_sounds: list[pygame.mixer.Sound] | None = None,
        intensity: float = DEFAULT_INTENSITY,
    ) -> None:
        super().__init__(screen, intensity)
        self.ripples: list[Ripple] = []
        self._note_sounds = note_sounds if note_sounds is not None else NOTE_SOUNDS
        scale = self._intensity_scale
        self._max_ripples = max(1, int(MAX_RIPPLES * scale))
        self._radius_growth = self.RADIUS_GROWTH * scale
        self._ring_width = max(2, int(self.RING_WIDTH * scale))
        self._initial_radius = 8.0 * scale

    def _on_clear(self) -> None:
        self.ripples.clear()

    def on_keypress(self, key: int) -> None:
        note_idx = key_to_note_index(key)
        self._note_sounds[note_idx].play()  # overlaps on separate channels

        if len(self.ripples) >= self._max_ripples:
            self.ripples.pop(0)
        x, y = self._random_position()
        ripple = Ripple(x, y, random.choice(PASTEL_PALETTE))
        ripple.radius = self._initial_radius
        self.ripples.append(ripple)

    def update(self, dt: float) -> None:
        alive: list[Ripple] = []
        for ripple in self.ripples:
            ripple.radius += self._radius_growth * dt
            ripple.alpha -= self.ALPHA_FADE * dt
            if ripple.alpha > 0:
                alive.append(ripple)
        self.ripples = alive

    def draw(self, screen: pygame.Surface) -> None:
        for ripple in self.ripples:
            r = int(ripple.radius)
            if r < 1:
                continue
            alpha = max(0, min(255, int(ripple.alpha)))
            if alpha == 0:
                continue

            diameter = r * 2
            surf = pygame.Surface((diameter, diameter), pygame.SRCALPHA)
            pygame.draw.circle(
                surf,
                (*ripple.color, alpha),
                (r, r),
                r,
                width=self._ring_width,
            )
            screen.blit(surf, (ripple.x - r, ripple.y - r))


# -----------------------------------------------------------------------------
# EmojiTheme — floating emojis that fade out
# -----------------------------------------------------------------------------


class EmojiSprite:
    __slots__ = ("x", "y", "char", "size", "age")

    def __init__(self, x: int, y: int, char: str, size: int) -> None:
        self.x = x
        self.y = y
        self.char = char
        self.size = size
        self.age = 0.0


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
        self._font_cache: dict[int, pygame.font.Font] = {}
        scale = self._intensity_scale
        self._max_emojis = max(1, int(MAX_EMOJIS * scale))
        self._size_min = max(16, int(EMOJI_SIZE_MIN * scale))
        self._size_max = max(self._size_min, int(EMOJI_SIZE_MAX * scale))

    def _on_clear(self) -> None:
        self.emojis.clear()

    def _font_for_size(self, size: int) -> pygame.font.Font:
        if size not in self._font_cache:
            self._font_cache[size] = pygame.font.SysFont(EMOJI_FONT_NAME, int(size * 1.3))
        return self._font_cache[size]

    def on_keypress(self, key: int) -> None:
        del key
        play_pop_sound()

        if len(self.emojis) >= self._max_emojis:
            self.emojis.pop(0)
        x, y = self._random_position(margin=60)
        size = random.randint(self._size_min, self._size_max)
        self.emojis.append(EmojiSprite(x, y, random.choice(EMOJI_CHARS), size))

    def update(self, dt: float) -> None:
        alive: list[EmojiSprite] = []
        for emoji in self.emojis:
            emoji.age += dt
            if emoji.age < EMOJI_LIFETIME:
                alive.append(emoji)
        self.emojis = alive

    def draw(self, screen: pygame.Surface) -> None:
        for emoji in self.emojis:
            t = emoji.age / EMOJI_LIFETIME
            alpha = int(255 * (1.0 - t))
            if alpha <= 0:
                continue

            font = self._font_for_size(emoji.size)
            text = font.render(emoji.char, True, (255, 255, 255))
            text.set_alpha(alpha)
            rect = text.get_rect(center=(emoji.x, emoji.y))
            screen.blit(text, rect)


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


def leave_playing_state(notification_suppressor: NotificationSuppressor) -> None:
    """Call when exiting PLAYING (return to setup or quit)."""
    notification_suppressor.restore()


def enter_playing_state(
    notification_suppressor: NotificationSuppressor,
    suppress: bool,
) -> None:
    """Apply notification suppression when a session starts."""
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

    TITLE_TEXT = "✨ Keyboard Masher"
    BUTTON_TEXT = "START SESSION"

    def __init__(self, screen: pygame.Surface) -> None:
        self._screen = screen
        self._title_font = pygame.font.SysFont(UI_FONT_NAME, 56)
        self._tile_emoji_font = pygame.font.SysFont(EMOJI_FONT_NAME, 60)
        self._tile_label_font = pygame.font.SysFont(UI_FONT_NAME, 24, bold=True)
        self._tile_subtitle_font = pygame.font.SysFont(UI_FONT_NAME, 14)
        self._button_font = pygame.font.SysFont(UI_FONT_NAME, 32)
        self._slider_label_font = pygame.font.SysFont(UI_FONT_NAME, 18)
        self._slider_value_font = pygame.font.SysFont(UI_FONT_NAME, 16)

        self._selected_index: int | None = None
        self._hovered_index: int | None = None
        self._dragging_slider: SetupSlider | None = None
        self._tile_rects: list[pygame.Rect] = []
        self._title_rect = pygame.Rect(0, 0, 0, 0)
        self._button_rect = pygame.Rect(0, 0, 0, 0)
        self._sliders: list[SetupSlider] = []
        self._settings = load_settings()
        self._layout()
        apply_session_volume(self.volume)

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

    def _layout(self) -> None:
        w, h = self._screen.get_size()
        title_surf = self._title_font.render(self.TITLE_TEXT, True, (255, 255, 255))
        self._title_rect = title_surf.get_rect(center=(w // 2, int(h * 0.18)))

        row_width = SETUP_TILE_WIDTH * 2 + SETUP_TILE_GAP
        tiles_left = (w - row_width) // 2
        tiles_top = int(h * 0.30)
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

        sliders_top = tiles_top + SETUP_TILE_HEIGHT + 28
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
        self._button_rect = button_surf.get_rect(
            center=(w // 2, toggle_bottom + 44),
        ).inflate(pad_x, pad_y)

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

    def draw(self, screen: pygame.Surface) -> None:
        screen.fill(SETUP_BACKGROUND_COLOR)

        title_surf = self._title_font.render(self.TITLE_TEXT, True, (255, 255, 255))
        screen.blit(title_surf, self._title_rect)

        for i, (tile, rect) in enumerate(zip(_THEME_TILES, self._tile_rects)):
            highlighted = i == self._selected_index or i == self._hovered_index
            self._draw_tile(screen, tile, rect, highlighted=highlighted)

        for slider in self._sliders:
            slider.draw(screen)

        self._notification_toggle.draw(screen)

        enabled = self._selected_index is not None
        if enabled:
            pygame.draw.rect(screen, (70, 70, 110), self._button_rect, border_radius=12)
            pygame.draw.rect(
                screen, (120, 120, 180), self._button_rect, width=2, border_radius=12
            )
            button_color = (255, 255, 255)
        else:
            pygame.draw.rect(
                screen, SETUP_BUTTON_DISABLED_BG, self._button_rect, border_radius=12
            )
            button_color = SETUP_BUTTON_DISABLED_TEXT

        button_surf = self._button_font.render(self.BUTTON_TEXT, True, button_color)
        label_rect = button_surf.get_rect(center=self._button_rect.center)
        screen.blit(button_surf, label_rect)


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
    return theme, theme.name, THEME_LABEL_DURATION


def run_playing_frame(
    screen: pygame.Surface,
    current_theme: Theme,
    label_text: str,
    label_timer: float,
    hud_font: pygame.font.Font,
    dt: float,
) -> tuple[Theme, str, float]:
    """Update and draw one playing frame; returns possibly updated theme/label."""
    current_theme.update(dt)

    screen.fill(BACKGROUND_COLOR)
    current_theme.draw(screen)

    if label_timer > 0:
        draw_theme_label(screen, label_text, hud_font)
        label_timer -= dt

    return current_theme, label_text, label_timer


def handle_playing_event(
    event: pygame.event.Event,
    screen: pygame.Surface,
    current_theme: Theme,
    label_text: str,
    label_timer: float,
) -> tuple[Theme, str, float]:
    if event.type != pygame.KEYDOWN:
        return current_theme, label_text, label_timer

    if event.key in THEME_FACTORIES:
        current_theme = switch_theme(
            THEME_FACTORIES[event.key], screen, current_theme
        )
        label_text = current_theme.name
        label_timer = THEME_LABEL_DURATION
    else:
        current_theme.on_keypress(event.key)

    return current_theme, label_text, label_timer


# -----------------------------------------------------------------------------
# Main loop
# -----------------------------------------------------------------------------


def main() -> None:
    pygame.mixer.pre_init(SAMPLE_RATE, -16, 2, 512)
    pygame.init()

    global NOTE_SOUNDS, POP_WAVE
    NOTE_SOUNDS = build_note_sounds()
    POP_WAVE = build_pop_wave()

    screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    pygame.display.set_caption("Toddler Key Smash")
    clock = pygame.time.Clock()
    hud_font = pygame.font.SysFont(UI_FONT_NAME, 28)

    app_state = AppState.SETUP
    setup_screen = SetupScreen(screen)
    notification_suppressor = NotificationSuppressor()
    current_theme: Theme | None = None
    label_text = ""
    label_timer = 0.0

    running = True
    try:
        while running:
            dt = clock.tick(TARGET_FPS) / 1000.0

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    running = False

                elif app_state == AppState.SETUP:
                    session = setup_screen.handle_event(event)
                    if session is not None:
                        app_state = AppState.PLAYING
                        current_theme, label_text, label_timer = begin_play_session(
                            screen, session
                        )
                        enter_playing_state(
                            notification_suppressor,
                            session.suppress_notifications,
                        )

                elif app_state == AppState.PLAYING and current_theme is not None:
                    current_theme, label_text, label_timer = handle_playing_event(
                        event, screen, current_theme, label_text, label_timer
                    )

            if app_state == AppState.SETUP:
                setup_screen.draw(screen)
            elif current_theme is not None:
                current_theme, label_text, label_timer = run_playing_frame(
                    screen, current_theme, label_text, label_timer, hud_font, dt
                )

            pygame.display.flip()
    finally:
        leave_playing_state(notification_suppressor)

    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()
