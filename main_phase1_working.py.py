"""
Toddler Key Smash — press keys to paint random bright shapes on screen.
Press Escape to quit.
"""

import random
import sys

import pygame

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------

BACKGROUND_COLOR = (0, 0, 0)
MAX_SHAPES = 15
MIN_SHAPE_SIZE = 80
MAX_SHAPE_SIZE = 200
SHAPE_KINDS = ("circle", "square", "triangle")


# -----------------------------------------------------------------------------
# Color helpers
# -----------------------------------------------------------------------------

def random_bright_color() -> tuple[int, int, int]:
    """
    Pick a vivid RGB color using HSV so we avoid muddy dark tones.
    Rejects near-pure red (flashy / harsh for little eyes).
    """
    for _ in range(50):
        hue = random.random()  # 0.0–1.0
        saturation = random.uniform(0.55, 1.0)
        value = random.uniform(0.78, 1.0)

        color = pygame.Color(0)
        color.hsva = (hue * 360, saturation * 100, value * 100, 100)
        rgb = (color.r, color.g, color.b)

        # Skip harsh pure-red flashes (high R, very low G and B).
        if rgb[0] > 220 and rgb[1] < 50 and rgb[2] < 50:
            continue
        return rgb

    # Fallback if random attempts keep landing on red.
    return random.choice([(255, 200, 80), (100, 220, 255), (180, 255, 120)])


# -----------------------------------------------------------------------------
# Shape model
# -----------------------------------------------------------------------------

class Shape:
    """One stamped shape: type, center position, size, and fill color."""

    __slots__ = ("type", "x", "y", "size", "color")

    def __init__(
        self,
        shape_type: str,
        x: int,
        y: int,
        size: int,
        color: tuple[int, int, int],
    ) -> None:
        self.type = shape_type
        self.x = x
        self.y = y
        self.size = size
        self.color = color

    def draw(self, surface: pygame.Surface) -> None:
        """Render this shape onto the given surface."""
        if self.type == "circle":
            radius = self.size // 2
            pygame.draw.circle(surface, self.color, (self.x, self.y), radius)

        elif self.type == "square":
            half = self.size // 2
            rect = pygame.Rect(0, 0, self.size, self.size)
            rect.center = (self.x, self.y)
            pygame.draw.rect(surface, self.color, rect)

        elif self.type == "triangle":
            half = self.size // 2
            # Equilateral triangle pointing upward, centered on (x, y).
            top = (self.x, self.y - half)
            bottom_left = (self.x - half, self.y + half)
            bottom_right = (self.x + half, self.y + half)
            pygame.draw.polygon(
                surface, self.color, [top, bottom_left, bottom_right]
            )


def random_shape(screen: pygame.Surface) -> Shape:
    """Build one shape that fits entirely on the screen."""
    width, height = screen.get_size()
    size = random.randint(MIN_SHAPE_SIZE, MAX_SHAPE_SIZE)
    margin = size // 2 + 2

    x = random.randint(margin, width - margin)
    y = random.randint(margin, height - margin)

    return Shape(
        shape_type=random.choice(SHAPE_KINDS),
        x=x,
        y=y,
        size=size,
        color=random_bright_color(),
    )


def add_shape(shapes: list[Shape], screen: pygame.Surface) -> None:
    """Append a new random shape; drop the oldest if over MAX_SHAPES (FIFO)."""
    shapes.append(random_shape(screen))
    while len(shapes) > MAX_SHAPES:
        shapes.pop(0)


def redraw_all(screen: pygame.Surface, shapes: list[Shape]) -> None:
    """Clear to black and draw every shape in the list."""
    screen.fill(BACKGROUND_COLOR)
    for shape in shapes:
        shape.draw(screen)


# -----------------------------------------------------------------------------
# Main loop
# -----------------------------------------------------------------------------

def main() -> None:
    pygame.init()

    screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    pygame.display.set_caption("Toddler Key Smash")
    clock = pygame.time.Clock()

    # type, x, y, size, color — capped at MAX_SHAPES (oldest removed first).
    shapes: list[Shape] = []
    running = True

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                else:
                    add_shape(shapes, screen)

        redraw_all(screen, shapes)
        pygame.display.flip()

        clock.tick(60)

    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()
