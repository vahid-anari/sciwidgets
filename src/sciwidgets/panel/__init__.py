"""Parameter panels built from plain descriptions."""

from .factory import RESERVED_KEYS, register_type, widget_from_spec, widget_types
from .page import ParameterPage
from .tabs import ParameterTabs

__all__ = [
    "ParameterPage",
    "ParameterTabs",
    "RESERVED_KEYS",
    "register_type",
    "widget_from_spec",
    "widget_types",
]
