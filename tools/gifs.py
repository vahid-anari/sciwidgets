"""Record the animated GIFs of the documentation from scripted demo sessions.

    python tools/gifs.py               # every animation
    python tools/gifs.py showcase      # only this one
    python tools/gifs.py --list

Each animation runs a demo in a fresh process and plays a short script on it:
mouse drags on sliders, right-click menus, dialogs, menu choices. Frames are
grabbed from the window about 20 times a second; menus and dialogs, which are
windows of their own, are pasted in at their place, and a mouse pointer is
drawn where the script's mouse is. The result goes to ``docs/figures``.

Frames show the window's contents (no title bar or shadow). Nothing here needs
the screen to stay free: the script sends its events to the windows directly.
"""

from __future__ import annotations

import argparse
import runpy
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Iterator, List, Optional

ROOT = Path(__file__).resolve().parent.parent
FIGURES = ROOT / "docs" / "figures"
FRAME_MS = 50
"""Time between frames (20 frames a second)."""
HOLD_END_MS = 1800
"""How long the last frame stays before the animation starts again."""
CHILD_TIMEOUT = 180


# ======================================================================= the player
class Player:
    """Plays a script on a window and records frames.

    A script is a generator that yields waits in seconds; between them it calls
    the player's actions (``drag_slider``, ``right_click``, ``choose`` ...).
    Actions that open a menu or a dialog with ``exec()`` are started from the
    event loop, so the script goes on while they are open.
    """

    def __init__(self, app, win, out: Path, width: int) -> None:
        from PySide6.QtCore import QPointF, QTimer
        self.app, self.win, self.out, self.width = app, win, out, width
        self.frames: List = []
        self.cursor = QPointF(win.width() * 0.6, win.height() * 0.5)
        self.pressed = False
        self._timer = QTimer()
        self._timer.timeout.connect(self._grab)
        self._script: Optional[Iterator[float]] = None

    # ----- running -----
    def run(self, script: Callable[["Player"], Iterator[float]]) -> None:
        from PySide6.QtCore import QTimer
        self._script = script(self)
        self._timer.start(FRAME_MS)
        QTimer.singleShot(0, self._step)

    def _step(self) -> None:
        from PySide6.QtCore import QTimer
        try:
            wait = next(self._script)
        except StopIteration:
            QTimer.singleShot(HOLD_END_MS, self._finish)
            return
        QTimer.singleShot(int(max(wait, 0) * 1000), self._step)

    def _finish(self) -> None:
        self._grab()
        self._timer.stop()
        save_gif(self.frames, self.out, self.width)
        self.app.quit()

    # ----- frames -----
    def _grab(self) -> None:
        from PySide6.QtCore import QPoint, QPointF, Qt
        from PySide6.QtGui import QColor, QPainter, QPalette, QPen, QPolygonF
        from PySide6.QtWidgets import QApplication
        pix = self.win.grab()
        image = pix.toImage()
        image.setDevicePixelRatio(pix.devicePixelRatio())
        painter = QPainter(image)
        origin = self.win.mapToGlobal(QPoint(0, 0))
        for top in QApplication.topLevelWidgets():
            if top is self.win or not top.isVisible() or not top.isWindow():
                continue
            if top.windowType() not in _POPUP_TYPES:
                continue
            pos = top.mapToGlobal(QPoint(0, 0)) - origin
            if top.windowType() != Qt.Popup:  # a dialog: a soft shadow and an edge, as a window would have
                painter.setPen(Qt.NoPen)
                for i, alpha in enumerate((40, 28, 16, 8)):
                    painter.setBrush(QColor(0, 0, 0, alpha))
                    painter.drawRoundedRect(pos.x() - i + 2, pos.y() - i + 4, top.width() + 2 * i,
                                            top.height() + 2 * i, 6 + i, 6 + i)
            painter.drawPixmap(pos, top.grab())
            painter.setPen(QPen(top.palette().color(QPalette.Mid), 1))
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(pos.x(), pos.y(), top.width() - 1, top.height() - 1)
        x, y = self.cursor.x(), self.cursor.y()
        arrow = QPolygonF([QPointF(x + dx, y + dy) for dx, dy in
                           ((0, 0), (0, 17), (4.5, 13), (7.5, 20), (10, 19), (7, 12), (12.5, 12))])
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor("white"), 1.6))
        painter.setBrush(QColor("black"))
        painter.drawPolygon(arrow)
        painter.end()
        self.frames.append(image)

    # ----- mouse -----
    def _target(self, global_pos):
        """The widget under a global point (popups first) and the point in its coordinates."""
        from PySide6.QtWidgets import QApplication
        popup = QApplication.activePopupWidget() or QApplication.activeModalWidget()
        for top in [popup, self.win]:
            if top is None:
                continue
            local = top.mapFromGlobal(global_pos)
            if top.rect().contains(local):
                child = top.childAt(local) or top
                return child, child.mapFromGlobal(global_pos)
        return self.win, self.win.mapFromGlobal(global_pos)

    def _send(self, kind, button, buttons) -> None:
        from PySide6.QtCore import QPointF, Qt
        from PySide6.QtGui import QMouseEvent
        from PySide6.QtWidgets import QApplication
        global_pos = self.win.mapToGlobal(self.cursor.toPoint())
        widget, local = self._target(global_pos)
        event = QMouseEvent(kind, QPointF(local), QPointF(global_pos), button, buttons, Qt.NoModifier)
        QApplication.sendEvent(widget, event)

    def move(self, to, seconds: float = 0.5) -> Iterator[float]:
        """Glide the mouse to a point of the main window (drags while pressed)."""
        from PySide6.QtCore import QEvent, QPointF, Qt
        start = QPointF(self.cursor)
        end = QPointF(to)
        steps = max(1, int(seconds * 1000 / FRAME_MS))
        for i in range(1, steps + 1):
            s = i / steps
            s = s * s * (3 - 2 * s)  # ease in and out
            self.cursor = start + (end - start) * s
            if self.pressed:
                self._send(QEvent.MouseMove, Qt.NoButton, Qt.LeftButton)
            yield FRAME_MS / 1000

    def press(self) -> None:
        from PySide6.QtCore import QEvent, Qt
        self.pressed = True
        self._send(QEvent.MouseButtonPress, Qt.LeftButton, Qt.LeftButton)

    def release(self) -> None:
        from PySide6.QtCore import QEvent, Qt
        self.pressed = False
        self._send(QEvent.MouseButtonRelease, Qt.LeftButton, Qt.NoButton)

    def right_click(self) -> None:
        """Right-click where the mouse is; the menu opens from the event loop."""
        from PySide6.QtCore import QEvent, Qt, QTimer
        from PySide6.QtGui import QContextMenuEvent
        from PySide6.QtWidgets import QApplication

        def click() -> None:
            self._send(QEvent.MouseButtonPress, Qt.RightButton, Qt.RightButton)
            self._send(QEvent.MouseButtonRelease, Qt.RightButton, Qt.NoButton)
            global_pos = self.win.mapToGlobal(self.cursor.toPoint())
            widget, local = self._target(global_pos)
            QApplication.sendEvent(widget, QContextMenuEvent(QContextMenuEvent.Mouse, local, global_pos))

        QTimer.singleShot(0, click)

    # ----- widgets -----
    def at(self, widget, fx: float = 0.5, fy: float = 0.5):
        """A point of ``widget`` (fractions of its size) in main-window coordinates."""
        from PySide6.QtCore import QPoint, QPointF
        local = QPoint(int(widget.width() * fx), int(widget.height() * fy))
        return QPointF(self.win.mapFromGlobal(widget.mapToGlobal(local)))

    def slider_point(self, slider, value: float):
        """Where ``value`` sits on a labeled slider's groove, in main-window coordinates."""
        from PySide6.QtCore import QPoint, QPointF
        from PySide6.QtWidgets import QStyle, QStyleOptionSlider
        qs = slider._slider
        opt = QStyleOptionSlider()
        qs.initStyleOption(opt)
        groove = qs.style().subControlRect(QStyle.CC_Slider, opt, QStyle.SC_SliderGroove, qs)
        handle = qs.style().subControlRect(QStyle.CC_Slider, opt, QStyle.SC_SliderHandle, qs)
        lo, hi = float(slider._min_value), float(slider._max_value)
        frac = min(max((value - lo) / (hi - lo), 0.0), 1.0)
        span = groove.width() - handle.width()
        x = groove.left() + handle.width() / 2 + frac * span
        return QPointF(self.win.mapFromGlobal(qs.mapToGlobal(QPoint(int(x), groove.center().y()))))

    def drag_slider(self, slider, value: float, seconds: float = 1.0) -> Iterator[float]:
        """Move to the slider's handle, press, drag to ``value``, release."""
        current = slider.get_value()
        yield from self.move(self.slider_point(slider, float(current)), 0.5)
        self.press()
        yield 0.15
        yield from self.move(self.slider_point(slider, value), seconds)
        yield 0.1
        self.release()

    def choose(self, text: str) -> Iterator[float]:
        """In the open menu, glide to the item ``text`` and choose it."""
        from PySide6.QtCore import QPointF, Qt
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QApplication
        menu = QApplication.activePopupWidget()
        action = next(a for a in menu.actions() if a.text().replace("…", "...") == text.replace("…", "..."))
        rect = menu.actionGeometry(action)
        point = self.win.mapFromGlobal(menu.mapToGlobal(rect.center()))
        yield from self.move(QPointF(point.x() - rect.width() * 0.25, point.y()), 0.45)
        menu.setActiveAction(action)
        yield 0.35
        QTest.keyClick(menu, Qt.Key_Return)
        yield 0.05

    def type_in_dialog(self, *texts: str) -> Iterator[float]:
        """Type into the open dialog's text fields, one text per field (``None`` skips one)."""
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QApplication, QLineEdit
        dialog = QApplication.activeModalWidget()
        edits = [e for e in dialog.findChildren(QLineEdit) if e.isVisible()]
        for edit, text in zip(edits, texts):
            if text is None:
                continue
            yield from self.move(self.at(edit, 0.7), 0.4)
            edit.setFocus()
            edit.selectAll()
            yield 0.25
            for ch in text:
                QTest.keyClicks(edit, ch)
                yield 0.09
            yield 0.2

    def press_button(self, text: str) -> Iterator[float]:
        """Glide to a button of the open dialog and click it."""
        from PySide6.QtWidgets import QAbstractButton, QApplication
        dialog = QApplication.activeModalWidget()
        button = next(b for b in dialog.findChildren(QAbstractButton) if b.text().replace("&", "") == text)
        yield from self.move(self.at(button), 0.45)
        yield 0.15
        button.click()
        yield 0.05

    def open_menu(self, title: str) -> Iterator[float]:
        """Open a menu of the window's menu bar."""
        bar = self.win.menuBar()
        action = next(a for a in bar.actions() if a.text().replace("&", "") == title)
        rect = bar.actionGeometry(action)
        yield from self.move(self.at(bar, (rect.center().x()) / bar.width(), 0.5), 0.6)
        bar.setActiveAction(action)
        yield 0.3


_POPUP_TYPES: tuple = ()


def save_gif(frames: List, out: Path, width: int) -> None:
    """Write the frames as a looping GIF of the given width."""
    from PIL import Image
    from PySide6.QtGui import QImage
    images = []
    for frame in frames:
        rgba = frame.convertToFormat(QImage.Format_RGBA8888)
        im = Image.frombuffer("RGBA", (rgba.width(), rgba.height()), bytes(rgba.constBits()), "raw", "RGBA", 0, 1)
        im = im.convert("RGB")
        if im.width != width:
            im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
        images.append(im)
    palette = images[len(images) // 2].quantize(colors=255, method=Image.Quantize.MEDIANCUT)
    paletted = [im.quantize(palette=palette, dither=Image.Dither.NONE) for im in images]
    durations = [FRAME_MS] * (len(paletted) - 1) + [HOLD_END_MS]
    out.parent.mkdir(parents=True, exist_ok=True)
    paletted[0].save(out, save_all=True, append_images=paletted[1:], duration=durations, loop=0,
                     optimize=True, disposal=1)


# ======================================================================= the scripts
def _panel_slider(win, path: str):
    return win.panel.get_widget(path)


def showcase(p: Player) -> Iterator[float]:
    """Fit the pulse by eye, type an exact width, then switch to dark mode."""
    win = p.win
    yield 0.6
    yield from p.drag_slider(_panel_slider(win, "pulse.a"), 1.6, 0.9)
    yield 0.25
    yield from p.drag_slider(_panel_slider(win, "pulse.t0"), 46.0, 1.1)
    yield 0.25
    yield from p.drag_slider(_panel_slider(win, "pulse.w"), 8.5, 0.8)
    yield 0.4
    w = _panel_slider(win, "pulse.w")
    yield from p.move(p.at(w._slider, 0.5), 0.4)
    p.right_click()
    yield 0.9
    yield from p.choose("Set Value...")
    yield 0.5
    yield from p.type_in_dialog("7")
    yield from p.press_button("OK")
    yield 1.0
    yield from p.open_menu("View")
    yield from p.choose("Dark Theme")
    yield 1.4
    yield from p.drag_slider(_panel_slider(win, "pulse.t0"), 30.0, 0.8)
    yield 0.2
    yield from p.drag_slider(_panel_slider(win, "pulse.t0"), 46.0, 0.8)
    yield 0.8


def _labeled(win, label: str):
    from PySide6.QtWidgets import QWidget
    return next(w for w in win.findChildren(QWidget)
                if getattr(w, "_label_text", None) == label and hasattr(w, "_slider"))


def sliders(p: Player) -> Iterator[float]:
    """The slider menu: Set Value, then Edit Configuration, then a drag."""
    t1 = _labeled(p.win, "T_1")
    yield 0.5
    yield from p.move(p.at(t1._slider, 0.6), 0.6)
    p.right_click()
    yield 0.9
    yield from p.choose("Set Value...")
    yield 0.5
    yield from p.type_in_dialog("4.25")
    yield from p.press_button("OK")
    yield 0.8
    yield from p.move(p.at(t1._slider, 0.6), 0.4)
    p.right_click()
    yield 0.9
    yield from p.choose("Edit Configuration...")
    yield 0.6
    yield from p.type_in_dialog(None, "20")
    yield from p.press_button("OK")
    yield 0.8
    yield from p.drag_slider(t1, 15.0, 1.2)
    yield 0.6


@dataclass
class Gif:
    module: str
    script: Callable[[Player], Iterator[float]]
    file: str
    width: int


GIFS: Dict[str, Gif] = {
    "showcase": Gif("sciwidgets", showcase, "showcase.gif", 900),
    "sliders": Gif("sciwidgets.params.sliders", sliders, "sliders_demo.gif", 760),
}


# ======================================================================= processes
def child(name: str, out: Path) -> int:
    import PySide6.QtWidgets as qtw
    from PySide6.QtCore import Qt, QTimer

    global _POPUP_TYPES
    _POPUP_TYPES = (Qt.Popup, Qt.Dialog, Qt.ToolTip, Qt.Sheet)
    gif = GIFS[name]
    base = qtw.QApplication

    class App(base):
        def exec(self):
            def start() -> None:
                windows = [w for w in base.topLevelWidgets() if w.isVisible() and w.isWindow()]
                win = max(windows, key=lambda w: w.width() * w.height())
                self.player = Player(self, win, out, gif.width)  # keep it alive until the end
                self.player.run(gif.script)

            QTimer.singleShot(900, start)
            return super().exec()

    qtw.QApplication = App
    sys.argv = [gif.module]
    try:
        runpy.run_module(gif.module, run_name="__main__")
    except SystemExit as stop:
        return int(stop.code or 0)
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("names", nargs="*", help="animations to record (default: all); see --list")
    parser.add_argument("--out-dir", type=Path, default=FIGURES, help="folder (default: docs/figures)")
    parser.add_argument("--list", action="store_true", help="show the names and stop")
    parser.add_argument("--child", help=argparse.SUPPRESS)
    parser.add_argument("--out", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    if args.child:
        return child(args.child, args.out)
    if args.list:
        for name, gif in GIFS.items():
            print(f"{name:10s} {gif.file:20s} {gif.script.__doc__}")
        return 0
    names = args.names or list(GIFS)
    unknown = [n for n in names if n not in GIFS]
    if unknown:
        parser.error(f"unknown animation(s): {', '.join(unknown)}; see --list")
    failed = []
    for name in names:
        out = args.out_dir / GIFS[name].file
        cmd = [sys.executable, str(Path(__file__).resolve()), "--child", name, "--out", str(out)]
        try:
            ok = subprocess.run(cmd, cwd=ROOT, timeout=CHILD_TIMEOUT).returncode == 0 and out.exists()
        except subprocess.TimeoutExpired:
            ok = False
        if ok:
            from PIL import Image
            with Image.open(out) as im:
                print(f"{out}  {im.width}×{im.height}  {im.n_frames} frames  {out.stat().st_size / 1e6:.1f} MB")
        else:
            failed.append(name)
            print(f"{name}: failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
