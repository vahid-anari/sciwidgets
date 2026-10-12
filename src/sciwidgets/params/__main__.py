"""Demo for the params subpackage: ``python -m sciwidgets.params``."""

import sys

from PySide6.QtWidgets import (
    QApplication, QFormLayout, QLabel, QVBoxLayout, QWidget,
)

from sciwidgets.params.numeric_line_edit import NumericLineEdit
from sciwidgets.style import SciStyle, widget_style_sheet


def _demo_main() -> int:
    """Run the params demo window.

    Returns:
        int: Qt application exit code.
    """
    app = QApplication(sys.argv)
    app.setStyle(SciStyle())
    app.setStyleSheet(widget_style_sheet(app))

    win = QWidget()
    win.setWindowTitle("Params demo")
    layout = QVBoxLayout(win)

    # --- NumericLineEdit ------------------------------------------------
    f_edit = NumericLineEdit(
        init_val=1.0, val_fmt="{:0.3g}", min_limit=-100.0,
        width_chars=11, max_length=10,
    )
    i_edit = NumericLineEdit(
        init_val=1, value_is_int=True, min_limit=-100, max_limit=100,
        width_chars=10, max_length=9,
    )
    committed = QLabel("")
    f_edit.valueChanged.connect(lambda v: committed.setText(f"float: {v}"))
    i_edit.valueChanged.connect(lambda v: committed.setText(f"int: {v}"))

    form = QFormLayout()
    form.addRow("Integer [-100, 100]:", i_edit)
    form.addRow("Float [-100, ∞):", f_edit)
    form.addRow("Last committed:", committed)
    layout.addLayout(form)
    layout.addStretch(1)

    win.resize(340, 160)
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(_demo_main())