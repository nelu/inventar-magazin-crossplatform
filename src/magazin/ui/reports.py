from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import QComboBox, QWidget

from ..inventory import Inventory
from .components import ProductTable, choices, label, named, page_layout


class _ReportScreen(QWidget):
    def __init__(self, name: str, hint: str, query_name: str, caption: str) -> None:
        super().__init__()
        self.body = page_layout(self, name, hint)
        self.query = named(QComboBox(), query_name)
        self.query.setEditable(True)
        self.query.setAccessibleName(caption)
        self.body.addWidget(self.query)
        self.inventory: Inventory | None = None
        self.dirty = False
        self.reset_query = False
        self.query.currentTextChanged.connect(self._result)

    def inventory_changed(self, inventory: Inventory) -> None:
        if self.inventory is not inventory:
            self.reset_query = True
        self.inventory = inventory
        self.dirty = True
        if self.isVisible():
            self._refresh()

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        if self.dirty:
            self._refresh()

    def _refresh(self) -> None:
        assert self.inventory is not None
        selected = None if self.reset_query else self.query.currentText()
        choices(self.query, sorted(self._options(self.inventory), key=str.casefold), selected)
        self.reset_query = self.dirty = False
        self._result(self.query.currentText())

    def _options(self, inventory: Inventory) -> set[str]:
        raise NotImplementedError

    def _result(self, text: str) -> None:
        raise NotImplementedError


class CategoryScreen(_ReportScreen):
    def __init__(self) -> None:
        super().__init__("categoryPage", "Valoarea însumează prețul unitar × stocul fiecărui produs din categorie.",
                         "categoryQuery", "Categorie")
        self.total = label("", "categoryTotal")
        self.body.addWidget(self.total)
        self.body.addStretch()

    def _options(self, inventory: Inventory) -> set[str]:
        return {p.categorie for p in inventory.products}

    def _result(self, text: str) -> None:
        assert self.inventory is not None
        query = text.strip()
        self.total.setText(f"{self.inventory.total(query):.2f} lei" if query else "Nicio categorie selectată.")


class BrandScreen(_ReportScreen):
    def __init__(self) -> None:
        super().__init__("brandPage", "Selectează o marcă sau scrie denumirea exactă pentru a vedea produsele și prețurile.",
                         "brandQuery", "Marcă")
        self.summary = label("", "brandSummary")
        self.body.addWidget(self.summary)
        self.matches = ProductTable("brandTable")
        self.body.addWidget(self.matches, 1)

    def _options(self, inventory: Inventory) -> set[str]:
        return {p.marca for p in inventory.products}

    def _result(self, text: str) -> None:
        assert self.inventory is not None
        query = text.strip()
        products = self.inventory.by_brand(query) if query else ()
        self.matches.display(products)
        self.summary.setText(f"Produse găsite: {len(products)}" if products else "Niciun produs găsit.")
