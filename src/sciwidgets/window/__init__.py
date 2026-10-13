"""Main-window helpers: declarative menu bar and status bar."""

from .menu_bar import MenuBarController, MenuSpec
from .status_bar import StatusBarController

__all__ = ["MenuBarController", "MenuSpec", "StatusBarController"]