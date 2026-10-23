"""Demo for the labels subpackage: ``python -m sciwidgets.labels``."""

from PySide6.QtCore import Qt

from sciwidgets.labels import math_label
from sciwidgets.labels.math_label import MathLabel


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

    status = "on" if math_label._latex_enabled else "off (mathtext fallback)"
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
        row.addWidget(lbl)
    stretched = MathLabel(r"\omega_0", font_size=14, keep_aspect_ratio=False, parent=box)
    stretched.setMinimumSize(90, 50)
    stretched.setAutoFillBackground(True)
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

    win.adjustSize()
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(_demo_main())