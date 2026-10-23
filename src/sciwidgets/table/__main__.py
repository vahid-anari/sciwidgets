"""Demo for the table package: ``python -m sciwidgets.table``."""

import sys

import numpy as np
import pandas as pd
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QFileDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)

from sciwidgets.formatting import pretty_sci_text
from sciwidgets.style import apply_sci_style, is_dark, set_color_scheme
from sciwidgets.table import DataFrameView


def make_frame(n: int = 200) -> pd.DataFrame:
    rng = np.random.default_rng(1)
    return pd.DataFrame({
        "Frequency (MHz)": np.sort(rng.uniform(1e3, 1e6, n)),
        "tau (s)": 10.0 ** rng.uniform(-3, 6, n),
        "U-S J": rng.integers(0, 12, n),
        "U-S E (cm^-1)": rng.uniform(0, 500, n),
        "L-S J": rng.integers(0, 12, n),
        "L-S E (cm^-1)": rng.uniform(0, 500, n),
        "Species": rng.choice(["OH", "CH3OH", "SiO"], n),
    })


def background(column: str):
    if column.startswith("U-S"):
        return "tan"
    if column.startswith("L-S"):
        return "lightskyblue"
    return None


def main() -> int:
    app = QApplication(sys.argv)
    apply_sci_style(app)

    view = DataFrameView()
    view.set_frame(
        make_frame(),
        formats={"Frequency (MHz)": "{:,.3f}", "tau (s)": lambda v: pretty_sci_text(v, 3),
                 "U-S E (cm^-1)": "{:.4f}", "L-S E (cm^-1)": "{:.4f}"},
        backgrounds=background,
        headers={"Frequency (MHz)": "Frequency\n(MHz)", "tau (s)": "&tau;<br>(s)",
                 "U-S E (cm^-1)": "U-S<br>Energy (cm<sup>-1</sup>)",
                 "L-S E (cm^-1)": "L-S<br>Energy (cm<sup>-1</sup>)"},
    )
    info = QLabel()

    def update_info():
        info.setText(f"{len(view.visible_columns())} of {len(view.model_().columns())} columns shown")

    def export():
        path, _ = QFileDialog.getSaveFileName(view, "Export CSV", "", "CSV Files (*.csv)")
        if path:
            view.export_csv(path)

    choose = QPushButton("Choose Columns…")
    choose.clicked.connect(view.choose_columns)
    save = QPushButton("Export CSV…")
    save.clicked.connect(export)
    view.configChanged.connect(lambda cfg: (update_info(), print("config:", cfg)))
    update_info()

    dark = QCheckBox("Dark theme", checked=is_dark())
    dark.toggled.connect(lambda on: set_color_scheme(app, "dark" if on else "light"))

    row = QHBoxLayout()
    row.addWidget(choose)
    row.addWidget(save)
    row.addWidget(dark)
    row.addStretch()
    row.addWidget(info)
    win = QWidget()
    win.setWindowTitle("sciwidgets.table demo — right-click a column header")
    layout = QVBoxLayout(win)
    layout.addLayout(row)
    layout.addWidget(view)
    win.resize(900, 500)
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
