"""Declarative menu-bar controller for a main window.

The menu bar is described by a plain Python mapping and built in one call.
Nested submenus, checkable actions, shortcuts and menu roles are supported,
and every action is reported through a single signal.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QMainWindow, QMenu

__all__ = ["MenuBarController", "MenuSpec"]

MenuSpec = Dict[str, List[Dict[str, Any]]]
"""Menu specification: menu title -> list of item dictionaries."""


class MenuBarController(QObject):
    """Build and manage a menu bar from a declarative specification.

    The specification maps each top-level menu title to a list of items. An
    item is one of:

    * an action: ``{"id": "save", "text": "Save", "shortcut": "Ctrl+S"}``
      with optional ``enabled``, ``checkable``, ``checked`` and ``role``;
    * a separator: ``{"id": "sep"}``;
    * a submenu: ``{"submenu": "Open Recent", "items": [...]}``.

    Action ids must be unique across the whole menu bar; they are used to
    look actions up later.

    Signals:
        actionTriggered (str, str, bool): Emitted when the user triggers an
            action, with the menu path (e.g. ``"File/Open Recent"``), the
            action id and the checked state.
    """

    actionTriggered = Signal(str, str, bool)

    def __init__(
            self,
            window: QMainWindow,
            menu_spec: Optional[MenuSpec] = None,
            *,
            native_menubar: bool = True,
    ) -> None:
        """Initialize the controller and build the menu bar.

        Args:
            window: Main window that owns the menu bar.
            menu_spec: Menu specification. ``None`` builds an empty menu bar.
            native_menubar: Whether to use the platform's native menu bar
                (the global menu bar on macOS) when available.

        Raises:
            ValueError: If an action has no ``id`` or an id is used twice.
        """
        super().__init__(window)
        self._w = window
        self._menu_spec: MenuSpec = {}
        self._actions: Dict[str, QAction] = {}
        self.set_menu_spec(menu_spec or {}, native_menubar=native_menubar)

    # ----- validation -----
    @staticmethod
    def _check_ids(menu_spec: MenuSpec) -> None:
        """Check that every action has an id and that no id is repeated.

        Args:
            menu_spec: Menu specification to check.

        Raises:
            ValueError: If an action has no ``id`` or an id is used twice.
        """
        seen: Dict[str, str] = {}

        def walk(items: List[Dict[str, Any]], path: str) -> None:
            for item in items:
                if "submenu" in item:
                    walk(item.get("items", []), f"{path}/{item['submenu']}")
                    continue
                action_id = str(item.get("id", "")).strip()
                if not action_id:
                    raise ValueError(f"Menu item in '{path}' must define 'id': {item}")
                if action_id == "sep":
                    continue
                if action_id in seen:
                    raise ValueError(
                        f"Duplicate menu action id {action_id!r} in '{path}' "
                        f"(already used in '{seen[action_id]}')"
                    )
                seen[action_id] = path

        for menu_name, items in menu_spec.items():
            walk(items, menu_name)

    # ----- construction -----
    @staticmethod
    def _to_keyseq(shortcut: Union[None, str, QKeySequence, QKeySequence.StandardKey]) -> Optional[QKeySequence]:
        """Convert a shortcut value to a ``QKeySequence``.

        Args:
            shortcut: ``None``, a string such as ``"Ctrl+S"``, a
                ``QKeySequence`` or a standard key such as
                ``QKeySequence.Save``.

        Returns:
            The key sequence, or ``None`` if no shortcut was given.
        """
        if shortcut is None:
            return None
        if isinstance(shortcut, QKeySequence):
            return shortcut
        return QKeySequence(shortcut)

    def _add_action(self, menu: QMenu, menu_name: str, item: Dict[str, Any]) -> None:
        """Create an action from an item specification and add it to a menu.

        Args:
            menu: Menu that receives the action.
            menu_name: Menu path reported by ``actionTriggered``.
            item: Item specification with at least an ``id``.
        """
        action_id = str(item["id"]).strip()
        act = QAction(str(item.get("text", action_id)), self._w)
        act.setEnabled(bool(item.get("enabled", True)))
        checkable = bool(item.get("checkable", False))
        act.setCheckable(checkable)
        if checkable:
            act.setChecked(bool(item.get("checked", False)))

        ks = self._to_keyseq(item.get("shortcut"))
        if ks is not None:
            act.setShortcut(ks)
        role = item.get("role")
        if role is not None:
            act.setMenuRole(role)

        act.triggered.connect(lambda c, m=menu_name, a=action_id: self.actionTriggered.emit(m, a, c))
        menu.addAction(act)
        self._actions[action_id] = act

    def _populate_menu(self, menu: QMenu, menu_name: str, items: List[Dict[str, Any]]) -> None:
        """Fill a menu from a list of item specifications.

        Args:
            menu: Menu to fill.
            menu_name: Menu path of this branch.
            items: Item specifications.
        """
        for item in items:
            if "submenu" in item:
                sub = menu.addMenu(str(item["submenu"]))
                self._populate_menu(sub, f"{menu_name}/{item['submenu']}", item.get("items", []))
            elif str(item["id"]).strip() == "sep":
                menu.addSeparator()
            else:
                self._add_action(menu, menu_name, item)

    def _build_menus(self, native_menubar: bool) -> None:
        """Build the menu bar from the stored specification.

        Args:
            native_menubar: Whether to use the platform's native menu bar.
        """
        menubar = self._w.menuBar()
        menubar.setNativeMenuBar(native_menubar)
        menubar.clear()
        for menu_name, items in self._menu_spec.items():
            menu = menubar.addMenu(menu_name)
            self._populate_menu(menu, menu_name, items)

    # ----- public API -----
    def set_menu_spec(self, menu_spec: MenuSpec, native_menubar: bool = True) -> None:
        """Replace the specification and rebuild the menu bar.

        The new specification is checked before the current menu bar is
        touched.

        Args:
            menu_spec: New menu specification.
            native_menubar: Whether to use the platform's native menu bar.

        Raises:
            ValueError: If an action has no ``id`` or an id is used twice.
        """
        self._check_ids(menu_spec)
        self._menu_spec = menu_spec
        self._actions.clear()
        self._build_menus(native_menubar)

    def action(self, action_id: str) -> QAction:
        """Return the ``QAction`` for an id, e.g. to add it to a toolbar.

        Args:
            action_id: Action identifier.

        Returns:
            The action.

        Raises:
            KeyError: If no action has this id.
        """
        try:
            return self._actions[action_id]
        except KeyError:
            raise KeyError(f"unknown menu action id {action_id!r}") from None

    def set_enabled(self, action_id: str, enabled: bool) -> None:
        """Enable or disable an action. Unknown ids are ignored.

        Args:
            action_id: Action identifier.
            enabled: New enabled state.
        """
        act = self._actions.get(action_id)
        if act is not None:
            act.setEnabled(enabled)

    def set_checked(self, action_id: str, checked: bool) -> None:
        """Set the checked state of a checkable action (no signal).

        Unknown ids are ignored.

        Args:
            action_id: Action identifier.
            checked: New checked state.
        """
        act = self._actions.get(action_id)
        if act is not None:
            act.setChecked(checked)

    def get_checked(self, action_id: str) -> bool:
        """Return the checked state of an action.

        Args:
            action_id: Action identifier.

        Returns:
            The checked state, or ``False`` if the id is unknown.
        """
        act = self._actions.get(action_id)
        return act.isChecked() if act is not None else False
