"""
Toddler Key Smash — themed visual play on keypress.
F1: Music (ripples)  |  F2: Emoji  |  Escape: quit
"""

from __future__ import annotations

import random
import sys
from abc import ABC, abstractmethod

import numpy as np
import pygame

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------

BACKGROUND_COLOR = (0, 0, 0)
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
MASTER_VOLUME = 0.6
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
    sound.set_volume(MASTER_VOLUME)
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
    sound.set_volume(MASTER_VOLUME)
    sound.play()


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

    def __init__(self, screen: pygame.Surface) -> None:
        self._screen_w, self._screen_h = screen.get_size()

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
    ) -> None:
        super().__init__(screen)
        self.ripples: list[Ripple] = []
        self._note_sounds = note_sounds if note_sounds is not None else NOTE_SOUNDS

    def _on_clear(self) -> None:
        self.ripples.clear()

    def on_keypress(self, key: int) -> None:
        note_idx = key_to_note_index(key)
        self._note_sounds[note_idx].play()  # overlaps on separate channels

        if len(self.ripples) >= MAX_RIPPLES:
            self.ripples.pop(0)
        x, y = self._random_position()
        self.ripples.append(Ripple(x, y, random.choice(PASTEL_PALETTE)))

    def update(self, dt: float) -> None:
        alive: list[Ripple] = []
        for ripple in self.ripples:
            ripple.radius += self.RADIUS_GROWTH * dt
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
                width=self.RING_WIDTH,
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

    def __init__(self, screen: pygame.Surface) -> None:
        super().__init__(screen)
        self.emojis: list[EmojiSprite] = []
        self._font_cache: dict[int, pygame.font.Font] = {}

    def _on_clear(self) -> None:
        self.emojis.clear()

    def _font_for_size(self, size: int) -> pygame.font.Font:
        if size not in self._font_cache:
            self._font_cache[size] = pygame.font.SysFont(EMOJI_FONT_NAME, size)
        return self._font_cache[size]

    def on_keypress(self, key: int) -> None:
        del key
        play_pop_sound()

        if len(self.emojis) >= MAX_EMOJIS:
            self.emojis.pop(0)
        x, y = self._random_position(margin=60)
        size = random.randint(EMOJI_SIZE_MIN, EMOJI_SIZE_MAX)
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
    if current is not None:
        current.clear()
    if factory is MusicTheme:
        return MusicTheme(screen, NOTE_SOUNDS)
    return factory(screen)


def draw_theme_label(
    screen: pygame.Surface,
    label: str,
    hud_font: pygame.font.Font,
) -> None:
    text = hud_font.render(label, True, (180, 180, 180))
    screen.blit(text, (16, 12))


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
    hud_font = pygame.font.SysFont("Segoe UI", 28)

    current_theme: Theme = MusicTheme(screen, NOTE_SOUNDS)
    label_text = current_theme.name
    label_timer = THEME_LABEL_DURATION

    running = True
    while running:
        dt = clock.tick(TARGET_FPS) / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False

                elif event.key in THEME_FACTORIES:
                    current_theme = switch_theme(
                        THEME_FACTORIES[event.key], screen, current_theme
                    )
                    label_text = current_theme.name
                    label_timer = THEME_LABEL_DURATION

                else:
                    current_theme.on_keypress(event.key)

        current_theme.update(dt)

        screen.fill(BACKGROUND_COLOR)
        current_theme.draw(screen)

        if label_timer > 0:
            draw_theme_label(screen, label_text, hud_font)
            label_timer -= dt

        pygame.display.flip()

    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()
