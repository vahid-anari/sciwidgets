"""Main-window helpers: declarative menu bar, status bar, screen placement."""

from .menu_bar import MenuBarController, MenuSpec
from .screen import center_on_screen
from .status_bar import StatusBarController

__all__ = ["MenuBarController", "MenuSpec", "StatusBarController", "center_on_screen"]
