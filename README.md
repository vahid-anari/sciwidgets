# sciwidgets

[![tests](https://github.com/vahid-anari/sciwidgets/actions/workflows/tests.yml/badge.svg)](https://github.com/vahid-anari/sciwidgets/actions/workflows/tests.yml)
[![PyPI](https://img.shields.io/pypi/v/sciwidgets)](https://pypi.org/project/sciwidgets/)
[![Python](https://img.shields.io/pypi/pyversions/sciwidgets)](https://pypi.org/project/sciwidgets/)
![License](https://img.shields.io/badge/license-MIT-green)

PySide6 building blocks for scientific desktop apps: parameter sliders and
panels described in JSON, Matplotlib plot canvases, DataFrame tables, LaTeX
labels, dialogs, and app support (launcher, updates, Help menu), in light and
dark mode.

<img src="https://raw.githubusercontent.com/vahid-anari/sciwidgets/main/docs/figures/showcase_demo.png" width="900" alt="The sciwidgets showcase: a parameter panel, a plot that follows the sliders, menus and a status bar">

The showcase above is `python -m sciwidgets`: a panel built from a JSON
description drives the plot, with a line-list table in the second tab and
dark mode in the View menu. Fitting the pulse by eye, a slider's Set Value
dialog, and switching to dark mode:

![Showcase in use](https://raw.githubusercontent.com/vahid-anari/sciwidgets/main/docs/figures/showcase.gif)

The widgets were written for
[Maxwell Bloch Studio](https://github.com/vahid-anari/maxwell-bloch-studio)
and moved into this package so other apps can share them.

## Features

- **Math labels**: `MathLabel` renders LaTeX through Matplotlib and scales
  cleanly as SVG. It uses your system LaTeX when installed and falls back to
  Matplotlib's mathtext otherwise.
- **Sliders**: integer, float, array, range and multi-variable sliders with
  LaTeX names and units, optional range labels, a default-value marker and a
  right-click menu (save/reset default, set value, ±inf, edit range and format;
  [see it in action](https://github.com/vahid-anari/sciwidgets/blob/main/docs/sliders.md)).
- **Scientific number format**: `"{:.3S}"` displays values as `1.23×10⁴`.
- **Validated input**: `NumericLineEdit` checks numbers and limits while typing
  and marks invalid input with a red frame.
- **Parameter widgets**: line edit, combo box and toggle sharing one interface
  with the sliders (`get_value` / `set_value`, `get_config` / `set_config`) and
  name/value columns that line up across a panel.
- **Parameter panels**: build groups, columns and tabs of parameter widgets
  from a JSON-style description, with templates and shared defaults, and read
  or restore all values as one dict.
- **Plot canvas**: Matplotlib panels, twins, legends and markers from a
  description; data by curve id; a right-click style menu for curves, grids
  and spans whose changes save as plain data.
- **Tables**: a read-only view of a pandas DataFrame with formats, coloured
  columns, rich-text headers, sorting, a column chooser and CSV export.
- **Dialogs**: information, warning, error, question, rich-text and About
  dialogs.
- **Splash screen**: your picture with the app name and version drawn on it,
  sharp on Retina, and start-up messages from anywhere in the app.
- **App support**: install a double-click launcher, check for and run updates
  from PyPI, and a shared Help menu with the User Guide and About.
- **Light and dark mode**: everything follows the system appearance, or
  `set_color_scheme(app, "dark")`; plots and tables get readable dark colours,
  and exports stay light.

## Components

| Import | Contents | Docs |
|--------|----------|------|
| `sciwidgets.params` (sliders) | `FloatSlider`, `IntSlider`, `ArraySlider`, `FloatRangeSlider`, `IntRangeSlider`, `MultiVariableSlider`, `SliderFeature` | [Sliders](https://github.com/vahid-anari/sciwidgets/blob/main/docs/sliders.md) |
| `sciwidgets.params` (inputs) | `ParameterLineEdit`, `ParameterComboBox`, `ParameterToggle`, `NumericLineEdit` | [Parameter widgets](https://github.com/vahid-anari/sciwidgets/blob/main/docs/params.md) |
| `sciwidgets.panel` | `ParameterPage`, `ParameterTabs`, `widget_from_spec`, `register_type` | [Parameter panels](https://github.com/vahid-anari/sciwidgets/blob/main/docs/panel.md) |
| `sciwidgets.plot` | `PlotCanvas`, `ScrollableFigure`, `CurveSelector`, `CurveCheckBox` | [Plot canvas](https://github.com/vahid-anari/sciwidgets/blob/main/docs/plot.md) |
| `sciwidgets.table` | `DataFrameModel`, `DataFrameView` (needs `pip install "sciwidgets[table]"`) | [DataFrame tables](https://github.com/vahid-anari/sciwidgets/blob/main/docs/table.md) |
| `sciwidgets.labels` | `MathLabel`, `set_latex_enabled` | [Labels](https://github.com/vahid-anari/sciwidgets/blob/main/docs/labels.md) |
| `sciwidgets.dialogs` | `show_information`, `show_warning`, `show_critical`, `show_rich_information`, `show_about_dialog`, `ask_question` | [Dialogs](https://github.com/vahid-anari/sciwidgets/blob/main/docs/dialogs.md) |
| `sciwidgets.splash` | `SplashScreen`, `splash_message` | [Splash screen](https://github.com/vahid-anari/sciwidgets/blob/main/docs/splash.md) |
| `sciwidgets.app` | `AppInfo`; `launcher.install_app_command`, `refresh_if_outdated`; `update.run_update`; `update_ui.AppUpdates`; `help.AppHelp` (shared Help menu, About with the libraries used) | [App launcher, updates, Help and About](https://github.com/vahid-anari/sciwidgets/blob/main/docs/app.md) |
| `sciwidgets.window` | `MenuBarController`, `StatusBarController`, `center_on_screen` | [Window helpers](https://github.com/vahid-anari/sciwidgets/blob/main/docs/window.md) |
| `sciwidgets.devtools` | `Shot`, `Gif`, `Player`, `main` (documentation pictures and GIFs taken by scripts) | [Documentation figures](https://github.com/vahid-anari/sciwidgets/blob/main/docs/devtools.md) |
| `sciwidgets.style`, `sciwidgets.colors`, `sciwidgets.formatting` | `apply_sci_style`, `SciStyle`, `set_color_scheme`, `is_dark`; `dark_variant`, `dark_fill`; `value_to_text`, `pretty_sci_text` | [Style, dark mode and formatting](https://github.com/vahid-anari/sciwidgets/blob/main/docs/style.md) |

## Installation

```bash
pip install sciwidgets
```

Requires Python 3.10+, PySide6 6.5+, Matplotlib and NumPy (installed
automatically). A LaTeX installation is optional. The table widgets need
pandas: `pip install "sciwidgets[table]"`.

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

The widgets, plots and tables follow light and dark mode by themselves;
`set_color_scheme(app, "light" | "dark" | "system")` chooses one, for example
from a View menu.

## Signals

`valueChanged`, `defaultChanged` and `configChanged` are emitted **only for
user actions** (dragging, typing, the context menu, dialogs). Setting values
from code with `set_value`, `set_config` and similar methods is silent, so
loading saved parameters never triggers your handlers. Read the new state
with `get_value()` / `get_config()` after setting it.

## Demos

`python -m sciwidgets` runs the showcase above. Each subpackage also has a
demo of its own:

```bash
python -m sciwidgets.labels
python -m sciwidgets.dialogs
python -m sciwidgets.params
python -m sciwidgets.params.sliders
python -m sciwidgets.window
python -m sciwidgets.panel
python -m sciwidgets.plot
python -m sciwidgets.table
python -m sciwidgets.splash
```

## Versions

Versions follow [semantic versioning](https://semver.org); what changed in each
is in [`CHANGELOG.md`](CHANGELOG.md). Pin a compatible range in your app's
requirements (for example `sciwidgets~=0.13.0`) and move to a newer version
when you are ready to test it.

## Development

From the repo root:

```bash
pip install -e ".[dev]"
pytest
```

The tests run without a window (Qt's offscreen platform) and take a few
seconds. Pushing a tag `vX.Y.Z` publishes a GitHub Release with that
version's section of `CHANGELOG.md`.

`python tools/figures.py` retakes the pictures and animations in
`docs/figures/` from the demos (`--list` for the names, `--dark` to check dark
mode), with [`sciwidgets.devtools`](https://github.com/vahid-anari/sciwidgets/blob/main/docs/devtools.md),
which apps use for their own docs too. On macOS the pictures have the window's
title bar and shadow; the terminal needs Screen Recording permission.

## Citing

If you use sciwidgets in published work, please cite it; GitHub's **Cite this
repository** button gives the reference (from `CITATION.cff`).

## License

MIT License. See [LICENSE](LICENSE).

## Author

Vahid Anari ·
[GitHub](https://github.com/vahid-anari) ·
[LinkedIn](https://www.linkedin.com/in/vahid-anari/)

Related projects: [mbsolver](https://github.com/vahid-anari/mbsolver) ·
[Maxwell Bloch Studio](https://github.com/vahid-anari/maxwell-bloch-studio) ·
[linecat](https://github.com/vahid-anari/linecat) ·
[Daftarche](https://github.com/vahid-anari/daftarche)
