import matplotlib.colors as mcolors
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


# ----- span style (0.8.0) -----

def span_canvas():
    return PlotCanvas({
        "layout": {"mosaic": [["flux"], ["profile"]], "sharex": True},
        "panels": {"flux": {"curves": {"flux": {}}}, "profile": {"curves": {"pump": {}}}},
        "markers": {
            "window": {"kind": "vspan", "panels": "all", "at": [3, 5], "name": "Window",
                       "center": "center", "props": {"color": "b", "alpha": 0.1}},
            "band": {"kind": "hspan", "panels": ["flux"], "at": [0.2, 0.4]},
            "center": {"kind": "vline", "panels": "all", "at": 4,
                       "props": {"color": "r", "linewidth": 0.75, "alpha": 0.6}},
        },
    })


def pixels(canvas):
    canvas.draw()
    return bytes(canvas.buffer_rgba())


def test_span_style_from_description():
    c = span_canvas()
    assert c.span_ids() == ["window", "band"]
    assert c.get_marker_name("window") == "Window" and c.get_marker_name("band") == "band"
    style = c.get_span_style("window")
    assert style == {"facecolor": "#0000ff", "alpha": 0.1, "edgecolor": "#0000ff",
                     "edge_alpha": 0.1, "linewidth": style["linewidth"], "linestyle": "-",
                     "center_color": "#ff0000", "center_alpha": 0.6, "center_linewidth": 0.75,
                     "center_linestyle": "-",
                     "dark_facecolor": None, "dark_edgecolor": None, "dark_center_color": None}
    assert c.default_span_style("window") == style
    assert "center_color" not in c.get_span_style("band")      # no centre line


def test_span_style_separate_opacities(spy):
    c = span_canvas()
    s = spy(c.spanStyleChanged)
    c.set_span_style("window", facecolor="#2ca02c", alpha=0.25, edgecolor="k", edge_alpha=0.9,
                     linewidth=2.0, linestyle="--")
    assert s.calls == [("window",)]
    for artist in [c.axes("flux").patches[0], c.axes("profile").patches[0]]:  # every panel
        assert artist.get_facecolor()[3] == pytest.approx(0.25)
        assert artist.get_edgecolor()[3] == pytest.approx(0.9)
    style = c.get_span_style("window")
    assert (style["alpha"], style["edge_alpha"], style["linestyle"]) == (0.25, 0.9, "--")
    c.set_span_style("window", alpha=0.5)                       # other keys stay
    assert c.get_span_style("window")["edge_alpha"] == 0.9


def test_span_style_errors():
    c = span_canvas()
    with pytest.raises(ValueError, match="not a span"):
        c.set_span_style("center", alpha=0.5)
    with pytest.raises(ValueError, match="unknown"):
        c.set_span_style("window", color="r")
    with pytest.raises(KeyError):
        c.get_span_style("nothing")
    with pytest.raises(ValueError, match="unknown"):
        c.set_span_style("band", center_color="r")              # band has no centre line
    with pytest.raises(ValueError, match="already belongs"):
        c.set_span_center("band", "center")
    with pytest.raises(ValueError, match="not a line"):
        c.set_span_center("window", "band")


def test_span_center_line():
    c = span_canvas()
    c.set_span_style("window", center_color="#00ff00", center_alpha=0.3, center_linewidth=2.0,
                     center_linestyle=":")
    for ax in (c.axes("flux"), c.axes("profile")):
        line = ax.lines[-1]
        assert mcolors.to_hex(line.get_color()) == "#00ff00" and line.get_alpha() == 0.3
        assert line.get_linewidth() == 2.0
    assert c.get_span_style("window")["alpha"] == 0.1           # the area is unchanged
    assert c.get_config() == {"markers": {"window": {"center_color": "#00ff00", "center_alpha": 0.3,
                                                     "center_linewidth": 2.0, "center_linestyle": ":"}}}
    c.remove_marker("center")
    assert "center_color" not in c.get_span_style("window")


def test_span_style_in_config(spy):
    c = span_canvas()
    changed = spy(c.configChanged)
    c.set_span_style("window", facecolor="#2ca02c", alpha=0.2)
    cfg = c.get_config()
    assert cfg == {"markers": {"window": {"facecolor": "#2ca02c", "alpha": 0.2}}}
    assert len(changed) == 0                                    # setters are silent

    other = span_canvas()
    other.set_config({"markers": {**cfg["markers"], "gone": {"alpha": 1},
                                  "center": {"alpha": 1}, "band": {"bad_key": 1}}})
    assert other.get_config() == cfg                            # unknown ids, lines and keys ignored


def test_span_reset_is_pixel_identical():
    c = span_canvas()
    c.set_marker_visible("window", True)
    before = pixels(c)
    c.set_span_style("window", facecolor="r", alpha=0.6, edge_alpha=1.0, linewidth=3,
                     center_color="k", center_linewidth=3)
    assert pixels(c) != before
    c.reset_config()
    assert c.get_config() == {}
    assert pixels(c) == before
    c.set_span_style("window", **c.default_span_style("window"))   # explicit default looks the same
    assert pixels(c) == before


def test_span_menu_entries():
    c = span_canvas()
    group = [a for a in c._axes.values() if a.panel_id == "flux"]
    texts = [a.text() for a in c._build_menu("flux", group, None).actions()]
    assert "Span style" in texts                                # two spans on this panel: a submenu
    group = [a for a in c._axes.values() if a.panel_id == "profile"]
    texts = [a.text() for a in c._build_menu("profile", group, None).actions()]
    assert texts.count("Window style…") == 1                    # one span: one entry, by name


def test_span_dialog_preview_and_cancel():
    from sciwidgets.plot._style_dialog import SpanStyleDialog

    seen = []
    c = span_canvas()
    dialog = SpanStyleDialog("Window", c.get_span_style("window"), c.default_span_style("window"),
                             preview=seen.append)
    assert seen == []                                           # filling the editors is no change
    dialog._edge_alpha.setValue(0.8)
    assert seen[-1]["edge_alpha"] == 0.8 and seen[-1]["alpha"] == 0.1
    dialog._line.setCurrentIndex(list(dialog._line.itemData(i) for i in range(dialog._line.count()))
                                 .index("None"))
    assert dialog.style()["linestyle"] == "None"
    dialog._c_width.setValue(1.5)
    assert seen[-1]["center_linewidth"] == 1.5
    c.set_span_style("window", **dialog.style())                # what the canvas does on OK
    assert c.get_span_style("window")["linestyle"] == "None"
    assert c.get_span_style("window")["center_linewidth"] == 1.5
    plain = SpanStyleDialog("Band", c.get_span_style("band"), c.default_span_style("band"))
    assert "center_color" not in plain.style()                 # no centre-line section


# ----- live preview in the curve and grid dialogs (0.8.1) -----

def test_curve_and_grid_dialog_preview():
    from sciwidgets.plot._style_dialog import CurveStyleDialog, GridStyleDialog

    seen = []
    c = make_canvas()
    dialog = CurveStyleDialog("F", c.get_curve_style("flux"), c.default_curve_style("flux"),
                              preview=seen.append)
    assert seen == []                                           # filling the editors is no change
    dialog._width.setValue(3.0)
    assert seen[-1]["linewidth"] == 3.0
    dialog._reset()
    assert seen[-1] == c.default_curve_style("flux")

    seen.clear()
    grid = GridStyleDialog(c.get_grid_style(), c.default_grid_style(), preview=seen.append)
    assert seen == []
    grid._alpha.setValue(0.8)
    assert seen[-1]["alpha"] == 0.8


@pytest.mark.parametrize("accept", [True, False])
def test_style_dialogs_ok_and_cancel(monkeypatch, accept):
    """The canvas previews each change and keeps it on OK, or puts the old style back on Cancel."""
    from PySide6.QtWidgets import QDialog

    import sciwidgets.plot.canvas as canvas_module

    def fake(cls, change):
        class Fake(cls):
            def exec(self):
                change(self)                                    # the user edits a field
                return QDialog.Accepted if accept else QDialog.Rejected
        return Fake

    c = make_canvas()
    previewed = {}

    def curve_change(d):
        d._width.setValue(4.0)
        previewed["curve"] = c.get_curve_style("flux")["linewidth"]

    def grid_change(d):
        d._width.setValue(2.5)
        previewed["grid"] = c.get_grid_style()["linewidth"]

    def span_change(d):
        d._alpha.setValue(0.7)
        previewed["span"] = c.get_span_style("window")["alpha"]

    monkeypatch.setattr(canvas_module, "CurveStyleDialog", fake(canvas_module.CurveStyleDialog, curve_change))
    monkeypatch.setattr(canvas_module, "GridStyleDialog", fake(canvas_module.GridStyleDialog, grid_change))
    monkeypatch.setattr(canvas_module, "SpanStyleDialog", fake(canvas_module.SpanStyleDialog, span_change))
    c._edit_style("flux")
    c._edit_grid_style()
    c._edit_span_style("window")
    assert previewed == {"curve": 4.0, "grid": 2.5, "span": 0.7}  # shown while the dialog is open
    if accept:
        assert c.get_curve_style("flux")["linewidth"] == 4.0
        assert c.get_grid_style()["linewidth"] == 2.5
        assert c.get_span_style("window")["alpha"] == 0.7
    else:
        assert c.get_config() == {}                             # Cancel: nothing changed


# ----- ScrollableFigure -----
def test_scrollable_figure_zoom():
    from matplotlib.figure import Figure

    from sciwidgets.plot import ScrollableFigure

    fig = Figure(figsize=(4, 2), dpi=100)
    sf = ScrollableFigure(fig)
    ratio = 1.0  # logical pixels = inches × the figure's own dpi, on any screen
    assert sf.figure is fig and sf.zoom() == (1.0, 1.0)
    assert sf.canvas_size() == (round(400 / ratio), round(200 / ratio))
    sf.set_zoom(2.0, 0.5)
    assert sf.zoom() == (2.0, 0.5)
    assert sf.canvas_size() == (round(800 / ratio), round(100 / ratio))
    assert tuple(fig.get_size_inches()) == (8.0, 1.0)
    sf.set_zoom(vertical=1.0)
    assert sf.zoom() == (2.0, 1.0)
    with pytest.raises(ValueError):
        sf.set_zoom(0)
    fig2 = Figure(figsize=(1, 1), dpi=100)
    sf.set_figure(fig2)
    assert sf.figure is fig2 and sf.zoom() == (2.0, 1.0)
    assert sf.canvas_size() == (round(200 / ratio), round(100 / ratio))
    sf.center()


def test_scrollable_figure_hidpi_dpi():
    """On a Retina screen Matplotlib doubles figure.dpi; the size must still use the original dpi."""
    from matplotlib.figure import Figure

    from sciwidgets.plot import ScrollableFigure

    fig = Figure(figsize=(12, 6), dpi=100)
    fig._original_dpi = 100
    sf = ScrollableFigure(fig)
    fig.dpi = 200  # what the Qt canvas does on a pixel ratio of 2
    sf.set_zoom(1.0, 1.0)
    assert sf.canvas_size() == (1200, 600)
    sf.show()
    assert sf.canvas_size() == (1200, 600)

