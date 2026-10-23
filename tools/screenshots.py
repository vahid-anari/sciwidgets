"""Take the documentation screenshots of the sciwidgets demos.

    python tools/screenshots.py                 # every picture, light mode
    python tools/screenshots.py plot params     # only these
    python tools/screenshots.py plot --dark     # plot_dark.png, to check dark mode
    python tools/screenshots.py --list          # the names

Each picture is taken in a fresh Python process: the demo is started, put into
the state the docs show (for example an invalid number in a field), and its
window captured into ``docs/figures/<name>.png``.

On macOS the window is captured by the system, as ⌘⇧4 Space does: title bar,
shadow and Retina resolution. That needs ``pyobjc-framework-Quartz`` (in the
``dev`` extra on macOS) and Screen Recording permission for the terminal
(System Settings → Privacy & Security → Screen & System Audio Recording).
Elsewhere, or without pyobjc, Qt's ``grab()`` is used: the inside of the
window only, good enough for a quick look.

Not covered (take by hand): ``sliders_demo.gif`` and anything with an open
menu, which closes when a capture starts.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
FIGURES = ROOT / "docs" / "figures"
SETTLE_MS = 900
"""Time for a demo to build and draw (LaTeX labels, plots) before it is prepared and captured."""
CHILD_TIMEOUT = 90
"""Seconds one picture may take before it is given up."""


# ----------------------------------------------------------------- capturing
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
    """Save a picture of a top-level window; returns how it was taken."""
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


# ------------------------------------------------------------ demo states
def _type_invalid_integer(win) -> None:
    """params: 500 in the field that accepts −100…100, so the red frame shows."""
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from sciwidgets.params.numeric_line_edit import NumericLineEdit
    edits = win.findChildren(NumericLineEdit, options=Qt.FindDirectChildrenOnly)  # not those inside parameters
    edit = next(e for e in edits if e._value_is_int)
    edit.setFocus()
    edit.selectAll()
    QTest.keyClicks(edit, "500")  # out of range: the field marks it invalid while typing


def _no_state(win) -> None:
    pass


@dataclass
class Shot:
    module: str
    prepare: Callable = _no_state
    shadow: bool = True


SHOTS: Dict[str, Shot] = {
    "showcase": Shot("sciwidgets"),
    "sliders": Shot("sciwidgets.params.sliders"),
    "params": Shot("sciwidgets.params", _type_invalid_integer),
    "panel": Shot("sciwidgets.panel"),
    "plot": Shot("sciwidgets.plot"),
    "table": Shot("sciwidgets.table"),
    "labels": Shot("sciwidgets.labels"),
    "window": Shot("sciwidgets.window"),
    "dialogs": Shot("sciwidgets.dialogs"),      # three dialogs, arranged (see _dialogs)
    "splash": Shot("sciwidgets.splash", shadow=False),
}
EXTRA = {"theme": "sliders in light and dark mode, side by side (docs/style.md)"}


# ------------------------------------------------------------ child process
def _main_window(app):
    windows = [w for w in app.topLevelWidgets() if w.isVisible() and w.isWindow()]
    return max(windows, key=lambda w: w.width() * w.height())


def _dialogs(app, out: Path, scheme: str) -> None:
    """Open three of the demo's dialogs side by side and combine them into one picture."""
    from PySide6.QtWidgets import QDialog, QPushButton
    opened: List = []

    def show_instead(self):  # the helpers call exec(); show the dialog and go on instead
        opened.append(self)
        self.show()
        return 0

    QDialog.exec = show_instead
    win = _main_window(app)
    buttons = {b.text(): b for b in win.findChildren(QPushButton)}
    for text in ("Ask: Save / Don't Save / Cancel", "About (default icon)", "Rich information"):
        buttons[text].click()
    win.hide()

    def shoot() -> None:
        tmp = Path(tempfile.mkdtemp())
        parts = []
        for i, dlg in enumerate(opened):
            _bring_to_front(dlg)
            app.processEvents()
            parts.append(tmp / f"{i}.png")
            capture(dlg, parts[-1])
        from PIL import Image
        ask, about, rich = (Image.open(p).convert("RGBA") for p in parts)
        gap = 24
        left_w = max(ask.width, about.width)
        canvas = Image.new("RGBA", (left_w + gap + rich.width, max(ask.height + gap + about.height, rich.height)),
                           (0, 0, 0, 0))
        canvas.paste(ask, ((left_w - ask.width) // 2, 0), ask)
        canvas.paste(about, ((left_w - about.width) // 2, ask.height + gap), about)
        canvas.paste(rich, (left_w + gap, (canvas.height - rich.height) // 2), rich)
        canvas.save(out)
        app.quit()

    from PySide6.QtCore import QTimer
    QTimer.singleShot(SETTLE_MS, shoot)


def _splash(app, out: Path) -> None:
    """The demo's splash with one message, without the window that follows it."""
    from PySide6.QtCore import QTimer
    from sciwidgets.splash import SplashScreen
    from sciwidgets.splash.__main__ import _demo_image
    splash = SplashScreen(_demo_image(), size=(560, 315), title="sciwidgets\nSplash", subtitle="Demo")
    splash.show_message("Loading settings...")

    def shoot() -> None:
        capture(splash, out, shadow=False)
        app.quit()

    QTimer.singleShot(SETTLE_MS, shoot)


def child(name: str, out: Path, scheme: str) -> int:
    """Run one demo and capture it (in a process of its own)."""
    import runpy
    import PySide6.QtWidgets as qtw
    from PySide6.QtCore import QTimer

    if name == "splash":
        from sciwidgets.style import apply_sci_style, set_color_scheme
        app = qtw.QApplication(sys.argv[:1])
        apply_sci_style(app)
        set_color_scheme(app, scheme)
        _splash(app, out)
        return app.exec()

    shot = SHOTS[name]
    base = qtw.QApplication

    class App(base):
        def exec(self):
            from sciwidgets.style import set_color_scheme
            set_color_scheme(self, scheme)

            def start() -> None:
                if name == "dialogs":
                    _dialogs(self, out, scheme)
                    return
                win = _main_window(self)
                _bring_to_front(win)
                shot.prepare(win)
                QTimer.singleShot(400, lambda: (capture(win, out, shadow=shot.shadow), base.quit()))

            QTimer.singleShot(SETTLE_MS, start)
            return super().exec()

    qtw.QApplication = App
    sys.argv = [shot.module]
    try:
        runpy.run_module(shot.module, run_name="__main__")
    except SystemExit as stop:
        return int(stop.code or 0)
    return 0


# ----------------------------------------------------------- parent process
def run_child(name: str, out: Path, scheme: str) -> bool:
    cmd = [sys.executable, str(Path(__file__).resolve()), "--child", name, "--out", str(out), "--scheme", scheme]
    try:
        result = subprocess.run(cmd, cwd=ROOT, timeout=CHILD_TIMEOUT)
    except subprocess.TimeoutExpired:
        print(f"{name}: no picture after {CHILD_TIMEOUT} s (a dialog waiting for an answer?)")
        return False
    return result.returncode == 0 and out.exists()


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("names", nargs="*", help="pictures to take (default: all); see --list")
    parser.add_argument("--dark", action="store_true", help="dark mode; saves <name>_dark.png")
    parser.add_argument("--out-dir", type=Path, default=FIGURES, help="folder (default: docs/figures)")
    parser.add_argument("--list", action="store_true", help="show the names and stop")
    parser.add_argument("--child", help=argparse.SUPPRESS)
    parser.add_argument("--out", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--scheme", default="light", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    if args.child:
        return child(args.child, args.out, args.scheme)
    if args.list:
        for name, shot in SHOTS.items():
            print(f"{name:10s} {shot.module}")
        for name, text in EXTRA.items():
            print(f"{name:10s} {text}")
        return 0

    names = args.names or list(SHOTS) + list(EXTRA)
    unknown = [n for n in names if n not in SHOTS and n not in EXTRA]
    if unknown:
        parser.error(f"unknown picture(s): {', '.join(unknown)}; see --list")
    if sys.platform == "darwin":
        try:
            import Quartz  # noqa: F401
        except ImportError:
            print("pyobjc-framework-Quartz is missing: pictures show the window contents only "
                  "(pip install -e \".[dev]\").")
    scheme = "dark" if args.dark else "light"
    failed = []
    for name in names:
        if name == "theme":
            tmp = Path(tempfile.mkdtemp())
            parts = [tmp / "light.png", tmp / "dark.png"]
            ok = run_child("sliders", parts[0], "light") and run_child("sliders", parts[1], "dark")
            out = args.out_dir / "theme_demo.png"
            if ok:
                side_by_side(parts, out)
        else:
            out = args.out_dir / (f"{name}_demo_dark.png" if args.dark else f"{name}_demo.png")
            ok = run_child(name, out, scheme)
        if ok:
            from PIL import Image
            w, h = Image.open(out).size
            print(f"{out.relative_to(ROOT) if out.is_relative_to(ROOT) else out}  {w}×{h}  "
                  f"(docs: width=\"{min(w // 2, 900)}\")")
        else:
            failed.append(name)
            print(f"{name}: failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
