"""The showcase window (``python -m sciwidgets``) builds and follows its panel."""

import numpy as np

from sciwidgets.__main__ import Showcase


def test_showcase_follows_the_panel(qapp):
    win = Showcase(qapp)
    canvas = win.canvas
    win.panel.set_value({"pulse.a": 3.0, "display.unit": "mJy"})
    win.update_plot()
    model = canvas.line("model").get_ydata()
    assert np.isclose(model.max(), 1000 * (3.0 + 2.0), rtol=1e-3)     # in mJy now
    win.panel.set_value({"display.window": {"range": (10.0, 20.0)}})
    win.update_plot()
    assert tuple(canvas.get_marker("window")) == (10.0, 20.0)
    win.on_menu("File", "reset", False)
    assert win.panel.get_value()["pulse.a"] == 1.0
    win.close()
