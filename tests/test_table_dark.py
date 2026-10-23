"""Tables in light and dark mode: darkened backgrounds, readable text."""

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

pd = pytest.importorskip("pandas")

from sciwidgets.colors import contrast_ratio, dark_fill, dark_variant  # noqa: E402
from sciwidgets.style import set_color_scheme  # noqa: E402
from sciwidgets.table import DataFrameModel, DataFrameView  # noqa: E402


def frame():
    return pd.DataFrame({"nu": [1.5, 9.5], "U-S J": [3, 4], "name": ["a", "b"]})


def colors(model, row, col):
    idx = model.index(row, col)
    bg, fg = model.data(idx, Qt.BackgroundRole), model.data(idx, Qt.ForegroundRole)
    return (bg.color().name() if bg is not None else None, fg.color().name() if fg is not None else None)


def test_light_mode_backgrounds_get_readable_text():
    m = DataFrameModel(frame(), backgrounds={"U-S J": "tan", "name": "#202060"}, dark=False)
    assert colors(m, 0, 1) == ("#d2b48c", "#000000")
    assert colors(m, 0, 2) == ("#202060", "#ffffff")       # a dark background gets white text
    assert colors(m, 0, 0) == (None, None)                  # no background: the palette's text


def test_dark_mode_darkens_backgrounds():
    m = DataFrameModel(frame(), backgrounds={"U-S J": "tan"}, text_colors={"nu": "navy"}, dark=True)
    bg, fg = colors(m, 0, 1)
    assert bg == dark_fill("tan") and fg == "#ffffff"
    assert contrast_ratio(fg, bg) > 7
    assert colors(m, 0, 0) == (None, dark_variant("navy"))  # dark text made readable
    assert m.column_color("U-S J") == "#d2b48c"              # stored colours stay light-mode colours


def test_own_dark_backgrounds_and_user_colors():
    m = DataFrameModel(frame(), backgrounds={"U-S J": "tan", "nu": "lightblue"},
                       dark_backgrounds={"U-S J": "#403020"}, dark=True)
    assert colors(m, 0, 1)[0] == "#403020"
    assert colors(m, 0, 0)[0] == dark_fill("lightblue")
    m.set_column_color("U-S J", "#ffcccc")                   # a user colour is darkened too
    assert colors(m, 0, 1)[0] == dark_fill("#ffcccc")


def test_row_backgrounds_in_dark_mode():
    m = DataFrameModel(frame(), row_backgrounds=lambda row: "lightyellow" if row["U-S J"] == 4 else None, dark=True)
    assert colors(m, 1, 2) == (dark_fill("lightyellow"), "#ffffff")
    assert colors(m, 0, 2) == (None, None)


def test_set_dark_switches_and_signals(spy):
    m = DataFrameModel(frame(), backgrounds={"U-S J": "tan"}, dark=False)
    s = spy(m.dataChanged)
    m.set_dark(True)
    assert m.dark() and len(s) == 1 and colors(m, 0, 1)[0] == dark_fill("tan")
    m.set_dark(True)
    assert len(s) == 1                                       # no change, no signal
    m.set_dark(False)
    assert colors(m, 0, 1)[0] == "#d2b48c"


def test_view_follows_the_application_palette(qapp):
    v = DataFrameView()
    v.set_frame(frame(), backgrounds={"U-S J": "tan"})
    assert not v.model_().dark()
    try:
        set_color_scheme(qapp, "dark")
        QApplication.processEvents()
        QApplication.processEvents()
        assert v.model_().dark()
        v.set_frame(frame(), backgrounds={"U-S J": "tan"})   # a new model starts dark too
        assert v.model_().dark()
    finally:
        set_color_scheme(qapp, "system")
        QApplication.processEvents()
        QApplication.processEvents()
    assert not v.model_().dark()
