"""A page of parameter widgets built from a nested layout description.

The description is a tree. Containers hold a list of items; anything with a
``"type"`` is a widget (see :func:`widget_from_spec`) and its ``"path"`` is
its id::

    {"column": [
        {"group": "Time grid", "column": [
            {"type": "float-slider", "path": "grid.t_max", "label": "t_\\mathrm{max}",
             "min_val": 1, "max_val": 1000},
            {"type": "int-slider", "path": "grid.nt", "label": "N_t",
             "min_val": 100, "max_val": 100000}]},
        {"row": [
            {"type": "toggle", "path": "norm", "text": "Normalize"},
            {"stretch": 1}]}
    ]}

Items:

* ``{"column": [...]}`` stacks items vertically; the name and value columns
  of the widgets directly in it are aligned.
* ``{"row": [...]}`` places items side by side.
* ``{"group": "Title", "column": [...]}`` (or ``"row"``) draws a titled box.
* ``{"stretch": n}`` alone is empty space that takes a share ``n`` of the
  free room; on any other item it sets that item's share.

Containers may also have ``"defaults"``, and widgets may use
``"template"``; see :mod:`sciwidgets.panel.expand`.
"""

from __future__ import annotations

from typing import Any, Dict, Iterator, List, Mapping, Optional, Tuple

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QBoxLayout, QGroupBox, QHBoxLayout, QVBoxLayout, QWidget

from sciwidgets.params import ParameterWidgetBase

from .expand import expand_layout
from .factory import widget_from_spec

__all__ = ["ParameterPage"]

_CONTAINER_KEYS = frozenset({"column", "row", "group", "stretch"})


class ParameterPage(QWidget):
    """Parameter widgets laid out from a description, addressed by path.

    Values and configurations of the whole page are read and written as flat
    dicts keyed by widget path. The page is top-aligned: free space collects
    at the bottom. It never scrolls: its minimum size is what its widgets
    need, so every parameter is always visible.

    Signals:
        valueChanged (str, object): The user changed a widget's value; sends
            the path and the new value.
        configChanged (str, object): The user changed a widget's
            configuration (range, format, ...); sends the path and the config.

    As with the widgets themselves, these signals are for user actions only:
    ``set_value`` and ``set_config`` do not emit them.
    """

    valueChanged = Signal(str, object)
    configChanged = Signal(str, object)

    def __init__(
            self,
            layout: Mapping[str, Any],
            parent: Optional[QWidget] = None,
            *,
            templates: Optional[Mapping[str, Any]] = None,
            defaults: Optional[Mapping[str, Any]] = None,
    ) -> None:
        """Build the page.

        Args:
            layout: Layout description; its top item is usually a
                ``"column"``.
            parent: Parent widget.
            templates: Named widget descriptions usable with ``"template"``.
            defaults: Defaults for every widget on the page.

        Raises:
            ValueError: If an item is malformed, a widget has no ``"path"``,
                or a path is used twice.
            TypeError: If a widget description has an argument its
                constructor does not accept.
        """
        super().__init__(parent)
        self._widgets: Dict[str, ParameterWidgetBase] = {}
        self._columns: List[List[ParameterWidgetBase]] = []

        outer = QVBoxLayout(self)
        self._add_item(outer, expand_layout(layout, templates, defaults), where="layout")
        outer.addStretch(1)

        for column in self._columns:
            self._connect_alignment(column)

    # ----- construction -----
    def _add_item(self, parent: QBoxLayout, item: Mapping[str, Any], where: str,
                  column: Optional[List[ParameterWidgetBase]] = None) -> None:
        """Add one description item to a layout.

        Args:
            parent: Layout that receives the item.
            item: Item description.
            where: Position of the item in the description, for error messages.
            column: Alignment list of the enclosing column, if the item sits
                directly in one.
        """
        if not isinstance(item, Mapping):
            raise ValueError(f"{where}: expected an object, got {item!r}")
        stretch = int(item.get("stretch", 0))

        if "type" in item:
            widget = self._make_widget(item, where)
            parent.addWidget(widget, stretch)
            if column is not None:
                column.append(widget)
            return

        unknown = set(item) - _CONTAINER_KEYS
        if unknown:
            raise ValueError(f"{where}: unknown key(s) {sorted(unknown)}; a widget needs 'type'")
        has_column, has_row = "column" in item, "row" in item
        if has_column and has_row:
            raise ValueError(f"{where}: use either 'column' or 'row', not both")
        if not (has_column or has_row):
            if "group" in item:
                raise ValueError(f"{where}: group {item['group']!r} needs a 'column' or 'row'")
            parent.addStretch(stretch)  # a bare {"stretch": n}
            return

        key = "column" if has_column else "row"
        children = item[key]
        if not isinstance(children, list):
            raise ValueError(f"{where}: '{key}' must be a list")

        if "group" in item:
            container: QWidget = QGroupBox(str(item["group"]))
        else:
            container = QWidget()
        lay = QVBoxLayout(container) if has_column else QHBoxLayout(container)
        if "group" not in item:
            lay.setContentsMargins(0, 0, 0, 0)

        aligned: Optional[List[ParameterWidgetBase]] = [] if has_column else None
        for i, child in enumerate(children):
            self._add_item(lay, child, f"{where}.{key}[{i}]", aligned)
        if aligned:
            self._columns.append(aligned)
        parent.addWidget(container, stretch)

    def _make_widget(self, spec: Mapping[str, Any], where: str) -> ParameterWidgetBase:
        """Create a widget from its description and register it by path.

        Args:
            spec: Widget description.
            where: Position in the description, for error messages.

        Returns:
            The new widget.
        """
        path = spec.get("path")
        if not path:
            raise ValueError(f"{where}: widget {spec.get('type')!r} has no 'path'")
        if path in self._widgets:
            raise ValueError(f"{where}: path {path!r} is used twice")

        widget = widget_from_spec(spec)
        self._widgets[path] = widget
        widget.valueChanged.connect(lambda v, p=path: self.valueChanged.emit(p, v))
        widget.configChanged.connect(lambda c, p=path: self.configChanged.emit(p, c))
        return widget

    # ----- alignment -----
    @staticmethod
    def _align(widgets: List[ParameterWidgetBase]) -> None:
        """Give the widgets of one column the same name and value widths."""
        name_w = max(w.get_name_width() for w in widgets)
        value_w = max(w.get_value_width() for w in widgets)
        for w in widgets:
            w.set_name_width(name_w)
            w.set_value_width(value_w)

    def _connect_alignment(self, widgets: List[ParameterWidgetBase]) -> None:
        """Align a column now and again whenever a measured width changes."""
        for w in widgets:
            w.nameWidthChanged.connect(lambda _, ws=widgets: self._align(ws))
            w.valueWidthChanged.connect(lambda _, ws=widgets: self._align(ws))
        self._align(widgets)

    # ----- widgets -----
    def paths(self) -> List[str]:
        """Return the widget paths in layout order."""
        return list(self._widgets)

    def get_widget(self, path: str) -> ParameterWidgetBase:
        """Return the widget at a path.

        Raises:
            KeyError: If no widget has this path.
        """
        try:
            return self._widgets[path]
        except KeyError:
            raise KeyError(f"no widget with path {path!r}") from None

    def items(self) -> Iterator[Tuple[str, ParameterWidgetBase]]:
        """Iterate over ``(path, widget)`` pairs in layout order."""
        return iter(self._widgets.items())

    def set_widget_visible(self, path: str, visible: bool) -> None:
        """Show or hide one widget."""
        self.get_widget(path).setVisible(visible)

    def set_widget_enabled(self, path: str, enabled: bool) -> None:
        """Enable or disable one widget."""
        self.get_widget(path).setEnabled(enabled)

    # ----- values and configuration -----
    def get_value(self) -> Dict[str, Any]:
        """Return all values as ``{path: value}``."""
        return {p: w.get_value() for p, w in self._widgets.items()}

    def set_value(self, values: Mapping[str, Any]) -> None:
        """Set values by path, without emitting ``valueChanged``.

        Unknown paths are ignored; widgets missing from ``values`` keep their
        value.

        Args:
            values: ``{path: value}``.
        """
        for p, v in values.items():
            w = self._widgets.get(p)
            if w is not None:
                w.set_value(v)

    def get_config(self) -> Dict[str, Dict[str, Any]]:
        """Return all configurations as ``{path: config}``."""
        return {p: w.get_config() for p, w in self._widgets.items()}

    def set_config(self, configs: Mapping[str, Mapping[str, Any]]) -> None:
        """Set configurations by path, without emitting ``configChanged``.

        Unknown paths are ignored. Restore the configuration before the
        values, so values are checked against the right ranges.

        Args:
            configs: ``{path: config}``.
        """
        for p, c in configs.items():
            w = self._widgets.get(p)
            if w is not None:
                w.set_config(dict(c))
