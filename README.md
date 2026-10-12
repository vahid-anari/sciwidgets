# sciwidgets

PySide6 widgets for scientific desktop apps: math labels rendered with
LaTeX/mathtext, dialogs, and parameter inputs (sliders and more).

![Sliders demo](docs/images/sliders_demo.png)

## Install

```bash
pip install "sciwidgets @ https://github.com/vahid-anari/sciwidgets/archive/refs/tags/v0.1.1.zip"
```

For development, from the repo root:

```bash
pip install -e .
```

## Use

```python
from sciwidgets.style import apply_sci_style
from sciwidgets.labels import MathLabel
from sciwidgets.params import FloatSlider, ParameterLineEdit
from sciwidgets.dialogs import ask_question, show_warning

apply_sci_style(app)  # required: the widgets rely on this style
```

## Demos

```bash
python -m sciwidgets.labels
python -m sciwidgets.dialogs
python -m sciwidgets.params
python -m sciwidgets.params.sliders
```