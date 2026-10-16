"""Place a window on the screen."""

from __future__ import annotations

from typing import Optional, Tuple

from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QWidget


def center_on_screen(window: QWidget, size: Tuple[int, int], *, fallback: Optional[Tuple[int, int]] = None) -> None:
    """Resize ``window`` and move it to the centre of its screen.

    The window gets ``size`` when that fits the available screen area,
    otherwise ``fallback`` (90 % of the available area by default).

    Args:
        window: Top-level widget to place.
        size: Wanted (width, height) in logical pixels.
        fallback: (width, height) used when ``size`` does not fit.
    """
    screen = window.screen() or QGuiApplication.primaryScreen()
    if screen is None:
        window.resize(*size)
        return
    geo = screen.availableGeometry()
    w, h = size
    if w > geo.width() or h > geo.height():
        w, h = fallback if fallback is not None else (int(geo.width() * 0.9), int(geo.height() * 0.9))
    window.resize(w, h)
    window.move(geo.x() + (geo.width() - w) // 2, geo.y() + (geo.height() - h) // 2)
