"""Demo for the sliders: ``python -m sciwidgets.params.sliders``."""

import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from sciwidgets.params.sliders.base import SliderFeature
from sciwidgets.params.sliders.single import ArraySlider, FloatSlider, IntSlider
from sciwidgets.style import apply_sci_style


def _demo_main() -> int:
    """Run a demo of the single-value sliders.

    Returns:
        int: Qt application exit code.
    """
    app = QApplication(sys.argv)
    apply_sci_style(app)

    win = QWidget()
    win.setWindowTitle("Sliders demo — right-click a slider for its menu")
    root = QVBoxLayout(win)

    # --- Signal log -----------------------------------------------------
    log = QPlainTextEdit()
    log.setReadOnly(True)
    log.setMaximumHeight(140)

    def watch(name: str, slider) -> None:
        """Log the user-action signals of a slider."""
        slider.valueChanged.connect(lambda v: log.appendPlainText(f"{name}: value → {v}"))
        slider.defaultChanged.connect(lambda d: log.appendPlainText(f"{name}: default → {d}"))
        slider.configChanged.connect(lambda c: log.appendPlainText(f"{name}: config → {c}"))

    # --- Horizontal sliders -----------------------------------------------
    t2 = FloatSlider(  # starts at +inf: "no dephasing"
        label="T_2", unit=r"\mathrm{ms}", min_val=0.1, max_val=10.0,
        init_val="+inf", val_fmt="{:.2f}", min_limit=0.0, min_limit_inclusive=False,
    )
    h_items = [
        ("N_z", IntSlider(  # integer, all menu features
            label="N_z", min_val=10, max_val=1000, init_val=200, min_limit=1,
        )),
        ("T_1", FloatSlider(  # float with a strict lower limit
            label="T_1", unit=r"\mathrm{ms}", min_val=0.1, max_val=10.0, init_val=1.0,
            val_fmt="{:.2f}", min_limit=0.0, min_limit_inclusive=False,
            features=SliderFeature.DEFAULTS | SliderFeature.SET_VALUE | SliderFeature.CONFIG,
        )),
        ("T_2", t2),
        ("gamma", FloatSlider(  # custom scientific format
            label=r"\gamma", unit=r"\mathrm{s^{-1}}", min_val=1e-3, max_val=1e-1,
            init_val=1e-2, val_fmt="{:.2S}", min_limit=0.0, min_limit_inclusive=False,
        )),
        ("Delta_omega", FloatSlider(  # signed values, no ±inf
            label=r"\Delta\omega", unit=r"\mathrm{MHz}", min_val=-5.0, max_val=5.0,
            init_val=0.0, val_fmt="{:+.2f}",
            features=SliderFeature.DEFAULTS | SliderFeature.SET_VALUE | SliderFeature.CONFIG,
        )),
        ("z", ArraySlider(  # picks from a grid of positions
            label="z", unit=r"\mathrm{m}", arr_length=51, min_val=0.0, max_val=1.0,
            init_index=25, val_fmt="{:.2f}",
            features=SliderFeature.DEFAULTS | SliderFeature.CONFIG,
        )),
        ("seed", IntSlider(  # no menu at all
            label=r"\mathrm{seed}", min_val=0, max_val=99, init_val=42,
            features=SliderFeature.NONE,
        )),
    ]

    h_box = QGroupBox("Horizontal")
    h_col = QVBoxLayout(h_box)
    for name, s in h_items:
        h_col.addWidget(s)
        watch(name, s)
    h_col.addStretch(1)

    def realign(_w: int = 0) -> None:
        """Align the name and value columns of the horizontal sliders."""
        sliders = [s for _, s in h_items]
        name_w = max(s.get_name_width() for s in sliders)
        value_w = max(s.get_value_width() for s in sliders)
        for s in sliders:
            s.set_name_width(name_w)
            s.set_value_width(value_w)

    for _, s in h_items:
        s.nameWidthChanged.connect(realign)
        s.valueWidthChanged.connect(realign)
    realign()

    # --- Vertical sliders ---------------------------------------------------
    v_items = [
        (f"E_{axis}", FloatSlider(
            label=f"E_{axis}", min_val=-1.0, max_val=1.0, init_val=0.0,
            val_fmt="{:.2f}", orientation=Qt.Vertical,
        ))
        for axis in "xyz"
    ]
    v_box = QGroupBox("Vertical")
    v_row = QHBoxLayout(v_box)
    for name, s in v_items:
        v_row.addWidget(s)
        watch(name, s)

    top = QHBoxLayout()
    top.addWidget(h_box, 3)
    top.addWidget(v_box, 1)
    root.addLayout(top, 1)

    # --- Programmatic controls ----------------------------------------------
    all_sliders = [s for _, s in h_items + v_items]

    enabled = QCheckBox("Sliders enabled")
    enabled.setChecked(True)
    ranges = QCheckBox("Show ranges")
    ranges.setChecked(True)
    allow_inf = QCheckBox("Allow T₂ = +inf")
    allow_inf.setChecked(True)

    def set_enabled(on: bool) -> None:
        for s in all_sliders:
            s.setEnabled(on)

    def set_ranges(on: bool) -> None:
        for s in all_sliders:
            s.set_show_range(on)

    enabled.toggled.connect(set_enabled)
    ranges.toggled.connect(set_ranges)
    allow_inf.toggled.connect(lambda on: t2.set_special_value_allowed("+inf", on))

    controls = QHBoxLayout()
    for cb in (enabled, ranges, allow_inf):
        controls.addWidget(cb)
    controls.addStretch(1)
    root.addLayout(controls)

    log_box = QGroupBox("Signals (user actions only)")
    QVBoxLayout(log_box).addWidget(log)
    root.addWidget(log_box)

    win.resize(1000, 620)
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(_demo_main())