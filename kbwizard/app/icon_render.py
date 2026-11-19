"""Supersampling helper for smooth procedurally drawn PIL icons."""

from __future__ import annotations

from typing import Callable

from PIL import Image

#: Scale factor to draw at before downsampling.
SUPERSAMPLE = 4


def render_supersampled(size: int, draw_fn: Callable[[int], Image.Image]) -> Image.Image:
    """Draw via ``draw_fn(scale)`` at ``SUPERSAMPLE`` times ``size``, then downsample.

    PIL's drawing primitives don't anti-alias, so drawing large and
    downsampling with LANCZOS is what produces smooth edges.
    """
    big = draw_fn(SUPERSAMPLE)
    return big.resize((size, size), Image.LANCZOS)
