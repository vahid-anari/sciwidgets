"""Showcase of sciwidgets: ``python -m sciwidgets``.

One small app built from the pieces together: a parameter panel described in
JSON, a plot canvas that follows the sliders, a DataFrame table, menus, a
status bar, an About dialog, and light and dark mode. Each subpackage also has
a demo of its own (``python -m sciwidgets.plot`` and so on).
"""

from __future__ import annotations

import json
import sys
from importlib.metadata import PackageNotFoundError, version

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from sciwidgets.dialogs import show_about_dialog
from sciwidgets.panel import ParameterTabs
from sciwidgets.plot import CurveSelector, PlotCanvas
from sciwidgets.style import apply_sci_style, is_dark, set_color_scheme
from sciwidgets.window import MenuBarController, StatusBarController

PANEL = json.loads(r"""
{"tabs": [
  {"id": "pulse", "title": "Pulse", "layout": {"column": [
    {"group": "Model:  F = b + a sech²((t − t₀)/w)", "column": [
      {"type": "float-slider", "path": "pulse.a", "label": "a", "unit": "\\mathrm{Jy}",
       "min_val": 0, "max_val": 5, "init_val": 1.0, "val_fmt": "{:.2f}"},
      {"type": "float-slider", "path": "pulse.t0", "label": "t_0", "unit": "\\mathrm{d}",
       "min_val": 0, "max_val": 100, "init_val": 35, "val_fmt": "{:.1f}"},
      {"type": "float-slider", "path": "pulse.w", "label": "w", "unit": "\\mathrm{d}",
       "min_val": 0.5, "max_val": 30, "init_val": 10, "val_fmt": "{:.2f}"},
      {"type": "line-edit", "path": "pulse.b", "label": "b", "unit": "\\mathrm{Jy}", "init_val": 2.0,
       "val_fmt": "{:.3g}"}]},
    {"group": "Display", "column": [
      {"type": "combo-box", "path": "display.unit", "label": "\\mathrm{unit}", "items": ["Jy", "mJy"]},
      {"row": [
        {"type": "toggle", "path": "display.data", "text": "Show the data", "checked": true},
        {"stretch": 1}]}]}]}},
  {"id": "window", "title": "Window", "layout": {"column": [
    {"group": "Ranges", "defaults": {"min_val": 0, "max_val": 100, "val_fmt": "{:.1f}", "use_margins": false},
     "column": [
      {"type": "range-slider", "path": "display.window", "label": "\\mathrm{window}", "unit": "\\mathrm{d}",
       "init_vals": [25, 50]},
      {"type": "range-slider", "path": "display.time", "label": "t", "unit": "\\mathrm{d}",
       "init_vals": [0, 100]}]}]}}
]}
""")

PLOT = json.loads(r"""
{
  "figure": {"facecolor": "floralwhite", "dark_facecolor": "#2b2a27",
             "margins": {"left": 0.11, "right": 0.97, "bottom": 0.1, "top": 0.97}},
  "layout": {"mosaic": [["signal"], ["lower"]], "height_ratios": [3, 2], "hspace": 0.08, "sharex": true},
  "markers": {
    "window": {"kind": "vspan", "at": [25, 50], "name": "Window", "props": {"color": "b", "alpha": 0.1}},
    "peak": {"kind": "vline", "at": 35, "props": {"color": "r", "linewidth": 0.75, "alpha": 0.6}}
  },
  "panels": {
    "signal": {
      "primary": "model", "legend": {"loc": "upper right"},
      "curves": {
        "data": {"label": "data", "legend": "data", "name": "Data",
                 "props": {"linestyle": "", "marker": "o", "markersize": 3, "color": "k"}},
        "model": {"label": "F", "unit": "Jy", "name": "Model", "props": {"color": "b", "linewidth": 1.5}}
      }
    },
    "lower": {
      "x": {"label": "t", "unit": "d"},
      "select": "one",
      "curves": {
        "residual": {"label": "F_\\mathrm{data} - F", "unit": "Jy", "name": "Residual",
                     "props": {"linestyle": "", "marker": "o", "markersize": 3, "color": "darkviolet"}},
        "integral": {"label": "\\int (F - b)\\, dt", "unit": "Jy\\,d", "name": "Integral",
                     "props": {"color": "darkgreen", "linewidth": 1.5}}
      }
    }
  }
}
""")

MENUS = {
    "File": [
        {"id": "reset", "text": "Reset Parameters"},
        {"id": "sep"},
        {"id": "quit", "text": "Quit", "shortcut": QKeySequence.Quit},
    ],
    "View": [
        {"id": "dark", "text": "Dark Theme", "checkable": True, "shortcut": "Ctrl+D"},
    ],
    "Help": [
        {"id": "about", "text": "About sciwidgets"},
    ],
}

TRUE = {"a": 1.6, "t0": 46.0, "w": 7.0, "b": 2.0}
"""The pulse the made-up data were drawn from; move the sliders to find it."""


def _pulse(t: np.ndarray, a: float, t0: float, w: float, b: float) -> np.ndarray:
    return b + a / np.cosh((t - t0) / w) ** 2


def _line_list():
    """The table demo's line list, or ``None`` without pandas."""
    try:
        from sciwidgets.table.__main__ import background, make_frame
    except ImportError:
        return None
    return make_frame(60), background


class Showcase(QMainWindow):
    """The showcase window."""

    def __init__(self, app: QApplication) -> None:
        super().__init__()
        self._app = app
        self.setWindowTitle("sciwidgets showcase")
        self.t = np.linspace(0, 100, 800)
        rng = np.random.default_rng(3)
        self.t_data = np.linspace(0, 100, 70)
        self.f_data = _pulse(self.t_data, **TRUE) + rng.normal(0, 0.06, self.t_data.size)

        self.panel = ParameterTabs(PANEL)
        self.canvas = PlotCanvas(PLOT)
        self.canvas.setMinimumSize(560, 420)
        lower = CurveSelector(self.canvas, "lower", none_text=None)
        lower.curveSelected.connect(lambda _: self.update_plot())

        plot_box = QWidget()
        plot_col = QVBoxLayout(plot_box)
        plot_col.setContentsMargins(0, 0, 0, 0)
        row = QHBoxLayout()
        row.addWidget(QLabel("Lower panel:"))
        row.addWidget(lower)
        row.addStretch(1)
        row.addWidget(QLabel("Right-click the plot for styles · right-click a slider for its menu"))
        plot_col.addLayout(row)
        plot_col.addWidget(self.canvas, 1)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.panel)
        splitter.addWidget(plot_box)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([430, 770])

        tabs = QTabWidget()
        tabs.addTab(splitter, "Model")
        table = _line_list()
        if table is not None:
            from sciwidgets.table import DataFrameView
            frame, background = table
            view = DataFrameView()
            view.set_frame(
                frame,
                formats={"Frequency (MHz)": "{:,.3f}", "U-S E (cm^-1)": "{:.4f}", "L-S E (cm^-1)": "{:.4f}",
                         "tau (s)": lambda v: _sci(v)},
                backgrounds=background,
                headers={"Frequency (MHz)": "Frequency\n(MHz)", "tau (s)": "&tau;<br>(s)",
                         "U-S E (cm^-1)": "U-S<br>Energy (cm<sup>-1</sup>)",
                         "L-S E (cm^-1)": "L-S<br>Energy (cm<sup>-1</sup>)"},
            )
            tabs.addTab(view, "Line list")
        else:
            tabs.addTab(QLabel("The table needs pandas: pip install \"sciwidgets[table]\"",
                               alignment=Qt.AlignCenter), "Line list")
        self.setCentralWidget(tabs)

        self.menus = MenuBarController(self, MENUS, native_menubar=False)
        self.menus.set_checked("dark", is_dark())
        self.menus.actionTriggered.connect(self.on_menu)
        self.status = StatusBarController(self, show_path=False, show_memory=False, show_time=False)
        self.chi2 = QLabel()
        self.statusBar().addPermanentWidget(self.chi2)

        self.defaults = self.panel.get_value()
        self.panel.valueChanged.connect(lambda *_: self.update_plot())
        self.update_plot()
        self.resize(1240, 720)

    def update_plot(self) -> None:
        """Draw the model, data, lower panel and markers from the panel's values."""
        v = self.panel.get_value()
        p = {k: float(v[f"pulse.{k}"]) for k in ("a", "t0", "w", "b")}
        scale, unit = (1000.0, "mJy") if v["display.unit"] == "mJy" else (1.0, "Jy")
        c = self.canvas
        model = _pulse(self.t, **p)
        at_data = _pulse(self.t_data, **p)
        c.set_curve_data("model", self.t, scale * model)
        c.set_curve_data("data", self.t_data, scale * self.f_data)
        c.set_curve_visible("data", bool(v["display.data"]))
        c.set_curve_data("residual", self.t_data, scale * (self.f_data - at_data))
        dt = self.t[1] - self.t[0]
        c.set_curve_data("integral", self.t, scale * np.cumsum(model - p["b"]) * dt)
        c.set_label("signal", "y", "F", unit)
        c.set_marker("window", tuple(v["display.window"]["range"]))
        c.set_marker("peak", p["t0"])
        c.set_limits("signal", x=tuple(v["display.time"]["range"]))
        for axis_id in ("signal", "lower"):
            ax = c.axes(axis_id)
            ax.relim(visible_only=True)
            ax.autoscale_view(scalex=False)
        c.redraw()
        chi2 = np.mean((self.f_data - at_data) ** 2) / 0.06 ** 2
        self.chi2.setText(f"χ²/N = {chi2:.2f}  ")

    def on_menu(self, _menu: str, action_id: str, checked: bool) -> None:
        if action_id == "dark":
            set_color_scheme(self._app, "dark" if checked else "light")
        elif action_id == "reset":
            self.panel.set_value(self.defaults)
            self.update_plot()
        elif action_id == "about":
            try:
                ver = version("sciwidgets")
            except PackageNotFoundError:
                ver = "(not installed)"
            show_about_dialog(
                "About sciwidgets",
                "PySide6 widgets for scientific desktop apps.<br><br>"
                f"<b>Version:</b> {ver}<br>"
                '<b>Source:</b> <a href="https://github.com/vahid-anari/sciwidgets">github.com/vahid-anari/sciwidgets</a>',
                parent=self,
            )
        elif action_id == "quit":
            self.close()


def _sci(value: float) -> str:
    from sciwidgets.formatting import pretty_sci_text
    return pretty_sci_text(value, 3)


def main() -> int:
    """Run the showcase.

    Returns:
        int: Qt application exit code.
    """
    app = QApplication(sys.argv)
    apply_sci_style(app)
    win = Showcase(app)
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
