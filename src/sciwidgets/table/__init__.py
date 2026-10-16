"""Table widgets for pandas DataFrames (needs the ``table`` extra: ``pip install sciwidgets[table]``)."""

try:
    import pandas  # noqa: F401
except ImportError as exc:  # pragma: no cover - depends on the environment
    raise ImportError("sciwidgets.table needs pandas: pip install sciwidgets[table]") from exc

from .model import DataFrameModel
from .view import DataFrameView

__all__ = ["DataFrameModel", "DataFrameView"]
