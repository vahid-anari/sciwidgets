"""PySide6 widgets for scientific desktop apps."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("sciwidgets")
except PackageNotFoundError:
    __version__ = "0+unknown"