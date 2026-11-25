from PySide6.QtWidgets import (
    QHBoxLayout, QListWidget, QMainWindow, QStackedWidget, QVBoxLayout, QWidget,
)

from ..inventory import Inventory
from .add_product import AddProductScreen
from .components import AUTHOR, label, named
from .dialogs import choose_file, error, message
from .home import HelpScreen, HomeScreen
from .listing import InventoryScreen
from .reports import BrandScreen, CategoryScreen
from .stock import StockScreen


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.inventory = Inventory()
        self.resize(1100, 690)
        self.setObjectName("mainWindow")
        root = QWidget()
        self.setCentralWidget(root)
        shell = QHBoxLayout(root)
        rail = QVBoxLayout()
        rail.addWidget(label("COMPONENTE  /  PC", "masthead"))
        self.nav = named(QListWidget(), "navigation")
        self.nav.setFixedWidth(195)
        rail.addWidget(self.nav)
        rail.addWidget(label(AUTHOR))
        shell.addLayout(rail)
        body = QVBoxLayout()
        shell.addLayout(body, 1)
        self.title = label("", "pageTitle")
        body.addWidget(self.title)
        self.stack = named(QStackedWidget(), "pages")
        body.addWidget(self.stack, 1)

        self.home = HomeScreen()
        self.listing = InventoryScreen(self.inventory)
        self.add = AddProductScreen(self.inventory)
        self.stock = StockScreen(self.inventory)
        self.category = CategoryScreen()
        self.brand = BrandScreen()
        help_page = HelpScreen()
        self._file_menu()
        pages_menu = self.menuBar().addMenu("&Navigare")
        for title, page in (("Acasă", self.home), ("Inventar", self.listing), ("Adăugare produs", self.add),
                            ("Operații de stoc", self.stock), ("Valoare pe categorie", self.category),
                            ("Căutare după marcă", self.brand), ("Ajutor", help_page)):
            row = self.stack.addWidget(page)
            self.nav.addItem(title)
            action = named(pages_menu.addAction(title), f"actionPage{row}")
            action.setShortcut("F1" if page is help_page else f"Alt+{row + 1}")
            action.triggered.connect(lambda checked=False, target=page: self._go(target))

        self.nav.currentRowChanged.connect(self._navigate)
        self.home.new_requested.connect(self.new_inventory)
        self.home.open_requested.connect(self.open_inventory)
        self.home.save_requested.connect(self.save_as)
        self.listing.add_requested.connect(lambda: self._go(self.add))
        self.listing.stock_requested.connect(lambda: self._go(self.stock))
        self.listing.code_selected.connect(self.stock.select_code)
        self.stock.code_selected.connect(self.listing.select_code)
        self.add.added.connect(self._product_added)
        self.listing.deleted.connect(lambda code: self._changed(None, f"Produs șters: {code}"))
        self.stock.updated.connect(self._changed)
        self._go(self.home)
        self._refresh()
        self.setStyleSheet("""
            QLabel#masthead { color: #257e79; font-weight: bold; padding: 8px 2px; }
            QLabel#pageTitle { font-size: 22pt; font-weight: bold; padding: 2px 8px; }
            QLabel#categoryTotal { font-size: 18pt; font-weight: bold; }
            QListWidget#navigation { border: none; background: #193d40; color: white; }
            QListWidget#navigation::item { padding: 10px 8px; }
            QListWidget#navigation::item:selected { background: #26746e; color: white; }
            QGroupBox { font-weight: bold; margin-top: 10px; padding-top: 10px; }
            QPushButton { padding: 5px 12px; }
        """)

    def _file_menu(self) -> None:
        menu = self.menuBar().addMenu("&Fișier")
        for text, name, key, callback in (
            ("Inventar nou…", "actionNew", "Ctrl+N", self.new_inventory),
            ("Deschide…", "actionOpen", "Ctrl+O", self.open_inventory),
            ("Salvează ca…", "actionSaveAs", "Ctrl+Shift+S", self.save_as),
            ("Ieșire", "actionExit", "Ctrl+Q", self.close),
        ):
            action = named(menu.addAction(text), name)
            action.setShortcut(key)
            action.triggered.connect(callback)
            if name == "actionSaveAs":
                self.save_action = action

    def _go(self, screen: QWidget) -> None:
        self.nav.setCurrentRow(self.stack.indexOf(screen))

    def _navigate(self, row: int) -> None:
        self.stack.setCurrentIndex(row)
        self.title.setText(self.nav.item(row).text())
        self._window_title()

    def _window_title(self) -> None:
        filename = self.inventory.path.name if self.inventory.path else "Fără fișier"
        self.setWindowTitle(f"{self.title.text()} | {filename} | {AUTHOR}")

    def new_inventory(self) -> None:
        try:
            path = choose_file(self, "Inventar nou", self.inventory.path, save=True)
            if path is None:
                return
            candidate = Inventory()
            candidate.save_as(path)
        except (ValueError, OSError) as exc:
            error(self, exc)
            return
        self._activate(candidate, "Inventarul nou a fost creat.")

    def open_inventory(self) -> None:
        try:
            path = choose_file(self, "Deschide inventarul", self.inventory.path, save=False)
            if path is None:
                return
            candidate = Inventory()
            warnings = candidate.load(path)
        except (ValueError, OSError) as exc:
            error(self, exc)
            return
        self._activate(candidate, "Inventarul a fost încărcat.")
        if warnings:
            message(self, "Avertismente la încărcare", "\n".join(warnings))

    def _activate(self, inventory: Inventory, status: str) -> None:
        self.inventory = inventory
        self.add.reset()
        self.stock.reset()
        self._go(self.listing)
        self._changed(None, status)

    def save_as(self) -> None:
        try:
            path = choose_file(self, "Salvează inventarul ca", self.inventory.path, save=True)
            if path is None:
                return
            self.inventory.save_as(path)
        except (ValueError, OSError) as exc:
            error(self, exc)
            return
        self._window_title()
        self._refresh_home()
        self.statusBar().showMessage("Inventarul a fost salvat în fișierul ales.", 5000)

    def _product_added(self, code: str) -> None:
        self._changed(code, f"Produs adăugat: {code}")
        self._go(self.listing)

    def _changed(self, selected: str | None, status: str) -> None:
        self._refresh(selected)
        self.statusBar().showMessage(status, 5000)

    def _refresh_home(self) -> str:
        products = self.inventory.products
        summary = f"Produse: {len(products)}   ·   Bucăți în stoc: {sum(p.stoc for p in products)}"
        self.home.refresh(self.inventory.path, summary)
        return summary

    def _refresh(self, selected: str | None = None) -> None:
        summary = self._refresh_home()
        selected = self.listing.refresh(self.inventory, summary, selected)
        self.stock.refresh(self.inventory, selected)
        self.add.refresh(self.inventory)
        self.save_action.setEnabled(self.inventory.path is not None)
        self.category.inventory_changed(self.inventory)
        self.brand.inventory_changed(self.inventory)
        self._window_title()
