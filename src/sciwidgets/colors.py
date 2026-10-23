"""Colours for light and dark mode: contrast, and the dark-mode versions of a colour.

No Qt here: plain functions on Matplotlib colour values (names, hex strings, RGB
tuples), used by the plot canvas and the table, and usable by apps.

* :func:`dark_variant` — a line or text colour for a dark background (lighter
  when needed, hue kept).
* :func:`dark_fill` — a background fill for dark mode (a light fill becomes a
  dark one of the same hue).
* :func:`readable_text` — black or white, whichever reads better on a fill.
"""

from __future__ import annotations

from typing import Any, Tuple

import matplotlib.colors as mcolors

__all__ = ["contrast_ratio", "dark_fill", "dark_variant", "readable_text", "MIN_CONTRAST", "TARGET_CONTRAST"]

MIN_CONTRAST = 3.0
"""Contrast ratio (WCAG) below which a colour counts as too dark for the dark background."""

TARGET_CONTRAST = 4.5
"""Contrast ratio a colour that had to be changed is brought up to (at least)."""


def _linear(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _gamma(c: float) -> float:
    c = min(max(c, 0.0), 1.0)
    return 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def _luminance(rgb: Tuple[float, float, float]) -> float:
    r, g, b = (_linear(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(color: Any, background: Any) -> float:
    """Return the WCAG contrast ratio (1 to 21) of two opaque colours."""
    a = _luminance(mcolors.to_rgb(color))
    b = _luminance(mcolors.to_rgb(background))
    hi, lo = max(a, b), min(a, b)
    return (hi + 0.05) / (lo + 0.05)


def _to_oklab(rgb: Tuple[float, float, float]) -> Tuple[float, float, float]:
    r, g, b = (_linear(c) for c in rgb)
    l_ = (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b) ** (1 / 3)
    m_ = (0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b) ** (1 / 3)
    s_ = (0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b) ** (1 / 3)
    return (0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_,
            1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
            0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_)


def _oklab_to_linear(lab: Tuple[float, float, float]) -> Tuple[float, float, float]:
    lightness, a, b = lab
    l_ = (lightness + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m_ = (lightness - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s_ = (lightness - 0.0894841775 * a - 1.2914855480 * b) ** 3
    return (4.0767416621 * l_ - 3.3077115913 * m_ + 0.2309699292 * s_,
            -1.2684380046 * l_ + 2.6097574011 * m_ - 0.3413193965 * s_,
            -0.0041960863 * l_ - 0.7034186147 * m_ + 1.7076147010 * s_)


def _from_oklch(lightness: float, chroma: float, hue_a: float, hue_b: float) -> Tuple[float, float, float]:
    """sRGB of an OKLCH colour, with the chroma reduced until it fits the sRGB gamut (hue kept)."""
    for _ in range(40):
        lin = _oklab_to_linear((lightness, chroma * hue_a, chroma * hue_b))
        if all(-1e-6 <= c <= 1 + 1e-6 for c in lin):
            break
        chroma *= 0.92
    return tuple(_gamma(c) for c in lin)


def dark_variant(color: Any, background: Any = "#1e1e1e") -> str:
    """Return the colour to draw ``color`` with on a dark ``background``.

    A colour that already stands out against the background (contrast ratio of
    at least :data:`MIN_CONTRAST`) is returned unchanged. A darker one gets its
    lightness flipped (OKLab L to 1 − L, at most 0.9 so black becomes light grey
    rather than white), with its hue kept and its saturation reduced only as far
    as needed to stay a valid colour, and is then lightened further if needed
    until its contrast reaches :data:`TARGET_CONTRAST`: black → light grey,
    blue → light blue, navy → pale blue. Like MATLAB's ``fliplightness``.

    Args:
        color: Any Matplotlib colour (name, hex, RGB tuple); alpha is ignored.
        background: The dark background colour.

    Returns:
        A hex colour ``"#rrggbb"``.
    """
    rgb = mcolors.to_rgb(color)
    if contrast_ratio(rgb, background) >= MIN_CONTRAST:
        return mcolors.to_hex(rgb)
    lightness, a, b = _to_oklab(rgb)
    chroma = (a * a + b * b) ** 0.5
    hue_a, hue_b = (a / chroma, b / chroma) if chroma > 1e-9 else (0.0, 0.0)
    flipped = min(1.0 - lightness, 0.9)
    out = _from_oklch(flipped, chroma, hue_a, hue_b)
    # Mid-light colours (pure blue) gain little from the flip: raise the lightness until readable
    while contrast_ratio(out, background) < TARGET_CONTRAST and flipped < 1.0:
        flipped = min(flipped + 0.04, 1.0)
        out = _from_oklch(flipped, chroma, hue_a, hue_b)
    return mcolors.to_hex(out)


def dark_fill(color: Any) -> str:
    """Return the dark-mode version of a background fill (a table column or row colour).

    A light fill (OKLab lightness above 0.5) becomes a dark one of the same
    hue, a little lighter than a dark window, with lighter fills ending up
    darker: white → near the background, tan → dark brown, light blue → dark
    blue. A fill that is already dark is returned unchanged.

    Args:
        color: Any Matplotlib colour; alpha is ignored.

    Returns:
        A hex colour ``"#rrggbb"``.
    """
    rgb = mcolors.to_rgb(color)
    lightness, a, b = _to_oklab(rgb)
    if lightness <= 0.5:
        return mcolors.to_hex(rgb)
    chroma = (a * a + b * b) ** 0.5
    hue_a, hue_b = (a / chroma, b / chroma) if chroma > 1e-9 else (0.0, 0.0)
    target = 0.24 + 0.36 * (1.0 - lightness)  # white → 0.24, a mid fill (0.75) → 0.33
    return mcolors.to_hex(_from_oklch(target, chroma * 0.8, hue_a, hue_b))


def readable_text(fill: Any) -> str:
    """Return ``"#000000"`` or ``"#ffffff"``, whichever contrasts more with ``fill``."""
    return "#000000" if contrast_ratio("#000000", fill) >= contrast_ratio("#ffffff", fill) else "#ffffff"
