"""Generate ``assets/icon.ico``, drawing each size separately so small sizes stay legible.

Usage: .venv/Scripts/python.exe tools/make_icon.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

REPO_ROOT = Path(__file__).resolve().parent.parent
# Make the project root importable when run as a script.
sys.path.insert(0, str(REPO_ROOT))

from kbwizard.app.icon_render import SUPERSAMPLE, render_supersampled  # noqa: E402

OUTPUT = REPO_ROOT / "assets" / "icon.ico"
SIZES = (16, 24, 32, 48, 64, 128, 256)

KEY_EDGE = (16, 64, 140, 255)  # keycap side, darker for depth
KEY_FACE = (38, 110, 210, 255)  # keycap top face
GLYPH = (255, 255, 255, 255)

#: Bold fonts on stock Windows, best first; PIL's default font is the fallback.
_FONT_CANDIDATES = ("segoeuib.ttf", "arialbd.ttf", "seguisb.ttf")


def _font(px: int) -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
    for name in _FONT_CANDIDATES:
        try:
            return ImageFont.truetype(name, px)
        except OSError:
            continue
    return ImageFont.load_default()


def _glyph_for(size: int) -> str:
    return "W" if size < 32 else "KW"


def _draw_keycap(size: int) -> Image.Image:
    """Draw the keycap shape without text, supersampled for smooth corners."""
    bevel_frac = 0.06 if size < 32 else 0.09

    def draw(scale: int) -> Image.Image:
        dim = size * scale
        image = Image.new("RGBA", (dim, dim), (0, 0, 0, 0))
        d = ImageDraw.Draw(image)
        radius = dim * 0.22
        d.rounded_rectangle((0, 0, dim - 1, dim - 1), radius=radius, fill=KEY_EDGE)
        # A deeper bottom bevel makes the square read as a keycap.
        inset = dim * bevel_frac
        d.rounded_rectangle(
            (inset, inset * 0.6, dim - 1 - inset, dim - 1 - inset * 1.8),
            radius=radius * 0.8,
            fill=KEY_FACE,
        )
        return image

    return render_supersampled(size, draw)


def _draw_glyph(image: Image.Image) -> None:
    """Center the glyph on the keycap's top face at about 70% of its width.

    Text is drawn at native size; FreeType already anti-aliases, and
    supersampling would only soften the strokes.
    """
    size = image.width
    text = _glyph_for(size)
    d = ImageDraw.Draw(image)
    target_width = size * (0.70 if len(text) > 1 else 0.62)
    px = max(6, size)
    font = _font(px)
    while px > 6:
        left, top, right, bottom = d.textbbox((0, 0), text, font=font)
        if right - left <= target_width and bottom - top <= size * 0.55:
            break
        px -= 1
        font = _font(px)
    left, top, right, bottom = d.textbbox((0, 0), text, font=font)
    face_center_y = size * 0.46  # top face sits slightly above center
    x = (size - (right - left)) / 2 - left
    y = face_center_y - (bottom - top) / 2 - top
    d.text((round(x), round(y)), text, font=font, fill=GLYPH)


def render(size: int) -> Image.Image:
    """Render the icon at ``size`` pixels; below 32 px the glyph is a single "W"."""
    image = _draw_keycap(size)
    _draw_glyph(image)
    return image


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    images = [render(size) for size in SIZES]
    largest = images[-1]
    # append_images keeps each hand-drawn size; `sizes` alone would make
    # Pillow resample the largest image.
    largest.save(
        OUTPUT,
        format="ICO",
        sizes=[(s, s) for s in SIZES],
        append_images=images[:-1],
    )
    print(f"Wrote {OUTPUT} ({', '.join(str(s) for s in SIZES)} px; supersample x{SUPERSAMPLE})")


if __name__ == "__main__":
    main()
