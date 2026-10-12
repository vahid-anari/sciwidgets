"""Demo for the dialogs subpackage: ``python -m sciwidgets.dialogs``."""

import sys

from PySide6.QtWidgets import (
    QApplication, QHBoxLayout, QPushButton, QStyle, QVBoxLayout, QWidget,
)

from sciwidgets.dialogs.message_dialogs import (
    ask_question,
    show_about_dialog,
    show_critical,
    show_information,
    show_rich_information,
    show_warning,
)


def _demo_main() -> int:
    """Run a window with one button per dialog helper.

    Returns:
        int: Qt application exit code.
    """
    app = QApplication(sys.argv)
    win = QWidget()
    win.setWindowTitle("Dialogs demo")

    # --- Questions --------------------------------------------------------
    def ask_save() -> None:
        r = ask_question(
            "Unsaved Changes",
            "Do you want to save your changes before closing?",
            "Your modifications will be lost if you close without saving.",
            yes_btn_label="Save", no_btn_label="Don't Save", parent=win,
        )
        print("ask (save):", r)

    def ask_yes_no() -> None:
        r = ask_question(
            "Continue", "Do you want to continue?",
            "Yes continues the operation.\nNo stops without changes.",
            no_btn_label="No", parent=win,
        )
        print("ask (yes/no):", r)

    def ask_two_buttons() -> None:
        r = ask_question(
            "Delete File", "Do you want to delete this file?",
            "This action cannot be undone.",
            yes_btn_label="Delete", parent=win,
        )
        print("ask (two buttons):", r)

    # --- Messages ---------------------------------------------------------
    def info() -> None:
        show_information(
            "Data Information", "The data file was loaded successfully.",
            "128 rows were read and validated.\nNo missing values were found.",
            parent=win,
        )

    def warning() -> None:
        show_warning(
            "Overwrite File", "A file with this name already exists.",
            "Saving now will replace the existing file.", parent=win,
        )

    def critical() -> None:
        show_critical(
            "Load Error", "The selected file could not be opened.",
            "Check that the file exists and that you can read it.", parent=win,
        )

    def rich_info() -> None:
        show_rich_information(
            "Notes",
            "<b>Rich information dialog</b><br><br>"
            "Useful for longer help text, with selectable text, a copy "
            "button, and links: "
            '<a href="https://doc.qt.io/qtforpython-6/">Qt for Python docs</a>',
            parent=win,
        )

    # --- About ------------------------------------------------------------
    about_html = (
        "A demo application for <b>sciwidgets</b>.<br><br>"
        "<b>Version:</b> 0.1.0<br>"
        '<b>Docs:</b> <a href="https://doc.qt.io/qtforpython-6/">Qt for Python</a>'
    )

    def about_default() -> None:
        # No app icon is set in this demo, so the information icon is used.
        show_about_dialog("About Demo", about_html, parent=win)

    def about_custom_icon() -> None:
        icon = win.style().standardIcon(QStyle.SP_ComputerIcon)
        show_about_dialog("About Demo", about_html, parent=win, icon=icon)

    # --- Layout -----------------------------------------------------------
    columns = [
        [("Ask: Save / Don't Save / Cancel", ask_save),
         ("Ask: Yes / No / Cancel", ask_yes_no),
         ("Ask: Delete / Cancel", ask_two_buttons)],
        [("Information", info),
         ("Warning", warning),
         ("Critical", critical),
         ("Rich information", rich_info)],
        [("About (default icon)", about_default),
         ("About (custom icon)", about_custom_icon)],
    ]

    row = QHBoxLayout(win)
    for buttons in columns:
        col = QVBoxLayout()
        for text, slot in buttons:
            btn = QPushButton(text)
            btn.clicked.connect(slot)
            col.addWidget(btn)
        col.addStretch(1)
        row.addLayout(col)

    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(_demo_main())