"""Tests for sciwidgets.splash."""

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import QWidget

from sciwidgets.splash import SplashScreen, splash_message


def _image(width=320, height=180, color="#174a87"):
    pixmap = QPixmap(width, height)
    pixmap.fill(QColor(color))
    return pixmap


@pytest.fixture(autouse=True)
def _forget_current():
    yield
    current = SplashScreen.current()
    if current is not None:
        current.finish(QWidget())


def test_size_and_crop():
    splash = SplashScreen(_image(400, 100), size=(160, 90), show=False)
    pm = splash.pixmap()
    dpr = pm.devicePixelRatio()
    assert (round(pm.width() / dpr), round(pm.height() / dpr)) == (160, 90)


def test_title_is_drawn():
    plain = SplashScreen(_image(), size=(320, 180), show=False).pixmap().toImage()
    titled = SplashScreen(_image(), size=(320, 180), title="Name\nApp", subtitle="Version 1",
                          show=False).pixmap().toImage()
    assert plain != titled
    # the text is at the top left; the bottom right stays the picture
    corner = titled.pixelColor(titled.width() - 2, titled.height() - 2)
    assert corner == QColor("#174a87")


def test_image_from_file(tmp_path):
    path = tmp_path / "art.png"
    _image().save(str(path))
    splash = SplashScreen(path, size=(160, 90), show=False)
    assert not splash.pixmap().isNull()


def test_missing_image():
    with pytest.raises(ValueError, match="Cannot load"):
        SplashScreen("does/not/exist.png", show=False)


def test_messages():
    splash = SplashScreen(_image(), show=False)
    splash.show_message("Loading...")
    assert splash.message() == "Loading..."
    splash_message("Almost done")
    assert splash.message() == "Almost done"


def test_current_and_finish():
    splash = SplashScreen(_image(), show=False)
    assert SplashScreen.current() is splash
    splash.finish(QWidget())
    assert SplashScreen.current() is None


def test_splash_message_without_splash():
    assert SplashScreen.current() is None
    splash_message("nobody listens")  # no error


def test_options():
    splash = SplashScreen(_image(), font_family="Times New Roman", message_font_size=12,
                          stay_on_top=False, show=False)
    assert splash.font().pointSize() == 12
    assert not splash.windowFlags() & Qt.WindowStaysOnTopHint
