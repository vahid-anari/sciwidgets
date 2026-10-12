# sciwidgets

PySide6 widgets for scientific desktop apps: math labels rendered with
LaTeX/mathtext, dialogs, and parameter inputs such as sliders, range sliders
and validated number fields.

![Sliders demo](docs/images/sliders_demo.png)

Right-click menu, Set Value and Edit Configuration:

![Slider interaction](docs/images/sliders_demo.gif)

The widgets were written for the
[Maxwell Bloch Solver](https://github.com/vahid-anari/maxwell-bloch-solver)
and moved into this package so other apps can share them.

## Features

- **Math labels**: `MathLabel` renders LaTeX through Matplotlib and scales
  cleanly as SVG. It uses your system LaTeX when installed and falls back to
  Matplotlib's mathtext otherwise.
- **Sliders**: integer, float, array, range and multi-variable sliders with
  LaTeX names and units, optional range labels, a default-value marker and a
  right-click menu (save/reset default, set value, ±inf, edit range and format).
- **Scientific number format**: `"{:.3S}"` displays values as `1.23×10⁴`.
- **Validated input**: `NumericLineEdit` checks numbers and limits while typing
  and marks invalid input with a red frame.
- **Parameter widgets**: line edit, combo box and toggle sharing one interface
  with the sliders (`get_value` / `set_value`, `get_config` / `set_config`) and
  name/value columns that line up across a panel.
- **Dialogs**: information, warning, error, question, rich-text and About
  dialogs.

## Install

```bash
pip install "sciwidgets @ https://github.com/vahid-anari/sciwidgets/archive/refs/tags/v0.1.1.zip"
```

Requires Python 3.10+, PySide6 6.5+, Matplotlib and NumPy (installed
automatically). A LaTeX installation is optional.

For development, from the repo root:

```bash
pip install -e .
```

## Quick start

```python
import sys

from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

from sciwidgets.params import FloatRangeSlider, FloatSlider
from sciwidgets.style import apply_sci_style

app = QApplication(sys.argv)
apply_sci_style(app)  # required, see "Style" below

win = QWidget()
layout = QVBoxLayout(win)

t1 = FloatSlider(
    label="T_1", unit=r"\mathrm{ms}",
    min_val=0.1, max_val=10.0, init_val=1.0, val_fmt="{:.2f}",
    min_limit=0.0, min_limit_inclusive=False,
)
band = FloatRangeSlider(
    label=r"\nu", unit=r"\mathrm{GHz}",
    min_val=6.60, max_val=6.75, init_vals=(6.65, 6.70), val_fmt="{:.3f}",
)
layout.addWidget(t1)
layout.addWidget(band)

t1.valueChanged.connect(lambda v: print("T1 =", v))
band.valueChanged.connect(lambda v: print("band =", v["range"]))

win.show()
sys.exit(app.exec())
```

Labels and units are written in LaTeX math mode, without the `$` signs.

## Style

The widgets rely on `SciStyle`, a Fusion-based Qt style, for part of their
behaviour: clicking a slider groove moves the handle there, disabled sliders
get a flat groove, and invalid numeric input gets a red frame. Apply it once
at startup:

```python
from sciwidgets.style import apply_sci_style

apply_sci_style(app, my_app_style_sheet)  # your own rules are appended
```

## Signals

`valueChanged`, `defaultChanged` and `configChanged` are emitted **only for
user actions** (dragging, typing, the context menu, dialogs). Setting values
from code with `set_value`, `set_config` and similar methods is silent, so
loading saved parameters never triggers your handlers. Read the new state
with `get_value()` / `get_config()` after setting it.

## Demos

Each subpackage has a runnable demo:

```bash
python -m sciwidgets.labels
python -m sciwidgets.dialogs
python -m sciwidgets.params
python -m sciwidgets.params.sliders
```

## Versions

Releases are Git tags following [semantic versioning](https://semver.org).
Pin an exact tag in your app's requirements, as in the install line above,
and move to a newer tag when you are ready to test it.