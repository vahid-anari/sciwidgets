"""QTableView with a DataFrameModel, column chooser and CSV export."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Union

import pandas as pd
from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontDatabase, QFontInfo, QPalette
from PySide6.QtWidgets import QColorDialog, QFontDialog, QMenu, QTableView, QWidget

from ._delegate import RichTextDelegate
from ._dialogs import ChooseColumnsDialog
from ._header import RichHeaderView
from .model import DataFrameModel


class DataFrameView(QTableView):
    """Table view for a DataFrame.

    ``set_frame`` builds a :class:`DataFrameModel` and resizes the columns to
    their contents. Columns can be hidden with ``set_visible_columns`` or by
    the user through ``choose_columns``; ``visible_frame`` and ``export_csv``
    use only the visible columns.

    A click on a column header sorts the rows by that column (``sortable``).
    A right-click opens a menu: column color, no column color, default column
    color, text color, hide this column, choose columns, reset colors, font. Header
    texts and formatted values may be HTML (``<sup>``,
    ``<sub>``, ``&tau;``, ``<br>``), e.g. ``pretty_sci_text(v)`` as a format;
    plain header texts use ``\\n`` for line breaks. What the
    user changes there is returned by ``get_config`` so the app can store it
    (the view keeps no settings itself) and restored with ``set_config``.

    Signals:
        visibleColumnsChanged(list): The user changed the visible columns
            (chooser dialog or "Hide this column"; not ``set_visible_columns``).
        configChanged(dict): The user changed colors or visible columns;
            carries ``get_config()``.
        headerMenuRequested(QMenu, str): The header menu is about to open
            for the named column; connect to add app-specific actions.
    """

    visibleColumnsChanged = Signal(list)
    configChanged = Signal(dict)
    headerMenuRequested = Signal(QMenu, str)

    def __init__(
            self, parent: Optional[QWidget] = None, *, header_padding: int = 12, sortable: bool = True
    ) -> None:
        """
        Args:
            parent: Optional parent widget.
            header_padding: Space in pixels left around the header text, on
                every side; also the minimum extra width of a column beyond
                its header text.
            sortable: Whether a click on a header sorts the rows by that
                column (a second click reverses the order).
        """
        super().__init__(parent)
        self._model: Optional[DataFrameModel] = None
        self._visible: Optional[List[str]] = None
        self._header_padding = int(header_padding)
        self._pending: Dict[str, Dict[str, Optional[str]]] = {"background": {}, "text": {}}
        self._font_key: Optional[str] = None
        self._table_font: Optional[QFont] = None
        header = RichHeaderView(self)
        self.setHorizontalHeader(header)
        self.setItemDelegate(RichTextDelegate(self))
        header.setContextMenuPolicy(Qt.CustomContextMenu)
        header.customContextMenuRequested.connect(self._show_header_menu)
        header.setSectionsClickable(True)
        header.setSortIndicator(-1, Qt.AscendingOrder)
        self.setSortingEnabled(sortable)
        self._fit_rows()

    # ----- data -----
    def set_frame(self, df: pd.DataFrame, **model_kwargs: Any) -> None:
        """Show ``df``; keyword arguments go to :class:`DataFrameModel`.

        Columns hidden before stay hidden if they still exist.
        """
        if self._model is not None:
            for kind in self._pending:
                self._pending[kind].update(self._model.column_overrides(kind=kind))
        self._model = DataFrameModel(df, **model_kwargs, parent=self)
        self.setModel(self._model)
        columns = self._model.columns()
        for kind, overrides in self._pending.items():
            for col, color in overrides.items():
                if col in columns:
                    self._model.set_column_color(col, color, kind=kind)
        self._apply_visibility()
        header = self.horizontalHeader()
        if self.isSortingEnabled() and 0 <= header.sortIndicatorSection() < self._model.columnCount():
            self._model.sort(header.sortIndicatorSection(), header.sortIndicatorOrder())
        self.resizeColumnsToContents()
        self._fit_headers()

    def frame(self) -> Optional[pd.DataFrame]:
        """Return the full DataFrame, or ``None`` before ``set_frame``."""
        return self._model.frame() if self._model is not None else None

    def model_(self) -> Optional[DataFrameModel]:
        """Return the DataFrameModel (``model()`` is the Qt base method)."""
        return self._model

    # ----- visible columns -----
    def set_visible_columns(self, columns: Optional[Iterable[str]]) -> None:
        """Show only ``columns`` (``None`` = all); the column order is kept."""
        self._visible = None if columns is None else list(columns)
        self._apply_visibility()

    def visible_columns(self) -> List[str]:
        """Return the names of the visible columns, in model order."""
        if self._model is None:
            return [] if self._visible is None else list(self._visible)
        cols = self._model.columns()
        if self._visible is None:
            return cols
        wanted = set(self._visible)
        return [c for c in cols if c in wanted]

    def choose_columns(self) -> bool:
        """Open the column chooser; return ``True`` if the selection changed."""
        if self._model is None:
            return False
        dlg = ChooseColumnsDialog(self._model.columns(), self.visible_columns(), self)
        if not dlg.exec():
            return False
        selected = dlg.selected()
        if selected == self.visible_columns():
            return False
        self._user_set_visible(selected)
        return True

    # ----- colors -----
    def set_column_color(self, column: str, color: Optional[Union[str, QColor]], *, kind: str = "background") -> None:
        """Override a color of ``column`` (``None`` = no background / palette text color); silent.

        ``kind`` is ``"background"`` or ``"text"``.
        """
        if self._model is None:
            self._pending[kind][column] = None if color is None else QColor(color).name()
            return
        self._model.set_column_color(column, color, kind=kind)

    def restore_column_color(self, column: str, *, kind: str = "background") -> None:
        """Drop the override of ``column`` so the app's default shows again; silent."""
        if self._model is None:
            self._pending[kind].pop(column, None)
            return
        self._model.restore_column_color(column, kind=kind)

    def column_color(self, column: str, *, kind: str = "background") -> Optional[str]:
        """Return the effective color of ``column`` as ``#rrggbb``, or ``None``."""
        return self._model.column_color(column, kind=kind) if self._model is not None else None

    def reset_colors(self) -> None:
        """Drop the user colors (backgrounds and text); silent."""
        for pending in self._pending.values():
            pending.clear()
        if self._model is not None:
            self._model.reset_colors()

    def _overrides(self, kind: str) -> Dict[str, Optional[str]]:
        return self._model.column_overrides(kind=kind) if self._model is not None else dict(self._pending[kind])

    # ----- font -----
    def set_table_font(self, font: Optional[QFont]) -> None:
        """Use ``font`` for cells and headers (``None`` = the application font); silent."""
        if font is None:
            self._font_key = None
            self._table_font = None
            self.setFont(QFont())
        else:
            self._font_key = font.toString()
            self._table_font = QFont(font)
            self.setFont(font)
        self.horizontalHeader().setFont(self.font())
        self.verticalHeader().setFont(self.font())
        self._fit_rows()
        if self._model is not None:
            self.resizeColumnsToContents()
            self._fit_headers()

    def table_font(self) -> Optional[QFont]:
        """Return the font set with ``set_table_font``, or ``None`` for the application font."""
        return QFont(self._table_font) if self._table_font is not None else None

    # ----- config -----
    def get_config(self) -> Dict[str, Any]:
        """Return what the user may have changed: user colors, visible columns and font."""
        return {
            "backgrounds": self._overrides("background"),
            "text_colors": self._overrides("text"),
            "visible_columns": None if self._visible is None else list(self._visible),
            "font": self._font_key,
        }

    def set_config(self, config: Dict[str, Any]) -> None:
        """Restore a ``get_config`` result; unknown keys are ignored; silent."""
        if "font" in config:
            key = config["font"]
            font = None
            if key:
                font = QFont()
                if not font.fromString(key):
                    font = None
            self.set_table_font(font)
        if "backgrounds" in config or "text_colors" in config:
            self.reset_colors()
            for key, kind in (("backgrounds", "background"), ("text_colors", "text")):
                for col, color in (config.get(key) or {}).items():
                    try:
                        self.set_column_color(col, color, kind=kind)
                    except KeyError:
                        pass
        if "visible_columns" in config:
            self.set_visible_columns(config["visible_columns"])

    def visible_frame(self) -> Optional[pd.DataFrame]:
        """Return the DataFrame restricted to the visible columns."""
        if self._model is None:
            return None
        df = self._model.frame()
        return df[[c for c in df.columns if str(c) in set(self.visible_columns())]]

    def export_csv(self, path: Union[str, Path], **to_csv_kwargs: Any) -> None:
        """Write the visible columns to ``path`` (``index=False`` by default)."""
        df = self.visible_frame()
        if df is None:
            raise RuntimeError("no data to export")
        to_csv_kwargs.setdefault("index", False)
        df.to_csv(path, **to_csv_kwargs)

    def set_header_padding(self, pixels: int) -> None:
        """Change the space around the header text and refit the header."""
        self._header_padding = int(pixels)
        if self._model is not None:
            self._fit_headers()

    def header_padding(self) -> int:
        """Return the space around the header text, in pixels."""
        return self._header_padding

    # ----- header menu -----
    def _show_header_menu(self, pos: QPoint) -> None:
        if self._model is None:
            return
        header = self.horizontalHeader()
        index = header.logicalIndexAt(pos)
        if index < 0:
            return
        menu = self.header_menu(self._model.columns()[index])
        menu.exec(header.mapToGlobal(pos))

    def header_menu(self, column: str) -> QMenu:
        """Build the header context menu for ``column`` (emits ``headerMenuRequested``)."""
        menu = QMenu(self)
        menu.addAction("Column Color…", lambda: self._pick_color(column))
        overrides = self._model.column_overrides()
        none = menu.addAction("No Column Color", lambda: self._user_set_color(column, None))
        none.setEnabled(not (column in overrides and overrides[column] is None))
        default = menu.addAction("Default Column Color", lambda: self._user_restore_color(column))
        default.setEnabled(column in overrides)
        menu.addSeparator()
        menu.addAction("Text Color…", lambda: self._pick_color(column, kind="text"))
        default_text = menu.addAction("Default Text Color", lambda: self._user_restore_color(column, kind="text"))
        default_text.setEnabled(column in self._model.column_overrides(kind="text"))
        menu.addSeparator()
        menu.addAction("Hide This Column", lambda: self._hide_column(column))
        menu.addAction("Choose Columns…", self.choose_columns)
        menu.addSeparator()
        reset = menu.addAction("Reset Colors", self._user_reset_colors)
        reset.setEnabled(bool(self._model.column_overrides()) or bool(self._model.column_overrides(kind="text")))
        menu.addSeparator()
        menu.addAction("Font…", self._pick_font)
        default_font = menu.addAction("Default Font", lambda: self._user_set_font(None))
        default_font.setEnabled(self._font_key is not None)
        self.headerMenuRequested.emit(menu, column)
        return menu

    def _pick_color(self, column: str, *, kind: str = "background") -> None:
        fallback = "white" if kind == "background" else self.palette().color(QPalette.Text).name()
        current = QColor(self.column_color(column, kind=kind) or fallback)
        what = "Color" if kind == "background" else "Text color"
        color = QColorDialog.getColor(current, self, f"{what} of column '{column}'")
        if color.isValid():
            self._user_set_color(column, color, kind=kind)

    def _pick_font(self) -> None:
        dlg = QFontDialog(self._resolved_font(), self)
        dlg.setWindowTitle("Table font")
        dlg.setOption(QFontDialog.DontUseNativeDialog, True)
        if dlg.exec():
            self._user_set_font(dlg.selectedFont())

    def _resolved_font(self) -> QFont:
        """The font to start the dialog from: the chosen table font, else the application font resolved
        to a family the dialog lists (the application font may be a hidden alias)."""
        if self._table_font is not None:
            return QFont(self._table_font)
        info = QFontInfo(self.font())
        family = info.family()
        families = QFontDatabase.families()
        if family.startswith(".") or family not in families:
            # macOS reports the hidden alias ".AppleSystemUIFont" (listed, but not shown by the dialog)
            visible = [f for f in families if not f.startswith(".")]
            for candidate in ("Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"):
                if candidate in visible:
                    family = candidate
                    break
            else:
                family = visible[0] if visible else family
        font = QFont(family, info.pointSize())
        font.setBold(info.bold())
        font.setItalic(info.italic())
        return font

    def _user_set_font(self, font: Optional[QFont]) -> None:
        self.set_table_font(font)
        self.configChanged.emit(self.get_config())

    def _user_set_color(self, column: str, color: Optional[QColor], *, kind: str = "background") -> None:
        self.set_column_color(column, color, kind=kind)
        self.configChanged.emit(self.get_config())

    def _user_restore_color(self, column: str, *, kind: str = "background") -> None:
        self.restore_column_color(column, kind=kind)
        self.configChanged.emit(self.get_config())

    def _user_reset_colors(self) -> None:
        self.reset_colors()
        self.configChanged.emit(self.get_config())

    def _hide_column(self, column: str) -> None:
        self._user_set_visible([c for c in self.visible_columns() if c != column])

    def _user_set_visible(self, columns: List[str]) -> None:
        self.set_visible_columns(columns)
        self.visibleColumnsChanged.emit(list(columns))
        self.configChanged.emit(self.get_config())

    # ----- helpers -----
    def _fit_rows(self) -> None:
        """Row height from the font (cheaper than resizeRowsToContents on large frames)."""
        self.verticalHeader().setDefaultSectionSize(self.fontMetrics().height() + 8)

    def _fit_headers(self) -> None:
        """Make the header tall enough for multi-line texts and the columns wide enough for them."""
        header = self.horizontalHeader()
        height = header.fontMetrics().lineSpacing()
        for i in range(self._model.columnCount()):
            size = header.text_size(str(self._model.headerData(i, Qt.Horizontal)))
            height = max(height, size.height())
            width = size.width() + 2 * self._header_padding + header.indicator_width()
            if width > self.columnWidth(i):
                self.setColumnWidth(i, width)
        header.setMinimumHeight(height + 2 * self._header_padding)

    def _apply_visibility(self) -> None:
        if self._model is None:
            return
        wanted = None if self._visible is None else set(self._visible)
        for i, col in enumerate(self._model.columns()):
            self.setColumnHidden(i, wanted is not None and col not in wanted)
