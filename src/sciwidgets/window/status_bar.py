"""Status-bar controller showing a state, a document path, elapsed time and memory."""

from __future__ import annotations

import os
from enum import Enum
from time import perf_counter_ns
from typing import Iterable, Optional, Union

import psutil
from PySide6.QtCore import QObject, Qt, QTimer
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QLayout, QMainWindow, QWidget

__all__ = ["StatusBarController"]


def _compact_number(value: float) -> str:
    """Format a number with fewer decimals as it grows (``1.23``, ``12.3``, ``123``)."""
    if value < 10:
        return f"{value:.2f}"
    if value < 100:
        return f"{value:.1f}"
    return f"{value:.0f}"


def _format_duration(ms: float) -> str:
    """Format a duration in milliseconds with an automatic unit (ms, s, m, h)."""
    if ms < 1000:
        return f"{_compact_number(ms)} ms"
    s = ms / 1000.0
    if s < 60:
        return f"{_compact_number(s)} s"
    m = s / 60.0
    if m < 60:
        return f"{_compact_number(m)} m"
    return f"{_compact_number(m / 60.0)} h"


def _format_bytes(n: float) -> str:
    """Format a byte count with an automatic unit (B, KB, MB, GB)."""
    for unit in ("B", "KB", "MB"):
        if n < 1000:
            return f"{_compact_number(n)} {unit}"
        n /= 1024.0
    return f"{_compact_number(n)} GB"


class StatusBarController(QObject):
    """Manage a main window's status bar.

    The left side shows the current state (e.g. ``"Ready"``) and, optionally,
    the current document path with a ``*`` when there are unsaved changes.
    The right side shows the process memory and the elapsed time of the last
    busy state.

    States are free text chosen by the app. A state set with ``busy=True``
    starts the elapsed-time clock; the next state stops it and leaves the
    final time visible::

        status.set_state("Solving…", busy=True)
        solve()
        status.set_state("Ready")
    """

    def __init__(
            self,
            window: QMainWindow,
            *,
            ready_text: str = "Ready",
            states: Iterable[Union[str, Enum]] = (),
            show_path: bool = True,
            path_label: str = "Path",
            show_memory: bool = True,
            show_time: bool = True,
            timer_interval: int = 700,
    ) -> None:
        """Initialize the controller and build the status-bar widgets.

        Args:
            window: Main window whose status bar is managed.
            ready_text: Initial state text.
            states: All state texts the app will show. The state label is
                sized for the widest one, so the path next to it does not
                move when the state changes. A wider state shown later still
                fits; the label then grows and keeps that width.
            show_path: Whether to show the document path section.
            path_label: Caption of the path section, e.g. ``"File"``.
            show_memory: Whether to show the process memory.
            show_time: Whether to show the elapsed time of busy states.
            timer_interval: Refresh interval, in milliseconds, of the time and
                memory displays while a busy state is active.
        """
        super().__init__(window)
        self._sb = window.statusBar()
        self._process = psutil.Process(os.getpid())
        self._start_ns = 0
        self._busy = False

        self._path = ""
        self._modified = False
        self._path_label = path_label

        self._timer = QTimer(self)
        self._timer.setInterval(timer_interval)
        self._timer.timeout.connect(self._refresh)

        self._state_lbl = QLabel(ready_text)
        self._path_lbl = QLabel() if show_path else None
        self._memory_lbl = self._fixed_label("0.00 MB", 7) if show_memory else None
        self._time_lbl = self._fixed_label("0.00 s", 7) if show_time else None

        self._make_layout()
        self._fit_state_width([ready_text, *states])
        self._update_path_label()
        self._update_memory()

    # ----- construction -----
    @staticmethod
    def _fixed_label(text: str, chars: int) -> QLabel:
        """Create a right-aligned label wide enough for ``chars`` digits."""
        lbl = QLabel(text, alignment=Qt.AlignRight | Qt.AlignVCenter)
        lbl.setFixedWidth(lbl.fontMetrics().horizontalAdvance("0" * chars) + 8)
        return lbl

    def _vline(self) -> QFrame:
        """Create a sunken vertical separator."""
        line = QFrame(self._sb)
        line.setFrameShape(QFrame.VLine)
        line.setFrameShadow(QFrame.Sunken)
        return line

    def _add_separator(self, layout: QLayout) -> None:
        """Add a padded vertical separator to a layout."""
        layout.addSpacing(10)
        layout.addWidget(self._vline())
        layout.addSpacing(10)

    def _make_layout(self) -> None:
        """Build the left (state, path) and right (memory, time) sections."""
        left = QWidget()
        ll = QHBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(0)
        ll.addSpacing(10)
        ll.addWidget(self._state_lbl)
        if self._path_lbl is not None:
            self._add_separator(ll)
            ll.addWidget(self._path_lbl)
        ll.addStretch(1)
        self._sb.addWidget(left, 1)

        if self._memory_lbl is None and self._time_lbl is None:
            return
        right = QWidget()
        rl = QHBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(0)
        for caption, lbl in (("Memory:", self._memory_lbl), ("Time:", self._time_lbl)):
            if lbl is not None:
                self._add_separator(rl)
                rl.addWidget(QLabel(caption))
                rl.addWidget(lbl)
        rl.addSpacing(8)
        self._sb.addPermanentWidget(right)

    # ----- updates -----
    def _update_time(self) -> None:
        """Show the time elapsed since the current busy state started."""
        if self._time_lbl is not None:
            ms = (perf_counter_ns() - self._start_ns) / 1.0e6
            self._time_lbl.setText(_format_duration(ms))

    def _update_memory(self) -> None:
        """Show the current memory use (resident set size) of the process."""
        if self._memory_lbl is not None:
            self._memory_lbl.setText(_format_bytes(self._process.memory_info().rss))

    def _refresh(self) -> None:
        """Timer slot: refresh time and memory."""
        self._update_time()
        self._update_memory()

    def _update_path_label(self) -> None:
        """Show the path, ``Untitled`` when empty, and ``*`` when modified."""
        if self._path_lbl is None:
            return
        mark = " *" if self._modified else ""
        text = f"{self._path_label}{mark}: {self._path or 'Untitled'}"
        self._path_lbl.setText(text)
        self._path_lbl.setToolTip(text)

    @staticmethod
    def _state_text(state: Union[str, Enum]) -> str:
        """Return the display text of a state (an enum's value, or the string)."""
        return state.value if isinstance(state, Enum) else str(state)

    def _fit_state_width(self, states: Iterable[Union[str, Enum]]) -> None:
        """Widen the state label to fit the given states; it never shrinks."""
        fm = self._state_lbl.fontMetrics()
        width = max((fm.horizontalAdvance(self._state_text(s)) for s in states), default=0) + 4
        if width > self._state_lbl.minimumWidth():
            self._state_lbl.setMinimumWidth(width)

    # ----- public API -----
    def set_state(self, state: Union[str, Enum], busy: bool = False) -> None:
        """Show a new state.

        A busy state starts the elapsed-time clock; any following state stops
        it and keeps the final time on display. The new state appears when
        control returns to the event loop, so run long tasks in a worker
        thread, or start them with ``QTimer.singleShot`` after this call.

        Args:
            state: Text to show, or an enum whose value is the text.
            busy: Whether a long-running task starts now.
        """
        self._timer.stop()
        if self._busy:
            self._update_time()
        self._busy = bool(busy)
        if self._busy:
            self._start_ns = perf_counter_ns()
            self._timer.start()

        self._update_memory()
        text = self._state_text(state)
        self._fit_state_width([text])
        self._state_lbl.setText(text)

    def is_busy(self) -> bool:
        """Return whether a busy state is active."""
        return self._busy

    def set_path(self, path: str) -> None:
        """Show a document path.

        A non-empty path clears the modified mark (the document was just
        opened or saved); an empty path shows ``Untitled`` and keeps the mark.

        Args:
            path: Path to show.
        """
        self._path = path
        if path:
            self._modified = False
        self._update_path_label()

    def get_path(self) -> str:
        """Return the shown document path."""
        return self._path

    def set_modified(self, modified: bool = True) -> None:
        """Mark or unmark the document as having unsaved changes.

        Args:
            modified: Whether there are unsaved changes.
        """
        self._modified = bool(modified)
        self._update_path_label()

    def is_modified(self) -> bool:
        """Return whether the document is marked as modified."""
        return self._modified
