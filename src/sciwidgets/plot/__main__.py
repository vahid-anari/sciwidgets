"""Demo for the plot package: ``python -m sciwidgets.plot``."""

import json
import sys

import numpy as np
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from sciwidgets.plot import PlotCanvas
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
  "panels": {
    "flux": {
      "primary": "flux",
      "legend": {"loc": "upper right"},
      "curves": {
        "data": {"label": "data", "legend": "data", "style": "data"},
        "flux": {"label": "F", "unit": "Jy", "style": "model", "props": {"color": "b"}},
        "fit": {"label": "F_\\mathrm{fit}", "style": "model", "props": {"color": "r", "linestyle": "--"}}
      }
    },
    "profiles": {
      "x": {"label": "t", "unit": "d"},
      "select": "one",
      "curves": {
        "lambda": {"label": "\\Lambda_n", "unit": "\\Lambda_0", "style": "model", "props": {"color": "c"}},
        "t1": {"label": "T_1", "unit": "T_0", "style": "model", "props": {"color": "forestgreen"}}
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
        "s1": {"label": "S_1", "style": "model"},
        "s2": {"label": "S_2", "style": "model", "props": {"linestyle": "--"}}
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

    profile = QComboBox()
    profile.addItem("Λₙ", "lambda")
    profile.addItem("T₁", "t1")
    profile.addItem("none", None)
    def on_profile() -> None:
        canvas.select_curve("profiles", profile.currentData())
        canvas.axes("profiles").relim(visible_only=True)
        canvas.axes("profiles").autoscale_view(scalex=False)
        canvas.redraw()
    profile.currentIndexChanged.connect(on_profile)

    show_w = QCheckBox("Show w", checked=True)
    show_w.toggled.connect(lambda on: (canvas.set_axis_visible("profiles.twin", on), canvas.redraw()))

    show_fit = QCheckBox("Show fit", checked=True)
    show_fit.toggled.connect(lambda on: (canvas.set_curve_visible("fit", on), canvas.redraw()))

    grid = QCheckBox("Grid")
    def toggle_grid(on: bool) -> None:
        for axis_id in ("flux", "profiles", "profiles.twin", "spectrum"):
            canvas.set_grid(axis_id, on)
        canvas.set_grid("flux", on, direction="x")
        canvas.redraw()
    grid.toggled.connect(toggle_grid)

    legend = QCheckBox("Legends", checked=True)
    legend.toggled.connect(lambda on: ([canvas.set_legend_visible(p, on) for p in ("flux", "spectrum")],
                                       canvas.redraw()))

    controls = QHBoxLayout()
    controls.addWidget(QLabel("Bottom plot:"))
    for w in (profile, show_w, show_fit, grid, legend):
        controls.addWidget(w)
    controls.addStretch(1)

    win = QWidget()
    win.setWindowTitle("PlotCanvas demo")
    col = QVBoxLayout(win)
    col.addWidget(canvas, 1)
    col.addLayout(controls)
    win.resize(1000, 650)
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(_demo_main())
