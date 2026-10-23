"""sciwidgets.devtools: the player's actions and the file names."""

import time

from PySide6.QtWidgets import QMainWindow, QVBoxLayout, QWidget

from sciwidgets.devtools import Gif, Player, Shot, _file
from sciwidgets.params import FloatSlider


def play(app, win, script, record=False):
    finished = []
    player = Player(app, win, record=record)
    player.run(script, lambda: finished.append(True))
    end = time.time() + 20
    while not finished and time.time() < end:
        app.processEvents()
        time.sleep(0.01)
    assert finished
    return player


def test_drag_slider_and_record(qapp):
    win = QMainWindow()
    box = QWidget()
    slider = FloatSlider(label="a", min_val=0.0, max_val=10.0, init_val=2.0, val_fmt="{:.1f}")
    QVBoxLayout(box).addWidget(slider)
    win.setCentralWidget(box)
    win.resize(500, 120)
    win.show()
    seen = []
    slider.valueChanged.connect(seen.append)

    def script(p):
        yield from p.drag_slider(slider, 8.0, 0.3)

    player = play(qapp, win, script, record=True)
    assert abs(slider.get_value() - 8.0) < 0.6 and seen       # moved like a user, signal sent
    assert len(player.frames) > 3                              # frames were recorded
    win.close()


def test_file_names():
    assert _file("plot", Shot("x")) == "plot.png"
    assert _file("plot", Shot("x"), dark=True) == "plot_dark.png"
    assert _file("plot", Shot("x", file="plot_demo.png"), dark=True) == "plot_demo_dark.png"
    assert _file("tour", Gif("x", lambda p: None)) == "tour.gif"
