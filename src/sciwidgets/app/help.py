"""The Help menu every sciwidgets app shares: guide, documents, updates, About.

One :class:`AppHelp` per main window builds the same menu in every app, in the same order
and with the same shortcuts::

    User Guide                       ⌘?
    <the app's own documents, or a submenu of them>
    ─────────
    Check for Updates…               ⌘U
    ─────────
    About <app name>

Apps that build their menus with :class:`~sciwidgets.window.MenuBarController` put
``help.menu_items()`` under their ``"Help"`` key and pass every triggered id to
``help.handle(id)``; apps with plain menus call ``help.add_to(menu)``. The About dialog lists
the libraries the app is built on (see :mod:`sciwidgets.app.about`).

Shortcuts shared by the apps (Ctrl is ⌘ on macOS): ⌘O open (the app's main Open…), ⌘S save,
⌘E export, ⌘Q quit, ⌘, settings, ⌘? user guide, ⌘U check for updates, ⌘I information about
what is loaded. Never use keys macOS keeps for itself: ⌥⌘D (Dock), ⌘M (minimise), ⌘H (hide),
⌘⌥H, ⌘Tab, ⌘Space, ⌃⌘F, ⌃⌘Q.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from html import escape
from pathlib import Path
from typing import Any, Callable, Sequence, Union

from PySide6.QtCore import QObject, QUrl
from PySide6.QtGui import QAction, QDesktopServices, QKeySequence
from PySide6.QtWidgets import QMenu, QWidget

from ..dialogs import show_about_dialog, show_warning
from . import AppInfo
from .about import Library, about_html
from .update_ui import AppUpdates

__all__ = ["AppHelp", "Document", "DocumentMenu", "UPDATES_SHORTCUT"]

UPDATES_SHORTCUT = "Ctrl+U"
"""Shortcut of Check for Updates… in every app."""


@dataclass(frozen=True)
class Document:
    """A local document (usually a PDF) shown in the Help menu."""

    text: str
    path: Path
    shortcut: Any = None


@dataclass(frozen=True)
class DocumentMenu:
    """A submenu of documents, e.g. "CDMS Documentation"."""

    title: str
    documents: Sequence[Document] = field(default_factory=tuple)


class AppHelp(QObject):
    """The Help menu and the actions behind it for one main window.

    Args:
        window: The main window (parent of the dialogs; a restart after an update closes it).
        info: The app.
        user_guide: The User Guide PDF; ``None`` leaves the item out.
        documents: Further documents after the guide: :class:`Document` items and
            :class:`DocumentMenu` submenus.
        author: Shown in About after the license, e.g. "Vahid Anari".
        license: The app's license, "MIT" by default.
        about_extra: Extra HTML for About (data credits).
        citation: HTML reference shown in About under "Citing" ("If you use <app> in published
            work, please cite: …"), e.g. with a DOI link.
        libraries: The library list for About; ``None`` reads it from the installed metadata.
        missing_hint: Added to the message when a document is missing (e.g. how to build it).
        success_note: Passed to :class:`AppUpdates` (shown after an update ran).

    Attributes:
        updates: The window's :class:`AppUpdates`; call ``updates.check()`` for the quiet
            check at start-up.
    """

    PREFIX = "help_"

    def __init__(self, window: QWidget, info: AppInfo, *, user_guide: Path | None = None,
                 documents: Sequence[Union[Document, DocumentMenu]] = (), author: str = "", license: str = "MIT",
                 about_extra: str = "", citation: str = "", libraries: Sequence[Library] | None = None, missing_hint: str = "",
                 success_note: str = "") -> None:
        super().__init__(window)
        self._window = window
        self.info = info
        self._documents: list[Union[Document, DocumentMenu]] = list(documents)
        if user_guide is not None:
            self._documents.insert(0, Document("User Guide", Path(user_guide), QKeySequence.HelpContents))
        self._author, self._license, self._extra = author, license, about_extra
        self._citation = citation
        self._libraries = libraries
        self._missing_hint = missing_hint
        self.updates = AppUpdates(window, info, success_note=success_note)
        self._actions: dict[str, Callable[[], None]] = {}

    # ----- the menu -----
    def _doc_items(self) -> list[tuple[str, Any]]:
        """``(id, Document)`` for every document, submenus flattened, in menu order."""
        out, n = [], 0
        for entry in self._documents:
            for doc in (entry.documents if isinstance(entry, DocumentMenu) else [entry]):
                out.append((f"{self.PREFIX}doc_{n}", doc))
                n += 1
        return out

    def menu_items(self) -> list[dict[str, Any]]:
        """Items for the ``"Help"`` key of a :class:`~sciwidgets.window.MenuBarController` spec.

        All ids start with ``"help_"``; pass triggered ids to :meth:`handle`.
        """
        ids = iter(self._doc_items())
        items: list[dict[str, Any]] = []
        for entry in self._documents:
            if isinstance(entry, DocumentMenu):
                sub = [self._doc_item(*next(ids)) for _ in entry.documents]
                items.append({"submenu": entry.title, "items": sub})
            else:
                items.append(self._doc_item(*next(ids)))
        if items:
            items.append({"id": "sep"})
        items.append({"id": f"{self.PREFIX}updates", "text": "Check for Updates…", "shortcut": UPDATES_SHORTCUT,
                      "role": QAction.MenuRole.NoRole})
        items.append({"id": "sep"})
        items.append({"id": f"{self.PREFIX}about", "text": f"About {self.info.name}",
                      "role": QAction.MenuRole.NoRole})
        return items

    @staticmethod
    def _doc_item(action_id: str, doc: Document) -> dict[str, Any]:
        item = {"id": action_id, "text": doc.text, "role": QAction.MenuRole.NoRole}
        if doc.shortcut is not None:
            item["shortcut"] = doc.shortcut
        return item

    def handle(self, action_id: str) -> bool:
        """Run the Help action ``action_id``; returns ``False`` for ids that are not Help's."""
        if not action_id.startswith(self.PREFIX):
            return False
        if action_id == f"{self.PREFIX}updates":
            self.check_for_updates()
        elif action_id == f"{self.PREFIX}about":
            self.show_about()
        else:
            docs = dict(self._doc_items())
            if action_id not in docs:
                return False
            self.open_document(docs[action_id])
        return True

    def add_to(self, menu: QMenu) -> None:
        """Fill a plain ``QMenu`` (apps without a MenuBarController) with the same items."""

        def add(target: QMenu, item: dict[str, Any]) -> None:
            if item.get("id") == "sep":
                target.addSeparator()
            elif "submenu" in item:
                sub = QMenu(item["submenu"], target)  # explicit parent: PySide frees parentless submenus
                target.addMenu(sub)
                for child in item["items"]:
                    add(sub, child)
            else:
                action = QAction(item["text"], target)
                action.setMenuRole(QAction.MenuRole.NoRole)
                if "shortcut" in item:
                    action.setShortcut(QKeySequence(item["shortcut"]))
                action.triggered.connect(lambda _=False, i=item["id"]: self.handle(i))
                target.addAction(action)

        for item in self.menu_items():
            add(menu, item)

    # ----- the actions -----
    def open_document(self, doc: Document) -> None:
        """Open a document in the system viewer, or explain that it is missing."""
        if not doc.path.is_file():
            show_warning(f"{doc.text} Not Found", f"{escape(doc.text)} is not included in this installation.",
                         f"Expected at {escape(str(doc.path))}. {self._missing_hint}".strip(), parent=self._window)
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(doc.path)))

    def check_for_updates(self) -> None:
        """Check for Updates…: reports every outcome."""
        self.updates.check(manual=True)

    def about_html(self) -> str:
        """The About text (see :func:`sciwidgets.app.about.about_html`)."""
        return about_html(self.info, author=self._author, license=self._license, extra_html=self._extra,
                          citation=self._citation, libraries=self._libraries)

    def show_about(self) -> None:
        """About <app name>."""
        show_about_dialog(f"About {self.info.name}", self.about_html(), parent=self._window,
                          heading=self.info.name)
