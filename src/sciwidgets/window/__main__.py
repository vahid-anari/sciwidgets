"""Demo for the window helpers: ``python -m sciwidgets.window``."""

import sys
import time

from PySide6.QtCore import QTimer
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QApplication, QMainWindow, QPlainTextEdit

from sciwidgets.window import MenuBarController, StatusBarController

MENU_SPEC = {
    "File": [
        {"id": "open", "text": "Open…", "shortcut": QKeySequence.Open},
        {"id": "recent", "submenu": "Open Recent", "items": [
            {"id": "recent_1", "text": "maser_run_1.json"},
            {"id": "recent_2", "text": "maser_run_2.json"},
            {"id": "sep"},
            {"id": "clear_recent", "text": "Clear Menu"},
        ]},
        {"id": "sep"},
        {"id": "save", "text": "Save", "shortcut": QKeySequence.Save},
        {"id": "sep"},
        {"id": "quit", "text": "Quit", "shortcut": QKeySequence.Quit, "role": QAction.QuitRole},
    ],
    "Edit": [
        {"id": "modify", "text": "Change Something", "shortcut": "Ctrl+E"},
    ],
    "Run": [
        {"id": "solve", "text": "Solve (2 s, window stays responsive)", "shortcut": "Ctrl+R"},
        {"id": "solve_blocking", "text": "Solve (2 s, blocking)", "shortcut": "Ctrl+Shift+R"},
        {"id": "sep"},
        {"id": "fail", "text": "Simulate Error"},
    ],
    "View": [
        {"id": "toolbar", "text": "Show Toolbar", "checkable": True, "checked": True},
    ],
}


def _demo_main() -> int:
    """Run a main window with a menu bar, a toolbar and a status bar.

    Returns:
        int: Qt application exit code.
    """
    app = QApplication(sys.argv)
    win = QMainWindow()
    win.setWindowTitle("Window helpers demo")

    log = QPlainTextEdit()
    log.setReadOnly(True)
    win.setCentralWidget(log)

    menu = MenuBarController(win, MENU_SPEC, native_menubar=False)
    status = StatusBarController(win, path_label="File")

    # The same QActions can also live on a toolbar
    toolbar = win.addToolBar("Main")
    for action_id in ("open", "save", "solve"):
        toolbar.addAction(menu.action(action_id))

    def finish_solve() -> None:
        status.set_state("Ready")
        menu.set_enabled("solve", True)
        menu.set_enabled("solve_blocking", True)
        log.appendPlainText("solve finished")

    def on_action(menu_path: str, action_id: str, checked: bool) -> None:
        log.appendPlainText(f"{menu_path} → {action_id} (checked={checked})")
        if action_id in ("open", "recent_1", "recent_2"):
            name = "maser_run_2.json" if action_id == "recent_2" else "maser_run_1.json"
            status.set_path(f"~/runs/{name}")
        elif action_id == "save":
            status.set_path(status.get_path() or "~/runs/untitled.json")
        elif action_id == "modify":
            status.set_modified(True)
        elif action_id == "solve":
            menu.set_enabled("solve", False)
            menu.set_enabled("solve_blocking", False)
            status.set_state("Solving…", busy=True)
            QTimer.singleShot(2000, finish_solve)
        elif action_id == "solve_blocking":
            status.set_state("Solving…", busy=True)

            def blocking_work() -> None:
                time.sleep(2.0)  # stands in for a long computation
                status.set_state("Ready")

            QTimer.singleShot(50, blocking_work)  # return to the event loop first, so the state is drawn
        elif action_id == "fail":
            status.set_state("Error")
        elif action_id == "toolbar":
            toolbar.setVisible(checked)
        elif action_id == "quit":
            win.close()

    menu.actionTriggered.connect(on_action)

    win.resize(640, 360)
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(_demo_main())
