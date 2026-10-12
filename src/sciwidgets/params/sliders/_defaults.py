"""Default sizes and slider border styling used by the parameter widgets."""

from __future__ import annotations

from enum import Enum

SLIDER_LABEL_SIZE = 20
"""Default font size, in points, for slider name labels."""

UNIT_LABEL_SIZE = 18
"""Default font size, in points, for unit labels."""

SLIDER_BORDER_STYLE_SHEET = """
        QWidget#labeled_slider[borderState="normal"] {
            border: 1px solid gray;
            border-radius: 3px;
            background: transparent;
        }
        QWidget#labeled_slider[borderState="error"] {
            border: 1px solid red;
            border-radius: 3px;
            background: transparent;
        }
        QWidget#labeled_slider[borderState="off"] {
            border: 0px;
        }
        """
"""Style sheet fragment used for custom slider border states."""


class SliderBorderState(str, Enum):
    """State values used when drawing custom slider borders."""

    OFF = "off"
    NORMAL = "normal"
    ERROR = "error"