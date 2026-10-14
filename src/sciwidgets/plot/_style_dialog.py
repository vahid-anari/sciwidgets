"""Dialog for editing one curve's line style."""

from __future__ import annotations

from typing import Any, Dict, Optional

import matplotlib.colors as mcolors
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QPushButton,
    QWidget,
)

LINE_STYLES = {"Solid": "-", "Dashed": "--", "Dotted": ":", "Dash-dot": "-.", "None": "None"}
MARKERS = {"None": "None", "Circle": "o", "Point": ".", "Square": "s", "Triangle": "^",
           "Diamond": "D", "Plus": "+", "Cross": "x", "Star": "*"}


def _pick(combo: QComboBox, table: Dict[str, str], value: str) -> None:
    """Select the entry of ``table`` whose value is ``value`` (adding it if unknown)."""
    for i, v in enumerate(table.values()):
        if v == value:
            combo.setCurrentIndex(i)
            return
    combo.addItem(str(value), value)
    combo.setCurrentIndex(combo.count() - 1)


class CurveStyleDialog(QDialog):
    """Edit colour, line style, line width, marker and marker size of a curve.

    "Reset" restores the style from the plot description.
    """

    def __init__(self, name: str, style: Dict[str, Any], default: Dict[str, Any],
                 parent: Optional[QWidget] = None) -> None:
        """Build the dialog.

        Args:
            name: Curve name shown in the title.
            style: Current style (``get_curve_style`` format).
            default: Style from the description, used by "Reset".
            parent: Parent widget.
        """
        super().__init__(parent)
        self.setWindowTitle(f"Style: {name}")
        self._default = dict(default)
        self._color = style["color"]

        self._color_btn = QPushButton()
        self._color_btn.clicked.connect(self._choose_color)
        self._line = QComboBox()
        for label, value in LINE_STYLES.items():
            self._line.addItem(label, value)
        self._width = QDoubleSpinBox(minimum=0.0, maximum=20.0, singleStep=0.25, decimals=2)
        self._marker = QComboBox()
        for label, value in MARKERS.items():
            self._marker.addItem(label, value)
        self._msize = QDoubleSpinBox(minimum=0.0, maximum=40.0, singleStep=0.5, decimals=1)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel | QDialogButtonBox.Reset)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.Reset).clicked.connect(lambda: self._show(self._default))

        form = QFormLayout(self)
        form.addRow("Colour:", self._color_btn)
        form.addRow("Line:", self._line)
        form.addRow("Line width:", self._width)
        form.addRow("Marker:", self._marker)
        form.addRow("Marker size:", self._msize)
        form.addRow(buttons)
        self._show(style)

    def _show(self, style: Dict[str, Any]) -> None:
        """Put a style into the editors."""
        self._set_color(style["color"])
        _pick(self._line, LINE_STYLES, style["linestyle"])
        self._width.setValue(style["linewidth"])
        _pick(self._marker, MARKERS, style["marker"])
        self._msize.setValue(style["markersize"])

    def _set_color(self, color: str) -> None:
        """Remember a colour and paint the button with it."""
        self._color = mcolors.to_hex(color)
        self._color_btn.setText(self._color)
        text = "#000000" if QColor(self._color).lightness() > 128 else "#ffffff"
        self._color_btn.setStyleSheet(f"background-color: {self._color}; color: {text};")

    def _choose_color(self) -> None:
        """Open the colour picker."""
        chosen = QColorDialog.getColor(QColor(self._color), self, "Curve colour")
        if chosen.isValid():
            self._set_color(chosen.name())

    def style(self) -> Dict[str, Any]:
        """Return the edited style."""
        return {
            "color": self._color,
            "linestyle": self._line.currentData(),
            "linewidth": float(self._width.value()),
            "marker": self._marker.currentData(),
            "markersize": float(self._msize.value()),
        }
