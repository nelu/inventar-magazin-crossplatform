from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QWidget

from ..inventory import Inventory
from .components import ProductTable, button, label, page_layout
from .dialogs import error, message


class InventoryScreen(QWidget):
    add_requested = Signal()
    stock_requested = Signal()
    code_selected = Signal(str)
    deleted = Signal(str)

    def __init__(self, inventory: Inventory) -> None:
        super().__init__()
        self.inventory = inventory
        layout = page_layout(self, "inventoryPage", "Selectează un rând pentru a modifica stocul sau a șterge produsul.")
        self.summary = label("", "listSummary")
        layout.addWidget(self.summary)
        self.table = ProductTable("inventoryTable")
        layout.addWidget(self.table, 1)
        tools = QHBoxLayout()
        tools.addWidget(button("Adaugă produs…", "goAdd", self.add_requested.emit))
        self.stock_button = button("Operații de stoc…", "goStock", self.stock_requested.emit)
        self.delete_button = button("Șterge produsul…", "deleteProduct", self._delete)
        tools.addWidget(self.stock_button)
        tools.addStretch()
        tools.addWidget(self.delete_button)
        layout.addLayout(tools)
        self.table.itemSelectionChanged.connect(self._selection_changed)

    def refresh(self, inventory: Inventory, summary: str, selected: str | None) -> str | None:
        if inventory is self.inventory and selected is None:
            selected = self.table.selected_code()
        self.inventory = inventory
        self.summary.setText(summary if inventory.path else "Niciun inventar deschis. Alege un fișier din meniul Fișier.")
        self.table.display(inventory.products, selected)
        code = self.table.selected_code()
        self._enable_actions(code)
        return code

    def select_code(self, code: str) -> None:
        if self.table.selected_code() != code:
            for row in range(self.table.rowCount()):
                if self.table.item(row, 0).text() == code:
                    self.table.selectRow(row)
                    break

    def _enable_actions(self, code: str | None) -> None:
        self.delete_button.setEnabled(code is not None)
        self.stock_button.setEnabled(code is not None)

    def _selection_changed(self) -> None:
        code = self.table.selected_code()
        self._enable_actions(code)
        if code is not None:
            self.code_selected.emit(code)

    def _delete(self) -> None:
        code = self.table.selected_code()
        if code is None or not message(self, "Ștergere produs", f"Ștergi definitiv produsul {code}?", confirm=True):
            return
        try:
            self.inventory.delete(code)
        except (ValueError, OSError) as exc:
            error(self, exc)
            return
        self.deleted.emit(code)
