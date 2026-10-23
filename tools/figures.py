"""The pictures and animations of the sciwidgets docs (``docs/figures``).

    python tools/figures.py                  # everything
    python tools/figures.py plot showcase    # only these
    python tools/figures.py plot --dark      # plot_demo_dark.png, to check dark mode
    python tools/figures.py --list

How it works: ``sciwidgets.devtools`` (docs/devtools.md). On macOS the
pictures have the window's title bar and shadow; that needs
``pip install -e ".[dev]"`` and Screen Recording permission for the terminal.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Iterator, List

from sciwidgets.devtools import Gif, Player, Shot, capture, main


# ------------------------------------------------------------------- picture states
def invalid_integer(p: Player) -> None:
    """500 typed into the field that accepts −100…100: the red frame shows."""
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from sciwidgets.params.numeric_line_edit import NumericLineEdit
    edits = p.win.findChildren(NumericLineEdit, options=Qt.FindDirectChildrenOnly)
    edit = next(e for e in edits if e._value_is_int)
    edit.setFocus()
    edit.selectAll()
    QTest.keyClicks(edit, "500")


_opened: List = []


def three_dialogs(p: Player) -> Iterator[float]:
    """The Save question, About and rich-information dialogs, side by side."""
    from PySide6.QtWidgets import QDialog, QPushButton

    def show_instead(dialog):  # the helpers call exec(); show the dialog and go on instead
        _opened.append(dialog)
        dialog.show()
        return 0

    QDialog.exec = show_instead
    buttons = {b.text(): b for b in p.win.findChildren(QPushButton)}
    for text in ("Ask: Save / Don't Save / Cancel", "About (default icon)", "Rich information"):
        buttons[text].click()
    p.win.hide()
    yield 0.6


def arrange_dialogs(p: Player, out: Path) -> None:
    """Capture each dialog and arrange them: two on the left, one on the right."""
    from PIL import Image
    tmp = Path(tempfile.mkdtemp())
    parts = []
    for i, dialog in enumerate(_opened):
        dialog.raise_()
        dialog.activateWindow()
        p.app.processEvents()
        parts.append(tmp / f"{i}.png")
        capture(dialog, parts[-1])
    ask, about, rich = (Image.open(path).convert("RGBA") for path in parts)
    gap = 24
    left = max(ask.width, about.width)
    canvas = Image.new("RGBA", (left + gap + rich.width, max(ask.height + gap + about.height, rich.height)),
                       (0, 0, 0, 0))
    canvas.paste(ask, ((left - ask.width) // 2, 0), ask)
    canvas.paste(about, ((left - about.width) // 2, ask.height + gap), about)
    canvas.paste(rich, (left + gap, (canvas.height - rich.height) // 2), rich)
    canvas.save(out)


def splash() -> int:
    """The demo's splash with one message, without the window that follows it."""
    from PySide6.QtWidgets import QApplication
    from sciwidgets.splash import SplashScreen
    from sciwidgets.splash.__main__ import _demo_image
    from sciwidgets.style import apply_sci_style
    app = QApplication([])
    apply_sci_style(app)
    screen = SplashScreen(_demo_image(), size=(560, 315), title="sciwidgets\nSplash", subtitle="Demo")
    screen.show_message("Loading settings...")
    return app.exec()


# ------------------------------------------------------------------- animations
def showcase(p: Player) -> Iterator[float]:
    """Fit the pulse by eye, type an exact width, then switch to dark mode."""
    panel = p.win.panel
    yield 0.6
    yield from p.drag_slider(panel.get_widget("pulse.a"), 1.6, 0.9)
    yield 0.25
    yield from p.drag_slider(panel.get_widget("pulse.t0"), 46.0, 1.1)
    yield 0.25
    yield from p.drag_slider(panel.get_widget("pulse.w"), 8.5, 0.8)
    yield 0.4
    yield from p.move(p.at(panel.get_widget("pulse.w")._slider, 0.5), 0.4)
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
    yield from p.drag_slider(panel.get_widget("pulse.t0"), 30.0, 0.8)
    yield 0.2
    yield from p.drag_slider(panel.get_widget("pulse.t0"), 46.0, 0.8)
    yield 0.8


def _labeled(win, label: str):
    from PySide6.QtWidgets import QWidget
    return next(w for w in win.findChildren(QWidget)
                if getattr(w, "_label_text", None) == label and hasattr(w, "_slider"))


def slider_menu(p: Player) -> Iterator[float]:
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


SHOTS = {
    "showcase": Shot("sciwidgets", file="showcase_demo.png"),
    "sliders": Shot("sciwidgets.params.sliders", file="sliders_demo.png"),
    "params": Shot("sciwidgets.params", invalid_integer, file="params_demo.png"),
    "panel": Shot("sciwidgets.panel", file="panel_demo.png"),
    "plot": Shot("sciwidgets.plot", file="plot_demo.png"),
    "table": Shot("sciwidgets.table", file="table_demo.png"),
    "labels": Shot("sciwidgets.labels", file="labels_demo.png"),
    "window": Shot("sciwidgets.window", file="window_demo.png"),
    "dialogs": Shot("sciwidgets.dialogs", three_dialogs, file="dialogs_demo.png", capture=arrange_dialogs),
    "splash": Shot(splash, file="splash_demo.png", shadow=False),
    "theme": Shot("sciwidgets.params.sliders", file="theme_demo.png", both=True),
}

GIFS = {
    "showcase_gif": Gif("sciwidgets", showcase, file="showcase.gif", width=900),
    "sliders_gif": Gif("sciwidgets.params.sliders", slider_menu, file="sliders_demo.gif", width=760),
}

if __name__ == "__main__":
    raise SystemExit(main(SHOTS, GIFS))
