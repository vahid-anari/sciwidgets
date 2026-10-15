"""Demo for the panel package: ``python -m sciwidgets.panel``."""

import json
import sys

from PySide6.QtWidgets import QApplication, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget

from sciwidgets.panel import ParameterTabs
from sciwidgets.style import apply_sci_style

# Plain JSON, as it would come from a settings file
DESCRIPTION = json.loads(r"""
{"tabs": [
  {"id": "grid", "title": "Grid", "layout": {"row": [
    {"group": "Time grid", "stretch": 1, "column": [
      {"type": "float-slider", "path": "grid.t_max", "label": "t_\\mathrm{max}", "unit": "\\mathrm{d}",
       "min_val": 1, "max_val": 1000, "init_val": 200, "val_fmt": "{:.1f}"},
      {"type": "int-slider", "path": "grid.nt", "label": "N_t",
       "min_val": 100, "max_val": 100000, "init_val": 4000}]},
    {"group": "Spatial grid", "stretch": 1, "column": [
      {"type": "int-slider", "path": "grid.nz", "label": "N_z",
       "min_val": 10, "max_val": 5000, "init_val": 400},
      {"type": "float-slider", "path": "grid.length", "label": "L", "unit": "\\mathrm{m}",
       "min_val": 0.1, "max_val": 10, "init_val": 1, "val_fmt": "{:.2f}"}]}]}},
  {"id": "sample", "title": "Sample", "layout": {"column": [
    {"group": "Sample", "column": [
      {"type": "line-edit", "path": "sample.nu", "label": "\\nu", "unit": "\\mathrm{MHz}",
       "init_val": 6668.519, "min_limit": 0, "min_limit_inclusive": false},
      {"type": "combo-box", "path": "sample.species", "label": "\\mathrm{species}",
       "items": ["CH3OH", "H2O", "OH"]}]},
    {"row": [
      {"type": "toggle", "path": "solve.normalize", "text": "Normalize", "checked": true},
      {"stretch": 1}]}]}},
  {"id": "display", "title": "Display", "layout": {"column": [
    {"group": "Windows (one template, defaults for the group)", "defaults": {"show_range": false},
     "column": [
      {"template": "window", "path": "display.t", "label": "t"},
      {"template": "window", "path": "display.f", "label": "F", "unit": "\\mathrm{Jy}",
       "max_val": 50, "init_vals": [0, 25]}]}]}}
],
"templates": {
  "window": {"type": "range-slider", "min_val": 0, "max_val": 100, "init_vals": [10, 60],
             "val_fmt": "{:.1f}"}
}}
""")


def _demo_main() -> int:
    """Show tabs built from the description above and log their signals.

    Returns:
        int: Qt application exit code.
    """
    app = QApplication(sys.argv)
    apply_sci_style(app)

    win = QWidget()
    win.setWindowTitle("ParameterTabs demo")
    col = QVBoxLayout(win)

    tabs = ParameterTabs(DESCRIPTION)
    log = QPlainTextEdit(readOnly=True, maximumHeight=110)
    tabs.valueChanged.connect(lambda p, v: log.appendPlainText(f"valueChanged  {p} = {v!r}"))
    tabs.configChanged.connect(lambda p, c: log.appendPlainText(f"configChanged {p} = {c!r}"))

    dump = QPushButton("Print get_value() and get_config()")
    dump.clicked.connect(lambda: log.appendPlainText(
        f"values: {tabs.get_value()}\nconfig: {tabs.get_config()}"))

    col.addWidget(tabs, 1)
    col.addWidget(dump)
    col.addWidget(log)

    win.resize(820, 560)
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(_demo_main())
