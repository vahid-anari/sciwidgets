import numpy as np
import pytest

from sciwidgets.plot import CurveCheckBox, CurveSelector, PlotCanvas


def make_canvas():
    return PlotCanvas({
        "layout": {"mosaic": [["flux"], ["profile"]], "height_ratios": [3, 1], "sharex": True},
        "styles": {"data": {"linestyle": "", "marker": "o", "markersize": 3, "color": "k"},
                   "model": {"linewidth": 1.25}},
        "panels": {
            "flux": {"primary": "flux", "legend": {"loc": "upper right"},
                     "curves": {"data": {"label": "data", "style": "data"},
                                "flux": {"label": "F", "unit": "Jy", "style": "model",
                                         "props": {"color": "b"}}}},
            "profile": {"select": "one",
                        "curves": {"pump": {"label": "\\Lambda"}, "t1": {"label": "T_1"}},
                        "twin": {"curves": {"w": {"label": "w", "props": {"color": "r"}}}}},
        },
        "markers": {"window": {"kind": "vspan", "panels": "all", "at": [3, 5]}},
    })


def gridlines_on(ax, direction):
    axis = ax.yaxis if direction == "y" else ax.xaxis
    return any(line.get_visible() for line in axis.get_gridlines())


def test_curves_and_styles():
    c = make_canvas()
    x = np.linspace(0, 10, 50)
    c.set_curve_data("flux", x, np.sin(x))
    np.testing.assert_array_equal(c.line("flux").get_xdata(), x)
    assert c.get_curve_style("flux")["color"] in ("b", "#0000ff")
    assert c.get_curve_style("data")["marker"] == "o"          # from the named style
    assert c.curve_ids("profile") == ["pump", "t1"]


def test_select_one():
    c = make_canvas()
    c.select_curve("profile", "t1")
    assert c.line("t1").get_visible() and not c.line("pump").get_visible()


def test_config_only_holds_changes(spy):
    c = make_canvas()
    s = spy(c.configChanged)
    assert c.get_config() == {}
    c.set_curve_style("flux", color="#d62728", linewidth=2.0)
    c.set_grid("flux", True, "major", "y")
    cfg = c.get_config()
    assert cfg["curves"]["flux"] == {"color": "#d62728", "linewidth": 2.0}
    assert len(s) == 0                                          # setters are silent

    other = make_canvas()
    other.set_config({**cfg, "curves": {**cfg["curves"], "gone": {"color": "k"}}})  # unknown curve ignored
    assert other.get_config() == cfg


def test_reset_removes_grids_and_styles():
    c = make_canvas()
    c.set_grid("flux", True, "major", "y")
    c.set_grid_style(linestyle=":")
    assert gridlines_on(c.axes("flux"), "y")
    c.reset_config()
    assert c.get_config() == {}
    assert not gridlines_on(c.axes("flux"), "y")               # 0.5.0 fix: reset switches grids off


def test_grid_style():
    c = make_canvas()
    c.set_grid_style(linestyle=":", alpha=0.5)
    assert c.get_grid_style()["linestyle"] == ":"
    assert c.get_config()["grid_style"] == {"linestyle": ":", "alpha": 0.5}
    with pytest.raises(ValueError):
        c.set_grid_style(color="r")


def test_limits_and_marker():
    c = make_canvas()
    c.set_limits("flux", x=(0, 10), y=(-1, 1))
    assert c.get_limits("flux") == ((0, 10), (-1, 1))
    c.set_marker("window", (6, 8))


def test_selector_and_checkbox():
    c = make_canvas()
    sel = CurveSelector(c, "profile", none_text="None")
    assert sel.count() == 3                                     # None + two curves
    sel.set_current("t1")
    assert sel.currentText() != "None"
    box = CurveCheckBox(c, "w", axis="profile.twin")
    assert box.text()


def test_export(tmp_path):
    c = make_canvas()
    c.set_curve_data("flux", [0, 1, 2], [1, 2, 3])
    path = tmp_path / "plot.png"
    c.export(str(path))
    assert path.stat().st_size > 0
