"""A Matplotlib figure inside a scroll area, with zoom."""

from __future__ import annotations

from typing import Optional, Tuple

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QScrollArea, QWidget


class _Canvas(FigureCanvasQTAgg):
    """Canvas that hands wheel events to the enclosing scroll area."""

    def __init__(self, figure: Figure, area: QScrollArea) -> None:
        super().__init__(figure)
        self._area = area

    def wheelEvent(self, event) -> None:
        delta = event.angleDelta()
        vbar = self._area.verticalScrollBar()
        hbar = self._area.horizontalScrollBar()
        vbar.setValue(vbar.value() - delta.y())
        hbar.setValue(hbar.value() - delta.x())
        event.accept()


class ScrollableFigure(QScrollArea):
    """Show a figure at its natural size, scrolled and zoomed by the user.

    The canvas keeps the size given by the figure (inches × the figure's own
    dpi, in logical pixels) times the zoom factors, so a figure larger than
    the widget is scrolled rather than shrunk. The mouse wheel scrolls.

    Args:
        figure: The figure to show.
        parent: Optional parent widget.
    """

    def __init__(self, figure: Figure, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(False)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.setAlignment(Qt.AlignCenter)
        self._zoom: Tuple[float, float] = (1.0, 1.0)
        self._canvas: Optional[_Canvas] = None
        self._origin: Tuple[float, float] = (1.0, 1.0)
        self.set_figure(figure)

    # ----- figure -----
    @property
    def figure(self) -> Figure:
        """The figure shown."""
        return self._canvas.figure

    @property
    def canvas(self) -> FigureCanvasQTAgg:
        """The canvas widget (for ``mpl_connect`` and ``draw_idle``)."""
        return self._canvas

    def set_figure(self, figure: Figure) -> None:
        """Show another figure; the zoom is kept and applied to it."""
        old = self.takeWidget()
        if old is not None:
            old.deleteLater()
        self._origin = tuple(figure.get_size_inches())
        # Matplotlib multiplies figure.dpi by the screen's pixel ratio once the canvas is on a
        # HiDPI screen and keeps the dpi it was created with as _original_dpi
        self._dpi = float(getattr(figure, "_original_dpi", figure.get_dpi()))
        self._canvas = _Canvas(figure, self)
        self.setWidget(self._canvas)
        self._apply_zoom()

    # ----- zoom -----
    def zoom(self) -> Tuple[float, float]:
        """Return the (horizontal, vertical) zoom factors."""
        return self._zoom

    def set_zoom(self, horizontal: Optional[float] = None, vertical: Optional[float] = None) -> None:
        """Set the zoom factors (1.0 = the figure's own size); ``None`` keeps a factor."""
        h = self._zoom[0] if horizontal is None else float(horizontal)
        v = self._zoom[1] if vertical is None else float(vertical)
        if h <= 0 or v <= 0:
            raise ValueError("zoom factors must be positive")
        self._zoom = (h, v)
        self._apply_zoom()

    def center(self) -> None:
        """Move the horizontal scroll bar to the middle."""
        hbar = self.horizontalScrollBar()
        hbar.setValue((hbar.minimum() + hbar.maximum()) // 2)

    def showEvent(self, event) -> None:
        # the pixel ratio is only known once the widget is on a screen
        self._apply_zoom()
        super().showEvent(event)

    def canvas_size(self) -> Tuple[int, int]:
        """Return the canvas size in logical pixels."""
        return self._canvas.width(), self._canvas.height()

    def _apply_zoom(self) -> None:
        fig = self._canvas.figure
        w_in = self._origin[0] * self._zoom[0]
        h_in = self._origin[1] * self._zoom[1]
        fig.set_size_inches(w_in, h_in, forward=True)
        w_px, h_px = int(round(w_in * self._dpi)), int(round(h_in * self._dpi))
        self._canvas.setMinimumSize(w_px, h_px)
        self._canvas.resize(w_px, h_px)
        self._canvas.draw_idle()
