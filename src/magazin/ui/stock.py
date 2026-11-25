from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import QComboBox, QFormLayout, QGroupBox, QWidget

from ..inventory import Inventory
from .components import button, choices, label, named, number, page_layout
from .dialogs import error


class StockScreen(QWidget):
    code_selected = Signal(str)
    updated = Signal(str, str)  # Selected code and status message after a successful write.

    def __init__(self, inventory: Inventory) -> None:
        super().__init__()
        self.inventory = inventory
        layout = page_layout(self, "stockPage", "Alege produsul după cod. Fiecare operație se salvează în fișierul curent.")
        form = QFormLayout()
        self.code = named(QComboBox(), "stockCode")
        form.addRow("Cod produs", self.code)
        self.info = label("", "stockInfo")
        form.addRow("Disponibilitate", self.info)
        layout.addLayout(form)
        self.sell_button = button("Vinde o bucată", "sellOne", self._sell)
        layout.addWidget(self.sell_button, 0, Qt.AlignmentFlag.AlignLeft)
        group = QGroupBox("Aprovizionare")
        form = QFormLayout(group)
        self.quantity = number("restockQuantity", 1)
        form.addRow("Cantitate de adăugat", self.quantity)
        self.restock_button = button("Adaugă în stoc", "restock", self._restock)
        form.addRow("", self.restock_button)
        layout.addWidget(group)
        layout.addStretch()
        self.code.currentTextChanged.connect(self._selection_changed)

    def refresh(self, inventory: Inventory, selected: str | None) -> None:
        self.inventory = inventory
        choices(self.code, [p.cod for p in inventory.products], selected)
        self._update_info()

    def reset(self) -> None:
        self.quantity.setValue(1)

    def select_code(self, code: str) -> None:
        self.code.setCurrentText(code)

    def _selection_changed(self, code: str) -> None:
        self._update_info()
        self.code_selected.emit(code)

    def _update_info(self) -> None:
        row = self.code.currentIndex()
        product = self.inventory.products[row] if row >= 0 else None
        self.info.setText(f"{product.marca} · {product.categorie} · {product.stoc} buc."
                          if product else "Niciun produs disponibil.")
        self.sell_button.setEnabled(product is not None and product.stoc > 0)
        self.restock_button.setEnabled(product is not None)
        self.quantity.setEnabled(product is not None)

    def _sell(self) -> None:
        code = self.code.currentText()
        try:
            self.inventory.sell(code)
        except (ValueError, OSError) as exc:
            error(self, exc)
            return
        self.updated.emit(code, f"Vânzare înregistrată: {code}")

    def _restock(self) -> None:
        code = self.code.currentText()
        try:
            self.inventory.restock(code, self.quantity.value())
        except (ValueError, OSError) as exc:
            error(self, exc)
            return
        self.updated.emit(code, f"Stoc actualizat: {code}")
