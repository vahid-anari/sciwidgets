"""Dialogs for editing the style of a curve, the grid lines and a span."""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional

import matplotlib.colors as mcolors
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
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


class _ColorButton(QPushButton):
    """A button showing a colour; clicking it opens the colour picker."""

    def __init__(self, title: str, on_change: Callable[[], None], parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._title = title
        self._on_change = on_change
        self._color = "#000000"
        self.clicked.connect(self._choose)

    def color(self) -> str:
        return self._color

    def set_color(self, color: str) -> None:
        """Show a colour (no callback)."""
        self._color = mcolors.to_hex(color)
        self.setText(self._color)
        text = "#000000" if QColor(self._color).lightness() > 128 else "#ffffff"
        self.setStyleSheet(f"background-color: {self._color}; color: {text};")

    def _choose(self) -> None:
        chosen = QColorDialog.getColor(QColor(self._color), self, self._title)
        if chosen.isValid():
            self.set_color(chosen.name())
            self._on_change()


class CurveStyleDialog(QDialog):
    """Edit colour, line style, line width, marker and marker size of a curve.

    Every change is shown at once through ``preview``; the caller restores the
    old style when the dialog is cancelled. "Reset" restores the style from
    the plot description.
    """

    def __init__(self, name: str, style: Dict[str, Any], default: Dict[str, Any],
                 parent: Optional[QWidget] = None,
                 preview: Optional[Callable[[Dict[str, Any]], None]] = None) -> None:
        """Build the dialog.

        Args:
            name: Curve name shown in the title.
            style: Current style (``get_curve_style`` format).
            default: Style from the description, used by "Reset".
            parent: Parent widget.
            preview: Called with the edited style after every change.
        """
        super().__init__(parent)
        self.setWindowTitle(f"Style: {name}")
        self._default = dict(default)
        self._preview = preview
        self._showing = False

        self._color_btn = _ColorButton("Curve colour", self._changed)
        self._line = QComboBox()
        for label, value in LINE_STYLES.items():
            self._line.addItem(label, value)
        self._width = QDoubleSpinBox(minimum=0.0, maximum=20.0, singleStep=0.25, decimals=2)
        self._marker = QComboBox()
        for label, value in MARKERS.items():
            self._marker.addItem(label, value)
        self._msize = QDoubleSpinBox(minimum=0.0, maximum=40.0, singleStep=0.5, decimals=1)
        for spin in (self._width, self._msize):
            spin.valueChanged.connect(self._changed)
        for combo in (self._line, self._marker):
            combo.currentIndexChanged.connect(self._changed)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel | QDialogButtonBox.Reset)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.Reset).clicked.connect(self._reset)

        form = QFormLayout(self)
        form.addRow("Colour:", self._color_btn)
        form.addRow("Line:", self._line)
        form.addRow("Line width:", self._width)
        form.addRow("Marker:", self._marker)
        form.addRow("Marker size:", self._msize)
        form.addRow(buttons)
        self._show(style)

    def _show(self, style: Dict[str, Any]) -> None:
        """Put a style into the editors (without previews for each field)."""
        self._showing = True
        try:
            self._color_btn.set_color(style["color"])
            _pick(self._line, LINE_STYLES, style["linestyle"])
            self._width.setValue(style["linewidth"])
            _pick(self._marker, MARKERS, style["marker"])
            self._msize.setValue(style["markersize"])
        finally:
            self._showing = False

    def _reset(self) -> None:
        self._show(self._default)
        self._changed()

    def _changed(self, *_: Any) -> None:
        if not self._showing and self._preview is not None:
            self._preview(self.style())

    def style(self) -> Dict[str, Any]:
        """Return the edited style."""
        return {
            "color": self._color_btn.color(),
            "linestyle": self._line.currentData(),
            "linewidth": float(self._width.value()),
            "marker": self._marker.currentData(),
            "markersize": float(self._msize.value()),
        }


class GridStyleDialog(QDialog):
    """Edit line style, width and opacity of all grid lines (colours stay automatic).

    Every change is shown at once through ``preview``; the caller restores the
    old style when the dialog is cancelled. "Reset" restores the style from
    the plot description.
    """

    def __init__(self, style: Dict[str, Any], default: Dict[str, Any],
                 parent: Optional[QWidget] = None,
                 preview: Optional[Callable[[Dict[str, Any]], None]] = None) -> None:
        """Build the dialog.

        Args:
            style: Current grid style (``linestyle``, ``linewidth``, ``alpha``).
            default: Style from the description, used by "Reset".
            parent: Parent widget.
            preview: Called with the edited style after every change.
        """
        super().__init__(parent)
        self.setWindowTitle("Grid style")
        self._default = dict(default)
        self._preview = preview
        self._showing = False

        self._line = QComboBox()
        for label, value in LINE_STYLES.items():
            if value != "None":
                self._line.addItem(label, value)
        self._width = QDoubleSpinBox(minimum=0.1, maximum=5.0, singleStep=0.1, decimals=2)
        self._alpha = QDoubleSpinBox(minimum=0.05, maximum=1.0, singleStep=0.05, decimals=2)
        for spin in (self._width, self._alpha):
            spin.valueChanged.connect(self._changed)
        self._line.currentIndexChanged.connect(self._changed)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel | QDialogButtonBox.Reset)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.Reset).clicked.connect(self._reset)

        form = QFormLayout(self)
        form.addRow("Line:", self._line)
        form.addRow("Line width:", self._width)
        form.addRow("Opacity:", self._alpha)
        form.addRow(buttons)
        self._show(style)

    def _show(self, style: Dict[str, Any]) -> None:
        """Put a style into the editors (without previews for each field)."""
        self._showing = True
        try:
            _pick(self._line, {k: v for k, v in LINE_STYLES.items() if v != "None"}, style["linestyle"])
            self._width.setValue(style["linewidth"])
            self._alpha.setValue(style["alpha"])
        finally:
            self._showing = False

    def _reset(self) -> None:
        self._show(self._default)
        self._changed()

    def _changed(self, *_: Any) -> None:
        if not self._showing and self._preview is not None:
            self._preview(self.style())

    def style(self) -> Dict[str, Any]:
        """Return the edited style."""
        return {
            "linestyle": self._line.currentData(),
            "linewidth": float(self._width.value()),
            "alpha": float(self._alpha.value()),
        }


class SpanStyleDialog(QDialog):
    """Edit fill colour and opacity, and edge colour, opacity, width and line of a span,
    and colour, opacity, width and line of its centre line if it has one.

    Every change is shown at once through ``preview``; the caller restores the
    old style when the dialog is cancelled. "Reset" restores the style from
    the plot description.
    """

    def __init__(self, name: str, style: Dict[str, Any], default: Dict[str, Any],
                 parent: Optional[QWidget] = None,
                 preview: Optional[Callable[[Dict[str, Any]], None]] = None) -> None:
        """Build the dialog.

        Args:
            name: Span name shown in the title.
            style: Current style (``get_span_style`` format).
            default: Style from the description, used by "Reset".
            parent: Parent widget.
            preview: Called with the edited style after every change.
        """
        super().__init__(parent)
        self.setWindowTitle(f"Style: {name}")
        self._default = dict(default)
        self._preview = preview
        self._showing = False

        self._face = _ColorButton("Fill colour", self._changed)
        self._alpha = QDoubleSpinBox(minimum=0.0, maximum=1.0, singleStep=0.05, decimals=2)
        self._edge = _ColorButton("Edge colour", self._changed)
        self._edge_alpha = QDoubleSpinBox(minimum=0.0, maximum=1.0, singleStep=0.05, decimals=2)
        self._width = QDoubleSpinBox(minimum=0.0, maximum=10.0, singleStep=0.25, decimals=2)
        self._line = QComboBox()
        for label, value in LINE_STYLES.items():
            self._line.addItem(label, value)
        for spin in (self._alpha, self._edge_alpha, self._width):
            spin.valueChanged.connect(self._changed)
        self._line.currentIndexChanged.connect(self._changed)

        self._has_center = "center_color" in style
        if self._has_center:
            self._c_color = _ColorButton("Centre line colour", self._changed)
            self._c_alpha = QDoubleSpinBox(minimum=0.0, maximum=1.0, singleStep=0.05, decimals=2)
            self._c_width = QDoubleSpinBox(minimum=0.0, maximum=10.0, singleStep=0.25, decimals=2)
            self._c_line = QComboBox()
            for label, value in LINE_STYLES.items():
                self._c_line.addItem(label, value)
            for spin in (self._c_alpha, self._c_width):
                spin.valueChanged.connect(self._changed)
            self._c_line.currentIndexChanged.connect(self._changed)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel | QDialogButtonBox.Reset)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.Reset).clicked.connect(self._reset)

        form = QFormLayout(self)
        if self._has_center:
            form.addRow(QLabel("<b>Area</b>"))
        form.addRow("Fill colour:", self._face)
        form.addRow("Fill opacity:", self._alpha)
        form.addRow("Edge colour:", self._edge)
        form.addRow("Edge opacity:", self._edge_alpha)
        form.addRow("Edge width:", self._width)
        form.addRow("Edge line:", self._line)
        if self._has_center:
            form.addRow(QLabel("<b>Centre line</b>"))
            form.addRow("Colour:", self._c_color)
            form.addRow("Opacity:", self._c_alpha)
            form.addRow("Width:", self._c_width)
            form.addRow("Line:", self._c_line)
        form.addRow(buttons)
        self._show(style)

    def _show(self, style: Dict[str, Any]) -> None:
        """Put a style into the editors (without previews for each field)."""
        self._showing = True
        try:
            self._face.set_color(style["facecolor"])
            self._alpha.setValue(style["alpha"])
            self._edge.set_color(style["edgecolor"])
            self._edge_alpha.setValue(style["edge_alpha"])
            self._width.setValue(style["linewidth"])
            _pick(self._line, LINE_STYLES, style["linestyle"])
            if self._has_center:
                self._c_color.set_color(style["center_color"])
                self._c_alpha.setValue(style["center_alpha"])
                self._c_width.setValue(style["center_linewidth"])
                _pick(self._c_line, LINE_STYLES, style["center_linestyle"])
        finally:
            self._showing = False

    def _reset(self) -> None:
        self._show(self._default)
        self._changed()

    def _changed(self, *_: Any) -> None:
        if not self._showing and self._preview is not None:
            self._preview(self.style())

    def style(self) -> Dict[str, Any]:
        """Return the edited style."""
        style = {
            "facecolor": self._face.color(),
            "alpha": round(float(self._alpha.value()), 4),
            "edgecolor": self._edge.color(),
            "edge_alpha": round(float(self._edge_alpha.value()), 4),
            "linewidth": float(self._width.value()),
            "linestyle": self._line.currentData(),
        }
        if self._has_center:
            style.update({
                "center_color": self._c_color.color(),
                "center_alpha": round(float(self._c_alpha.value()), 4),
                "center_linewidth": float(self._c_width.value()),
                "center_linestyle": self._c_line.currentData(),
            })
        return style
