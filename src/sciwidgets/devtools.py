"""Documentation pictures and animations of an app, taken by scripts.

An app lists what it wants in a small tool file and hands it to :func:`main`::

    # tools/figures.py
    from pathlib import Path
    from sciwidgets.devtools import Gif, Shot, main

    def solved(p):                       # a script: waits and actions, as a generator
        yield from p.wait_until(lambda: p.win._results)

    SHOTS = {"main_window": Shot("myapp", solved)}
    GIFS = {"tour": Gif("myapp", tour, width=900)}

    if __name__ == "__main__":
        raise SystemExit(main(SHOTS, GIFS, Path(__file__).parent.parent / "docs" / "figures"))

``python tools/figures.py`` then takes every picture and animation;
``python tools/figures.py main_window --dark`` one picture in dark mode;
``--list`` shows the names.

Each item runs in a fresh Python process with empty settings (so your own
saved settings never show in the pictures). The app is started (``start`` is
a module run like ``python -m``, or a function), its largest window is found,
the script is played on it, and then:

* a :class:`Shot` is captured. On macOS this is the system's window capture,
  as ⌘⇧4 Space takes it: title bar, shadow, Retina resolution. That needs
  ``pyobjc-framework-Quartz`` (the ``dev`` extra of sciwidgets on macOS) and
  Screen Recording permission for the terminal. Elsewhere, or with
  ``composite=True`` (to include an open menu), the window is grabbed by Qt and
  menus and dialogs are pasted in: no title bar.
* a :class:`Gif` is recorded while the script plays (about 20 frames a second,
  menus and dialogs pasted in, a mouse pointer drawn) and saved as a looping GIF.

Scripts are generators that call the :class:`Player`'s actions (``drag_slider``,
``right_click``, ``choose``, ``type_in_dialog``, ``press_button``, ``open_menu``
...) and yield waits in seconds. Events go to the windows directly, so the
computer can be used while a GIF records.

This module needs Pillow (installed with Matplotlib).
"""

from __future__ import annotations

import argparse
import os
import runpy
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional, Union

__all__ = ["Gif", "Player", "Shot", "capture", "main", "side_by_side"]

FRAME_MS = 50
"""Time between animation frames (20 frames a second)."""
HOLD_END_MS = 1800
"""How long the last frame of an animation stays before it starts again."""
SETTLE_MS = 900
"""Time for an app to build and draw before its script starts."""
CHILD_TIMEOUT = 180
"""Seconds one picture or animation may take before it is given up."""

Start = Union[str, Callable[[], Any]]
Script = Callable[["Player"], Any]


@dataclass
class Shot:
    """A picture.

    Attributes:
        start: Module to run as ``python -m <start>``, or a function that starts
            the app (and runs ``app.exec()``).
        script: Brings the app into the state to show (a generator of waits, or
            a plain function); ``None`` takes it as it opens.
        file: File name in the figures folder; default ``<name>.png``.
        shadow: Keep the window shadow (macOS capture).
        composite: Grab the window with Qt and paste open menus and dialogs in
            (no title bar); for pictures of a menu.
        target: ``"window"`` (the main window) or ``"dialog"`` (the dialog open
            at the end of the script).
        both: Take it in light and dark mode and put the two side by side.
        size: Resize the main window to ``(width, height)`` first.
        capture: Takes the picture instead: called with the player and the
            output path (e.g. to arrange several windows in one picture).
    """

    start: Start
    script: Optional[Script] = None
    file: Optional[str] = None
    shadow: bool = True
    composite: bool = False
    target: str = "window"
    both: bool = False
    size: Optional[tuple] = None
    capture: Optional[Callable[["Player", Path], None]] = None


@dataclass
class Gif:
    """An animation: the script is recorded while it plays.

    Attributes:
        start: As for :class:`Shot`.
        script: The actions to record.
        file: File name in the figures folder; default ``<name>.gif``.
        width: Width of the GIF in pixels (frames are scaled).
        size: Resize the main window to ``(width, height)`` first.
    """

    start: Start
    script: Script
    file: Optional[str] = None
    width: int = 900
    size: Optional[tuple] = None


# ======================================================================= capturing
def _window_number(widget) -> Optional[int]:
    """The macOS window number of a top-level Qt window (``None`` without pyobjc)."""
    try:
        import Quartz
    except ImportError:
        return None
    frame = widget.frameGeometry()
    best, best_err = None, None
    for info in Quartz.CGWindowListCopyWindowInfo(Quartz.kCGWindowListOptionOnScreenOnly, Quartz.kCGNullWindowID):
        if int(info.get("kCGWindowOwnerPID", -1)) != os.getpid():
            continue
        b = info.get("kCGWindowBounds", {})
        err = (abs(b.get("X", 0) - frame.x()) + abs(b.get("Y", 0) - frame.y())
               + abs(b.get("Width", 0) - frame.width()) + abs(b.get("Height", 0) - frame.height()))
        if best_err is None or err < best_err:
            best, best_err = int(info["kCGWindowNumber"]), err
    return best


def _bring_to_front(widget) -> None:
    """Make the app and the window active, so the title bar is drawn in colour."""
    try:
        from AppKit import NSApplication
        NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
    except ImportError:
        pass
    widget.raise_()
    widget.activateWindow()


def capture(widget, path: Path, *, shadow: bool = True) -> str:
    """Save a picture of a top-level window; returns how it was taken (``"screencapture"`` or ``"grab"``)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    number = _window_number(widget) if sys.platform == "darwin" else None
    if number is not None and shutil.which("screencapture"):
        cmd = ["screencapture", "-x", f"-l{number}"] + ([] if shadow else ["-o"]) + [str(path)]
        if subprocess.run(cmd).returncode == 0 and path.exists():
            return "screencapture"
    widget.grab().save(str(path))
    return "grab"


def side_by_side(paths: List[Path], out: Path, gap: int = 24) -> None:
    """Put pictures next to each other on a transparent background."""
    from PIL import Image
    images = [Image.open(p).convert("RGBA") for p in paths]
    width = sum(im.width for im in images) + gap * (len(images) - 1)
    canvas = Image.new("RGBA", (width, max(im.height for im in images)), (0, 0, 0, 0))
    x = 0
    for im in images:
        canvas.paste(im, (x, 0), im)
        x += im.width + gap
    canvas.save(out)


def _composite(win, cursor=None):
    """The window grabbed by Qt, with open menus and dialogs pasted in; optionally a mouse pointer."""
    from PySide6.QtCore import QPoint, QPointF, Qt
    from PySide6.QtGui import QColor, QPainter, QPalette, QPen, QPolygonF
    from PySide6.QtWidgets import QApplication
    pix = win.grab()
    image = pix.toImage()
    image.setDevicePixelRatio(pix.devicePixelRatio())
    painter = QPainter(image)
    origin = win.mapToGlobal(QPoint(0, 0))
    for top in QApplication.topLevelWidgets():
        if top is win or not top.isVisible() or not top.isWindow():
            continue
        if top.windowType() not in (Qt.Popup, Qt.Dialog, Qt.ToolTip, Qt.Sheet):
            continue
        pos = top.mapToGlobal(QPoint(0, 0)) - origin
        if top.windowType() != Qt.Popup:  # a dialog: a soft shadow, as a window would have
            painter.setPen(Qt.NoPen)
            for i, alpha in enumerate((40, 28, 16, 8)):
                painter.setBrush(QColor(0, 0, 0, alpha))
                painter.drawRoundedRect(pos.x() - i + 2, pos.y() - i + 4, top.width() + 2 * i,
                                        top.height() + 2 * i, 6 + i, 6 + i)
        painter.drawPixmap(pos, top.grab())
        painter.setPen(QPen(top.palette().color(QPalette.Mid), 1))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(pos.x(), pos.y(), top.width() - 1, top.height() - 1)
    if cursor is not None:
        x, y = cursor.x(), cursor.y()
        arrow = QPolygonF([QPointF(x + dx, y + dy) for dx, dy in
                           ((0, 0), (0, 17), (4.5, 13), (7.5, 20), (10, 19), (7, 12), (12.5, 12))])
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor("white"), 1.6))
        painter.setBrush(QColor("black"))
        painter.drawPolygon(arrow)
    painter.end()
    return image


def save_gif(frames: List, out: Path, width: int) -> None:
    """Write Qt images as a looping GIF of the given width."""
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
    # one palette for every frame, from up to eight frames spread over the animation (so that a switch
    # to dark mode, or colours that appear late, keep their colours)
    picks = images[::max(1, len(images) // 8)][:8]
    w, h = max(1, picks[0].width // 2), max(1, picks[0].height // 2)
    mosaic = Image.new("RGB", (w, h * len(picks)))
    for i, im in enumerate(picks):
        mosaic.paste(im.resize((w, h)), (0, i * h))
    palette = mosaic.quantize(colors=255, method=Image.Quantize.FASTOCTREE)
    paletted = [im.quantize(palette=palette, dither=Image.Dither.NONE) for im in images]
    durations = [FRAME_MS] * (len(paletted) - 1) + [HOLD_END_MS]
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    paletted[0].save(out, save_all=True, append_images=paletted[1:], duration=durations, loop=0,
                     optimize=True, disposal=1)


# ======================================================================= the player
class Player:
    """Plays a script on a window, optionally recording frames.

    A script is a function of the player that yields waits in seconds (a
    generator) and calls the actions in between. Actions that open a menu or
    a dialog with ``exec()`` start it from the event loop, so the script goes
    on while it is open.

    Attributes:
        app: The application.
        win: The main window.
        cursor: The script's mouse position, in main-window coordinates.
    """

    def __init__(self, app, win, *, record: bool = False) -> None:
        from PySide6.QtCore import QPointF, QTimer
        self.app, self.win = app, win
        self.frames: List = []
        self.cursor = QPointF(win.width() * 0.6, win.height() * 0.5)
        self.pressed = False
        self._timer = QTimer()
        self._timer.timeout.connect(self._grab)
        self._record = record
        self._script: Optional[Iterator[float]] = None
        self._done: Optional[Callable[[], None]] = None
        # Code that asks where the mouse is (QCursor.pos(), e.g. to open a menu there) gets the
        # script's mouse instead of the real one, which the script never moves.
        from PySide6.QtGui import QCursor
        QCursor.pos = staticmethod(lambda *args: self.win.mapToGlobal(self.cursor.toPoint()))

    # ----- running -----
    def run(self, script: Optional[Script], done: Callable[[], None]) -> None:
        """Play ``script`` and call ``done`` afterwards (from the event loop)."""
        from PySide6.QtCore import QTimer
        result = script(self) if script is not None else None
        self._script = result if hasattr(result, "__next__") else iter(())
        self._done = done
        if self._record:
            self._timer.start(FRAME_MS)
        QTimer.singleShot(0, self._step)

    def _step(self) -> None:
        from PySide6.QtCore import QTimer
        try:
            wait = next(self._script)
        except StopIteration:
            QTimer.singleShot(HOLD_END_MS if self._record else 400, self._finish)
            return
        QTimer.singleShot(int(max(wait or 0, 0) * 1000), self._step)

    def _finish(self) -> None:
        if self._record:
            self._grab()
            self._timer.stop()
        self._done()

    def _grab(self) -> None:
        self.frames.append(_composite(self.win, self.cursor))

    # ----- waiting -----
    def wait_until(self, condition: Callable[[], Any], timeout: float = 60.0, step: float = 0.1) -> Iterator[float]:
        """Wait until ``condition()`` is true (e.g. a solve has finished)."""
        waited = 0.0
        while not condition() and waited < timeout:
            yield step
            waited += step

    # ----- mouse -----
    def _target(self, global_pos):
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
        start, end = QPointF(self.cursor), QPointF(to)
        steps = max(1, int(seconds * 1000 / FRAME_MS))
        for i in range(1, steps + 1):
            s = i / steps
            s = s * s * (3 - 2 * s)  # ease in and out
            self.cursor = start + (end - start) * s
            if self.pressed:
                self._send(QEvent.MouseMove, Qt.NoButton, Qt.LeftButton)
            yield FRAME_MS / 1000

    def press(self) -> None:
        """Press the left button where the mouse is."""
        from PySide6.QtCore import QEvent, Qt
        self.pressed = True
        self._send(QEvent.MouseButtonPress, Qt.LeftButton, Qt.LeftButton)

    def release(self) -> None:
        """Release the left button."""
        from PySide6.QtCore import QEvent, Qt
        self.pressed = False
        self._send(QEvent.MouseButtonRelease, Qt.LeftButton, Qt.NoButton)

    def click(self) -> None:
        """Click the left button where the mouse is."""
        self.press()
        self.release()

    def right_click(self) -> None:
        """Right-click where the mouse is; a menu it opens runs from the event loop."""
        from PySide6.QtCore import QEvent, Qt, QTimer
        from PySide6.QtGui import QContextMenuEvent
        from PySide6.QtWidgets import QApplication

        def go() -> None:
            self._send(QEvent.MouseButtonPress, Qt.RightButton, Qt.RightButton)
            self._send(QEvent.MouseButtonRelease, Qt.RightButton, Qt.NoButton)
            if QApplication.activePopupWidget() is not None:  # the press already opened a menu
                return
            global_pos = self.win.mapToGlobal(self.cursor.toPoint())
            widget, local = self._target(global_pos)
            QApplication.sendEvent(widget, QContextMenuEvent(QContextMenuEvent.Mouse, local, global_pos))

        QTimer.singleShot(0, go)

    # ----- widgets -----
    def at(self, widget, fx: float = 0.5, fy: float = 0.5):
        """A point of ``widget`` (fractions of its size) in main-window coordinates."""
        from PySide6.QtCore import QPoint, QPointF
        local = QPoint(int(widget.width() * fx), int(widget.height() * fy))
        return QPointF(self.win.mapFromGlobal(widget.mapToGlobal(local)))

    @staticmethod
    def _qslider(slider):
        from PySide6.QtWidgets import QSlider
        return slider if isinstance(slider, QSlider) else getattr(slider, "_slider")

    def slider_point(self, slider, fraction: Optional[float] = None, *, value: Optional[float] = None):
        """A point on a slider's groove in main-window coordinates.

        Args:
            slider: A sciwidgets slider (or a ``QSlider``).
            fraction: Position along the groove, 0 to 1; default: where the handle is.
            value: Instead of ``fraction``, a value of a float or int slider.
        """
        from PySide6.QtCore import QPoint, QPointF
        from PySide6.QtWidgets import QStyle, QStyleOptionSlider
        qs = self._qslider(slider)
        if value is not None:
            lo, hi = float(slider._min_value), float(slider._max_value)
            fraction = (value - lo) / (hi - lo)
        elif fraction is None:
            span = qs.maximum() - qs.minimum()
            fraction = (qs.value() - qs.minimum()) / span if span else 0.0
        fraction = min(max(fraction, 0.0), 1.0)
        opt = QStyleOptionSlider()
        qs.initStyleOption(opt)
        groove = qs.style().subControlRect(QStyle.CC_Slider, opt, QStyle.SC_SliderGroove, qs)
        handle = qs.style().subControlRect(QStyle.CC_Slider, opt, QStyle.SC_SliderHandle, qs)
        x = groove.left() + handle.width() / 2 + fraction * (groove.width() - handle.width())
        return QPointF(self.win.mapFromGlobal(qs.mapToGlobal(QPoint(int(x), groove.center().y()))))

    def drag_slider(self, slider, value: Optional[float] = None, seconds: float = 1.0, *,
                    fraction: Optional[float] = None) -> Iterator[float]:
        """Move to the slider's handle, press, drag to ``value`` (or ``fraction`` of the groove), release."""
        yield from self.move(self.slider_point(slider), 0.5)
        self.press()
        yield 0.15
        yield from self.move(self.slider_point(slider, fraction, value=value), seconds)
        yield 0.1
        self.release()

    def choose(self, text: str) -> Iterator[float]:
        """In the open menu, glide to the item ``text`` and choose it (a submenu opens)."""
        from PySide6.QtCore import QPointF, Qt
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QApplication
        menu = QApplication.activePopupWidget()
        if menu is None:
            raise RuntimeError(f"no menu is open to choose {text!r} from")
        wanted = text.replace("…", "...").replace("&", "")
        action = next(a for a in menu.actions() if a.text().replace("…", "...").replace("&", "") == wanted)
        rect = menu.actionGeometry(action)
        point = self.win.mapFromGlobal(menu.mapToGlobal(rect.center()))
        yield from self.move(QPointF(point.x() - rect.width() * 0.25, point.y()), 0.45)
        menu.setActiveAction(action)
        yield 0.35
        QTest.keyClick(menu, Qt.Key_Right if action.menu() is not None else Qt.Key_Return)
        yield 0.3 if action.menu() is not None else 0.05

    def type_in_dialog(self, *texts: Optional[str]) -> Iterator[float]:
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
        yield from self.move(self.at(bar, rect.center().x() / bar.width(), 0.5), 0.6)
        bar.setActiveAction(action)
        yield 0.3

    def select(self, combo, text: str) -> Iterator[float]:
        """Glide to a combo box and choose the entry ``text`` (as the user would)."""
        yield from self.move(self.at(combo, 0.4), 0.5)
        yield 0.2
        index = combo.findText(text)
        if index < 0:
            raise ValueError(f"combo box has no entry {text!r}")
        combo.setCurrentIndex(index)
        yield 0.3

    def trigger(self, text: str) -> None:
        """Trigger a menu action of the window by its text (without showing the menu)."""
        from PySide6.QtGui import QAction
        from PySide6.QtCore import QTimer
        wanted = text.replace("…", "...").replace("&", "")
        action = next(a for a in self.win.findChildren(QAction)
                      if a.text().replace("…", "...").replace("&", "") == wanted)
        QTimer.singleShot(0, action.trigger)


# ======================================================================= processes
def _main_window(app):
    windows = [w for w in app.topLevelWidgets() if w.isVisible() and w.isWindow()]
    return max(windows, key=lambda w: w.width() * w.height())


def _isolate_settings() -> None:
    """Keep the app's saved settings in an empty temporary folder.

    ``QSettings(organization, application)`` always uses the system's own
    store (on macOS the user's preferences), whatever the default format, so
    ``QSettings`` itself is replaced by a class that writes ``.ini`` files in a
    temporary folder. This runs before the app's modules are imported.
    """
    import PySide6.QtCore as qtcore
    folder = Path(tempfile.mkdtemp(prefix="figures-settings-"))
    base = qtcore.QSettings

    class IsolatedSettings(base):
        def __init__(self, *args, **kwargs):
            if len(args) >= 2 and isinstance(args[0], str) and isinstance(args[1], base.Format):
                super().__init__(*args, **kwargs)  # an explicit file: leave it as asked
                return
            names = [a for a in args if isinstance(a, str)]
            parent = [a for a in args if isinstance(a, qtcore.QObject)]
            stem = "_".join(names) or "default"
            super().__init__(str(folder / f"{stem}.ini"), base.IniFormat, *parent, **kwargs)

    qtcore.QSettings = IsolatedSettings
    base.setDefaultFormat(base.IniFormat)
    for scope in (base.UserScope, base.SystemScope):
        base.setPath(base.IniFormat, scope, str(folder))


def _child(item: Union[Shot, Gif], out: Path, scheme: str) -> int:
    """Start the app, play the script, capture or record (in a process of its own)."""
    import PySide6.QtWidgets as qtw
    from PySide6.QtCore import QTimer

    _isolate_settings()
    base = qtw.QApplication
    is_gif = isinstance(item, Gif)

    class App(base):
        def exec(self):
            from sciwidgets.style import set_color_scheme

            def start() -> None:
                set_color_scheme(self, scheme)
                win = _main_window(self)
                if item.size:
                    win.resize(*item.size)
                _bring_to_front(win)
                player = Player(self, win, record=is_gif)
                self._figures_player = player  # keep it alive until the end

                def done() -> None:
                    if is_gif:
                        save_gif(player.frames, out, item.width)
                    elif item.capture is not None:
                        item.capture(player, out)
                    else:
                        target = win
                        if item.target == "dialog":
                            target = qtw.QApplication.activeModalWidget() or win
                        if os.environ.get("FIGURES_DEBUG"):
                            from PySide6.QtWidgets import QLabel
                            for w in qtw.QApplication.topLevelWidgets():
                                if w.isVisible():
                                    texts = [lab.text()[:80] for lab in w.findChildren(QLabel) if lab.text()][:4]
                                    print("window:", type(w).__name__, w.windowTitle(), texts, flush=True)
                        if item.composite:
                            _composite(win).save(str(out))
                        else:
                            _bring_to_front(target)
                            self.processEvents()
                            capture(target, out, shadow=item.shadow)
                    os._exit(0)  # an open dialog or menu would keep exec() from returning

                QTimer.singleShot(200, lambda: player.run(item.script, done))

            QTimer.singleShot(0, lambda: set_color_scheme(self, scheme))
            QTimer.singleShot(SETTLE_MS, start)
            return super().exec()

    qtw.QApplication = App
    if isinstance(item.start, str):
        sys.argv = [item.start]
        try:
            runpy.run_module(item.start, run_name="__main__")
        except SystemExit as stop:
            return int(stop.code or 0)
        return 0
    result = item.start()
    return int(result or 0) if isinstance(result, int) else 0


def _run(tool: Path, name: str, out: Path, scheme: str) -> bool:
    cmd = [sys.executable, str(tool), "--child", name, "--out", str(out), "--scheme", scheme]
    try:
        result = subprocess.run(cmd, cwd=tool.parent, timeout=CHILD_TIMEOUT)
    except subprocess.TimeoutExpired:
        print(f"{name}: nothing after {CHILD_TIMEOUT} s (a dialog waiting for an answer?)")
        return False
    return result.returncode == 0 and out.exists()


def main(shots: Dict[str, Shot], gifs: Optional[Dict[str, Gif]] = None, figures: Optional[Path] = None,
         argv: Optional[List[str]] = None) -> int:
    """The command line of an app's figures tool (see the module docstring).

    Args:
        shots: Pictures by name.
        gifs: Animations by name.
        figures: Folder to save into (default: ``docs/figures`` next to the tool's folder).
        argv: Command-line arguments (default: ``sys.argv[1:]``).

    Returns:
        0 if every item was made, 1 otherwise.
    """
    gifs = gifs or {}
    tool = Path(sys.argv[0]).resolve()
    figures = Path(figures) if figures is not None else tool.parent.parent / "docs" / "figures"
    parser = argparse.ArgumentParser(description="Take the documentation pictures and animations.")
    parser.add_argument("names", nargs="*", help="items to make (default: all); see --list")
    parser.add_argument("--dark", action="store_true", help="pictures in dark mode, saved as <name>_dark.png")
    parser.add_argument("--pictures", action="store_true", help="only the pictures")
    parser.add_argument("--gifs", action="store_true", help="only the animations")
    parser.add_argument("--out-dir", type=Path, default=figures, help=f"folder (default: {figures})")
    parser.add_argument("--list", action="store_true", help="show the names and stop")
    parser.add_argument("--child", help=argparse.SUPPRESS)
    parser.add_argument("--out", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--scheme", default="light", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    items: Dict[str, Union[Shot, Gif]] = {**shots, **gifs}
    if args.child:
        return _child(items[args.child], args.out, args.scheme)
    if args.list:
        for name, item in items.items():
            kind = "gif" if isinstance(item, Gif) else "png"
            doc = (item.script.__doc__ or "").strip().splitlines()[0] if item.script and item.script.__doc__ else ""
            print(f"{name:16s} {kind}  {_file(name, item)}  {doc}")
        return 0
    names = args.names or [n for n in items
                           if not (args.pictures and n in gifs) and not (args.gifs and n in shots)]
    unknown = [n for n in names if n not in items]
    if unknown:
        parser.error(f"unknown item(s): {', '.join(unknown)}; see --list")
    if sys.platform == "darwin" and any(n in shots for n in names):
        try:
            import Quartz  # noqa: F401
        except ImportError:
            print('pyobjc-framework-Quartz is missing: pictures show the window contents only '
                  '(pip install "sciwidgets[dev]").')
    failed = []
    for name in names:
        item = items[name]
        out = args.out_dir / _file(name, item, dark=args.dark and isinstance(item, Shot))
        if isinstance(item, Shot) and item.both:
            tmp = Path(tempfile.mkdtemp())
            parts = [tmp / "light.png", tmp / "dark.png"]
            ok = _run(tool, name, parts[0], "light") and _run(tool, name, parts[1], "dark")
            if ok:
                side_by_side(parts, out)
        else:
            ok = _run(tool, name, out, "dark" if args.dark else "light")
        if ok:
            from PIL import Image
            with Image.open(out) as im:
                extra = f"  {im.n_frames} frames  {out.stat().st_size / 1e6:.1f} MB" if isinstance(item, Gif) else ""
                print(f"{out}  {im.width}×{im.height}{extra}")
        else:
            failed.append(name)
            print(f"{name}: failed")
    return 1 if failed else 0


def _file(name: str, item: Union[Shot, Gif], dark: bool = False) -> str:
    if item.file:
        stem, dot, ext = item.file.rpartition(".")
        return f"{stem}_dark.{ext}" if dark else item.file
    ext = "gif" if isinstance(item, Gif) else "png"
    return f"{name}_dark.{ext}" if dark else f"{name}.{ext}"
