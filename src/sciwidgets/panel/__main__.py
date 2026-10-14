"""Demo for the panel package: ``python -m sciwidgets.panel``."""

import json
import sys

from PySide6.QtWidgets import QApplication, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget

from sciwidgets.panel import ParameterPage
from sciwidgets.style import apply_sci_style

# Plain JSON, as it would come from a settings file
LAYOUT = json.loads(r"""
{"column": [
  {"row": [
    {"group": "Time grid", "stretch": 1, "column": [
      {"type": "float-slider", "path": "grid.t_max", "label": "t_\\mathrm{max}", "unit": "\\mathrm{d}",
       "min_val": 1, "max_val": 1000, "init_val": 200, "val_fmt": "{:.1f}"},
      {"type": "int-slider", "path": "grid.nt", "label": "N_t",
       "min_val": 100, "max_val": 100000, "init_val": 4000}]},
    {"group": "Spatial grid", "stretch": 1, "column": [
      {"type": "int-slider", "path": "grid.nz", "label": "N_z",
       "min_val": 10, "max_val": 5000, "init_val": 400},
      {"type": "float-slider", "path": "grid.length", "label": "L", "unit": "\\mathrm{m}",
       "min_val": 0.1, "max_val": 10, "init_val": 1, "val_fmt": "{:.2f}"}]}]},
  {"group": "Sample", "column": [
    {"type": "line-edit", "path": "sample.nu", "label": "\\nu", "unit_label": "\\mathrm{MHz}",
     "init_val": 6668.519, "min_limit": 0, "min_limit_inclusive": false},
    {"type": "combo-box", "path": "sample.species", "label": "\\mathrm{species}",
     "items": ["CH3OH", "H2O", "OH"]},
    {"type": "range-slider", "path": "display.window", "label": "t_\\mathrm{window}",
     "min_val": 0, "max_val": 100, "init_vals": [10, 60], "val_fmt": "{:.1f}"}]},
  {"row": [
    {"type": "toggle", "path": "solve.normalize", "text": "Normalize", "checked": true},
    {"stretch": 1}]}
]}
""")


def _demo_main() -> int:
    """Show a page built from the description above and log its signals.

    Returns:
        int: Qt application exit code.
    """
    app = QApplication(sys.argv)
    apply_sci_style(app)

    win = QWidget()
    win.setWindowTitle("ParameterPage demo")
    col = QVBoxLayout(win)

    page = ParameterPage(LAYOUT)
    log = QPlainTextEdit(readOnly=True, maximumHeight=110)
    page.valueChanged.connect(lambda p, v: log.appendPlainText(f"valueChanged  {p} = {v!r}"))
    page.configChanged.connect(lambda p, c: log.appendPlainText(f"configChanged {p} = {c!r}"))

    dump = QPushButton("Print get_value() and get_config()")
    dump.clicked.connect(lambda: log.appendPlainText(
        f"values: {page.get_value()}\nconfig: {page.get_config()}"))

    col.addWidget(page, 1)
    col.addWidget(dump)
    col.addWidget(log)

    win.resize(820, 560)
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(_demo_main())
