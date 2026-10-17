"""The update check inside an app: background check, update notice, "Update Now" and restart.

The check reads the latest version from PyPI and, when it is newer, the release notes from
GitHub; both requests go through ``QNetworkAccessManager``, so they never block the window.
:class:`AppUpdates` puts it all together for a main window::

    updates = AppUpdates(window, APP_INFO)
    QTimer.singleShot(2000, updates.check)          # quiet: only a newer version is shown
    help_menu_action.triggered.connect(lambda: updates.check(manual=True))
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable, Sequence
from html import escape

from PySide6.QtCore import QObject, QProcess, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QFontDatabase
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from sciwidgets.app import AppInfo
from sciwidgets.app.update import (
    EDITABLE_HINT,
    install_kind,
    newer_release_notes,
    parse_version,
    update_command,
    version_known,
)
from sciwidgets.dialogs import show_information, show_warning

REQUEST_TIMEOUT_MS = 5000


class UpdateChecker(QObject):
    """Query PyPI asynchronously and report whether a newer version exists."""

    updateAvailable = Signal(str, object)
    """``(latest_version, notes)``; ``notes`` are ``(version, markdown)`` pairs, newest first (may be empty)."""

    upToDate = Signal()
    checkFailed = Signal(str)

    def __init__(self, info: AppInfo, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._info = info
        self._manager = QNetworkAccessManager(self)

    def check(self) -> None:
        """Start a check; the result arrives through the signals."""
        if not version_known(self._info.version):
            self.checkFailed.emit(f"The running version is unknown ({self._info.name} is not installed as a package).")
            return
        reply = self._manager.get(self._request(self._info.pypi_json_url))
        reply.finished.connect(lambda: self._on_version(reply))

    def _request(self, url: str) -> QNetworkRequest:
        request = QNetworkRequest(QUrl(url))
        request.setRawHeader(b"User-Agent", f"{self._info.name}/{self._info.version}".encode())
        request.setTransferTimeout(REQUEST_TIMEOUT_MS)
        return request

    def _on_version(self, reply: QNetworkReply) -> None:
        try:
            if reply.error() != QNetworkReply.NetworkError.NoError:
                self.checkFailed.emit(reply.errorString())
                return
            data = json.loads(bytes(reply.readAll()).decode("utf-8"))
            self.handle_latest(str(data["info"]["version"]))
        except (ValueError, KeyError, TypeError) as exc:
            self.checkFailed.emit(str(exc))
        finally:
            reply.deleteLater()

    def handle_latest(self, latest: str) -> None:
        """Compare ``latest`` with the running version; fetch the notes if it is newer."""
        if parse_version(latest) <= parse_version(self._info.version):
            self.upToDate.emit()
            return
        request = self._request(self._info.releases_api_url)
        request.setRawHeader(b"Accept", b"application/vnd.github+json")
        reply = self._manager.get(request)
        reply.finished.connect(lambda: self._on_notes(reply, latest))

    def _on_notes(self, reply: QNetworkReply, latest: str) -> None:
        notes: list[tuple[str, str]] = []
        try:
            if reply.error() == QNetworkReply.NetworkError.NoError:
                data = json.loads(bytes(reply.readAll()).decode("utf-8"))
                if isinstance(data, list):
                    notes = newer_release_notes(data, self._info.version, latest)
        except (ValueError, TypeError):
            notes = []
        finally:
            reply.deleteLater()
        self.updateAvailable.emit(latest, notes)


def notes_markdown(notes: Sequence[tuple[str, str]]) -> str:
    """The notes of several versions as one Markdown text, one ``###`` heading per version."""
    return "\n\n".join(f"### {version}\n\n{body.strip()}" for version, body in notes)


class UpdateDialog(QDialog):
    """Tell the user a newer version exists, what changed, and offer to update now.

    ``exec()`` returns ``UpdateDialog.UPDATE_NOW`` when "Update Now" was clicked.

    Args:
        info: The app.
        latest: Latest version on PyPI.
        update_command: Command that updates this installation (shown), or ``""``.
        notes: ``(version, markdown)`` pairs, newest first; may be empty.
        parent: Optional parent widget.
        can_update: Offer the "Update Now" button.
        hint: Shown instead of the command when the app cannot update itself.
    """

    UPDATE_NOW = 2

    def __init__(self, info: AppInfo, latest: str, update_command: str, notes: Sequence[tuple[str, str]],
                 parent: QWidget | None = None, *, can_update: bool = False, hint: str = "") -> None:
        super().__init__(parent)
        self.setWindowTitle("Update Available")
        self.resize(620, 520)

        heading = QLabel(f"<b>{escape(info.name)} {escape(latest)}</b> is available.<br>"
                         f"You have version {escape(info.version)}.")
        if hint:
            how_text = escape(hint)
        elif can_update:
            how_text = ("<b>Update Now</b> runs, while the app stays open:"
                        f"<pre>    {escape(update_command)}</pre>"
                        "Restart the app afterwards to use the new version.")
        else:
            command = update_command or f"pipx upgrade {info.dist_name}"
            how_text = ("To update, close the app and run in a terminal:"
                        f"<pre>    {escape(command)}</pre>"
                        f"(or <code>pip install -U {escape(info.dist_name)}</code> in the environment "
                        "where you installed it).")
        how = QLabel(how_text)
        how.setWordWrap(True)
        how.setTextInteractionFlags(Qt.TextSelectableByMouse)

        whats_new = QLabel("<b>What's new</b>")
        browser = QTextBrowser(self)
        browser.setOpenExternalLinks(True)
        browser.setMarkdown(notes_markdown(notes))

        notes_btn = QPushButton("Open Release Notes")
        notes_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(info.releases_url)))
        pypi_btn = QPushButton("Open PyPI Page")
        pypi_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(info.pypi_url)))
        later_btn = QPushButton("Later")
        later_btn.clicked.connect(self.accept)
        self.update_btn = QPushButton("Update Now")
        self.update_btn.setEnabled(can_update)
        self.update_btn.clicked.connect(lambda: self.done(self.UPDATE_NOW))
        (self.update_btn if can_update else later_btn).setDefault(True)

        buttons = QHBoxLayout()
        buttons.addWidget(notes_btn)
        buttons.addWidget(pypi_btn)
        buttons.addStretch(1)
        buttons.addWidget(later_btn)
        buttons.addWidget(self.update_btn)

        layout = QVBoxLayout(self)
        layout.addWidget(heading)
        layout.addWidget(how)
        if notes:
            layout.addWidget(whats_new)
            layout.addWidget(browser, 1)
        else:
            whats_new.hide()
            browser.hide()
            layout.addStretch(1)
            self.resize(560, 260)
        layout.addLayout(buttons)


class UpdateProgressDialog(QDialog):
    """Run the update command, show its output, then offer a restart.

    ``succeeded`` and ``restart_requested`` tell the outcome. After a failure the dialog shows
    ``manual_hint`` (what to do by hand). ``success_note`` is added after "Restart now…?".
    """

    def __init__(self, command: Sequence[str], info: AppInfo, latest: str, manual_hint: str,
                 parent: QWidget | None = None, *, success_note: str = "") -> None:
        super().__init__(parent)
        self.setWindowTitle("Updating")
        self.resize(640, 380)
        self._command = list(command)
        self._latest = latest
        self._manual_hint = manual_hint
        self._success_note = success_note
        self.succeeded = False
        self.restart_requested = False

        self._status = QLabel(f"Updating {info.name} to {latest}…")
        self._status.setWordWrap(True)
        self._output = QPlainTextEdit(readOnly=True)
        self._output.setFont(QFontDatabase.systemFont(QFontDatabase.FixedFont))
        self._output.appendPlainText("$ " + " ".join(self._command))

        self._later = QPushButton("Later")
        self._later.clicked.connect(self.reject)
        self._restart = QPushButton("Restart Now")
        self._restart.clicked.connect(self._choose_restart)
        self._close = QPushButton("Close")
        self._close.clicked.connect(self.reject)
        for button in (self._later, self._restart, self._close):
            button.hide()

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(self._close)
        buttons.addWidget(self._later)
        buttons.addWidget(self._restart)

        layout = QVBoxLayout(self)
        layout.addWidget(self._status)
        layout.addWidget(self._output, 1)
        layout.addLayout(buttons)

        self._proc = QProcess(self)
        self._proc.setProcessChannelMode(QProcess.MergedChannels)
        self._proc.readyReadStandardOutput.connect(self._read_output)
        self._proc.finished.connect(self._finished)
        self._proc.errorOccurred.connect(self._error)
        self._done = False

    def start(self) -> None:
        """Start the update (``exec`` calls it)."""
        self._proc.start(self._command[0], self._command[1:])

    def exec(self) -> int:
        self.start()
        return super().exec()

    def wait(self, msecs: int = 30000) -> bool:
        """Block until the command has finished (for tests)."""
        return self._proc.waitForFinished(msecs)

    def reject(self) -> None:
        if not self._done:  # no closing while pip is replacing files
            return
        super().reject()

    def _read_output(self) -> None:
        text = bytes(self._proc.readAllStandardOutput()).decode("utf-8", "replace")
        if text:
            self._output.appendPlainText(text.rstrip("\n"))

    def _finished(self, exit_code: int, exit_status: QProcess.ExitStatus) -> None:
        self._read_output()
        if exit_status == QProcess.NormalExit and exit_code == 0:
            self._succeed()
        else:
            self._fail(f"The update stopped with exit code {exit_code}.")

    def _error(self, error: QProcess.ProcessError) -> None:
        if error == QProcess.FailedToStart:
            self._fail(f"Could not start {self._command[0]}.")

    def _succeed(self) -> None:
        self._done = True
        self.succeeded = True
        note = f" {self._success_note}" if self._success_note else ""
        self._status.setText(f"<b>Updated to {self._latest}.</b> Restart now to use the new version?{note}")
        self._later.show()
        self._restart.show()
        self._restart.setDefault(True)

    def _fail(self, reason: str) -> None:
        if self._done:
            return
        self._done = True
        self._status.setText(f"<b>The update did not finish.</b> {reason}<br>{self._manual_hint}")
        self._close.show()
        self._close.setDefault(True)

    def _choose_restart(self) -> None:
        self.restart_requested = True
        self.accept()


def restart_command(info: AppInfo) -> list[str]:
    """How to start the app again in the same Python (picks up the new version)."""
    return [sys.executable, "-m", info.module]


def restart_app(info: AppInfo, close_window: Callable[[], bool],
                start_detached: Callable[[str, list], object] = QProcess.startDetached) -> bool:
    """Close the main window (which may ask about unsaved work) and start the app again.

    Returns ``False`` if the window did not close.
    """
    if not close_window():
        return False
    command = restart_command(info)
    start_detached(command[0], command[1:])
    return True


class AppUpdates(QObject):
    """The whole update flow of a main window: check, notice, Update Now, restart.

    ``check()`` is quiet: only a newer version is shown. ``check(manual=True)`` (a "Check for
    Updates…" menu item) also reports "up to date" and failures.

    Args:
        window: The main window; the dialogs are its children and a restart closes it.
        info: The app.
        success_note: Added after "Restart now…?" once the update has run, e.g.
            "Unsaved parameters are asked about as usual."
    """

    def __init__(self, window: QWidget, info: AppInfo, *, success_note: str = "") -> None:
        super().__init__(window)
        self._window = window
        self._info = info
        self._success_note = success_note
        self._manual = False
        self.checker = UpdateChecker(info, self)
        self.checker.updateAvailable.connect(self._on_update_available)
        self.checker.upToDate.connect(self._on_up_to_date)
        self.checker.checkFailed.connect(self._on_failed)

    def check(self, manual: bool = False) -> None:
        """Ask PyPI for a newer version."""
        self._manual = manual
        self.checker.check()

    def _on_update_available(self, latest: str, notes: list) -> None:
        self._manual = False
        kind = install_kind(self._info)
        command = update_command(self._info, kind)
        dialog = UpdateDialog(self._info, latest, " ".join(command) if command else "", notes, parent=self._window,
                              can_update=command is not None, hint=EDITABLE_HINT if kind == "editable" else "")
        if dialog.exec() != UpdateDialog.UPDATE_NOW or command is None:
            return
        progress = UpdateProgressDialog(
            command, self._info, latest,
            manual_hint=(f"Close the app and run <code>{escape(self._info.command)} update</code> in a terminal "
                         f"(or <code>{escape(' '.join(command))}</code>)."),
            parent=self._window, success_note=self._success_note,
        )
        progress.exec()
        if progress.restart_requested:
            restart_app(self._info, self._window.close)

    def _on_up_to_date(self) -> None:
        if self._manual:
            show_information("No Updates", f"{self._info.name} {self._info.version} is the latest version.",
                             parent=self._window)
        self._manual = False

    def _on_failed(self, message: str) -> None:
        if self._manual:
            show_warning("Update Check Failed", "Could not check for updates.", escape(message), parent=self._window)
        self._manual = False
