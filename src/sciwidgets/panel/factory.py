"""Create parameter widgets from plain descriptions (e.g. loaded from JSON).

A description is a mapping with a ``"type"`` and the widget's constructor
arguments::

    {"type": "float-slider", "label": "t_0", "min_val": 0, "max_val": 10}

The type name selects the class from a registry; every other key is passed
to the constructor under the same name. Apps add their own widget classes
with :func:`register_type`.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Mapping, Optional, Type

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget

from sciwidgets.params import (
    ArraySlider,
    FloatRangeSlider,
    FloatSlider,
    IntRangeSlider,
    IntSlider,
    MultiVariableSlider,
    ParameterComboBox,
    ParameterLineEdit,
    ParameterToggle,
    SliderFeature,
)

__all__ = ["RESERVED_KEYS", "register_type", "widget_from_spec", "widget_types"]

RESERVED_KEYS = frozenset({"type", "path", "stretch"})
"""Keys used by the panel itself; they are never passed to a constructor."""

_TYPES: Dict[str, Type[QWidget]] = {
    "float-slider": FloatSlider,
    "int-slider": IntSlider,
    "array-slider": ArraySlider,
    "float-range-slider": FloatRangeSlider,
    "int-range-slider": IntRangeSlider,
    "range-slider": FloatRangeSlider,
    "multi-slider": MultiVariableSlider,
    "line-edit": ParameterLineEdit,
    "combo-box": ParameterComboBox,
    "toggle": ParameterToggle,
}


def _to_orientation(value: Any) -> Any:
    """Convert ``"h"``/``"horizontal"``/``"v"``/``"vertical"`` to a Qt orientation."""
    if not isinstance(value, str):
        return value
    token = value.strip().lower()
    if token in ("h", "horizontal"):
        return Qt.Horizontal
    if token in ("v", "vertical"):
        return Qt.Vertical
    raise ValueError(f"orientation must be 'h' or 'v', got {value!r}")


def _to_features(value: Any) -> Any:
    """Convert a feature name or a list of names to ``SliderFeature`` flags."""
    if isinstance(value, (str, list)):
        return SliderFeature.from_json(value)
    return value


_CONVERTERS: Dict[str, Callable[[Any], Any]] = {
    "orientation": _to_orientation,
    "features": _to_features,
}
"""Arguments whose JSON form differs from the Python one, by argument name."""


def register_type(name: str, cls: Type[QWidget], *, replace: bool = False) -> None:
    """Make a widget class available under a type name.

    The class is built with the description's keys as keyword arguments, so
    its constructor must accept them by name.

    Args:
        name: Type name used in descriptions, e.g. ``"pulse"``.
        cls: Widget class.
        replace: Allow replacing an existing type of the same name.

    Raises:
        ValueError: If the name is already registered and ``replace`` is False.
    """
    if name in _TYPES and not replace:
        raise ValueError(f"widget type {name!r} is already registered (pass replace=True to override)")
    _TYPES[name] = cls


def widget_types() -> List[str]:
    """Return the registered type names, sorted."""
    return sorted(_TYPES)


def widget_from_spec(spec: Mapping[str, Any], parent: Optional[QWidget] = None) -> QWidget:
    """Create a widget from its description.

    ``"type"`` selects the class; ``"path"`` and ``"stretch"`` are ignored
    (they belong to the panel); all other keys become constructor arguments.
    ``"orientation"`` may be ``"h"`` or ``"v"`` and ``"features"`` a name or a
    list of names (see ``SliderFeature``). The description is not modified.

    Args:
        spec: Widget description.
        parent: Parent widget.

    Returns:
        The new widget.

    Raises:
        ValueError: If ``"type"`` is missing or unknown, or a value cannot be
            converted.
        TypeError: If the description has a key the constructor does not
            accept, or lacks a required one.
    """
    type_name = spec.get("type")
    if not type_name:
        raise ValueError(f"widget description has no 'type': {dict(spec)}")
    cls = _TYPES.get(type_name)
    if cls is None:
        raise ValueError(f"unknown widget type {type_name!r}; known types: {', '.join(widget_types())}")

    kwargs = {k: v for k, v in spec.items() if k not in RESERVED_KEYS}
    for key, convert in _CONVERTERS.items():
        if key in kwargs:
            kwargs[key] = convert(kwargs[key])

    try:
        return cls(**kwargs, parent=parent)
    except TypeError as exc:
        where = f" at {spec['path']!r}" if "path" in spec else ""
        raise TypeError(f"{type_name}{where}: {exc}") from exc
