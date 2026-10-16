"""Start-up splash screen: a picture with the app name drawn on it, and messages."""

from __future__ import annotations

import time
from pathlib import Path
from typing import ClassVar, Optional, Tuple, Union

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QSplashScreen, QWidget

ColorLike = Union[QColor, Qt.GlobalColor, str]


def _scaled_pixmap(image: Union[str, Path, QPixmap], size: Tuple[int, int], dpr: float) -> QPixmap:
    """Return ``image`` filled into ``size`` (cropped to its centre if needed), sharp at ``dpr``."""
    pixmap = image if isinstance(image, QPixmap) else QPixmap(str(image))
    if pixmap.isNull():
        raise ValueError(f"Cannot load the splash image: {image!r}")
    w, h = round(size[0] * dpr), round(size[1] * dpr)
    scaled = pixmap.scaled(w, h, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
    x, y = (scaled.width() - w) // 2, (scaled.height() - h) // 2
    result = scaled.copy(x, y, w, h)
    result.setDevicePixelRatio(dpr)
    return result


def _draw_title(
    pixmap: QPixmap,
    title: str,
    subtitle: str,
    family: str,
    title_color: QColor,
    subtitle_color: QColor,
) -> None:
    """Draw the title (one line per ``\\n``) and the subtitle at the top left.

    Sizes and positions are fractions of the image height, so the layout looks
    the same at any splash size.
    """
    if not title and not subtitle:
        return
    dpr = pixmap.devicePixelRatio()
    h = pixmap.height() / dpr
    x = 0.054 * pixmap.width() / dpr
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.TextAntialiasing)
    font = QFont(family)
    font.setPixelSize(round(0.108 * h))
    painter.setFont(font)
    painter.setPen(title_color)
    y = 0.095 * h
    line_step = 0.127 * h
    for line in title.splitlines():
        y += line_step * (0.82 if y < 0.1 * h else 1.0)
        painter.drawText(round(x), round(y), line)
    if subtitle:
        font.setPixelSize(round(0.048 * h))
        painter.setFont(font)
        painter.setPen(subtitle_color)
        painter.drawText(round(x + 0.003 * h), round(y + 0.105 * h), subtitle)
    painter.end()


class SplashScreen(QSplashScreen):
    """A splash screen with the app's name drawn on a picture, and start-up messages.

    The title and subtitle are drawn by the widget, so a new version or name
    never needs a new picture. Messages appear at the bottom; call
    :meth:`show_message`, or :func:`splash_message` from anywhere in the app.

    Args:
        image: Picture file or ``QPixmap``. It fills ``size``; if its shape
            differs, the centre is kept.
        size: Shown size ``(width, height)`` in screen points. The picture is
            scaled for the screen's pixel ratio, so it stays sharp on Retina.
        title: Text at the top left, one line per ``\\n`` (e.g. the app name).
        subtitle: Smaller text below the title (e.g. the version).
        font_family: Font for title, subtitle and messages; default: the
            application's font.
        title_color: Colour of the title (default white).
        subtitle_color: Colour of the subtitle (default light blue).
        message_color: Colour of the messages (default white).
        message_font_size: Point size of the messages.
        message_alignment: Where messages appear (default bottom centre).
        delay: Seconds each message stays before the app continues; useful to
            make quick start-ups readable. Default 0.
        click_to_close: Whether a click closes the splash (default ``False``).
        stay_on_top: Keep the splash above other windows (default ``True``).
        show: Show the splash right away (default ``True``).

    Raises:
        RuntimeError: If no ``QApplication`` exists yet.
        ValueError: If the picture cannot be loaded.
    """

    _current: ClassVar[Optional["SplashScreen"]] = None

    def __init__(
        self,
        image: Union[str, Path, QPixmap],
        *,
        size: Tuple[int, int] = (560, 315),
        title: str = "",
        subtitle: str = "",
        font_family: Optional[str] = None,
        title_color: ColorLike = Qt.white,
        subtitle_color: ColorLike = QColor(200, 225, 255),
        message_color: ColorLike = Qt.white,
        message_font_size: int = 15,
        message_alignment: Qt.AlignmentFlag = Qt.AlignBottom | Qt.AlignHCenter,
        delay: float = 0.0,
        click_to_close: bool = False,
        stay_on_top: bool = True,
        show: bool = True,
    ) -> None:
        app = QApplication.instance()
        if app is None:
            raise RuntimeError("Create the QApplication before the SplashScreen")
        family = font_family or app.font().family()
        pixmap = _scaled_pixmap(image, size, app.devicePixelRatio())
        _draw_title(pixmap, title, subtitle, family, QColor(title_color), QColor(subtitle_color))
        super().__init__(pixmap)
        self._message_color = QColor(message_color)
        self._message_alignment = message_alignment
        self._delay = float(delay)
        self._click_to_close = click_to_close
        self.setFont(QFont(family, message_font_size))
        if stay_on_top:
            self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        SplashScreen._current = self
        if show:
            self.show()
            self.raise_()
            self.activateWindow()
            app.processEvents()

    @classmethod
    def current(cls) -> Optional["SplashScreen"]:
        """The splash being shown, or ``None`` before it was made or after :meth:`finish`."""
        return cls._current

    def show_message(self, text: str) -> None:
        """Show ``text`` at the bottom of the splash right away.

        Then waits ``delay`` seconds, if one was given.
        """
        self.showMessage(text, alignment=self._message_alignment, color=self._message_color)
        QApplication.processEvents()
        if self._delay > 0:
            time.sleep(self._delay)

    def finish(self, window: QWidget) -> None:
        """Close the splash once ``window`` is shown, and forget it."""
        super().finish(window)
        if SplashScreen._current is self:
            SplashScreen._current = None

    def mousePressEvent(self, event) -> None:
        """Ignore clicks unless ``click_to_close`` is set."""
        if self._click_to_close:
            super().mousePressEvent(event)
        else:
            event.accept()


def splash_message(text: str) -> None:
    """Show ``text`` on the current splash screen; does nothing if there is none.

    Lets any part of an app report start-up progress without passing the
    splash around.
    """
    splash = SplashScreen.current()
    if splash is not None:
        splash.show_message(text)
