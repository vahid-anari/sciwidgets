"""Read-only table model over a pandas DataFrame."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Union

import pandas as pd
from pandas.api.types import is_numeric_dtype
from PySide6.QtCore import QAbstractTableModel, QModelIndex, QObject, Qt
from PySide6.QtGui import QBrush, QColor

Formatter = Union[str, Callable[[Any], str]]
Color = Union[str, QColor]
Backgrounds = Union[Dict[str, Color], Callable[[str], Optional[Color]]]
Alignments = Union[Dict[str, str], Callable[[str], Optional[str]]]
RowColors = Callable[[pd.Series], Optional[Color]]
_ALIGN = {
    "left": int(Qt.AlignLeft | Qt.AlignVCenter),
    "center": int(Qt.AlignHCenter | Qt.AlignVCenter),
    "right": int(Qt.AlignRight | Qt.AlignVCenter),
}


class DataFrameModel(QAbstractTableModel):
    """Show a DataFrame in a ``QTableView``.

    The model is read-only. Values are displayed with ``str(value)`` unless a
    format is given for the column; cells of numeric columns, and of columns
    with a format, are right-aligned.

    Args:
        df: Data to show.
        formats: Per-column display format: a format string such as
            ``"{:,.3f}"`` or a callable taking the value and returning text.
        backgrounds: Per-column background: a ``{column: color}`` dict or a
            callable taking the column name and returning a color (or ``None``
            for the default background).
        text_colors: Per-column text color, same forms as ``backgrounds``.
        row_backgrounds: Callable taking a row (``pandas.Series``) and
            returning its background color or ``None``. It wins over the
            column defaults; a colour the user set on a column wins over it.
        alignments: Per-column text alignment, ``"left"``, ``"center"`` or
            ``"right"``, as a dict or a callable taking the column name
            (``None`` keeps the rule: right for numeric columns and columns
            with a format, left otherwise).
        headers: Per-column header text; the column name by default.
        parent: Optional parent object.
    """

    def __init__(
            self,
            df: pd.DataFrame,
            *,
            formats: Optional[Dict[str, Formatter]] = None,
            backgrounds: Optional[Backgrounds] = None,
            text_colors: Optional[Backgrounds] = None,
            row_backgrounds: Optional[RowColors] = None,
            alignments: Optional[Alignments] = None,
            headers: Optional[Dict[str, str]] = None,
            parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._formats: Dict[str, Callable[[Any], str]] = {}
        for col, fmt in (formats or {}).items():
            self._formats[col] = fmt.format if isinstance(fmt, str) else fmt
        self._defaults = {"background": backgrounds or {}, "text": text_colors or {}}
        self._row_backgrounds = row_backgrounds
        self._row_brushes: Dict[int, Optional[QBrush]] = {}
        self._alignments = alignments or {}
        self._alignment_overrides: Dict[str, str] = {}
        self._headers = dict(headers or {})
        self._brush_cache: Dict[str, Dict[str, Optional[QBrush]]] = {"background": {}, "text": {}}
        self._overrides: Dict[str, Dict[str, Optional[str]]] = {"background": {}, "text": {}}
        self._df = pd.DataFrame()
        self._columns: List[str] = []
        self._alignment: List[int] = []
        self.set_frame(df)

    # ----- data -----
    def set_frame(self, df: pd.DataFrame) -> None:
        """Replace the data; formats, backgrounds and headers are kept."""
        self.beginResetModel()
        self._df = df
        self._columns = [str(c) for c in df.columns]
        self._alignment = [self._column_alignment(col, df[c]) for col, c in zip(self._columns, df.columns)]
        self._row_brushes = {}
        for cache in self._brush_cache.values():
            cache.clear()
        self.endResetModel()

    def frame(self) -> pd.DataFrame:
        """Return the DataFrame shown by the model."""
        return self._df

    def columns(self) -> List[str]:
        """Return the column names as strings, in model order."""
        return list(self._columns)

    # ----- sorting -----
    def sort(self, column: int, order: Qt.SortOrder = Qt.AscendingOrder) -> None:
        """Sort the rows by a column (called by the view when the user clicks a header).

        A text column whose values are all numbers (e.g. a CSV read with ``dtype=str``) is sorted numerically.
        """
        if not 0 <= column < len(self._columns) or not len(self._df):
            return
        name = self._df.columns[column]
        key = None
        if not is_numeric_dtype(self._df[name]):
            numeric = pd.to_numeric(self._df[name], errors="coerce")
            if numeric.notna().all():
                key = lambda s: pd.to_numeric(s, errors="coerce")  # noqa: E731 - text that is all numbers
        self.beginResetModel()
        self._df = self._df.sort_values(by=name, ascending=order == Qt.AscendingOrder, kind="stable", key=key)
        self._row_brushes = {}
        self.endResetModel()

    # ----- colors -----
    def set_column_color(self, column: str, color: Optional[Color], *, kind: str = "background") -> None:
        """Override a color of ``column``; ``None`` means no background (or the palette's text color).

        Args:
            column: Column name.
            color: New color, or ``None``.
            kind: ``"background"`` or ``"text"``.
        """
        self._check(column, kind)
        self._overrides[kind][column] = None if color is None else QColor(color).name()
        self._brush_cache[kind].pop(column, None)
        self._emit_column_changed(column)

    def restore_column_color(self, column: str, *, kind: str = "background") -> None:
        """Drop the override of ``column``; the default given to the constructor shows again."""
        self._check(column, kind)
        self._overrides[kind].pop(column, None)
        self._brush_cache[kind].pop(column, None)
        self._emit_column_changed(column)

    def column_color(self, column: str, *, kind: str = "background") -> Optional[str]:
        """Return the effective color of ``column`` as ``#rrggbb``, or ``None``."""
        self._check(column, kind)
        brush = self._brush(kind, column)
        return brush.color().name() if brush is not None else None

    def column_overrides(self, *, kind: str = "background") -> Dict[str, Optional[str]]:
        """Return the user colors set with ``set_column_color`` (``None`` = no color)."""
        return dict(self._overrides[kind])

    def reset_colors(self) -> None:
        """Drop every color set with ``set_column_color`` (backgrounds and text)."""
        changed = set()
        for kind in self._overrides:
            changed.update(self._overrides[kind])
            self._overrides[kind].clear()
            self._brush_cache[kind].clear()
        for col in changed:
            self._emit_column_changed(col)

    # ----- alignment -----
    def set_column_alignment(self, column: str, alignment: Optional[str]) -> None:
        """Override the alignment of ``column`` (``"left"``, ``"center"``, ``"right"``; ``None`` = default)."""
        if column not in self._columns:
            raise KeyError(column)
        if alignment is None:
            self._alignment_overrides.pop(column, None)
        elif alignment in _ALIGN:
            self._alignment_overrides[column] = alignment
        else:
            raise ValueError(f"alignment must be 'left', 'center' or 'right', not {alignment!r}")
        i = self._columns.index(column)
        self._alignment[i] = self._column_alignment(column, self._df.iloc[:, i])
        if len(self._df):
            self.dataChanged.emit(self.index(0, i), self.index(len(self._df) - 1, i), [Qt.TextAlignmentRole])

    def column_alignment(self, column: str) -> str:
        """Return the effective alignment of ``column``: ``"left"``, ``"center"`` or ``"right"``."""
        if column not in self._columns:
            raise KeyError(column)
        value = self._alignment[self._columns.index(column)]
        return next(name for name, flags in _ALIGN.items() if flags == value)

    def alignment_overrides(self) -> Dict[str, str]:
        """Return the alignments set with ``set_column_alignment``."""
        return dict(self._alignment_overrides)

    def _check(self, column: str, kind: str) -> None:
        if kind not in self._overrides:
            raise ValueError(f"kind must be 'background' or 'text', not {kind!r}")
        if column not in self._columns:
            raise KeyError(column)

    def _emit_column_changed(self, column: str) -> None:
        if column in self._columns and len(self._df):
            i = self._columns.index(column)
            self.dataChanged.emit(self.index(0, i), self.index(len(self._df) - 1, i),
                                  [Qt.BackgroundRole, Qt.ForegroundRole])

    # ----- QAbstractTableModel -----
    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self._df)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self._columns)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        if not index.isValid():
            return None
        col = self._columns[index.column()]
        if role == Qt.DisplayRole:
            value = self._df.iat[index.row(), index.column()]
            fmt = self._formats.get(col)
            return fmt(value) if fmt else str(value)
        if role == Qt.TextAlignmentRole:
            return self._alignment[index.column()]
        if role == Qt.BackgroundRole:
            if self._row_backgrounds is not None and col not in self._overrides["background"]:
                row_brush = self._row_brush(index.row())
                if row_brush is not None:
                    return row_brush
            return self._brush("background", col)
        if role == Qt.ForegroundRole:
            return self._brush("text", col)
        return None

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole) -> Any:
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            col = self._columns[section]
            return self._headers.get(col, col)
        return str(section + 1)

    # ----- helpers -----
    def _column_alignment(self, col: str, series: pd.Series) -> int:
        wanted = self._alignment_overrides.get(col)
        if wanted is None:
            wanted = self._alignments(col) if callable(self._alignments) else self._alignments.get(col)
        if wanted is None:
            wanted = "right" if col in self._formats or is_numeric_dtype(series) else "left"
        if wanted not in _ALIGN:
            raise ValueError(f"alignment of column {col!r} must be 'left', 'center' or 'right', not {wanted!r}")
        return _ALIGN[wanted]

    def _row_brush(self, row: int) -> Optional[QBrush]:
        if row not in self._row_brushes:
            color = self._row_backgrounds(self._df.iloc[row])
            self._row_brushes[row] = QBrush(QColor(color)) if color is not None else None
        return self._row_brushes[row]

    def _brush(self, kind: str, col: str) -> Optional[QBrush]:
        cache = self._brush_cache[kind]
        if col not in cache:
            overrides, defaults = self._overrides[kind], self._defaults[kind]
            if col in overrides:
                color = overrides[col]
            elif callable(defaults):
                color = defaults(col)
            else:
                color = defaults.get(col)
            cache[col] = QBrush(QColor(color)) if color is not None else None
        return cache[col]
