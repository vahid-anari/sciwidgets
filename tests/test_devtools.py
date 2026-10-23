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


def test_gif_keeps_the_colours_of_late_frames(qapp, tmp_path):
    """Light frames, then dark frames with a red mark: the red stays red (one palette for all frames)."""
    from PIL import Image
    from PySide6.QtGui import QColor, QImage
    from sciwidgets.devtools import save_gif

    def frame(background, mark=None):
        image = QImage(120, 80, QImage.Format_RGB32)
        image.fill(QColor(background))
        if mark:
            for x in range(40, 80):
                for y in range(30, 50):
                    image.setPixelColor(x, y, QColor(mark))
        return image

    frames = [frame("#f0f0f0", "#202020")] * 12 + [frame("#1e1e1e", "#ec6a5a")] * 12
    out = tmp_path / "anim.gif"
    save_gif(frames, out, 120)
    with Image.open(out) as gif:
        gif.seek(gif.n_frames - 1)
        r, g, b = gif.convert("RGB").getpixel((60, 40))
    assert abs(r - 0xec) < 12 and abs(g - 0x6a) < 12 and abs(b - 0x5a) < 12
