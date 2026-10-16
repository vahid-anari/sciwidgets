"""Item delegate that draws rich-text (HTML) cell values."""

from __future__ import annotations

from PySide6.QtCore import QModelIndex, QSize, Qt
from PySide6.QtGui import QAbstractTextDocumentLayout, QPainter, QPalette, QTextDocument, QTextOption
from PySide6.QtWidgets import QStyle, QStyledItemDelegate, QStyleOptionViewItem

from ._header import is_rich_text


class RichTextDelegate(QStyledItemDelegate):
    """Draw cells whose display text contains HTML; plain cells use the default painting."""

    _H_MARGIN = 3

    def _document(self, option: QStyleOptionViewItem, text: str, alignment: Qt.Alignment) -> QTextDocument:
        doc = QTextDocument()
        doc.setDefaultFont(option.font)
        text_option = QTextOption()
        text_option.setAlignment(alignment & Qt.AlignHorizontal_Mask)
        doc.setDefaultTextOption(text_option)
        doc.setDocumentMargin(0)
        doc.setHtml(text)
        return doc

    @staticmethod
    def _alignment(index: QModelIndex) -> Qt.Alignment:
        value = index.data(Qt.TextAlignmentRole)
        return Qt.Alignment(int(value)) if value is not None else Qt.AlignLeft | Qt.AlignVCenter

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        text = index.data(Qt.DisplayRole)
        if text is None or not is_rich_text(str(text)):
            super().paint(painter, option, index)
            return
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        opt.text = ""
        style = opt.widget.style() if opt.widget is not None else None
        if style is None:
            from PySide6.QtWidgets import QApplication

            style = QApplication.style()
        style.drawControl(QStyle.CE_ItemViewItem, opt, painter, opt.widget)

        alignment = self._alignment(index)
        doc = self._document(opt, str(text), alignment)
        rect = opt.rect.adjusted(self._H_MARGIN, 0, -self._H_MARGIN, 0)
        doc.setTextWidth(rect.width())
        painter.save()
        painter.setClipRect(rect)
        painter.translate(rect.x(), rect.y() + (rect.height() - doc.size().height()) / 2)
        if opt.state & QStyle.State_Selected:
            # same colour group as the plain cells: Inactive when the table has no focus
            group = QPalette.Active if opt.state & QStyle.State_Active else QPalette.Inactive
            color = opt.palette.color(group, QPalette.HighlightedText)
        else:
            foreground = index.data(Qt.ForegroundRole)
            color = foreground.color() if foreground is not None else opt.palette.color(QPalette.Text)
        ctx = QAbstractTextDocumentLayout.PaintContext()
        ctx.palette.setColor(QPalette.Text, color)
        doc.documentLayout().draw(painter, ctx)
        painter.restore()

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:
        text = index.data(Qt.DisplayRole)
        if text is None or not is_rich_text(str(text)):
            return super().sizeHint(option, index)
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        doc = self._document(opt, str(text), self._alignment(index))
        width = doc.idealWidth()
        doc.setTextWidth(width)
        return QSize(int(width + 0.5) + 2 * self._H_MARGIN + 4, int(doc.size().height() + 0.5) + 4)
