"""Small controls tied to a PlotCanvas: a curve selector and a curve check box.

Both show each curve's colour as a swatch and follow colour changes.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QSize, Signal
from PySide6.QtWidgets import QCheckBox, QComboBox, QWidget

from ._icons import color_icon
from .canvas import PlotCanvas

__all__ = ["CurveCheckBox", "CurveSelector", "color_icon"]


class CurveSelector(QComboBox):
    """Choose which curve of a ``select: one`` panel is shown.

    Items are the curves' ``name``s with colour swatches, plus an optional
    "none" entry. Choosing an item shows that curve and redraws the canvas.

    Signals:
        curveSelected (object): The user chose a curve; sends its id, or
            ``None`` for the "none" entry.
    """

    curveSelected = Signal(object)

    def __init__(self, canvas: PlotCanvas, axis_id: str, *, none_text: Optional[str] = "None",
                 parent: Optional[QWidget] = None) -> None:
        """Build the combo box from the curves of a panel or twin.

        Args:
            canvas: The canvas.
            axis_id: A panel or twin with ``"select": "one"``.
            none_text: Text of the entry that shows no curve; ``None`` for no
                such entry.
            parent: Parent widget.
        """
        super().__init__(parent)
        self._canvas = canvas
        self._axis_id = axis_id
        self.setIconSize(QSize(12, 12))
        for curve_id in canvas.curve_ids(axis_id):
            self.addItem(color_icon(canvas.curve_color(curve_id)),
                         canvas.get_curve_name(curve_id), curve_id)
        if none_text is not None:
            self.addItem(none_text, None)
        self.set_current(canvas.selected_curve(axis_id))
        self.currentIndexChanged.connect(self._on_index_changed)
        canvas.curveStyleChanged.connect(self._on_style_changed)

    def _on_index_changed(self, _index: int) -> None:
        curve_id = self.currentData()
        self._canvas.select_curve(self._axis_id, curve_id)
        self._canvas.redraw()
        self.curveSelected.emit(curve_id)

    def _on_style_changed(self, curve_id: str) -> None:
        i = self.findData(curve_id)
        if i >= 0:
            self.setItemIcon(i, color_icon(self._canvas.curve_color(curve_id)))

    def current(self) -> Optional[str]:
        """Return the chosen curve id (``None`` for the "none" entry)."""
        return self.currentData()

    def set_current(self, curve_id: Optional[str]) -> None:
        """Choose an entry and show its curve, without emitting ``curveSelected``."""
        i = self.findData(curve_id)
        if i < 0:
            return
        self.blockSignals(True)
        self.setCurrentIndex(i)
        self.blockSignals(False)
        self._canvas.select_curve(self._axis_id, curve_id)


class CurveCheckBox(QCheckBox):
    """Show or hide a curve, or a whole twin axis, with the curve's colour swatch.

    Example: ``CurveCheckBox(canvas, "w", axis="profiles.twin")`` hides the
    twin axis with its curve, as MB Solver's "w" toggle does.
    """

    def __init__(self, canvas: PlotCanvas, curve_id: str, *, text: Optional[str] = None,
                 axis: Optional[str] = None, parent: Optional[QWidget] = None) -> None:
        """Build the check box.

        Args:
            canvas: The canvas.
            curve_id: The curve whose colour (and, without ``axis``,
                visibility) the box shows.
            text: Box text; defaults to the curve's name.
            axis: A panel or twin id to show/hide instead of the single curve.
            parent: Parent widget.
        """
        super().__init__(text if text is not None else canvas.get_curve_name(curve_id), parent)
        self._canvas = canvas
        self._curve_id = curve_id
        self._axis = axis
        self.setIconSize(QSize(12, 12))
        self._update_icon(curve_id)
        visible = canvas.is_axis_visible(axis) if axis else canvas.is_curve_visible(curve_id)
        self.setChecked(visible)
        self.toggled.connect(self._on_toggled)
        canvas.curveStyleChanged.connect(self._update_icon)

    def _on_toggled(self, on: bool) -> None:
        if self._axis:
            self._canvas.set_axis_visible(self._axis, on)
        else:
            self._canvas.set_curve_visible(self._curve_id, on)
        self._canvas.redraw()

    def _update_icon(self, curve_id: str) -> None:
        if curve_id == self._curve_id:
            self.setIcon(color_icon(self._canvas.curve_color(curve_id)))
