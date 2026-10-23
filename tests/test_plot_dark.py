"""Plots in light and dark mode: automatic dark colours, own dark colours, export in light."""

import matplotlib.colors as mcolors
import pytest
from PySide6.QtWidgets import QApplication

from sciwidgets.plot import PlotCanvas, dark_variant
from sciwidgets.colors import MIN_CONTRAST, TARGET_CONTRAST, contrast_ratio
from sciwidgets.style import set_color_scheme

DARK_BG = "#1e1e1e"


def make_canvas(**kwargs):
    return PlotCanvas({
        "figure": {"facecolor": "floralwhite", "dark_facecolor": "#2b2a27"},
        "layout": {"mosaic": [["flux"], ["profile"]], "sharex": True},
        "panels": {
            "flux": {"primary": "flux", "legend": {},
                     "curves": {"data": {"label": "d", "props": {"color": "k", "marker": "o", "linestyle": ""}},
                                "flux": {"label": "F", "props": {"color": "b"}},
                                "fit": {"label": "f", "props": {"color": "r", "dark_color": "#ffaaaa"}}}},
            "profile": {"curves": {"pump": {"label": "P", "props": {"color": "c"}}}},
        },
        "markers": {
            "window": {"kind": "vspan", "panels": "all", "at": [3, 5], "center": "center",
                       "props": {"color": "b", "alpha": 0.1}},
            "center": {"kind": "vline", "panels": "all", "at": 4, "props": {"color": "navy", "alpha": 0.6}},
        },
    }, **kwargs)


def pixels(canvas):
    canvas.draw()
    return bytes(canvas.buffer_rgba())


def hexes(color):
    return mcolors.to_hex(color)


# ----- the automatic dark colour -----

@pytest.mark.parametrize("color", ["k", "b", "navy", "darkred", "darkviolet", "#333333", "purple"])
def test_dark_variant_makes_dark_colours_readable(color):
    assert contrast_ratio(color, DARK_BG) < MIN_CONTRAST
    assert contrast_ratio(dark_variant(color, DARK_BG), DARK_BG) >= TARGET_CONTRAST


@pytest.mark.parametrize("color", ["r", "c", "orange", "yellowgreen", "#1f77b4", "white"])
def test_dark_variant_keeps_readable_colours(color):
    assert dark_variant(color, DARK_BG) == hexes(color)


def test_dark_variant_keeps_the_hue():
    h_in = mcolors.rgb_to_hsv(mcolors.to_rgb("navy"))[0]
    h_out = mcolors.rgb_to_hsv(mcolors.to_rgb(dark_variant("navy", DARK_BG)))[0]
    assert abs(h_in - h_out) < 0.08          # still blue (HSV hue differs a little from OKLCH hue)


# ----- the canvas -----

def test_dark_scheme_colours():
    c = make_canvas(scheme="dark")
    assert c.shows_dark()
    assert hexes(c.figure.get_facecolor()) == "#2b2a27"
    assert hexes(c.axes("flux").get_facecolor()) == DARK_BG
    assert c.curve_color("data") == dark_variant("k", DARK_BG)          # automatic
    assert c.curve_color("fit") == "#ffaaaa"                             # own dark colour
    assert c.curve_color("pump") == hexes("c")                            # readable: unchanged
    assert hexes(c.line("flux").get_color()) == c.curve_color("flux")
    # stored styles stay the light ones
    assert c.get_curve_style("data")["color"] == "#000000" and c.get_curve_style("data")["dark_color"] is None
    assert c.get_curve_style("fit")["dark_color"] == "#ffaaaa"
    span = c.get_span_style("window")
    assert span["facecolor"] == "#0000ff" and span["dark_facecolor"] is None and span["center_color"] == "#000080"
    face = c._markers["window"].artists[0].get_facecolor()
    assert hexes(face) == dark_variant("b", DARK_BG) and face[3] == pytest.approx(0.1)


def test_light_round_trip_is_pixel_identical():
    c = make_canvas(scheme="light")
    before = pixels(c)
    c.set_scheme("dark")
    assert c.shows_dark() and pixels(c) != before
    c.set_scheme("light")
    assert pixels(c) == before


def test_follows_the_application_palette(qapp):
    c = make_canvas()
    assert not c.shows_dark()
    try:
        set_color_scheme(qapp, "dark")
        QApplication.processEvents()
        QApplication.processEvents()
        assert c.shows_dark()
    finally:
        set_color_scheme(qapp, "system")
        QApplication.processEvents()
        QApplication.processEvents()
    assert not c.shows_dark()


def test_export_is_light_by_default(tmp_path):
    light = make_canvas(scheme="light")
    light.export(str(tmp_path / "light.png"))
    dark = make_canvas(scheme="dark")
    shown = pixels(dark)
    dark.export(str(tmp_path / "from_dark.png"))
    assert (tmp_path / "light.png").read_bytes() == (tmp_path / "from_dark.png").read_bytes()
    assert dark.shows_dark() and pixels(dark) == shown            # the screen stays dark
    dark.export(str(tmp_path / "dark.png"), scheme="current")
    assert (tmp_path / "dark.png").read_bytes() != (tmp_path / "light.png").read_bytes()
    with pytest.raises(ValueError):
        dark.export(str(tmp_path / "x.png"), scheme="dim")


def test_own_dark_colours_in_the_config():
    c = make_canvas(scheme="dark")
    assert c.get_config() == {}
    c.set_curve_style("flux", dark_color="#88ccff")
    c.set_span_style("window", dark_facecolor="#334455", dark_center_color="#ffff00")
    assert c.curve_color("flux") == "#88ccff"
    config = c.get_config()
    assert config["curves"]["flux"] == {"dark_color": "#88ccff"}
    assert config["markers"]["window"] == {"dark_facecolor": "#334455", "dark_center_color": "#ffff00"}
    other = make_canvas(scheme="dark")
    other.set_config(config)
    assert other.get_config() == config and other.curve_color("flux") == "#88ccff"
    other.set_curve_style("flux", dark_color=None)                      # back to automatic
    assert other.curve_color("flux") == dark_variant("b", DARK_BG)
    other.reset_config()
    assert other.get_config() == {}


def test_bad_scheme():
    with pytest.raises(ValueError):
        make_canvas(scheme="dim")
    with pytest.raises(ValueError):
        make_canvas().set_scheme("dim")
