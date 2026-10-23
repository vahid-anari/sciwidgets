"""Qt style and style-sheet fragments that sciwidgets widgets rely on.

The parameter widgets depend on these for behaviour and appearance (click-to-
position sliders, disabled slider grooves, the red frame on invalid numeric
input, value-label colors). Apps should call::

    app.setStyle(SciStyle())
    app.setStyleSheet(widget_style_sheet(app) + app_specific_sheet)

The colors follow the light or dark palette; ``apply_sci_style`` re-applies
the style sheet by itself when the palette switches (for example when macOS
changes appearance). ``set_color_scheme`` forces light or dark, or follows
the system again.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QEvent, QObject, Qt, QTimer
from PySide6.QtGui import QColor, QPalette, QPen
from PySide6.QtWidgets import (
    QApplication,
    QLineEdit,
    QProxyStyle,
    QStyle,
    QStyleFactory,
    QStyleOptionSlider,
)

__all__ = [
    "SciStyle",
    "sci_style_sheet",
    "apply_sci_style",
    "is_dark",
    "set_color_scheme",
    "color_scheme",
    "dark_palette",
]

VALUE_COLOR = {False: "blue", True: "#5aa9ff"}
"""Color of slider values and line-edit text, for light (False) and dark (True) palettes."""

RANGE_LABEL_COLOR = {False: "black", True: "#d0d0d0"}
"""Color of the slider range labels, for light and dark palettes."""

DISABLED_GROOVE = {False: ("#b3b3b3", "#cccccc"), True: ("#5a5a5a", "#4a4a4a")}
"""Edge and fill of a disabled slider groove, for light and dark palettes."""


def is_dark(palette: Optional[QPalette] = None) -> bool:
    """Return whether a palette (default: the application's) is a dark one.

    Decided by the window background: darker than mid-grey counts as dark.
    """
    if palette is None:
        palette = QApplication.palette()
    return palette.color(QPalette.Window).lightness() < 128


def dark_palette() -> QPalette:
    """Return a dark palette close to macOS Dark Mode.

    :func:`set_color_scheme` uses it where the platform does not provide a dark
    palette itself (Linux without a dark desktop theme, older Qt versions).
    """
    pal = QPalette()
    roles = QPalette.ColorRole
    for role, color in (
            (roles.Window, "#323232"), (roles.WindowText, "#ffffff"), (roles.Base, "#1e1e1e"),
            (roles.AlternateBase, "#2a2a2a"), (roles.Text, "#ffffff"), (roles.Button, "#3c3c3c"),
            (roles.ButtonText, "#ffffff"), (roles.Highlight, "#0a64d6"), (roles.HighlightedText, "#ffffff"),
            (roles.ToolTipBase, "#3c3c3c"), (roles.ToolTipText, "#ffffff"), (roles.PlaceholderText, "#8c8c8c"),
            (roles.Light, "#505050"), (roles.Midlight, "#454545"), (roles.Mid, "#2c2c2c"),
            (roles.Dark, "#1a1a1a"), (roles.Shadow, "#000000"), (roles.Link, "#5aa9ff"),
            (roles.BrightText, "#ff6060"),
    ):
        pal.setColor(role, QColor(color))
    for role in (roles.WindowText, roles.Text, roles.ButtonText):
        pal.setColor(QPalette.ColorGroup.Disabled, role, QColor("#7a7a7a"))
    return pal


_scheme: str = "system"


def color_scheme() -> str:
    """Return the scheme last chosen with :func:`set_color_scheme`: ``"light"``, ``"dark"`` or ``"system"``."""
    return _scheme


def set_color_scheme(app: QApplication, scheme: str) -> None:
    """Show the app in light or dark colors, or follow the system again.

    Asks Qt for the scheme first (on macOS this switches the whole app,
    including native dialogs). Where that does not give the wanted palette,
    a fitting palette is set directly. The widgets follow by themselves; the
    sciwidgets style sheet (when set with :func:`apply_sci_style`) is applied
    again once control returns to the event loop.

    Args:
        app: The application.
        scheme: ``"light"``, ``"dark"`` or ``"system"``.

    Raises:
        ValueError: For any other ``scheme``.
    """
    global _scheme
    if scheme not in ("light", "dark", "system"):
        raise ValueError(f"scheme must be 'light', 'dark' or 'system', got {scheme!r}")
    _scheme = scheme
    hints = app.styleHints()
    if hasattr(hints, "setColorScheme"):  # Qt 6.8+
        hints.setColorScheme({"light": Qt.ColorScheme.Light, "dark": Qt.ColorScheme.Dark,
                              "system": Qt.ColorScheme.Unknown}[scheme])
    app.setPalette(QPalette())  # back to the platform's own palette
    if scheme == "dark" and not is_dark(app.palette()):
        app.setPalette(dark_palette())
    elif scheme == "light" and is_dark(app.palette()):
        app.setPalette(app.style().standardPalette())


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

                    edge, fill = DISABLED_GROOVE[is_dark(option.palette)]
                    painter.save()
                    painter.setPen(QPen(QColor(edge), 1))
                    painter.setBrush(QColor(fill))
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


def sci_style_sheet(app: QApplication) -> str:
    """Return the style-sheet rules the sciwidgets widgets expect.

    Sizes are relative to the application's current font, so call this after
    the app font is set. Colors are those of the current palette (light or dark).

    Args:
        app: Running application whose font is used as the base.

    Returns:
        Style-sheet text to include in the app's own style sheet.
    """
    f = app.font()
    fs, fm = f.pointSize(), f.family()
    dark = is_dark(app.palette())
    value = VALUE_COLOR[dark]
    return (
        _font_rule("QLabel#slider_value", fs + 1, fm, value)
        + _font_rule("QLabel#slider_range", fs - 1, fm, RANGE_LABEL_COLOR[dark])
        + _font_rule("QLineEdit", fs + 1, fm, value)
        + _font_rule("QSpinBox", fs + 1, fm, value)
    )


class _SchemeWatcher(QObject):
    """Re-applies the style sheet when the application palette turns light or dark.

    The new sheet is set from the event loop, not inside the palette-change
    delivery: changing the style sheet while Qt is still sending that event to
    every widget is not safe.
    """

    def __init__(self, app: QApplication, extra: str) -> None:
        super().__init__(app)
        self.extra = extra
        self.dark = is_dark(app.palette())
        self._pending = False
        app.installEventFilter(self)

    def eventFilter(self, obj, event) -> bool:
        if (event.type() == QEvent.ApplicationPaletteChange and obj is QApplication.instance()
                and not self._pending):
            self._pending = True
            QTimer.singleShot(0, self.refresh)
        return False

    def refresh(self) -> None:
        """Set the style sheet again if the palette changed between light and dark."""
        self._pending = False
        app = QApplication.instance()
        if app is None:
            return
        dark = is_dark(app.palette())
        if dark != self.dark:
            self.dark = dark
            app.setStyleSheet(sci_style_sheet(app) + self.extra)

def apply_sci_style(app: QApplication, extra_style_sheet: str = "") -> None:
    """Set SciStyle and the sciwidgets style sheet on ``app``.

    The style sheet is applied again by itself whenever the palette switches
    between light and dark, so call this once.

    Args:
        app: Application to style.
        extra_style_sheet: App-specific rules appended after the
            sciwidgets rules.
    """
    app.setStyle(SciStyle())
    app.setStyleSheet(sci_style_sheet(app) + extra_style_sheet)
    watcher = app.findChild(_SchemeWatcher)
    if watcher is None:
        _SchemeWatcher(app, extra_style_sheet)
    else:
        watcher.extra = extra_style_sheet
        watcher.dark = is_dark(app.palette())