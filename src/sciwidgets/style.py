"""Qt style and style-sheet fragments that sciwidgets widgets rely on.

The parameter widgets depend on these for behaviour and appearance (click-to-
position sliders, disabled slider grooves, the red frame on invalid numeric
input, value-label colors). Apps should call::

    app.setStyle(SciStyle())
    app.setStyleSheet(widget_style_sheet(app) + app_specific_sheet)
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPen
from PySide6.QtWidgets import (
    QApplication,
    QLineEdit,
    QProxyStyle,
    QStyle,
    QStyleFactory,
    QStyleOptionSlider,
)

__all__ = ["SciStyle", "widget_style_sheet"]


class SciStyle(QProxyStyle):
    """Fusion-based proxy style required by the sciwidgets widgets."""

    def __init__(self):
        """Initialize the proxy style with Fusion as the base style."""

        base = QStyleFactory.create("Fusion")
        super().__init__(base)

    def styleHint(self, hint, option=None, widget=None, returnData=None):
        """Return a Qt style hint for the requested control.

        Args:
            hint: Requested style-hint identifier.
            option: Optional style option associated with the request.
            widget: Optional widget associated with the request.
            returnData: Optional return-data holder supplied by Qt.

        Returns:
            Style-hint value for the requested control.
        """

        if hint == QStyle.SH_Slider_AbsoluteSetButtons:
            return Qt.LeftButton.value
        if hint == QStyle.SH_Slider_PageSetButtons:
            return 0
        return super().styleHint(hint, option, widget, returnData)

    def drawComplexControl(self, control, option, painter, widget=None):
        """Draw a customized Qt complex control.

        Args:
            control: Complex-control type to draw.
            option: Style option describing the control state.
            painter: Painter used for rendering.
            widget: Optional widget being drawn.
        """

        if control == QStyle.CC_Slider and isinstance(option, QStyleOptionSlider):
            if not (option.state & QStyle.State_Enabled):
                requested = option.subControls
                if requested == QStyle.SC_None:
                    requested = (
                        QStyle.SC_SliderGroove
                        | QStyle.SC_SliderHandle
                        | QStyle.SC_SliderTickmarks
                    )

                if requested & QStyle.SC_SliderGroove:
                    groove_rect = self.subControlRect(
                        QStyle.CC_Slider,
                        option,
                        QStyle.SC_SliderGroove,
                        widget,
                    )

                    painter.save()
                    painter.setPen(QPen(QColor("#b3b3b3"), 1))
                    painter.setBrush(QColor("#cccccc"))
                    r = groove_rect.adjusted(1, 2, -1, -1)
                    painter.drawRoundedRect(r, 1, 1)
                    painter.restore()

                fg = requested & (QStyle.SC_SliderTickmarks | QStyle.SC_SliderHandle)
                if fg:
                    opt_fg = QStyleOptionSlider(option)
                    opt_fg.subControls = fg
                    super().drawComplexControl(control, opt_fg, painter, widget)

                return

            return super().drawComplexControl(control, option, painter, widget)

        return super().drawComplexControl(control, option, painter, widget)

    def drawPrimitive(self, element, option, painter, widget=None):
        """Draw a customized Qt primitive element.

        Args:
            element: Primitive-element type to draw.
            option: Style option describing the primitive state.
            painter: Painter used for rendering.
            widget: Optional widget being drawn.
        """

        super().drawPrimitive(element, option, painter, widget)

        if element == QStyle.PE_PanelLineEdit and isinstance(widget, QLineEdit):
            if (option.state & QStyle.State_Enabled) and bool(widget.property("invalid")):
                painter.save()
                try:
                    pen = QPen(QColor("#d32f2f"))
                    pen.setWidth(3)
                    pen.setCapStyle(Qt.RoundCap)
                    pen.setJoinStyle(Qt.RoundJoin)
                    painter.setPen(pen)
                    painter.setBrush(Qt.NoBrush)
                    r = option.rect.adjusted(1, 1, -1, -1)
                    painter.drawRect(r)
                finally:
                    painter.restore()

def _font_rule(selector: str, size: int, family: str, color: Optional[str] = None) -> str:
    """Build a font (and optional color) rule for one selector."""
    rule = f"{selector}{{font-size: {size}pt; font-family: {family};"
    if color is None:
        return rule + "}"
    c = QColor(color)
    disabled = QColor(color)
    disabled.setAlpha(50)
    return (
        rule + f"color: {c.name()};}}"
        f"{selector}:disabled{{color: {disabled.name(QColor.HexArgb)};}}"
    )


def widget_style_sheet(app: QApplication) -> str:
    """Return the style-sheet rules the sciwidgets widgets expect.

    Sizes are relative to the application's current font, so call this after
    the app font is set.

    Args:
        app: Running application whose font is used as the base.

    Returns:
        Style-sheet text to include in the app's own style sheet.
    """
    f = app.font()
    fs, fm = f.pointSize(), f.family()
    return (
        _font_rule("QLabel#slider_value", fs + 1, fm, "blue")
        + _font_rule("QLabel#slider_range", fs - 1, fm, "black")
        + _font_rule("QLineEdit", fs + 1, fm, "blue")
        + _font_rule("QSpinBox", fs + 1, fm, "blue")
    )