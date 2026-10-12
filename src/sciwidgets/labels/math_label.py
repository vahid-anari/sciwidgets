"""Math label widget rendered through Matplotlib (LaTeX or mathtext)."""

from __future__ import annotations

import io
import shutil
from typing import Optional, List, Dict, Any

from matplotlib.figure import Figure

from PySide6.QtCore import QSize, QRectF, QByteArray, Signal, Qt, QEvent
from PySide6.QtGui import QPainter, QPalette, QColor
from PySide6.QtWidgets import QLabel, QWidget, QMenu
from PySide6.QtSvg import QSvgRenderer

_latex_enabled: bool = shutil.which("latex") is not None


def set_latex_enabled(enabled: bool) -> None:
    """Globally allow or forbid external LaTeX rendering for SvgLabel.

    Affects labels created afterwards; existing labels keep their setting.
    """
    global _latex_enabled
    _latex_enabled = bool(enabled)


class MathLabel(QLabel):
    """Display math text rendered by Matplotlib.

    This widget behaves similarly to :class:`QLabel`, but its text is always
    interpreted in math mode and rendered through Matplotlib (external LaTeX
    when enabled, otherwise mathtext). Internally the result is converted to
    SVG and drawn with :class:`QSvgRenderer`, so it scales cleanly.

    The rendering pipeline is:

    text -> Matplotlib (optionally external LaTeX) -> SVG bytes -> QSvgRenderer

    Notes:
        - The rendered SVG is rescaled when the widget size changes.
        - By default, scaling preserves the SVG aspect ratio.
        - The natural SVG size is cached and used as the widget's minimum size.
        - The label is regenerated when the enabled state changes so disabled
          text appearance stays in sync with the palette.
        - If LaTeX rendering is enabled and available, Matplotlib may use the
          system LaTeX installation for text rendering.

    Signals:
        rightClickRequested: Emitted when a context-menu action is triggered.
            The signal arguments are the action id and the resulting checked
            state.
    """

    rightClickRequested = Signal(str, bool)

    def __init__(
            self,
            text: str = "",
            font_size: float = 18.0,
            text_color: str | QColor = "black",
            pad_inches: float = 0.06,
            alignment: Qt.Alignment = Qt.AlignCenter,
            fix_size: bool = False,
            keep_aspect_ratio: bool = True,
            use_tex: bool = True,
            parent: Optional[QWidget] = None,
    ) -> None:
        """Initialize the SVG label.

        Args:
            text: Initial text to render. When non-empty, it is wrapped in
                ``$...$`` before rendering so it is interpreted in math mode.
            font_size: Font size in points used by Matplotlib.
            text_color: Text color used for rendering.
            pad_inches: Extra padding, in inches, added around the rendered text
                when the SVG is saved with a tight bounding box.
            alignment: Alignment of the rendered SVG inside the widget.
            fix_size: If ``True``, the widget size is fixed to the SVG's natural
                size after rendering. Otherwise, the natural size is applied as
                the minimum size.
            keep_aspect_ratio: If ``True``, scale the SVG uniformly to preserve
                aspect ratio. If ``False``, stretch it to fill the widget.
            use_tex: If ``True``, allow Matplotlib to use external LaTeX
                rendering, provided it is also enabled globally (see
                :func:`set_latex_enabled`; on by default when ``latex`` is
                found on the system). Otherwise Matplotlib's mathtext is used.
            parent: Parent widget.
        """
        super().__init__(parent)

        self._editable = False
        self._menu_items = None
        self._renderer = QSvgRenderer(self)
        self._keep_aspect_ratio = keep_aspect_ratio
        self._natural_size: QSize = QSize()

        # Store current text settings
        self._text: str = f"${text}$" if text else ""
        self._font_size: float = font_size
        self._text_color = QColor(text_color)
        self._use_tex: bool = _latex_enabled and use_tex
        self._pad_inches: float = pad_inches
        self._alignment: Qt.Alignment = alignment
        self._fix_size: bool = fix_size

        # We do not use QLabel's text painting
        super().setText("")

        if text:
            self._update_from_text()

    # ---------- Public API ----------
    def set_menu_items(self, items: List[Dict[str, Any]]) -> None:
        """Set the context-menu item specifications for the label.

        Args:
            items: List of menu item specification dictionaries. Each dictionary
                may define keys such as ``id``, ``text``, ``enabled``,
                ``checkable``, and ``checked``. A separator is represented by
                ``{"id": "sep"}``.
        """
        self._editable = True
        self._menu_items = items

    def set_menu_item_checked(self, act_id, checked: bool) -> bool:
        """Update the checked state of a context-menu item.

        Args:
            act_id: Identifier of the target menu item.
            checked: Checked state to store for the item.

        Returns:
            bool: ``True`` if the item was found and updated, otherwise
            ``False``.
        """
        if not self._menu_items:
            return False

        for item in self._menu_items:
            if item.get("id") == "sep":
                continue
            if item.get("id") == act_id:
                # ensure it's checkable (optional; remove if you want strict behavior)
                item["checkable"] = bool(item.get("checkable", True))
                item["checked"] = bool(checked)
                return True

        return False

    def set_editable(self, editable: bool) -> None:
        """Enable or disable the custom context menu.

        Args:
            editable: If ``True``, the widget accepts the configured context menu.
                If ``False``, right clicks do not open the custom menu.
        """
        self._editable = editable

    def set_menu_item_enabled(self, act_id, enabled: bool) -> bool:
        """Update the enabled state of a context-menu item.

        Args:
            act_id: Identifier of the target menu item.
            enabled: Enabled state to store for the item.

        Returns:
            bool: ``True`` if the item was found and updated, otherwise
            ``False``.
        """
        if not self._menu_items:
            return False

        for item in self._menu_items:
            if item.get("id") == "sep":
                continue
            if item.get("id") == act_id:
                item["enabled"] = bool(enabled)
                return True

        return False

    def set_text(
            self,
            text: str,
            font_size: Optional[float] = None,
            pad_inches: Optional[float] = None,
    ) -> None:
        """Update the label text and optional rendering settings.

        Args:
            text: New text to display. The text is wrapped in ``$...$`` and
                rendered in math mode, so plain words should be written using
                LaTeX text commands such as ``\\mathrm{...}`` when needed.
            font_size: New font size in points. If ``None``, the current value is
                kept.
            pad_inches: New padding value in inches. If ``None``, the current
                value is kept.
        """
        self._text = f"${text}$" if text else ""
        if font_size is not None:
            self._font_size = font_size
        if pad_inches is not None:
            self._pad_inches = pad_inches

        self._update_from_text()

    def setAlignment(self, alignment: Qt.Alignment) -> None:
        """Set how the SVG is positioned inside the widget rectangle.

        Args:
            alignment: Qt alignment flags controlling horizontal and vertical
                positioning of the rendered SVG.
        """
        self._alignment = alignment
        self.update()

    def alignment(self) -> Qt.Alignment:
        """Return the alignment used for rendering.

        Returns:
            Qt.Alignment: Current alignment flags for the rendered SVG.
        """
        return self._alignment

    # ---------- Internal helpers ----------
    def _update_from_text(self) -> None:
        """Regenerate and load the SVG from the current text settings.

        The SVG is rebuilt using the current text, font size, padding, and
        effective text color. If loading succeeds, the widget's cached natural
        size, layout geometry, and display are refreshed.
        """
        svg_bytes = self._create_text_svg(
            text=self._text,
            font_size=self._font_size,
            pad_inches=self._pad_inches,
            color=self._current_text_color(),
        )

        if self._renderer.load(QByteArray(svg_bytes)):
            self._update_natural_size()
            self.updateGeometry()
            self.update()

    def _create_text_svg(
            self,
            text: str,
            font_size: float,
            pad_inches: float = 0.06,
            color: str | tuple[float, float, float, float] = "black",
    ) -> bytes:
        """Render text to SVG bytes using Matplotlib.

        Uses a standalone :class:`matplotlib.figure.Figure` rather than
        ``pyplot``, so no global Matplotlib state or GUI backend is touched.

        Args:
            text: Text passed to Matplotlib for rendering. This may be plain
                text, mathtext, or a LaTeX-style string depending on how it was
                prepared before calling this method.
            font_size: Font size in points.
            pad_inches: Padding in inches passed to Matplotlib when saving with
                ``bbox_inches="tight"``.
            color: Text color passed to Matplotlib, as a color name or an
                RGBA tuple of floats in ``[0, 1]``.

        Returns:
            bytes: Raw SVG data.
        """
        fig = Figure()
        fig.patch.set_alpha(0.0)  # Transparent background

        # Centered text
        fig.text(
            0.5,
            0.5,
            text,
            fontsize=font_size,
            ha="center",
            va="center",
            usetex=self._use_tex,
            color=color,
        )

        buf = io.BytesIO()
        fig.savefig(
            buf,
            format="svg",
            bbox_inches="tight",
            pad_inches=pad_inches,
            transparent=True,
        )
        return buf.getvalue()

    def _update_natural_size(self) -> None:
        """Update the cached natural size from the loaded SVG.

        If the renderer reports a valid default size, that size is cached and
        applied either as the widget's fixed size or minimum size, depending on
        ``self._fix_size``. If the SVG size is invalid, the cached size is
        cleared.
        """
        size = self._renderer.defaultSize()
        if size.isValid():
            self._natural_size = size
            if self._fix_size:
                self.setFixedSize(size)
            else:
                self.setMinimumSize(size)
        else:
            self._natural_size = QSize()

    def _current_text_color(self):
        """Return the effective text color for the current widget state.

        When the widget is disabled, the base text color keeps its RGB values
        but adopts the alpha channel of the disabled ``WindowText`` palette
        color.

        Returns:
            tuple[float, float, float, float]: RGBA color components in the
            normalized format returned by :meth:`QColor.getRgbF`.
        """
        base = QColor(self._text_color)

        if not self.isEnabled():
            ref = self.palette().color(QPalette.Disabled, QPalette.WindowText)
            base.setAlphaF(ref.alphaF())

        return base.getRgbF()

    # ---------- QWidget overrides ----------
    def changeEvent(self, event) -> None:
        """Handle widget state changes.

        When the enabled or disabled state changes, the SVG is regenerated so
        the text appearance matches the current palette state.

        Args:
            event: Qt change event delivered to the widget.
        """
        super().changeEvent(event)
        if event.type() == QEvent.EnabledChange:
            self._update_from_text()

    def contextMenuEvent(self, event):
        """Show the configured context menu and emit the selected action.

        The menu is built from the stored menu item specifications. For
        checkable actions, the method updates the stored checked state and emits
        :attr:`rightClickRequested` with the action id and the resulting checked
        state.

        Args:
            event: Qt context-menu event.
        """
        parent = self.parentWidget()
        if parent is not None:
            parent.contextMenuEvent(event)
        if not self._editable:
            return
        if not self._menu_items:
            return

        menu = QMenu(self)

        # map id -> underlying dict so we can update checked state
        item_by_id = {}

        for item in self._menu_items:
            act_id = item.get("id")
            if act_id == "sep":
                menu.addSeparator()
                continue

            text = str(item.get("text", act_id if act_id is not None else "None"))
            enabled = bool(item.get("enabled", True))
            checkable = bool(item.get("checkable", False))
            checked = bool(item.get("checked", False))

            act = menu.addAction(text)
            act.setEnabled(enabled)
            act.setCheckable(checkable)
            if checkable:
                act.setChecked(checked)
            act.setData(act_id)
            item_by_id[act_id] = item

        action = menu.exec(event.globalPos())
        if action is None:
            return

        act_id = action.data()
        if act_id is None:
            act_id = action.text()

        # Determine (and ensure) the new checked state
        new_checked = False
        if action.isCheckable():
            old_checked = bool(item_by_id.get(act_id, {}).get("checked", action.isChecked()))
            new_checked = bool(action.isChecked())

            # Safety: if Qt didn't toggle for some reason, toggle ourselves once
            if new_checked == old_checked:
                new_checked = not old_checked
                action.setChecked(new_checked)

            # Persist back to spec
            if act_id in item_by_id:
                item_by_id[act_id]["checked"] = new_checked

        self.rightClickRequested.emit(act_id, new_checked)

    def sizeHint(self) -> QSize:
        """Return the preferred size for layouts.

        Returns:
            QSize: The cached natural SVG size when available, otherwise the
            renderer default size, otherwise the base :class:`QLabel` size hint.
        """
        if self._natural_size.isValid():
            return self._natural_size
        default = self._renderer.defaultSize()
        if default.isValid():
            return default
        return super().sizeHint()

    def minimumSizeHint(self) -> QSize:
        """Return the minimum size hint for layouts.

        Returns:
            QSize: The cached natural SVG size when available, otherwise the
            renderer default size, otherwise the base :class:`QLabel` minimum
            size hint.
        """
        if self._natural_size.isValid():
            return self._natural_size
        size = self._renderer.defaultSize()
        if size.isValid():
            return size
        return super().minimumSizeHint()

    def paintEvent(self, event) -> None:
        """Paint the rendered SVG into the widget.

        If aspect-ratio preservation is enabled, the SVG is scaled uniformly and
        positioned according to the current alignment. Otherwise, it is stretched
        to fill the widget rectangle.

        Args:
            event: Qt paint event.
        """
        if not self._renderer.isValid():
            return super().paintEvent(event)

        painter = QPainter(self)
        widget_rect = self.rect()

        if not self._keep_aspect_ratio:
            self._renderer.render(painter, widget_rect)
            return

        svg_size = self._renderer.defaultSize()
        if not svg_size.isValid():
            self._renderer.render(painter, widget_rect)
            return

        svg_w = svg_size.width()
        svg_h = svg_size.height()
        if svg_w <= 0 or svg_h <= 0:
            self._renderer.render(painter, widget_rect)
            return

        # Uniform scale factor
        scale = min(
            widget_rect.width() / svg_w,
            widget_rect.height() / svg_h,
        )

        target_w = svg_w * scale
        target_h = svg_h * scale

        align = self._alignment

        # horizontal
        if align & Qt.AlignLeft:
            x = widget_rect.left()
        elif align & Qt.AlignRight:
            x = widget_rect.right() - target_w
        else:  # center (default)
            x = widget_rect.left() + (widget_rect.width() - target_w) / 2.0

        # vertical
        if align & Qt.AlignTop:
            y = widget_rect.top()
        elif align & Qt.AlignBottom:
            y = widget_rect.bottom() - target_h
        else:  # center (default)
            y = widget_rect.top() + (widget_rect.height() - target_h) / 2.0

        target_rect = QRectF(x, y, target_w, target_h)
        self._renderer.render(painter, target_rect)


def _demo_main() -> int:
    """Run this module as a standalone demo application.

    Shows LaTeX vs mathtext rendering, alignment and stretching, colors and
    the disabled state (toggled from a context menu), and a live editor for
    trying arbitrary expressions.

    Returns:
        int: Qt application exit code.
    """
    from PySide6.QtWidgets import (
        QApplication, QDoubleSpinBox, QGridLayout, QGroupBox, QHBoxLayout,
        QLabel, QLineEdit, QVBoxLayout, QWidget,
    )

    app = QApplication([])
    win = QWidget()
    win.setWindowTitle("MathLabel demo")
    root = QVBoxLayout(win)

    status = "on" if _latex_enabled else "off (mathtext fallback)"
    root.addWidget(QLabel(f"External LaTeX: {status}"))

    # --- 1. LaTeX vs mathtext -------------------------------------------
    box = QGroupBox("use_tex=True  vs  use_tex=False")
    grid = QGridLayout(box)
    samples = [
        r"T_1",
        r"E = mc^2",
        r"\Omega_{\mathrm{R}} = \frac{d\,E}{\hbar}",
        r"\mathrm{Population}\ \Delta N",
    ]
    for row, s in enumerate(samples):
        grid.addWidget(MathLabel(s, font_size=16, parent=box), row, 0)
        grid.addWidget(MathLabel(s, font_size=16, use_tex=False, parent=box), row, 1)
    root.addWidget(box)

    # --- 2. Alignment and stretching ------------------------------------
    box = QGroupBox("Alignment (aspect kept)  and  keep_aspect_ratio=False")
    row = QHBoxLayout(box)
    for align in (Qt.AlignLeft, Qt.AlignCenter, Qt.AlignRight):
        lbl = MathLabel(r"\eta", font_size=14, alignment=align, parent=box)
        lbl.setMinimumSize(90, 50)
        lbl.setAutoFillBackground(True)  # makes the label's area visible
        lbl.setStyleSheet("background: #ffffff;")
        row.addWidget(lbl)
    stretched = MathLabel(r"\omega_0", font_size=14, keep_aspect_ratio=False, parent=box)
    stretched.setMinimumSize(90, 50)
    stretched.setAutoFillBackground(True)
    stretched.setStyleSheet("background: #ffffff;")
    row.addWidget(stretched)
    root.addWidget(box)

    # --- 3. Colors, disabled state, context menu ------------------------
    box = QGroupBox("Colors  (right-click the first label)")
    row = QHBoxLayout(box)
    controller = MathLabel(r"\mathrm{Menu}", font_size=16, parent=box)
    colored = [
        MathLabel(r"^4_2\mathrm{He}", font_size=16, text_color="red", parent=box),
        MathLabel(r"A'", font_size=16, text_color="green", parent=box),
        MathLabel(r"w", font_size=16, text_color="blue", parent=box),
    ]
    controller.set_menu_items([
        {"id": "enable", "text": "Colors enabled", "checkable": True, "checked": True},
        {"id": "sep"},
        {"id": "hello", "text": "Print hello"},
    ])

    def on_action(act_id: str, checked: bool) -> None:
        print(f"action={act_id!r} checked={checked}")
        if act_id == "enable":
            for lbl in colored:
                lbl.setEnabled(checked)

    controller.rightClickRequested.connect(on_action)
    row.addWidget(controller)
    for lbl in colored:
        row.addWidget(lbl)
    root.addWidget(box)

    # --- 4. Live editor ---------------------------------------------------
    box = QGroupBox("Live editor  (press Enter to render)")
    col = QVBoxLayout(box)
    controls = QHBoxLayout()
    editor = QLineEdit(r"\frac{\partial E}{\partial z} = -\frac{1}{c}\frac{\partial E}{\partial t}")
    size = QDoubleSpinBox()
    size.setRange(6.0, 48.0)
    size.setValue(18.0)
    controls.addWidget(editor, 1)
    controls.addWidget(size)
    preview = MathLabel(font_size=size.value(), parent=box)
    error = QLabel()
    error.setStyleSheet("color: #b00020;")
    col.addLayout(controls)
    col.addWidget(preview)
    col.addWidget(error)

    def render() -> None:
        try:
            preview.set_text(editor.text(), font_size=size.value())
            error.clear()
        except Exception as exc:  # bad LaTeX/mathtext raises here
            error.setText(f"{type(exc).__name__}: {str(exc).splitlines()[0]}")

    editor.returnPressed.connect(render)
    size.valueChanged.connect(lambda _: render())
    render()
    root.addWidget(box)

    win.resize(520, 560)
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(_demo_main())
