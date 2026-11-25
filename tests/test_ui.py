"""Headless smoke tests using the same Qt controls as the desktop user."""

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from PySide6.QtCore import QTimer
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QLabel, QLineEdit, QListWidget,
    QMessageBox, QPushButton, QSpinBox, QStackedWidget, QTableWidget,
)

# src/main.py runs with src on the import path; discovery runs from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
try:
    from magazin.ui.main_window import MainWindow
finally:
    sys.path.pop(0)


AUTHOR = "Cosmin Zarzu 208ID"
SCREENS = (
    ("Acasă", "homePage"), ("Inventar", "inventoryPage"),
    ("Adăugare produs", "addPage"), ("Operații de stoc", "stockPage"),
    ("Valoare pe categorie", "categoryPage"), ("Căutare după marcă", "brandPage"),
    ("Ajutor", "helpPage"),
)


class WidgetSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(["ui-smoke", "-platform", "offscreen"])

    def setUp(self):
        self.window = MainWindow()
        self.addCleanup(self.window.deleteLater)
        self.addCleanup(self.window.close)
        self.window.show()
        self.nav = self.control(QListWidget, "navigation")

    def control(self, kind, name):
        widget = self.window.findChild(kind, name)
        self.assertIsNotNone(widget, name)
        return widget

    def click(self, name, *, title=None, file=None, answer=None):
        button = self.control(QPushButton, name)
        self.assertTrue(button.isVisible() and button.isEnabled(), name)
        seen = []
        errors = []

        # exec() runs a nested event loop. Answer there, but report failures in
        # the test thread after click() returns; never leave a modal open on error.
        def respond():
            dialog = self.app.activeModalWidget()
            if dialog is None:
                return
            seen.append(dialog.windowTitle())
            try:
                self.assertEqual(seen, [f"{title} | {AUTHOR}"] if title else [])
                if file is not None:
                    self.assertIsInstance(dialog, QFileDialog)
                    # Submit the absolute path through the filename field, without
                    # waiting for the dialog's asynchronous directory model.
                    filename = dialog.findChild(QLineEdit, "fileNameEdit")
                    self.assertIsNotNone(filename)
                    filename.setText(str(file))
                    dialog.accept()
                else:
                    self.assertIsInstance(dialog, QMessageBox)
                    next(b for b in dialog.buttons() if b.text() == answer).click()
            except Exception as exc:
                errors.append(exc)
                dialog.reject()

        timer = QTimer()
        timer.timeout.connect(respond)
        timer.start(20)
        try:
            button.click()
        finally:
            timer.stop()
        if errors:
            raise errors[0]
        self.assertEqual(seen, [f"{title} | {AUTHOR}"] if title else [])

    def test_seven_screens_and_titles(self):
        pages = self.control(QStackedWidget, "pages")
        self.assertEqual(self.nav.count(), len(SCREENS))
        self.assertEqual(pages.count(), len(SCREENS))
        for index, (title, page) in enumerate(SCREENS):
            with self.subTest(title=title):
                self.nav.setCurrentRow(index)
                self.assertEqual(self.nav.currentItem().text(), title)
                self.assertEqual(pages.currentWidget().objectName(), page)
                self.assertTrue(pages.currentWidget().isVisible())
                self.assertEqual(self.control(QLabel, "pageTitle").text(), title)
                self.assertEqual(self.window.windowTitle(), f"{title} | Fără fișier | {AUTHOR}")

    def test_menu_actions_shortcuts_and_initial_controls(self):
        menu_actions = self.window.menuBar().actions()
        file_menu, navigation = [a.menu() for a in menu_actions]
        self.assertEqual((file_menu.title(), navigation.title()), ("&Fișier", "&Navigare"))
        self.assertEqual([(a.objectName(), a.shortcut().toString()) for a in file_menu.actions()], [
            ("actionNew", "Ctrl+N"), ("actionOpen", "Ctrl+O"),
            ("actionSaveAs", "Ctrl+Shift+S"), ("actionExit", "Ctrl+Q"),
        ])
        self.assertFalse(self.control(QAction, "actionSaveAs").isEnabled())
        self.assertFalse(self.control(QPushButton, "saveAs").isEnabled())
        self.assertFalse(self.control(QPushButton, "addProduct").isEnabled())
        for index, ((title, page), action) in enumerate(zip(SCREENS, navigation.actions(), strict=True)):
            self.assertEqual(action.objectName(), f"actionPage{index}")
            self.assertEqual(action.text(), title)
            self.assertEqual(action.shortcut().toString(), "F1" if page == "helpPage" else f"Alt+{index + 1}")
            action.trigger()
            self.assertEqual(self.control(QStackedWidget, "pages").currentWidget().objectName(), page)
        self.assertEqual(self.control(QComboBox, "brandQuery").accessibleName(), "Marcă")
        self.assertEqual(self.control(QComboBox, "categoryQuery").accessibleName(), "Categorie")

    def test_selection_sync_and_deferred_reports(self):
        path = Path(self.enterContext(TemporaryDirectory())) / "parts.csv"
        path.write_text("A;2;First;2020;1;Factory;RO;CPU;1\nB;3;Second;2021;2;Factory;RO;RAM;2\n",
                        encoding="utf-8")
        self.click("openInventory", title="Deschide inventarul", file=path)
        table = self.control(QTableWidget, "inventoryTable")
        code = self.control(QComboBox, "stockCode")
        table.selectRow(1)
        self.click("goStock")
        self.assertEqual(code.currentText(), "B")
        code.setCurrentText("A")
        self.assertEqual(table.selectionModel().selectedRows()[0].data(), "A")
        code.setCurrentText("B")
        self.assertEqual(table.selectionModel().selectedRows()[0].data(), "B")

        category = self.control(QComboBox, "categoryQuery")
        brand = self.control(QComboBox, "brandQuery")
        self.nav.setCurrentRow(4)
        category.setCurrentText("RAM")
        self.nav.setCurrentRow(5)
        brand.setCurrentText("Second")
        self.nav.setCurrentRow(3)
        inventory = self.window.inventory
        with (patch.object(inventory, "total", wraps=inventory.total) as total,
              patch.object(inventory, "by_brand", wraps=inventory.by_brand) as by_brand):
            self.click("sellOne")
            total.assert_not_called()
            by_brand.assert_not_called()
            self.nav.setCurrentRow(4)
            total.assert_called_once_with("RAM")
            self.assertEqual(self.control(QLabel, "categoryTotal").text(), "3.00 lei")
            by_brand.assert_not_called()
            self.nav.setCurrentRow(5)
            by_brand.assert_called_once_with("Second")
            self.assertEqual(self.control(QTableWidget, "brandTable").item(0, 8).text(), "1")

        self.nav.setCurrentRow(0)
        self.click("newInventory", title="Inventar nou", file=path.with_name("empty.csv"))
        self.nav.setCurrentRow(4)
        self.assertEqual(category.currentText(), "")
        self.assertEqual(self.control(QLabel, "categoryTotal").text(), "Nicio categorie selectată.")
        self.nav.setCurrentRow(5)
        self.assertEqual(brand.currentText(), "")
        self.assertEqual(self.control(QTableWidget, "brandTable").rowCount(), 0)

    def test_save_as_switches_file_without_losing_draft(self):
        source = Path(self.enterContext(TemporaryDirectory())) / "source.csv"
        copy = source.with_name("copy.csv")
        original = "A;2;First;2020;1;Factory;RO;CPU;1\n"
        source.write_text(original, encoding="utf-8")
        self.click("openInventory", title="Deschide inventarul", file=source)
        self.click("goAdd")
        draft = self.control(QLineEdit, "cod")
        draft.setText("draft")
        self.nav.setCurrentRow(0)
        self.click("saveAs", title="Salvează inventarul ca", file=copy)
        self.assertEqual(self.window.windowTitle(), f"Acasă | copy.csv | {AUTHOR}")
        self.assertEqual(Path(self.control(QLabel, "currentFile").text()), copy)
        self.nav.setCurrentRow(2)
        self.assertEqual(draft.text(), "draft")
        self.nav.setCurrentRow(3)
        self.click("sellOne")
        self.assertEqual(source.read_text(encoding="utf-8"), original)
        self.assertEqual(copy.read_text(encoding="utf-8").splitlines()[-1], "A;2.00;First;2020;1;Factory;RO;CPU;0")
        self.nav.setCurrentRow(0)
        self.click("openInventory", title="Deschide inventarul", file=source)
        self.nav.setCurrentRow(2)
        self.assertEqual(draft.text(), "")

    def test_inventory_workflow(self):
        directory = self.enterContext(TemporaryDirectory())
        path = Path(directory) / "smoke.csv"
        self.click("newInventory", title="Inventar nou", file=path)
        self.assertEqual(self.window.windowTitle(), f"Inventar | smoke.csv | {AUTHOR}")
        table = self.control(QTableWidget, "inventoryTable")
        self.assertEqual(table.rowCount(), 0)
        self.click("goAdd")
        for field, text in (("cod", "C01"), ("pret", "12,50"), ("marca", "Acme"),
                            ("producator", "Factory"), ("tara", "RO"), ("categorie", "CPU")):
            self.control(QLineEdit, field).setText(text)
        for field, value in (("an", 2024), ("garantie", 12), ("stoc", 1)):
            self.control(QSpinBox, field).setValue(value)
        self.click("addProduct")
        row = ["C01", "12.50", "Acme", "2024", "12", "Factory", "RO", "CPU", "1"]

        def check_row(grid):
            self.assertEqual(grid.rowCount(), 1)
            self.assertEqual([grid.item(0, i).text() for i in range(grid.columnCount())], row)

        check_row(table)
        table.selectRow(0)
        self.click("goStock")
        self.assertEqual(self.control(QComboBox, "stockCode").currentText(), "C01")
        self.click("sellOne")
        self.assertFalse(self.control(QPushButton, "sellOne").isEnabled())
        self.assertEqual(table.item(0, 8).text(), "0")
        self.control(QSpinBox, "restockQuantity").setValue(3)
        self.click("restock")
        row[-1] = "3"
        check_row(table)

        self.nav.setCurrentRow(4)
        category = self.control(QComboBox, "categoryQuery")
        for query, total in (("RAM", "0.00 lei"), ("CPU", "37.50 lei")):
            category.setCurrentText(query)
            self.assertEqual(self.control(QLabel, "categoryTotal").text(), total)
        self.nav.setCurrentRow(5)
        brand = self.control(QComboBox, "brandQuery")
        matches = self.control(QTableWidget, "brandTable")
        brand.setCurrentText("Other")
        self.assertEqual(matches.rowCount(), 0)
        brand.setCurrentText("Acme")
        check_row(matches)

        # Switch files first so stale in-memory rows cannot pass a reopen check.
        self.nav.setCurrentRow(0)
        self.click("newInventory", title="Inventar nou", file=path.with_name("empty.csv"))
        self.assertEqual(table.rowCount(), 0)
        self.nav.setCurrentRow(0)
        self.click("openInventory", title="Deschide inventarul", file=path)
        self.assertEqual(self.window.windowTitle(), f"Inventar | smoke.csv | {AUTHOR}")
        check_row(table)
        self.click("deleteProduct", title="Ștergere produs", answer="Nu")
        check_row(table)
        self.click("deleteProduct", title="Ștergere produs", answer="Da")
        self.assertEqual(table.rowCount(), 0)
        self.nav.setCurrentRow(0)
        self.click("openInventory", title="Deschide inventarul", file=path)
        self.assertEqual(table.rowCount(), 0)
        self.assertFalse(self.control(QPushButton, "deleteProduct").isEnabled())
