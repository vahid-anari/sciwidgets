"""Text and scalar parameter widget backed by a line edit."""

from __future__ import annotations

import numbers
from typing import Optional, Union

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QGridLayout

from ..labels import MathLabel
from .base import ParameterWidgetBase
from .numeric_line_edit import NumericLineEdit

Num = Union[int, float]


class ParameterLineEdit(ParameterWidgetBase[Num]):
    """Parameter widget that exposes a numeric value through a line edit."""

    def __init__(
            self,
            label: str,
            init_val: Num,
            val_fmt: str = "{:0.6g}",
            value_is_int: bool = False,
            unit: str = "",
            min_limit: Num | None = None,
            max_limit: Num | None = None,
            min_limit_inclusive: bool = True,
            max_limit_inclusive: bool = True,
            max_length: Optional[int] = None,
            width_chars: Optional[int] = None,
            parent: Optional[QWidget] = None,
            unit_label: Optional[str] = None,
    ) -> None:
        """Initialize the parameter line edit.

        Args:
            label: Parameter name displayed to the left of the line edit.
            init_val: Initial value.
            val_fmt: Display format string.
            value_is_int: Whether the value is an integer.
            unit: Optional unit shown to the right in parentheses, as LaTeX
                (the same name as on the sliders).
            min_limit: Optional lower hard limit.
            max_limit: Optional upper hard limit.
            min_limit_inclusive: Whether the lower hard limit is inclusive.
            max_limit_inclusive: Whether the upper hard limit is inclusive.
            max_length: Optional maximum number of characters.
            width_chars: Optional width of the line edit in characters.
            parent: Optional parent widget.
            unit_label: Older name of ``unit``, still accepted.

        Raises:
            TypeError: If both ``unit`` and ``unit_label`` are given.
        """

        super().__init__(parent)
        if unit_label is not None:
            if unit:
                raise TypeError("give either unit or unit_label (its older name), not both")
            unit = unit_label

        self._value_is_int = value_is_int
        self._parse = int if value_is_int else float
        self._label = MathLabel(f"{label}=", alignment=Qt.AlignRight | Qt.AlignVCenter)
        self._measured_name_width = self._label.sizeHint().width()
        self._unit_label: MathLabel | None = None
        if unit:
            self._unit_label = MathLabel(f"({unit})")
        self._line_edit = NumericLineEdit(
            init_val=init_val,
            value_is_int=value_is_int,
            val_fmt=val_fmt,
            min_limit=min_limit,
            max_limit=max_limit,
            min_limit_inclusive=min_limit_inclusive,
            max_limit_inclusive=max_limit_inclusive,
            place_holder_text="Enter an int" if value_is_int else "Enter a float",
            max_length=max_length,
            width_chars=width_chars,
        )
        self._line_edit.valueChanged.connect(self._on_values_changed)

        self._make_layout()

    def _make_layout(self) -> None:
        """Create the layout used by this widget."""

        gl = QGridLayout(self)
        gl.setSpacing(0)
        gl.addWidget(self._label, 0, 0)
        gl.addWidget(self._line_edit, 0, 1)
        if self._unit_label is not None:
            gl.addWidget(self._unit_label, 0, 2)
            gl.setColumnStretch(3, 1)
        else:
            gl.setColumnStretch(2, 1)
        self._gl = gl
        self._update_layout()

    def _update_layout(self) -> None:
        """Reserve the effective name width for the label column."""

        self._gl.setColumnMinimumWidth(0, self._effective_name_width())

    # ----- internal helpers -----
    def _on_values_changed(self) -> None:
        """Handle the values changed event."""

        self.valueChanged.emit(self.get_value())

    # ----- public API -----
    def get_value(self) -> Num:
        """Return the current value."""

        return self._line_edit.get_value()

    def _validate_value(self, value: Num) -> Num:
        """Validate a value before applying it.

        Args:
            value: Proposed value.

        Returns:
            Validated value.

        Raises:
            TypeError: If ``value`` is not a number, or not an integer on an
                integer line edit. ``bool`` is rejected.
        """
        if isinstance(value, bool) or not isinstance(value, numbers.Real):
            raise TypeError(f"value must be a number, not {type(value).__name__}")
        if self._value_is_int and not isinstance(value, numbers.Integral):
            raise TypeError(f"value must be an int, not {type(value).__name__}")
        return value

    def _apply_value(self, value: Num) -> None:
        """Apply a validated value to the widget state."""

        self._line_edit.set_value(self._parse(value))
