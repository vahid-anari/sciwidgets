"""Dialog used by DataFrameView to choose the visible columns."""

from __future__ import annotations

from typing import Iterable, List, Optional

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


class ChooseColumnsDialog(QDialog):
    """Checkbox per column, with Select all / Select none buttons."""

    def __init__(self, columns: Iterable[str], visible: Iterable[str], parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Choose Columns")
        visible = set(visible)
        self._checks: List[QCheckBox] = []

        inner = QWidget()
        form = QVBoxLayout(inner)
        for col in columns:
            cb = QCheckBox(col)
            cb.setChecked(col in visible)
            form.addWidget(cb)
            self._checks.append(cb)
        form.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(inner)

        all_btn = QPushButton("Select All")
        none_btn = QPushButton("Select None")
        all_btn.clicked.connect(lambda: self._set_all(True))
        none_btn.clicked.connect(lambda: self._set_all(False))
        row = QHBoxLayout()
        row.addWidget(all_btn)
        row.addWidget(none_btn)
        row.addStretch()

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(row)
        layout.addWidget(scroll)
        layout.addWidget(buttons)
        self.resize(320, 420)

    def _set_all(self, checked: bool) -> None:
        for cb in self._checks:
            cb.setChecked(checked)

    def selected(self) -> List[str]:
        """Return the names of the checked columns, in the original order."""
        return [cb.text() for cb in self._checks if cb.isChecked()]
