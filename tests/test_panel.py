import pytest

from sciwidgets.panel import ParameterPage, ParameterTabs, register_type, widget_from_spec
from sciwidgets.params import FloatSlider, ParameterLineEdit, ParameterToggle, ParameterWidgetBase

GRID = {"column": [
    {"group": "Time grid", "column": [
        {"type": "float-slider", "path": "grid.t_max", "label": "t_\\mathrm{max}",
         "min_val": 1, "max_val": 1000, "init_val": 200},
        {"type": "int-slider", "path": "grid.nt", "label": "N_t",
         "min_val": 100, "max_val": 100000, "init_val": 4000}]},
    {"row": [{"type": "toggle", "path": "normalize", "text": "Normalize"}, {"stretch": 1}]},
]}


def test_widget_from_spec():
    w = widget_from_spec({"type": "float-slider", "label": "t_0", "unit": "\\mathrm{s}",
                          "min_val": 0, "max_val": 10, "init_val": 2.5, "val_fmt": "{:.2f}"})
    assert isinstance(w, FloatSlider) and w.get_value() == 2.5


def test_widget_from_spec_unit_on_line_edit():
    w = widget_from_spec({"type": "line-edit", "label": "\\nu", "init_val": 1.0, "unit": "\\mathrm{MHz}"})
    assert isinstance(w, ParameterLineEdit) and w._unit_label is not None


def test_misspelled_key_names_the_path():
    with pytest.raises(TypeError, match="maxval"):
        ParameterPage({"column": [{"type": "float-slider", "path": "grid.t_max", "label": "t",
                                   "min_val": 0, "maxval": 10}]})


def test_page_values_flat_by_path(spy):
    page = ParameterPage(GRID)
    assert page.paths() == ["grid.t_max", "grid.nt", "normalize"]
    values = page.get_value()
    assert values["grid.t_max"] == 200 and values["grid.nt"] == 4000
    s = spy(page.valueChanged)
    page.set_value({"grid.nt": 5000, "not.a.path": 1})        # unknown paths are ignored
    assert page.get_value()["grid.nt"] == 5000 and len(s) == 0


def test_config_round_trip():
    page = ParameterPage(GRID)
    cfg = page.get_config()
    cfg["grid.t_max"]["max_val"] = 2000.0
    other = ParameterPage(GRID)
    other.set_config(cfg)
    assert other.get_config()["grid.t_max"]["max_val"] == 2000.0


def test_templates_and_defaults():
    desc = {
        "templates": {"window": {"type": "range-slider", "min_val": 0, "max_val": 100,
                                 "init_vals": [10, 60], "val_fmt": "{:.1f}"}},
        "defaults": {"val_fmt": "{:.3S}"},
        "tabs": [{"id": "display", "title": "Display", "layout": {"column": [
            {"template": "window", "path": "display.t", "label": "t"},
            {"template": "window", "path": "display.f", "label": "F", "max_val": 200},
            {"group": "Inner", "defaults": {"val_fmt": "{:.2f}"}, "column": [
                {"template": "window", "path": "display.g", "label": "G"}]},
            {"type": "toggle", "path": "display.log", "text": "Log"},
        ]}}],
    }
    cfg = ParameterTabs(desc).get_config()
    assert cfg["display.f"]["max_val"] == 200          # the widget's own key wins
    assert cfg["display.t"]["max_val"] == 100          # from the template
    assert cfg["display.t"]["val_fmt"] == "{:.3S}"     # outer defaults beat the template
    assert cfg["display.g"]["val_fmt"] == "{:.2f}"     # inner defaults beat outer ones
    # the toggle does not accept val_fmt, so the defaults skip it without error


def test_defaults_typo_is_an_error():
    with pytest.raises((ValueError, TypeError)):
        ParameterPage({"defaults": {"val_fmtt": "{:.2f}"}, "column": [
            {"type": "float-slider", "path": "a", "label": "a", "min_val": 0, "max_val": 1}]})


def test_tabs():
    tabs = ParameterTabs({"tabs": [
        {"id": "grid", "title": "Grid", "layout": GRID},
        {"id": "other", "title": "Other", "layout": {"column": [
            {"type": "line-edit", "path": "x", "label": "x", "init_val": 1.0}]}},
    ]})
    assert tabs.tab_ids() == ["grid", "other"]
    assert set(tabs.get_value()) == {"grid.t_max", "grid.nt", "normalize", "x"}
    tabs.set_tab_enabled("other", False)
    assert isinstance(tabs.page("other").get_widget("x"), ParameterLineEdit)


def test_register_type():
    class Answer(ParameterWidgetBase):
        def __init__(self, answer=42, parent=None):
            super().__init__(parent)
            self._v = answer

        def get_value(self):
            return self._v

        def _validate_value(self, value):
            return value

        def _apply_value(self, value):
            self._v = value

    register_type("answer-test", Answer, replace=True)
    page = ParameterPage({"column": [{"type": "answer-test", "path": "q", "answer": 7}]})
    assert page.get_value() == {"q": 7}
