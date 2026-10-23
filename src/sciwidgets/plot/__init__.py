"""Matplotlib plots built from plain descriptions of panels and curves."""

from ..colors import dark_variant
from .canvas import DEFAULT_AXES_STYLE, PlotCanvas, axis_text
from .scroll import ScrollableFigure
from .selector import CurveCheckBox, CurveSelector, color_icon

__all__ = ["CurveCheckBox", "CurveSelector", "DEFAULT_AXES_STYLE", "PlotCanvas", "ScrollableFigure", "axis_text",
           "color_icon", "dark_variant"]
