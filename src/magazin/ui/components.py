from collections.abc import Callable, Sequence
from typing import TypeVar

from PySide6.QtCore import QObject, QSignalBlocker, Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QLabel, QPushButton, QSpinBox, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from ..inventory import Product


AUTHOR = "Cosmin Zarzu 208ID"
FIELDS = ("cod", "pret", "marca", "an", "garantie", "producator", "tara", "categorie", "stoc")
HEADERS = ("Cod", "Preț (lei)", "Marcă", "An fabricație", "Garanție (luni)",
           "Producător", "Țară", "Categorie", "Stoc")
T = TypeVar("T", bound=QObject)


def named(widget: T, name: str) -> T:
    widget.setObjectName(name)
    return widget


def label(text: str, name: str = "") -> QLabel:
    widget = named(QLabel(), name)
    widget.setTextFormat(Qt.TextFormat.PlainText)
    widget.setWordWrap(True)
    widget.setText(text)
    return widget


def page_layout(page: QWidget, name: str, hint: str) -> QVBoxLayout:
    page.setObjectName(name)
    layout = QVBoxLayout(page)
    layout.setSpacing(12)
    layout.addWidget(label(hint))
    return layout


def button(text: str, name: str, callback: Callable[[], None]) -> QPushButton:
    widget = named(QPushButton(text), name)
    widget.clicked.connect(lambda: callback())
    return widget


def number(name: str, minimum: int = 0, maximum: int = 2_147_483_647) -> QSpinBox:
    widget = named(QSpinBox(), name)
    widget.setRange(minimum, maximum)
    return widget


def choices(combo: QComboBox, values: list[str], selected: str | None) -> None:
    with QSignalBlocker(combo):
        combo.clear()
        combo.addItems(values)
        if selected and (combo.isEditable() or selected in values):
            combo.setCurrentText(selected)


class ProductTable(QTableWidget):
    def __init__(self, name: str) -> None:
        super().__init__(0, len(FIELDS))
        self.setObjectName(name)
        self.setHorizontalHeaderLabels(HEADERS)
        self.verticalHeader().hide()
        self.setAlternatingRowColors(True)
        self.setShowGrid(False)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

    def display(self, products: Sequence[Product], selected: str | None = None) -> None:
        with QSignalBlocker(self):
            self.setRowCount(0)
            self.setRowCount(len(products))
            target = 0
            for row, product in enumerate(products):
                if product.cod == selected:
                    target = row
                for column, field in enumerate(FIELDS):
                    value = getattr(product, field)
                    item = QTableWidgetItem(f"{value:.2f}" if field == "pret" else str(value))
                    if field in ("pret", "an", "garantie", "stoc"):
                        item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                    self.setItem(row, column, item)
            self.resizeColumnsToContents()
            if products:
                self.selectRow(target)

    def selected_code(self) -> str | None:
        rows = self.selectionModel().selectedRows(0)
        return rows[0].data() if rows else None
