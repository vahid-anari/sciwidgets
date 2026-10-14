"""Colour swatch icons for menus, combo boxes and check boxes."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap

__all__ = ["color_icon"]


def color_icon(color: str, size: int = 12) -> QIcon:
    """Return a square icon filled with a colour, with a thin dark border."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setPen(QColor(0, 0, 0, 120))
    painter.setBrush(QColor(color))
    painter.drawRect(0, 0, size - 1, size - 1)
    painter.end()
    return QIcon(pixmap)
