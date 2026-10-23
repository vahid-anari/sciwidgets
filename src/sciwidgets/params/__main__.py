"""Demo for the params subpackage: ``python -m sciwidgets.params``."""

import sys

from PySide6.QtWidgets import (
    QApplication, QCheckBox, QFormLayout, QFrame, QLabel, QVBoxLayout, QWidget,
)

from sciwidgets.params.combo_box import ParameterComboBox
from sciwidgets.params.line_edit import ParameterLineEdit
from sciwidgets.params.numeric_line_edit import NumericLineEdit
from sciwidgets.params.toggle import ParameterToggle
from sciwidgets.style import apply_sci_style, is_dark, set_color_scheme


def _demo_main() -> int:
    """Run the params demo window.

    Returns:
        int: Qt application exit code.
    """
    app = QApplication(sys.argv)
    apply_sci_style(app)

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
    # --- Simple parameter widgets ----------------------------------------
    t_edit = ParameterLineEdit(
        label="t", init_val=5, val_fmt="{:0.1f}", unit=r"\mathrm{s}",
        min_limit=0.0, min_limit_inclusive=False, parent=win,
    )
    n_edit = ParameterLineEdit(label=r"A_\alpha", init_val=5, value_is_int=True, parent=win)
    unit = ParameterComboBox(
        label="t", items=["T₀", "d", "h", "m", "S", "ms", "µs", "ns"], parent=win,
    )
    unit.set_value("ns")
    toggle = ParameterToggle(
        text="Normalize to max",
        label_on=r"F = I_\mathrm{res} / \max(I_\mathrm{res}) \times I_\mathrm{scale}",
        label_off=r"F = I_\mathrm{res} \times I_\mathrm{scale}",
        parent=win,
    )
    plain = ParameterToggle(text="Plain checkbox (no labels)", checked=False, parent=win)

    # Align the name column the way a panel would
    widgets = [t_edit, n_edit, unit, toggle, plain]
    name_w = max(w.get_name_width() for w in widgets)
    for w in widgets:
        w.set_name_width(name_w)
        w.valueChanged.connect(lambda v, w=w: print(type(w).__name__, v))
        layout.addWidget(w)

    layout.addStretch(1)

    line = QFrame()
    line.setFrameShape(QFrame.HLine)
    line.setFrameShadow(QFrame.Sunken)
    layout.addWidget(line)
    dark = QCheckBox("Dark theme")
    dark.setChecked(is_dark())
    dark.toggled.connect(lambda on: set_color_scheme(app, "dark" if on else "light"))
    layout.addWidget(dark)

    win.adjustSize()
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(_demo_main())
