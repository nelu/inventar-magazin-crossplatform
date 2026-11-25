from pathlib import Path

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import QGroupBox, QHBoxLayout, QVBoxLayout, QWidget

from .components import button, label, page_layout


class HomeScreen(QWidget):
    new_requested = Signal()
    open_requested = Signal()
    save_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        layout = page_layout(self, "homePage", "Gestionează componentele PC într-un fișier CSV la alegere.")
        group = QGroupBox("Inventar curent")
        card = QVBoxLayout(group)
        self.file_label = label("", "currentFile")
        self.file_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.summary = label("", "inventorySummary")
        card.addWidget(self.file_label)
        card.addWidget(self.summary)
        layout.addWidget(group)
        tools = QHBoxLayout()
        tools.addWidget(button("Inventar nou…", "newInventory", self.new_requested.emit))
        tools.addWidget(button("Deschide CSV…", "openInventory", self.open_requested.emit))
        self.save_button = button("Salvează ca…", "saveAs", self.save_requested.emit)
        tools.addWidget(self.save_button)
        tools.addStretch()
        layout.addLayout(tools)
        layout.addStretch()

    def refresh(self, path: Path | None, summary: str) -> None:
        self.file_label.setText(str(path) if path else "Niciun fișier ales")
        self.summary.setText(summary)
        self.save_button.setEnabled(path is not None)


class HelpScreen(QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = page_layout(self, "helpPage", "Ghid rapid pentru inventarul de componente PC")
        for heading, text in (
            ("1. Alege fișierul", "Din Fișier, creează un inventar nou sau deschide un CSV existent. Salvează ca creează o copie și o folosește ca inventar curent."),
            ("2. Lucrează cu produsele", "Adaugă produse cu un cod unic și un an între 1980 și 2026. Din Inventar poți șterge un produs; din Operații de stoc poți vinde o bucată sau adăuga o cantitate pozitivă."),
            ("3. Editează în afara aplicației", "Coloanele CSV, în ordine: cod;pret;marca;an;garantie;producator;tara;categorie;stoc. După editarea externă redeschide fișierul înainte de alte operații. Verifică avertismentele de import înainte de a salva modificări."),
        ):
            group = QGroupBox(heading)
            QVBoxLayout(group).addWidget(label(text))
            layout.addWidget(group)
        layout.addStretch()
