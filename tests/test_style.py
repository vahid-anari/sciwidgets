"""Light and dark colors: the style sheet, math labels and set_color_scheme."""

import pytest
from PySide6.QtGui import QColor, QPalette

from sciwidgets.labels import MathLabel
from sciwidgets.style import (
    RANGE_LABEL_COLOR,
    VALUE_COLOR,
    color_scheme,
    dark_palette,
    is_dark,
    sci_style_sheet,
    set_color_scheme,
)


@pytest.fixture
def scheme(qapp):
    """Switch the scheme and let the event loop apply the style sheet; back to the system's after the test."""

    def switch(name):
        set_color_scheme(qapp, name)
        qapp.processEvents()

    yield switch
    switch("system")


def test_dark_palette_is_dark():
    assert is_dark(dark_palette())
    light = QPalette()
    light.setColor(QPalette.Window, QColor("#efefef"))
    assert not is_dark(light)


def test_set_color_scheme_switches_the_palette(qapp, scheme):
    scheme("dark")
    assert is_dark() and color_scheme() == "dark"
    scheme("light")
    assert not is_dark() and color_scheme() == "light"
    scheme("system")
    assert color_scheme() == "system"
    with pytest.raises(ValueError):
        scheme("dim")


def test_style_sheet_follows_the_scheme(qapp, scheme):
    light_value = QColor(VALUE_COLOR[False]).name()
    dark_value = QColor(VALUE_COLOR[True]).name()
    scheme("light")
    assert light_value in qapp.styleSheet() and QColor(RANGE_LABEL_COLOR[False]).name() in qapp.styleSheet()
    scheme("dark")
    assert dark_value in qapp.styleSheet() and light_value not in qapp.styleSheet()
    assert sci_style_sheet(qapp) in qapp.styleSheet()
    scheme("light")
    assert light_value in qapp.styleSheet()


def _rgb(color):
    return tuple(round(c, 3) for c in color[:3])


def test_math_label_follows_the_palette(qapp, scheme):
    scheme("light")
    label = MathLabel("T_1")
    label.show()
    qapp.processEvents()
    light = _rgb(label._rendered_color)
    assert light == _rgb(qapp.palette().color(QPalette.WindowText).getRgbF())
    scheme("dark")
    qapp.processEvents()
    assert _rgb(label._rendered_color) == _rgb(QColor("#ffffff").getRgbF())
    scheme("light")
    qapp.processEvents()
    assert _rgb(label._rendered_color) == light
    label.close()


def test_math_label_keeps_an_explicit_color(qapp, scheme):
    scheme("light")
    label = MathLabel("w", text_color="red")
    scheme("dark")
    qapp.processEvents()
    assert _rgb(label._rendered_color) == (1.0, 0.0, 0.0)
