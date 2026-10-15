"""Shared test setup: a headless QApplication with the sciwidgets style, mathtext labels."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("MPLBACKEND", "Agg")

import pytest
from PySide6.QtWidgets import QApplication

from sciwidgets.labels import set_latex_enabled
from sciwidgets.style import apply_sci_style

set_latex_enabled(False)  # fast and independent of a local LaTeX installation


@pytest.fixture(scope="session", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    apply_sci_style(app)
    yield app


class Spy:
    """Record the arguments of every emission of a Qt signal."""

    def __init__(self, signal):
        self.calls = []
        signal.connect(lambda *args: self.calls.append(args))

    def __len__(self):
        return len(self.calls)


@pytest.fixture
def spy():
    return Spy
