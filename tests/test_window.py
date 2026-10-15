import pytest
from PySide6.QtWidgets import QMainWindow

from sciwidgets.labels import MathLabel
from sciwidgets.window import MenuBarController, StatusBarController


def test_menu_bar(spy):
    win = QMainWindow()
    menu = MenuBarController(win, {
        "File": [{"id": "open", "text": "Open"}, {"id": "sep"},
                 {"submenu": "Recent", "items": [{"id": "r1", "text": "a.json"}]}],
        "View": [{"id": "grid", "text": "Grid", "checkable": True, "checked": True}],
    })
    s = spy(menu.actionTriggered)
    assert menu.get_checked("grid") is True
    menu.set_checked("grid", False)
    assert menu.get_checked("grid") is False and len(s) == 0
    menu.action("open").trigger()
    assert s.calls[-1][:2] == ("File", "open")
    menu.action("r1").trigger()
    assert s.calls[-1][0] == "File/Recent"
    with pytest.raises(KeyError):
        menu.action("nope")


def test_menu_bar_rejects_duplicate_ids():
    with pytest.raises(ValueError):
        MenuBarController(QMainWindow(), {"File": [{"id": "a", "text": "A"}, {"id": "a", "text": "B"}]})


def test_status_bar():
    win = QMainWindow()
    status = StatusBarController(win, states=["Ready", "Solving…"])
    status.set_state("Solving…", busy=True)
    assert status.is_busy()
    status.set_state("Ready")
    assert not status.is_busy()
    status.set_path("~/run.json")
    status.set_modified(True)
    assert status.is_modified() and status.get_path() == "~/run.json"
    status.set_path("~/run.json")                               # saving clears the *
    assert not status.is_modified()


def test_math_label_renders_mathtext():
    label = MathLabel(r"\Omega = \frac{dE}{\hbar}")
    assert label.sizeHint().width() > 0
    label.set_text(r"\alpha")
    with pytest.raises(Exception):
        MathLabel(r"\frac{")
