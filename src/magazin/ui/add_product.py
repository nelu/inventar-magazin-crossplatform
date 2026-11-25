from decimal import Decimal, InvalidOperation

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import QFormLayout, QGroupBox, QLineEdit, QSpinBox, QWidget

from ..inventory import Inventory, Product
from .components import FIELDS, HEADERS, button, label, named, number, page_layout
from .dialogs import error


class AddProductScreen(QWidget):
    added = Signal(str)

    def __init__(self, inventory: Inventory) -> None:
        super().__init__()
        self.inventory = inventory
        layout = page_layout(self, "addPage", "Completează toate câmpurile. Codul trebuie să fie unic în inventar.")
        self.form = QGroupBox("Fișa produsului")
        form = QFormLayout(self.form)
        self.fields: dict[str, QLineEdit | QSpinBox] = {}
        for field, caption in zip(FIELDS, HEADERS):
            if field == "an":
                editor = number(field, 1980, 2026)
                editor.setValue(2026)
            elif field in ("garantie", "stoc"):
                editor = number(field)
            else:
                editor = named(QLineEdit(), field)
                if field == "pret":
                    editor.setPlaceholderText("Ex.: 249,90")
            self.fields[field] = editor
            form.addRow(caption, editor)
        layout.addWidget(self.form)
        self.add_button = button("Adaugă în inventar", "addProduct", self._add)
        layout.addWidget(self.add_button, 0, Qt.AlignmentFlag.AlignLeft)
        self.hint = label("Creează sau deschide mai întâi un inventar din meniul Fișier.")
        layout.addWidget(self.hint)
        layout.addStretch()

    def refresh(self, inventory: Inventory) -> None:
        self.inventory = inventory
        active = inventory.path is not None
        self.form.setEnabled(active)
        self.add_button.setEnabled(active)
        self.hint.setVisible(not active)

    def reset(self) -> None:
        for field, editor in self.fields.items():
            if isinstance(editor, QSpinBox):
                editor.setValue(2026 if field == "an" else 0)
            else:
                editor.clear()

    def _product(self) -> Product:
        values = {}
        for (field, editor), caption in zip(self.fields.items(), HEADERS):
            if isinstance(editor, QSpinBox):
                values[field] = editor.value()
                continue
            value = editor.text().strip()
            if not value:
                editor.setFocus()
                raise ValueError(f"Completează câmpul „{caption}”.")
            if field == "pret":
                try:
                    price = Decimal(value.replace(",", "."))
                    if not price.is_finite() or price < 0:
                        raise InvalidOperation
                except InvalidOperation:
                    editor.setFocus()
                    raise ValueError("Introdu un preț numeric mai mare sau egal cu zero.") from None
                values[field] = price
            else:
                values[field] = value
        return Product(**values)

    def _add(self) -> None:
        try:
            product = self._product()
            self.inventory.add(product)
        except (ValueError, OSError) as exc:
            error(self, exc)
            return
        self.reset()
        self.added.emit(product.cod)
