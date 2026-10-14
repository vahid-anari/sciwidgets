"""Matplotlib plots built from plain descriptions of panels and curves."""

from .canvas import DEFAULT_AXES_STYLE, PlotCanvas, axis_text
from .selector import CurveCheckBox, CurveSelector, color_icon

__all__ = ["CurveCheckBox", "CurveSelector", "DEFAULT_AXES_STYLE", "PlotCanvas", "axis_text", "color_icon"]
