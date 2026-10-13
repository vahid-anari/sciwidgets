# Parameter widgets

Small input widgets for single parameters: a number field, a choice and an
on/off switch. They share one interface with the [sliders](sliders.md), so a
panel can treat every parameter the same way. Import them from
`sciwidgets.params`.

| Widget | Value | Use it for |
|--------|-------|------------|
| `ParameterLineEdit` | `int` or `float` | a number typed by the user, with a LaTeX name and unit |
| `ParameterComboBox` | `str` | one choice from a fixed list |
| `ParameterToggle` | `bool` | an option that is on or off, optionally with a formula for each state |
| `NumericLineEdit` | `int` or `float` | the bare validated number field, without name or unit |

Run `python -m sciwidgets.params` to try them.

## ParameterLineEdit

```python
from sciwidgets.params import ParameterLineEdit

t0 = ParameterLineEdit(
    label="t_0", unit_label=r"\mathrm{s}",
    init_val=5.0, val_fmt="{:.1f}",
    min_limit=0.0, min_limit_inclusive=False,   # t0 > 0
)
n = ParameterLineEdit(label="N", init_val=10, value_is_int=True)
```

| Argument | Default | Meaning |
|----------|---------|---------|
| `label` | required | Name in LaTeX math mode, shown as `label =` |
| `init_val` | required | Initial value |
| `val_fmt` | `"{:0.6g}"` | Display format; typed values are rounded to it |
| `value_is_int` | `False` | Accept integers only |
| `unit_label` | `""` | Unit in LaTeX, shown in parentheses |
| `min_limit`, `max_limit` | `None` | Allowed bounds |
| `min_limit_inclusive`, `max_limit_inclusive` | `True` | Whether the bound itself is allowed |
| `max_length` | `None` | Maximum number of characters |
| `width_chars` | `None` | Field width, in digits |

## NumericLineEdit

The number field inside `ParameterLineEdit`, usable on its own wherever you
need validated numeric input:

```python
from sciwidgets.params import NumericLineEdit

edit = NumericLineEdit(init_val=1.5, min_limit=0.0, max_limit=100.0, val_fmt="{:.3g}")
edit.valueChanged.connect(lambda v: print("new value:", v))
```

How it behaves:

- While typing, anything that could still become a valid number is accepted,
  and out-of-range or incomplete input gets a **red frame**. Text that can
  never be a number (letters, say) is refused outright. Scientific notation
  such as `1.5e-3` works; `inf` and `nan` do not.
- The value is **committed** on Enter, Tab, or when focus moves elsewhere;
  only then is `valueChanged` emitted, and only if the value really changed.
- Leaving the field with invalid text shows a warning explaining the allowed
  range, restores the last valid value and returns focus to the field.

The red frame is drawn by `SciStyle`, so call `apply_sci_style(app)` at
startup (see [style](style.md)).

Other methods: `get_value()`, `set_value(v)`, `set_fmt(fmt)`,
`set_width_chars(n)`.

## ParameterComboBox

```python
from sciwidgets.params import ParameterComboBox

unit = ParameterComboBox(label="t", items=["d", "h", "m", "s", "ms"])
unit.set_value("ms")
```

The value is the selected text. `set_value` raises `ValueError` for text that
is not one of the items.

## ParameterToggle

A checkbox with an optional formula on the right that changes with the state:

```python
from sciwidgets.params import ParameterToggle

normalize = ParameterToggle(
    text="Normalize to max",
    label_on=r"F = I / \max(I) \times I_\mathrm{scale}",
    label_off=r"F = I \times I_\mathrm{scale}",
    checked=True,
)
```

Leave `label_on` / `label_off` as `None` to show nothing in that state, or
both to get a plain checkbox.

## The shared interface

All parameter widgets and sliders derive from `ParameterWidgetBase` and offer:

| Method / signal | Meaning |
|-----------------|---------|
| `get_value()` / `set_value(v)` | read or set the value |
| `get_config()` / `set_config(cfg)` | read or set the configuration (range, format; empty for the widgets on this page) |
| `valueChanged` | the user changed the value |
| `defaultChanged`, `configChanged` | the user changed the default or the configuration (sliders) |
| `get_name_width()` / `set_name_width(w)` | align the name column across a panel |
| `get_value_width()` / `set_value_width(w)` | align the value column across a panel |
| `nameWidthChanged`, `valueWidthChanged` | a measured width changed, so re-align |

Two rules hold for all of them:

- **Signals are for user actions only.** `set_value` and `set_config` never
  emit `valueChanged` or `configChanged`, so restoring saved state does not
  trigger your handlers.
- **`set_config` ignores unknown keys.** A config saved by an older version
  with extra keys still loads; missing keys keep their current values.

See [sliders](sliders.md#aligning-sliders-in-a-panel) for an alignment example
that works for every widget on this page too.

## Writing your own parameter widget

Subclass `ParameterWidgetBase` and implement three methods; `set_value` then
validates before anything changes:

```python
from PySide6.QtWidgets import QSpinBox
from sciwidgets.params import ParameterWidgetBase


class SpinParameter(ParameterWidgetBase[int]):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._spin = QSpinBox(self)
        # emit only for user actions:
        self._spin.valueChanged.connect(lambda v: self.valueChanged.emit(v))

    def get_value(self) -> int:
        return self._spin.value()

    def _validate_value(self, value: int) -> int:
        if not isinstance(value, int):
            raise TypeError("value must be an int")
        return value

    def _apply_value(self, value: int) -> None:
        self._spin.blockSignals(True)   # keep set_value silent
        self._spin.setValue(value)
        self._spin.blockSignals(False)
```
