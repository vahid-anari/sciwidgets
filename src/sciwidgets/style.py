"""Qt style and style-sheet fragments that sciwidgets widgets rely on.

The parameter widgets depend on these for behaviour and appearance (click-to-
position sliders, disabled slider grooves, the red frame on invalid numeric
input, value-label colors). Apps should call::

    app.setStyle(SciStyle())
    app.setStyleSheet(widget_style_sheet(app) + app_specific_sheet)

The colors follow the light or dark palette; ``apply_sci_style`` re-applies
the style sheet by itself when the palette switches (for example when macOS
changes appearance). ``set_color_scheme`` forces light or dark, or follows
the system again, and ``set_sci_colors`` changes the widgets' own colors
(values, range labels, default markers, invalid input).
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple, Union

from PySide6.QtCore import QEvent, QObject, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QPalette, QPen
from PySide6.QtWidgets import (
    QApplication,
    QLineEdit,
    QProxyStyle,
    QStyle,
    QStyleFactory,
    QStyleOptionMenuItem,
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
    "set_sci_colors",
    "sci_color",
    "DEFAULT_SCI_COLORS",
]

DEFAULT_SCI_COLORS: Dict[str, Tuple[str, str]] = {
    "value": ("blue", "#5aa9ff"),
    "range_label": ("black", "#d0d0d0"),
    "marker": ("red", "#ff6b6b"),
    "invalid": ("#d32f2f", "#ff6b6b"),
}
"""The widgets' own colors, as (light mode, dark mode):

``value``
    slider values and the text of line edits and spin boxes;
``range_label``
    the small min/max labels under sliders;
``marker``
    the default-value tick on sliders;
``invalid``
    the frame around invalid input.

Change them with :func:`set_sci_colors`. The filled part of a slider groove is
not one of them: it is the palette's highlight color (on macOS the system
accent color).
"""

ACCENT = "accent"
"""Color value that stands for the palette's highlight color (the system accent on macOS)."""

_colors: Dict[str, Tuple[str, str]] = dict(DEFAULT_SCI_COLORS)

VALUE_COLOR = {False: DEFAULT_SCI_COLORS["value"][0], True: DEFAULT_SCI_COLORS["value"][1]}
"""Default color of values, for light (False) and dark (True) palettes (see ``DEFAULT_SCI_COLORS``)."""

RANGE_LABEL_COLOR = {False: DEFAULT_SCI_COLORS["range_label"][0], True: DEFAULT_SCI_COLORS["range_label"][1]}
"""Default color of the slider range labels, for light and dark palettes."""

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


def sci_color(name: str, dark: Optional[bool] = None) -> str:
    """Return one of the widgets' colors (see ``DEFAULT_SCI_COLORS``) as ``#rrggbb``.

    Args:
        name: ``"value"``, ``"range_label"``, ``"marker"`` or ``"invalid"``.
        dark: Which mode; default: whether the application palette is dark.

    Raises:
        KeyError: For an unknown name.
    """
    if name not in _colors:
        raise KeyError(f"no color {name!r}; known: {', '.join(_colors)}")
    if dark is None:
        dark = QApplication.instance() is not None and is_dark()
    color = _colors[name][1 if dark else 0]
    if color == ACCENT:
        return QApplication.palette().color(QPalette.Highlight).name()
    return QColor(color).name()


ColorPair = Union[None, str, QColor, Tuple[Union[str, QColor], Union[str, QColor]]]


def set_sci_colors(app: Optional[QApplication] = None, **colors: ColorPair) -> None:
    """Change the widgets' own colors; names not given keep theirs.

    Each color is a pair ``(light, dark)``, or one color for both modes, or
    ``"accent"`` for the palette's highlight color (the system accent color on
    macOS), or ``None`` for the default::

        set_sci_colors(app, value=("#0055cc", "#6cb4ff"), marker="accent")

    With ``app`` (after :func:`apply_sci_style`), the style sheet is applied
    again and the widgets redraw; without it, the colors are used from the next
    :func:`apply_sci_style` on.

    Args:
        app: The running application, or ``None``.
        **colors: ``value``, ``range_label``, ``marker``, ``invalid``.

    Raises:
        ValueError: For an unknown name or a color Qt does not know.
    """
    unknown = set(colors) - set(DEFAULT_SCI_COLORS)
    if unknown:
        raise ValueError(f"unknown color(s) {sorted(unknown)}; known: {', '.join(DEFAULT_SCI_COLORS)}")
    for name, given in colors.items():
        if given is None:
            _colors[name] = DEFAULT_SCI_COLORS[name]
            continue
        pair = given if isinstance(given, (tuple, list)) else (given, given)
        if len(pair) != 2:
            raise ValueError(f"{name}: give one color or a (light, dark) pair")
        checked = []
        for color in pair:
            text = color.name() if isinstance(color, QColor) else str(color)
            if text != ACCENT and not QColor.isValidColorName(text):
                raise ValueError(f"{name}: unknown color {text!r}")
            checked.append(text)
        _colors[name] = (checked[0], checked[1])
    if app is not None:
        watcher = app.findChild(_SchemeWatcher)
        if watcher is not None:
            watcher.refresh(force=True)
        for widget in app.allWidgets():
            widget.update()


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

        super().drawComplexControl(control, option, painter, widget)
        if control == QStyle.CC_SpinBox and option.frame:
            _dark_input_edge(option, painter)

    def drawControl(self, element, option, painter, widget=None):
        """Draw a Qt control; menu separators get a visible line in dark mode.

        Fusion draws a menu separator a shade darker than the menu, which is
        lost on a dark menu.

        Args:
            element: Control element to draw.
            option: Style option describing the control.
            painter: Painter used for rendering.
            widget: Optional widget being drawn.
        """
        super().drawControl(element, option, painter, widget)
        if (element == QStyle.CE_MenuItem and isinstance(option, QStyleOptionMenuItem)
                and option.menuItemType == QStyleOptionMenuItem.Separator and is_dark(option.palette)):
            r = option.rect
            y = r.center().y()
            painter.save()
            painter.setPen(QPen(QColor(255, 255, 255, 64), 1))
            painter.drawLine(r.left() + 5, y, r.right() - 5, y)
            painter.restore()

    def drawPrimitive(self, element, option, painter, widget=None):
        """Draw a customized Qt primitive element.

        Args:
            element: Primitive-element type to draw.
            option: Style option describing the primitive state.
            painter: Painter used for rendering.
            widget: Optional widget being drawn.
        """

        super().drawPrimitive(element, option, painter, widget)

        if element == QStyle.PE_FrameLineEdit:
            _dark_input_edge(option, painter)

        if element == QStyle.PE_PanelLineEdit and isinstance(widget, QLineEdit):
            if (option.state & QStyle.State_Enabled) and bool(widget.property("invalid")):
                painter.save()
                try:
                    pen = QPen(QColor(sci_color("invalid", is_dark(option.palette))))
                    pen.setWidth(3)
                    pen.setCapStyle(Qt.RoundCap)
                    pen.setJoinStyle(Qt.RoundJoin)
                    painter.setPen(pen)
                    painter.setBrush(Qt.NoBrush)
                    r = option.rect.adjusted(1, 1, -1, -1)
                    painter.drawRect(r)
                finally:
                    painter.restore()

def _dark_input_edge(option, painter) -> None:
    """Draw a visible edge around an input field (line edit, spin box) in dark mode.

    Fusion's edge is a shade darker than the window, which is lost on a dark
    one. A field with focus keeps Fusion's highlight edge.
    """
    if not is_dark(option.palette) or option.state & QStyle.State_HasFocus:
        return
    alpha = 70 if option.state & QStyle.State_Enabled else 35
    painter.save()
    painter.setRenderHint(painter.RenderHint.Antialiasing, True)
    painter.setPen(QPen(QColor(255, 255, 255, alpha), 1))
    painter.setBrush(Qt.NoBrush)
    painter.drawRoundedRect(QRectF(option.rect).adjusted(0.5, 0.5, -0.5, -0.5), 2, 2)
    painter.restore()


def _font_rule(selector: str, size: int, family: str, color: Optional[str] = None,
               disabled_alpha: int = 50) -> str:
    """Build a font (and optional color) rule for one selector."""
    rule = f"{selector}{{font-size: {size}pt; font-family: {family};"
    if color is None:
        return rule + "}"
    c = QColor(color)
    disabled = QColor(color)
    disabled.setAlpha(disabled_alpha)
    return (
        rule + f"color: {c.name()};}}"
        f"{selector}:disabled{{color: {disabled.name(QColor.HexArgb)};}}"
    )


def sci_style_sheet(app: QApplication) -> str:
    """Return the style-sheet rules the sciwidgets widgets expect.

    Sizes are relative to the application's current font, so call this after
    the app font is set. Colors are those of ``set_sci_colors`` for the current
    palette (light or dark).

    Args:
        app: Running application whose font is used as the base.

    Returns:
        Style-sheet text to include in the app's own style sheet.
    """
    f = app.font()
    fs, fm = f.pointSize(), f.family()
    dark = is_dark(app.palette())
    value = sci_color("value", dark)
    faded = 110 if dark else 50  # disabled text: a faint color is lost on a dark background
    return (
        _font_rule("QLabel#slider_value", fs + 1, fm, value, faded)
        + _font_rule("QLabel#slider_range", fs - 1, fm, sci_color("range_label", dark), faded)
        + _font_rule("QLineEdit", fs + 1, fm, value, faded)
        + _font_rule("QAbstractSpinBox", fs + 1, fm, value, faded)  # QSpinBox, QDoubleSpinBox, date and time edits
    )


class _SchemeWatcher(QObject):
    """Re-applies the style sheet when the application palette changes (light or dark, or the accent color).

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

    def refresh(self, force: bool = False) -> None:
        """Set the style sheet again if its colors changed (or always, with ``force``)."""
        self._pending = False
        app = QApplication.instance()
        if app is None:
            return
        self.dark = is_dark(app.palette())
        sheet = sci_style_sheet(app) + self.extra
        if force or sheet != app.styleSheet():
            app.setStyleSheet(sheet)


def apply_sci_style(app: QApplication, extra_style_sheet: str = "",
                    colors: Optional[Dict[str, ColorPair]] = None) -> None:
    """Set SciStyle and the sciwidgets style sheet on ``app``.

    The style sheet is applied again by itself whenever the palette switches
    between light and dark, so call this once.

    Args:
        app: Application to style.
        extra_style_sheet: App-specific rules appended after the
            sciwidgets rules.
        colors: The widgets' own colors, as for :func:`set_sci_colors`.
    """
    if colors:
        set_sci_colors(None, **colors)
    app.setStyle(SciStyle())
    app.setStyleSheet(sci_style_sheet(app) + extra_style_sheet)
    watcher = app.findChild(_SchemeWatcher)
    if watcher is None:
        _SchemeWatcher(app, extra_style_sheet)
    else:
        watcher.extra = extra_style_sheet
        watcher.dark = is_dark(app.palette())
