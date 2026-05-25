"""Generate icon.png and icon.ico for KeyboardMasher."""
from __future__ import annotations

from PIL import Image, ImageDraw

SIZE = 256
BG      = (26, 26, 46, 255)        # #1a1a2e
WHITE   = (255, 255, 255, 255)
ACCENT  = (124, 106, 247, 255)     # #7c6af7
KEY_CLR = (255, 255, 255, 200)     # slightly transparent key squares
SHADOW  = (0, 0, 0, 60)

img  = Image.new("RGBA", (SIZE, SIZE), BG)
draw = ImageDraw.Draw(img)

# ── Background circle / soft vignette (optional subtle depth) ────────────────
for r in range(128, 0, -4):
    alpha = int(18 * (1 - r / 128))
    draw.ellipse(
        [SIZE // 2 - r, SIZE // 2 - r, SIZE // 2 + r, SIZE // 2 + r],
        fill=(255, 255, 255, alpha),
    )

# ── Keyboard body ────────────────────────────────────────────────────────────
KB_LEFT, KB_TOP     = 36, 90
KB_RIGHT, KB_BOTTOM = 220, 190
KB_RADIUS           = 18

# Drop shadow
draw.rounded_rectangle(
    [KB_LEFT + 4, KB_TOP + 5, KB_RIGHT + 4, KB_BOTTOM + 5],
    radius=KB_RADIUS, fill=SHADOW,
)
# Main body — filled white outline then slightly dark fill
draw.rounded_rectangle(
    [KB_LEFT, KB_TOP, KB_RIGHT, KB_BOTTOM],
    radius=KB_RADIUS, fill=(45, 45, 80, 240), outline=WHITE, width=3,
)

# ── Key grid ─────────────────────────────────────────────────────────────────
# Row 1: 7 keys across the top portion of the keyboard
KEY_W, KEY_H = 22, 22
KEY_GAP      =  5
ROW1_Y       = KB_TOP + 16
ROW2_Y       = ROW1_Y + KEY_H + KEY_GAP
ROW3_Y       = ROW2_Y + KEY_H + KEY_GAP

# Number of columns and their starting X so they centre in the body
BODY_W = KB_RIGHT - KB_LEFT

def draw_key_row(
    draw: ImageDraw.ImageDraw,
    cols: int,
    y: int,
    key_w: int = KEY_W,
    key_h: int = KEY_H,
    gap: int = KEY_GAP,
    left_margin: int = KB_LEFT,
    body_width: int = BODY_W,
    color: tuple = KEY_CLR,
    radius: int = 4,
) -> None:
    total_w = cols * key_w + (cols - 1) * gap
    start_x = left_margin + (body_width - total_w) // 2
    for c in range(cols):
        x0 = start_x + c * (key_w + gap)
        draw.rounded_rectangle([x0, y, x0 + key_w, y + key_h], radius=radius, fill=color)

draw_key_row(draw, 7, ROW1_Y)
draw_key_row(draw, 6, ROW2_Y)
# Spacebar row: one wide key
SPACE_W = 90
SPACE_X = KB_LEFT + (BODY_W - SPACE_W) // 2
draw.rounded_rectangle(
    [SPACE_X, ROW3_Y, SPACE_X + SPACE_W, ROW3_Y + KEY_H],
    radius=4, fill=KEY_CLR,
)

# ── Accent sparkle / music note in top-right of keyboard ────────────────────
# Small sparkle: 4-pointed star drawn with lines in accent colour
STAR_CX = KB_RIGHT - 24
STAR_CY = KB_TOP   - 18
STAR_R_LONG = 14
STAR_R_SHORT =  6

import math
for i in range(8):
    angle = math.radians(i * 45)
    r = STAR_R_LONG if i % 2 == 0 else STAR_R_SHORT
    ex = STAR_CX + math.cos(angle) * r
    ey = STAR_CY + math.sin(angle) * r
    width = 3 if i % 2 == 0 else 2
    draw.line([(STAR_CX, STAR_CY), (ex, ey)], fill=ACCENT, width=width)

# Filled centre dot
draw.ellipse(
    [STAR_CX - 4, STAR_CY - 4, STAR_CX + 4, STAR_CY + 4],
    fill=ACCENT,
)

# Small secondary dots around sparkle for extra pop
for angle_deg, dist in [(30, 20), (330, 18), (60, 16)]:
    a = math.radians(angle_deg)
    dx = STAR_CX + math.cos(a) * dist
    dy = STAR_CY + math.sin(a) * dist
    draw.ellipse([dx - 2, dy - 2, dx + 2, dy + 2], fill=(*ACCENT[:3], 180))

# ── Save ─────────────────────────────────────────────────────────────────────
img.save("icon.png")
print("Saved icon.png")

# ICO with multiple sizes for best quality at all shell/taskbar sizes
img.save(
    "icon.ico",
    format="ICO",
    sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
)
print("Saved icon.ico")
