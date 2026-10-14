"""Parameter panels built from plain descriptions."""

from .factory import RESERVED_KEYS, register_type, widget_from_spec, widget_types
from .page import ParameterPage

__all__ = ["ParameterPage", "RESERVED_KEYS", "register_type", "widget_from_spec", "widget_types"]
