"""Generate the app icon and the images derived from it.

Writes ``assets/icon.ico`` (each size drawn separately so small sizes stay
legible), ``assets/logo.png`` for the README, and ``assets/social-preview.png``
for the GitHub repository's social preview.

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
LOGO_OUTPUT = REPO_ROOT / "assets" / "logo.png"
SOCIAL_OUTPUT = REPO_ROOT / "assets" / "social-preview.png"
SIZES = (16, 24, 32, 48, 64, 128, 256)

#: GitHub's recommended social preview size.
SOCIAL_SIZE = (1280, 640)
SOCIAL_BACKGROUND = (14, 32, 66, 255)
SOCIAL_SUBTEXT = (190, 210, 240, 255)

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


def render_social_preview() -> Image.Image:
    """Render the repository card: the icon beside the name and a one-line pitch."""
    width, height = SOCIAL_SIZE
    card = Image.new("RGBA", SOCIAL_SIZE, SOCIAL_BACKGROUND)
    icon_size = 280
    margin = 90
    card.alpha_composite(render(icon_size), (margin, (height - icon_size) // 2))

    d = ImageDraw.Draw(card)
    text_x = margin + icon_size + 60
    lines = (
        ("Keyboard Wizard", 92, GLYPH),
        ("Fix text typed in the wrong layout", 40, SOCIAL_SUBTEXT),
        ("Ctrl+Alt+W  ·  Hebrew ↔ English  ·  no keylogger", 32, SOCIAL_SUBTEXT),
    )
    gap = 26
    heights = [d.textbbox((0, 0), text, font=_font(px))[3] for text, px, _ in lines]
    y = (height - (sum(heights) + gap * (len(lines) - 1))) / 2
    for (text, px, colour), line_height in zip(lines, heights):
        d.text((text_x, round(y)), text, font=_font(px), fill=colour)
        y += line_height + gap
    return card


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
    largest.save(LOGO_OUTPUT, format="PNG")
    print(f"Wrote {LOGO_OUTPUT}")
    render_social_preview().convert("RGB").save(SOCIAL_OUTPUT, format="PNG")
    print(f"Wrote {SOCIAL_OUTPUT}")


if __name__ == "__main__":
    main()
