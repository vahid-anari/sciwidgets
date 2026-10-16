import pytest
from PySide6.QtCore import Qt

pd = pytest.importorskip("pandas")

from sciwidgets.table import DataFrameModel, DataFrameView  # noqa: E402


def frame():
    return pd.DataFrame({"nu": [1234.5678, 9.5], "U-S J": [3, 4], "name": ["a", "b"]})


def test_model_display_alignment_and_headers():
    m = DataFrameModel(frame(), formats={"nu": "{:,.2f}"}, headers={"nu": "Frequency\n(MHz)"})
    assert (m.rowCount(), m.columnCount()) == (2, 3)
    idx = m.index(0, 0)
    assert m.data(idx) == "1,234.57"
    assert m.data(m.index(0, 2)) == "a"
    assert m.data(idx, Qt.TextAlignmentRole) == int(Qt.AlignRight | Qt.AlignVCenter)
    assert m.data(m.index(0, 1), Qt.TextAlignmentRole) == int(Qt.AlignRight | Qt.AlignVCenter)
    assert m.data(m.index(0, 2), Qt.TextAlignmentRole) == int(Qt.AlignLeft | Qt.AlignVCenter)
    assert m.headerData(0, Qt.Horizontal) == "Frequency\n(MHz)"
    assert m.headerData(1, Qt.Horizontal) == "U-S J"
    assert m.headerData(1, Qt.Vertical) == "2"
    assert m.columns() == ["nu", "U-S J", "name"]


def test_model_callable_format_and_backgrounds():
    m = DataFrameModel(frame(), formats={"nu": lambda v: f"{v:.0e}"},
                       backgrounds=lambda col: "tan" if col.startswith("U-") else None)
    assert m.data(m.index(1, 0)) == "1e+01"
    assert m.data(m.index(0, 1), Qt.BackgroundRole).color().name() == "#d2b48c"
    assert m.data(m.index(0, 0), Qt.BackgroundRole) is None
    m2 = DataFrameModel(frame(), backgrounds={"name": "#ff0000"})
    assert m2.data(m2.index(0, 2), Qt.BackgroundRole).color().name() == "#ff0000"


def test_model_set_frame_keeps_formats(spy):
    m = DataFrameModel(frame(), formats={"nu": "{:.1f}"})
    s = spy(m.modelReset)
    m.set_frame(pd.DataFrame({"nu": [2.25]}))
    assert len(s) == 1 and m.rowCount() == 1 and m.data(m.index(0, 0)) == "2.2"


def test_view_visible_columns_and_export(tmp_path, spy):
    v = DataFrameView()
    assert v.frame() is None and v.visible_columns() == []
    v.set_frame(frame(), formats={"nu": "{:.1f}"})
    assert v.visible_columns() == ["nu", "U-S J", "name"]
    s = spy(v.visibleColumnsChanged)
    v.set_visible_columns(["name", "nu"])
    assert v.visible_columns() == ["nu", "name"] and len(s) == 0
    assert v.isColumnHidden(1) and not v.isColumnHidden(0)
    assert list(v.visible_frame().columns) == ["nu", "name"]
    path = tmp_path / "out.csv"
    v.export_csv(path)
    assert path.read_text().splitlines()[0] == "nu,name"
    v.set_frame(pd.DataFrame({"nu": [1.0], "other": [2]}))
    assert v.visible_columns() == ["nu"]
    v.set_visible_columns(None)
    assert v.visible_columns() == ["nu", "other"]


def test_view_choose_columns_dialog(monkeypatch, spy):
    from sciwidgets.table import _dialogs

    v = DataFrameView()
    v.set_frame(frame())
    s = spy(v.visibleColumnsChanged)

    class FakeDialog:
        def __init__(self, columns, visible, parent=None):
            self.columns = list(columns)

        def exec(self):
            return 1

        def selected(self):
            return [self.columns[0]]

    monkeypatch.setattr(_dialogs, "ChooseColumnsDialog", FakeDialog)
    monkeypatch.setattr("sciwidgets.table.view.ChooseColumnsDialog", FakeDialog)
    assert v.choose_columns() is True
    assert v.visible_columns() == ["nu"] and s.calls[-1] == (["nu"],)
    assert v.choose_columns() is False


def test_export_without_data():
    with pytest.raises(RuntimeError):
        DataFrameView().export_csv("x.csv")


def test_view_fits_multiline_headers():
    v = DataFrameView()
    v.set_frame(pd.DataFrame({"a": [1], "b": [2]}), headers={"a": "Upper state\nEnergy (cm^-1)", "b": "b"})
    fm = v.horizontalHeader().fontMetrics()
    assert v.horizontalHeader().minimumHeight() >= 2 * fm.lineSpacing()
    assert v.columnWidth(0) >= fm.horizontalAdvance("Energy (cm^-1)")
    assert v.columnWidth(1) < v.columnWidth(0)
    h0 = v.horizontalHeader().minimumHeight()
    v.set_header_padding(30)
    assert v.header_padding() == 30
    assert v.horizontalHeader().minimumHeight() == h0 + 36
    assert v.columnWidth(0) >= fm.horizontalAdvance("Energy (cm^-1)") + 60


def test_column_colors_and_config(spy):
    v = DataFrameView()
    v.set_column_color("nu", "#112233")
    v.set_frame(frame(), backgrounds=lambda c: "tan" if c.startswith("U-") else None)
    assert v.column_color("nu") == "#112233" and v.column_color("U-S J") == "#d2b48c"
    s = spy(v.configChanged)
    v.set_column_color("U-S J", "#ff0000")
    assert v.column_color("U-S J") == "#ff0000" and len(s) == 0
    v.set_column_color("U-S J", None)
    assert v.column_color("U-S J") is None
    v.restore_column_color("U-S J")
    assert v.column_color("U-S J") == "#d2b48c"
    v.set_visible_columns(["nu"])
    assert v.get_config() == {"backgrounds": {"nu": "#112233"}, "text_colors": {}, "visible_columns": ["nu"],
                              "font": None}
    v.set_frame(frame())
    assert v.column_color("nu") == "#112233"
    v.reset_colors()
    assert v.column_color("nu") is None
    assert v.get_config()["font"] is None
    v.set_config({"backgrounds": {"name": "#00ff00"}, "visible_columns": None, "other": 1})
    assert v.column_color("name") == "#00ff00" and v.visible_columns() == ["nu", "U-S J", "name"]
    with pytest.raises(KeyError):
        v.set_column_color("nope", "red")


def test_header_menu_hide_and_user_color(spy):
    v = DataFrameView()
    v.set_frame(frame())
    s = spy(v.configChanged)
    s2 = spy(v.visibleColumnsChanged)
    v._hide_column("U-S J")
    assert v.visible_columns() == ["nu", "name"] and s2.calls[-1] == (["nu", "name"],)
    assert s.calls[-1][0]["visible_columns"] == ["nu", "name"]
    v._user_set_color("nu", "#123456")
    assert s.calls[-1][0]["backgrounds"] == {"nu": "#123456"}
    v._user_reset_colors()
    assert s.calls[-1][0]["backgrounds"] == {}


def test_header_menu_hook():
    v = DataFrameView()
    v.set_frame(frame())
    seen = []
    v.headerMenuRequested.connect(lambda menu, col: (seen.append(col), menu.addAction("Extra")))
    menu = v.header_menu("nu")
    texts = [a.text() for a in menu.actions() if a.text()]
    assert seen == ["nu"]
    assert texts == ["Column Color…", "No Column Color", "Default Column Color", "Text Color…",
                     "Default Text Color", "Hide This Column", "Choose Columns…", "Reset Colors", "Font…",
                     "Default Font", "Extra"]
    assert menu.actions()[1].isEnabled() and not menu.actions()[2].isEnabled()
    v.set_column_color("nu", None)
    menu = v.header_menu("nu")
    assert not menu.actions()[1].isEnabled() and menu.actions()[2].isEnabled()


def test_rich_text_headers():
    from sciwidgets.table._header import RichHeaderView, is_rich_text

    assert is_rich_text("&tau;<br>(s)") and is_rich_text("cm<sup>-1</sup>") and not is_rich_text("a\nb")
    v = DataFrameView()
    v.set_frame(pd.DataFrame({"t": [1.0], "E": [2.0]}),
                headers={"t": "&tau;<br>(s)", "E": "Energy<br>(cm<sup>-1</sup>)"})
    header = v.horizontalHeader()
    assert isinstance(header, RichHeaderView)
    fm = header.fontMetrics()
    assert header.minimumHeight() >= 2 * fm.lineSpacing()
    assert v.columnWidth(1) >= fm.horizontalAdvance("Energy")
    v.resize(400, 200)
    v.show()
    v.grab()


def test_rich_text_values():
    from sciwidgets.formatting import pretty_sci_text
    from sciwidgets.table._delegate import RichTextDelegate

    v = DataFrameView()
    v.set_frame(pd.DataFrame({"tau": [123.0, 0.00456], "s": ["a", "b"]}),
                formats={"tau": lambda x: pretty_sci_text(x, 3)})
    assert isinstance(v.itemDelegate(), RichTextDelegate)
    from PySide6.QtWidgets import QStyleOptionViewItem

    assert v.model_().data(v.model_().index(0, 0)) == "123"
    text = v.model_().data(v.model_().index(1, 0))
    assert text == "4.56×10<sup>-3</sup>"
    hint = v.itemDelegate().sizeHint(QStyleOptionViewItem(), v.model_().index(1, 0))
    assert hint.width() > 40 and hint.height() > 10
    v.resize(300, 150)
    v.show()
    v.grab()


def test_sorting_by_header():
    from PySide6.QtCore import Qt

    v = DataFrameView()
    v.set_frame(pd.DataFrame({"nu": [3.0, 1.0, 2.0], "name": ["c", "a", "b"]}))
    assert v.isSortingEnabled() and v.horizontalHeader().sortIndicatorSection() == -1
    assert list(v.frame()["nu"]) == [3.0, 1.0, 2.0]
    v.sortByColumn(0, Qt.AscendingOrder)
    assert list(v.frame()["nu"]) == [1.0, 2.0, 3.0] and list(v.visible_frame()["name"]) == ["a", "b", "c"]
    v.sortByColumn(0, Qt.DescendingOrder)
    assert list(v.frame()["name"]) == ["c", "b", "a"]
    v.set_frame(pd.DataFrame({"nu": [5.0, 4.0, 6.0]}))
    assert list(v.frame()["nu"]) == [6.0, 5.0, 4.0]
    v2 = DataFrameView(sortable=False)
    v2.set_frame(pd.DataFrame({"nu": [3.0, 1.0]}))
    assert not v2.isSortingEnabled() and list(v2.frame()["nu"]) == [3.0, 1.0]


def test_table_font_and_config(spy):
    from PySide6.QtGui import QFont

    v = DataFrameView()
    v.set_frame(frame())
    rows0 = v.verticalHeader().defaultSectionSize()
    s = spy(v.configChanged)
    big = QFont(v.font())
    big.setPointSize(v.font().pointSize() + 8)
    v.set_table_font(big)
    assert len(s) == 0 and v.table_font().pointSize() == big.pointSize()
    assert v.verticalHeader().defaultSectionSize() > rows0
    assert v.horizontalHeader().font().pointSize() == big.pointSize()
    cfg = v.get_config()
    assert cfg["font"] == big.toString()
    v2 = DataFrameView()
    v2.set_config(cfg)
    assert v2.table_font() is not None and v2.font().pointSize() == big.pointSize()
    v2.set_config({"font": None})
    assert v2.table_font() is None and v2.verticalHeader().defaultSectionSize() == rows0
    v._user_set_font(None)
    assert s.calls[-1][0]["font"] is None


def test_resolved_font_has_listed_family():
    from PySide6.QtGui import QFontDatabase

    from PySide6.QtGui import QFont

    v = DataFrameView()
    font = v._resolved_font()
    assert font.family() in QFontDatabase.families() and font.pointSize() > 0
    assert not font.family().startswith(".")
    listed = [f for f in QFontDatabase.families() if not f.startswith(".")][-1]
    v.set_table_font(QFont(listed, 17))
    font = v._resolved_font()
    assert font.pointSize() == 17 and font.family() == listed
    v.set_table_font(None)
    assert v._resolved_font().pointSize() != 17 or v._resolved_font().family() != listed


def test_header_click_sorts():
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest

    v = DataFrameView()
    v.set_frame(pd.DataFrame({"a": [3, 1, 2]}))
    v.resize(300, 150)
    v.show()
    header = v.horizontalHeader()
    assert header.sectionsClickable()
    point = QPoint(header.sectionViewportPosition(0) + header.sectionSize(0) // 2, header.height() // 2)
    QTest.mouseClick(header.viewport(), Qt.LeftButton, Qt.NoModifier, point)
    assert list(v.frame()["a"]) == [1, 2, 3]
    QTest.mouseClick(header.viewport(), Qt.LeftButton, Qt.NoModifier, point)
    assert list(v.frame()["a"]) == [3, 2, 1]


def test_text_colors_per_column(spy):
    from PySide6.QtCore import Qt

    v = DataFrameView()
    v.set_column_color("name", "#00ff00", kind="text")
    v.set_frame(frame(), text_colors={"nu": "#0000ff"})
    m = v.model_()
    assert m.data(m.index(0, 0), Qt.ForegroundRole).color().name() == "#0000ff"
    assert m.data(m.index(0, 2), Qt.ForegroundRole).color().name() == "#00ff00"
    assert m.data(m.index(0, 1), Qt.ForegroundRole) is None
    s = spy(v.configChanged)
    v.set_column_color("nu", "#ff0000", kind="text")
    assert v.column_color("nu", kind="text") == "#ff0000" and len(s) == 0
    assert v.get_config()["text_colors"] == {"name": "#00ff00", "nu": "#ff0000"}
    v.restore_column_color("nu", kind="text")
    assert v.column_color("nu", kind="text") == "#0000ff"
    v.set_frame(frame())
    assert v.column_color("name", kind="text") == "#00ff00"
    v._user_restore_color("name", kind="text")
    assert s.calls[-1][0]["text_colors"] == {}
    v.set_config({"text_colors": {"nu": "#123456"}, "backgrounds": {"nu": "#654321"}})
    assert v.column_color("nu", kind="text") == "#123456" and v.column_color("nu") == "#654321"
    v.reset_colors()
    assert v.get_config()["text_colors"] == {} and v.get_config()["backgrounds"] == {}
    with pytest.raises(ValueError):
        v.set_column_color("nu", "red", kind="border")
    v.set_frame(pd.DataFrame({"t": [7.71e5]}), formats={"t": lambda x: "7×10<sup>5</sup>"})
    v.set_column_color("t", "#ff0000", kind="text")
    v.resize(200, 80)
    v.show()
    img = v.grab().toImage()
    reds = [(x, y) for x in range(img.width()) for y in range(img.height())
            if img.pixelColor(x, y).red() > 200 and img.pixelColor(x, y).green() < 80]
    assert reds


def test_rich_header_sort_indicator_and_width():
    from PySide6.QtCore import Qt

    v = DataFrameView()
    v.set_frame(pd.DataFrame({"t": [2.0, 1.0]}), headers={"t": "&tau;<br>(s)"})
    header = v.horizontalHeader()
    assert header.indicator_width() > 0
    assert v.columnWidth(0) >= header.text_size("&tau;<br>(s)").width() + 24 + header.indicator_width()
    v.sortByColumn(0, Qt.AscendingOrder)
    assert header.sortIndicatorSection() == 0 and list(v.frame()["t"]) == [1.0, 2.0]
    v.resize(300, 120)
    v.show()
    v.grab()
    v2 = DataFrameView(sortable=False)
    v2.set_frame(pd.DataFrame({"t": [1.0]}))
    assert v2.horizontalHeader().indicator_width() == 0
