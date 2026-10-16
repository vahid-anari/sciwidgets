"""Horizontal header that draws rich-text (HTML) section labels."""

from __future__ import annotations

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QPainter, QTextDocument, QTextOption
from PySide6.QtWidgets import QHeaderView, QStyle, QStyleOptionHeader, QWidget


def is_rich_text(text: str) -> bool:
    """Return True when ``text`` should be rendered as HTML."""
    return "<" in text and ">" in text or "&" in text and ";" in text


class RichHeaderView(QHeaderView):
    """Horizontal header whose labels may be HTML (``<sup>``, ``<sub>``, ``&tau;``, ``<br>``).

    Plain labels (with ``\\n`` for line breaks) are drawn by the base class.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(Qt.Horizontal, parent)
        self.setDefaultAlignment(Qt.AlignCenter)

    def _document(self, text: str, width: int | None = None) -> QTextDocument:
        doc = QTextDocument()
        doc.setDefaultFont(self.font())
        opt = QTextOption()
        opt.setAlignment(Qt.AlignCenter)
        doc.setDefaultTextOption(opt)
        doc.setDocumentMargin(0)
        doc.setHtml(text)
        if width is not None:
            doc.setTextWidth(width)
        return doc

    def text_size(self, text: str) -> QSize:
        """Size of ``text`` as it would be drawn (plain or rich)."""
        if is_rich_text(text):
            doc = self._document(text)
            width = doc.idealWidth()
            doc.setTextWidth(width)
            return QSize(int(width + 0.5), int(doc.size().height() + 0.5))
        fm = self.fontMetrics()
        lines = text.split("\n")
        return QSize(max(fm.horizontalAdvance(line) for line in lines), fm.lineSpacing() * len(lines))

    def sectionSizeFromContents(self, logical_index: int) -> QSize:
        model = self.model()
        text = model.headerData(logical_index, Qt.Horizontal, Qt.DisplayRole) if model is not None else None
        if text is None or not is_rich_text(str(text)):
            return super().sectionSizeFromContents(logical_index)
        size = self.text_size(str(text))
        margin = self.style().pixelMetric(QStyle.PM_HeaderMargin, None, self)
        return QSize(size.width() + 2 * margin + self.indicator_width(), size.height() + 2 * margin)

    def indicator_width(self) -> int:
        """Horizontal room taken by the sort indicator (0 when sorting is off)."""
        if not self.isSortIndicatorShown():
            return 0
        style = self.style()
        return style.pixelMetric(QStyle.PM_HeaderMarkSize, None, self) + style.pixelMetric(
            QStyle.PM_HeaderMargin, None, self
        )

    def paintSection(self, painter: QPainter, rect: QRect, logical_index: int) -> None:
        model = self.model()
        text = model.headerData(logical_index, Qt.Horizontal, Qt.DisplayRole) if model is not None else None
        if text is None or not is_rich_text(str(text)):
            super().paintSection(painter, rect, logical_index)
            return
        painter.save()
        opt = QStyleOptionHeader()
        self.initStyleOption(opt)
        opt.rect = rect
        opt.section = logical_index
        opt.text = ""
        opt.orientation = Qt.Horizontal
        opt.textAlignment = self.defaultAlignment()
        visual = self.visualIndex(logical_index)
        first = self.logicalIndex(0) == logical_index
        last = visual == self.count() - self.hiddenSectionCount() - 1
        if first and last:
            opt.position = QStyleOptionHeader.OnlyOneSection
        elif first:
            opt.position = QStyleOptionHeader.Beginning
        elif last:
            opt.position = QStyleOptionHeader.End
        else:
            opt.position = QStyleOptionHeader.Middle
        if self.isSortIndicatorShown() and self.sortIndicatorSection() == logical_index:
            opt.sortIndicator = (QStyleOptionHeader.SortDown if self.sortIndicatorOrder() == Qt.AscendingOrder
                                 else QStyleOptionHeader.SortUp)
        self.style().drawControl(QStyle.CE_Header, opt, painter, self)
        painter.restore()
        text_rect = rect.adjusted(0, 0, -self.indicator_width(), 0) if opt.sortIndicator else rect
        doc = self._document(str(text), text_rect.width())
        painter.save()
        painter.translate(text_rect.x(), text_rect.y() + (text_rect.height() - doc.size().height()) / 2)
        doc.drawContents(painter)
        painter.restore()
