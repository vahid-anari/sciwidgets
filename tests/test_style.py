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


# ----- the widgets' own colors (0.13.1) -----

@pytest.fixture
def colors(qapp):
    """Put the default colors back after the test."""
    from sciwidgets.style import DEFAULT_SCI_COLORS, set_sci_colors
    yield
    set_sci_colors(qapp, **{name: None for name in DEFAULT_SCI_COLORS})
    qapp.processEvents()


def test_set_sci_colors(qapp, scheme, colors):
    from sciwidgets.style import sci_color, set_sci_colors
    scheme("light")
    assert sci_color("value") == "#0000ff" and sci_color("marker", dark=True) == "#ff6b6b"
    set_sci_colors(qapp, value=("#0055cc", "#6cb4ff"), marker="green")
    assert "#0055cc" in qapp.styleSheet() and "#0000ff" not in qapp.styleSheet()
    assert sci_color("marker", dark=False) == sci_color("marker", dark=True) == QColor("green").name()
    scheme("dark")
    assert "#6cb4ff" in qapp.styleSheet()
    set_sci_colors(qapp, value="accent")
    assert sci_color("value") == qapp.palette().color(QPalette.Highlight).name()
    set_sci_colors(qapp, value=None)
    assert sci_color("value", dark=False) == "#0000ff"
    with pytest.raises(ValueError):
        set_sci_colors(qapp, values="red")
    with pytest.raises(ValueError):
        set_sci_colors(qapp, value="not-a-colour")


def test_double_spin_boxes_get_the_value_color(qapp, scheme):
    scheme("light")
    assert "QAbstractSpinBox{" in qapp.styleSheet()


def test_slider_marker_uses_the_marker_color(qapp, scheme, colors):
    from sciwidgets.params import FloatSlider
    from sciwidgets.style import set_sci_colors
    scheme("light")
    slider = FloatSlider(label="x", min_val=0.0, max_val=1.0, init_val=0.5)
    marker = next(c for c in slider.findChildren(object) if type(c).__name__ == "MarkerOverlay")
    assert marker._current_color().name() == "#ff0000"
    set_sci_colors(qapp, marker=("#00aa00", "#66ff66"))
    assert marker._current_color().name() == "#00aa00"
    scheme("dark")
    assert marker._current_color().name() == "#66ff66"


def test_menu_separator_is_visible_in_dark_mode(qapp, scheme):
    from PySide6.QtWidgets import QMenu
    scheme("dark")
    menu = QMenu()
    one = menu.addAction("One")
    separator = menu.addSeparator()
    menu.addAction("Two")
    menu.popup(menu.pos())
    qapp.processEvents()
    image = menu.grab().toImage()
    rect = menu.actionGeometry(separator)
    line = max(QColor(image.pixel(rect.center().x(), y)).lightness() for y in range(rect.top(), rect.bottom() + 1))
    first = menu.actionGeometry(one)
    background = QColor(image.pixel(first.right() - 3, first.top() + 1)).lightness()
    menu.close()
    assert line - background > 20


def test_input_edges_are_visible_in_dark_mode(qapp, scheme):
    from PySide6.QtWidgets import QDoubleSpinBox, QLineEdit
    scheme("dark")
    for field in (QLineEdit("1.5"), QDoubleSpinBox()):
        field.resize(160, 28)
        image = field.grab().toImage()
        edge = QColor(image.pixel(field.width() // 2, 0)).lightness()
        inside = QColor(image.pixel(field.width() // 2, 4)).lightness()
        assert edge - inside > 20, type(field).__name__
