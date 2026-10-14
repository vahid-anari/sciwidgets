"""Several parameter pages in a tab widget, addressed by path as one panel.

The description lists the tabs; each has an ``"id"``, a ``"title"`` and a
``"layout"`` in the :class:`ParameterPage` format::

    {"tabs": [
        {"id": "grid", "title": "Grid", "layout": {"column": [...]}},
        {"id": "sample", "title": "Sample", "layout": {"column": [...]}}
    ]}

Widget paths are unique across all tabs, so values and configurations of
the whole panel are one flat dict.
"""

from __future__ import annotations

from typing import Any, Dict, Iterator, List, Mapping, Optional, Tuple

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QTabWidget, QWidget

from sciwidgets.params import ParameterWidgetBase

from .page import ParameterPage

__all__ = ["ParameterTabs"]

_TAB_KEYS = frozenset({"id", "title", "layout"})


class ParameterTabs(QTabWidget):
    """Parameter pages in tabs, read and written as one flat dict by path.

    Signals:
        valueChanged (str, object): The user changed a widget's value; sends
            the path and the new value.
        configChanged (str, object): The user changed a widget's
            configuration; sends the path and the config.

    The signals are for user actions only; ``set_value`` and ``set_config``
    do not emit them.
    """

    valueChanged = Signal(str, object)
    configChanged = Signal(str, object)

    def __init__(self, description: Mapping[str, Any], parent: Optional[QWidget] = None) -> None:
        """Build one page per tab.

        Args:
            description: Mapping with a ``"tabs"`` list.
            parent: Parent widget.

        Raises:
            ValueError: If a tab is malformed, a tab id is used twice, or a
                widget path is used in two tabs (or see ``ParameterPage``).
        """
        super().__init__(parent)
        self._pages: Dict[str, ParameterPage] = {}
        self._page_of_path: Dict[str, ParameterPage] = {}

        tabs = description.get("tabs")
        if not isinstance(tabs, list):
            raise ValueError("description needs a 'tabs' list")

        for i, tab in enumerate(tabs):
            where = f"tabs[{i}]"
            if not isinstance(tab, Mapping):
                raise ValueError(f"{where}: expected an object, got {tab!r}")
            unknown = set(tab) - _TAB_KEYS
            if unknown:
                raise ValueError(f"{where}: unknown key(s) {sorted(unknown)}")
            tab_id = tab.get("id")
            if not tab_id:
                raise ValueError(f"{where}: tab has no 'id'")
            if tab_id in self._pages:
                raise ValueError(f"{where}: tab id {tab_id!r} is used twice")
            if "layout" not in tab:
                raise ValueError(f"{where}: tab {tab_id!r} has no 'layout'")

            try:
                page = ParameterPage(tab["layout"])
            except (ValueError, TypeError) as exc:
                raise type(exc)(f"tab {tab_id!r}: {exc}") from exc
            for path in page.paths():
                if path in self._page_of_path:
                    raise ValueError(f"tab {tab_id!r}: path {path!r} is already used in another tab")
                self._page_of_path[path] = page

            page.valueChanged.connect(self.valueChanged)
            page.configChanged.connect(self.configChanged)
            self._pages[tab_id] = page
            self.addTab(page, str(tab.get("title", tab_id)))

    # ----- tabs -----
    def tab_ids(self) -> List[str]:
        """Return the tab ids in order."""
        return list(self._pages)

    def page(self, tab_id: str) -> ParameterPage:
        """Return the page of a tab.

        Raises:
            KeyError: If no tab has this id.
        """
        try:
            return self._pages[tab_id]
        except KeyError:
            raise KeyError(f"no tab with id {tab_id!r}") from None

    def set_tab_enabled(self, tab_id: str, enabled: bool) -> None:
        """Enable or disable a whole tab."""
        self.setTabEnabled(self.indexOf(self.page(tab_id)), enabled)

    def set_tab_visible(self, tab_id: str, visible: bool) -> None:
        """Show or hide a tab."""
        self.setTabVisible(self.indexOf(self.page(tab_id)), visible)

    def set_current_tab(self, tab_id: str) -> None:
        """Bring a tab to the front."""
        self.setCurrentWidget(self.page(tab_id))

    def current_tab(self) -> str:
        """Return the id of the tab in front."""
        current = self.currentWidget()
        return next((i for i, p in self._pages.items() if p is current), "")

    # ----- widgets -----
    def paths(self) -> List[str]:
        """Return all widget paths, tab by tab in layout order."""
        return [p for page in self._pages.values() for p in page.paths()]

    def get_widget(self, path: str) -> ParameterWidgetBase:
        """Return the widget at a path.

        Raises:
            KeyError: If no widget has this path.
        """
        page = self._page_of_path.get(path)
        if page is None:
            raise KeyError(f"no widget with path {path!r}")
        return page.get_widget(path)

    def items(self) -> Iterator[Tuple[str, ParameterWidgetBase]]:
        """Iterate over ``(path, widget)`` pairs of all tabs."""
        for page in self._pages.values():
            yield from page.items()

    def set_widget_visible(self, path: str, visible: bool) -> None:
        """Show or hide one widget."""
        self.get_widget(path).setVisible(visible)

    def set_widget_enabled(self, path: str, enabled: bool) -> None:
        """Enable or disable one widget."""
        self.get_widget(path).setEnabled(enabled)

    # ----- values and configuration -----
    def get_value(self) -> Dict[str, Any]:
        """Return all values as ``{path: value}``."""
        out: Dict[str, Any] = {}
        for page in self._pages.values():
            out.update(page.get_value())
        return out

    def set_value(self, values: Mapping[str, Any]) -> None:
        """Set values by path, without emitting ``valueChanged``.

        Unknown paths are ignored; widgets missing from ``values`` keep their
        value.
        """
        for page in self._pages.values():
            page.set_value(values)

    def get_config(self) -> Dict[str, Dict[str, Any]]:
        """Return all configurations as ``{path: config}``."""
        out: Dict[str, Dict[str, Any]] = {}
        for page in self._pages.values():
            out.update(page.get_config())
        return out

    def set_config(self, configs: Mapping[str, Mapping[str, Any]]) -> None:
        """Set configurations by path, without emitting ``configChanged``.

        Unknown paths are ignored. Restore the configuration before the
        values, so values are checked against the right ranges.
        """
        for page in self._pages.values():
            page.set_config(configs)
