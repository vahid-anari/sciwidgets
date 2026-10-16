"""Demo for the splash subpackage: ``python -m sciwidgets.splash``."""

import sys

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QLabel, QMainWindow

from sciwidgets.splash import SplashScreen, splash_message


def _demo_image() -> QPixmap:
    """A navy-to-blue gradient, so the demo needs no picture file."""
    pixmap = QPixmap(1600, 900)
    gradient = QLinearGradient(0, 900, 1600, 0)
    gradient.setColorAt(0.0, QColor("#06173a"))
    gradient.setColorAt(0.6, QColor("#174a87"))
    gradient.setColorAt(1.0, QColor("#5b8fc9"))
    painter = QPainter(pixmap)
    painter.fillRect(pixmap.rect(), gradient)
    painter.end()
    return pixmap


def _demo_main() -> int:
    """Show the splash with a few messages, then a main window.

    Returns:
        int: Qt application exit code.
    """
    app = QApplication(sys.argv)
    splash = SplashScreen(
        _demo_image(),
        size=(560, 315),
        title="sciwidgets\nSplash",
        subtitle="Demo",
        delay=0.6,
    )
    win = QMainWindow()
    win.setWindowTitle("Main window")
    win.setCentralWidget(QLabel("Started.", alignment=Qt.AlignCenter))
    win.resize(400, 200)

    steps = ["Starting...", "Loading settings...", "Building the window...", "Done."]

    def run(i: int = 0) -> None:
        splash_message(steps[i])
        if i + 1 < len(steps):
            QTimer.singleShot(0, lambda: run(i + 1))
        else:
            win.show()
            splash.finish(win)

    QTimer.singleShot(0, run)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(_demo_main())
