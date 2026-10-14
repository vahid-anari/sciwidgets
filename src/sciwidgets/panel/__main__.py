"""Demo for the panel package: ``python -m sciwidgets.panel``."""

import json
import sys

from PySide6.QtWidgets import QApplication, QPlainTextEdit, QVBoxLayout, QWidget

from sciwidgets.panel import widget_from_spec
from sciwidgets.style import apply_sci_style

# Plain JSON, as it would come from a settings file
SPECS = json.loads(r"""
[
  {"type": "float-slider", "path": "t0", "label": "t_0", "unit": "\\mathrm{s}",
   "min_val": 0, "max_val": 10, "init_val": 2.5, "val_fmt": "{:.2f}"},
  {"type": "int-slider", "path": "nz", "label": "N_z", "min_val": 10, "max_val": 5000,
   "init_val": 400, "features": ["defaults", "config"]},
  {"type": "range-slider", "path": "window", "label": "t", "min_val": 0, "max_val": 100,
   "init_vals": [10, 60], "val_fmt": "{:.1f}"},
  {"type": "line-edit", "path": "nu", "label": "\\nu", "unit_label": "\\mathrm{MHz}",
   "init_val": 6668.519, "min_limit": 0, "min_limit_inclusive": false},
  {"type": "combo-box", "path": "solver", "label": "\\mathrm{solver}", "items": ["RK4", "Euler"]},
  {"type": "toggle", "path": "norm", "text": "Normalize", "checked": true}
]
""")


def _demo_main() -> int:
    """Build the widgets above from their descriptions and log value changes.

    Returns:
        int: Qt application exit code.
    """
    app = QApplication(sys.argv)
    apply_sci_style(app)

    win = QWidget()
    win.setWindowTitle("widget_from_spec demo")
    col = QVBoxLayout(win)
    log = QPlainTextEdit(readOnly=True, maximumHeight=120)

    for spec in SPECS:
        w = widget_from_spec(spec)
        w.valueChanged.connect(lambda v, p=spec["path"]: log.appendPlainText(f"{p} = {v!r}"))
        col.addWidget(w)
    col.addWidget(log)

    win.adjustSize()
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(_demo_main())
