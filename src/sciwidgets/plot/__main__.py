"""Demo for the plot package: ``python -m sciwidgets.plot``."""

import json
import sys

import numpy as np
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from sciwidgets.plot import CurveCheckBox, CurveSelector, PlotCanvas
from sciwidgets.style import apply_sci_style

# Plain JSON, as it would come from a settings file
DESCRIPTION = json.loads(r"""
{
  "figure": {"figsize": [10, 6], "facecolor": "floralwhite",
             "margins": {"left": 0.08, "right": 0.92, "bottom": 0.1, "top": 0.96}},
  "layout": {"mosaic": [["flux", "flux"], ["profiles", "spectrum"]],
             "height_ratios": [3, 2], "width_ratios": [2, 1], "hspace": 0.12, "wspace": 0.4,
             "sharex": ["flux", "profiles"]},
  "styles": {
    "data": {"linestyle": "", "marker": "o", "markersize": 3, "color": "k"},
    "model": {"linewidth": 1.25}
  },
  "markers": {
    "window": {"kind": "vspan", "panels": ["flux", "profiles"], "at": [30, 50],
               "props": {"color": "b", "alpha": 0.1}},
    "center": {"kind": "vline", "panels": ["flux", "profiles"], "at": 40,
               "props": {"color": "r", "linewidth": 0.75, "alpha": 0.6}}
  },
  "panels": {
    "flux": {
      "primary": "flux",
      "legend": {"loc": "upper right"},
      "curves": {
        "data": {"label": "data", "legend": "data", "style": "data"},
        "flux": {"label": "F", "name": "F", "unit": "Jy", "style": "model", "props": {"color": "b"}},
        "fit": {"label": "F_\\mathrm{fit}", "name": "F fit", "style": "model", "props": {"color": "r", "linestyle": "--"}}
      }
    },
    "profiles": {
      "x": {"label": "t", "unit": "d"},
      "select": "one",
      "curves": {
        "lambda": {"label": "\\Lambda_n", "name": "Λₙ", "unit": "\\Lambda_0", "style": "model", "props": {"color": "c"}},
        "t1": {"label": "T_1", "name": "T₁", "unit": "T_0", "style": "model", "props": {"color": "forestgreen"}}
      },
      "twin": {
        "primary": "w",
        "grid": {"linestyle": ":"},
        "curves": {"w": {"label": "w", "style": "model", "props": {"color": "m"}}}
      }
    },
    "spectrum": {
      "x": {"label": "v", "unit": "km\\,s^{-1}"},
      "y": {"label": "S", "unit": "Jy"},
      "legend": {"loc": "upper left", "fontsize": 8},
      "curves": {
        "s1": {"label": "S_1", "name": "S₁", "style": "model"},
        "s2": {"label": "S_2", "name": "S₂", "style": "model", "props": {"linestyle": "--"}}
      }
    }
  }
}
""")


def _demo_main() -> int:
    """Show the canvas with made-up data and a few controls.

    Returns:
        int: Qt application exit code.
    """
    app = QApplication(sys.argv)
    apply_sci_style(app)

    canvas = PlotCanvas(DESCRIPTION)

    t = np.linspace(0, 100, 600)
    flux = 2 + 1.5 * np.exp(-((t - 40) / 6) ** 2)
    rng = np.random.default_rng(1)
    canvas.set_curve_data("data", t[::12], flux[::12] + rng.normal(0, 0.08, t[::12].size))
    canvas.set_curve_data("flux", t, flux)
    canvas.set_curve_data("fit", t, flux * 0.97)
    canvas.set_curve_data("lambda", t, 1e-3 * (1 + np.sin(t / 8)))
    canvas.set_curve_data("t1", t, 45 + 5 * np.cos(t / 15))
    canvas.set_curve_data("w", t, 0.5 * np.tanh((t - 50) / 10))
    v = np.linspace(-10, 10, 300)
    canvas.set_curve_data("s1", v, np.exp(-v ** 2 / 4))
    canvas.set_curve_data("s2", v, 0.6 * np.exp(-(v - 2) ** 2 / 2))
    for axis_id in ("flux", "profiles", "profiles.twin", "spectrum"):
        canvas.axes(axis_id).relim(visible_only=True)
        canvas.axes(axis_id).autoscale_view()

    profile = CurveSelector(canvas, "profiles", none_text="none")

    def rescale_profile(_curve_id) -> None:
        canvas.axes("profiles").relim(visible_only=True)
        canvas.axes("profiles").autoscale_view(scalex=False)
        canvas.redraw()
    profile.curveSelected.connect(rescale_profile)

    show_w = CurveCheckBox(canvas, "w", axis="profiles.twin")

    show_fit = QCheckBox("Show fit", checked=True)
    show_fit.toggled.connect(lambda on: (canvas.set_curve_visible("fit", on), canvas.redraw()))

    grid = QCheckBox("Grid")
    def toggle_grid(on: bool) -> None:
        for axis_id in ("flux", "profiles", "profiles.twin", "spectrum"):
            canvas.set_grid(axis_id, on)
        canvas.set_grid("flux", on, direction="x")
        canvas.redraw()
    grid.toggled.connect(toggle_grid)

    show_window = QCheckBox("Window", checked=True)
    show_window.toggled.connect(lambda on: ([canvas.set_marker_visible(m, on) for m in ("window", "center")],
                                            canvas.redraw()))

    def move_window(event) -> None:
        """Click on the top panel to move the window there."""
        if event.button == 1 and event.inaxes is canvas.axes("flux") and event.xdata is not None:
            canvas.set_marker("center", event.xdata)
            canvas.set_marker("window", (event.xdata - 10, event.xdata + 10))
            canvas.redraw()
    canvas.mpl_connect("button_press_event", move_window)

    legend = QCheckBox("Legends", checked=True)
    legend.toggled.connect(lambda on: ([canvas.set_legend_visible(p, on) for p in ("flux", "spectrum")],
                                       canvas.redraw()))

    controls = QHBoxLayout()
    controls.addWidget(QLabel("Bottom plot:"))
    for w in (profile, show_w, show_fit, grid, legend, show_window):
        controls.addWidget(w)
    controls.addStretch(1)
    controls.addWidget(QLabel("Left-click the top panel: move the window · Right-click any panel: styles"))

    # User changes made through the right-click menu, saved and restored as plain data
    log = QPlainTextEdit(readOnly=True, maximumHeight=70)
    canvas.configChanged.connect(lambda cfg: log.setPlainText(f"configChanged: {cfg}"))
    saved = {}
    save = QPushButton("Save config")
    save.clicked.connect(lambda: (saved.update(cfg=canvas.get_config()), log.setPlainText(f"saved: {saved['cfg']}")))
    restore = QPushButton("Restore saved")
    restore.clicked.connect(lambda: (canvas.set_config(saved.get("cfg", {})), canvas.redraw()))
    export = QPushButton("Export…")

    def do_export() -> None:
        path, _ = QFileDialog.getSaveFileName(win, "Export plot", "plot.pdf",
                                              "PDF (*.pdf);;PNG (*.png);;SVG (*.svg)")
        if path:
            canvas.export(path)
    export.clicked.connect(do_export)
    reset = QPushButton("Reset all")
    reset.clicked.connect(lambda: (canvas.reset_config(), canvas.redraw()))
    config_row = QHBoxLayout()
    for b in (save, restore, reset, export):
        config_row.addWidget(b)
    config_row.addWidget(log, 1)

    win = QWidget()
    win.setWindowTitle("PlotCanvas demo")
    col = QVBoxLayout(win)
    col.addWidget(canvas, 1)
    col.addLayout(controls)
    col.addLayout(config_row)
    win.resize(1000, 720)
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(_demo_main())
