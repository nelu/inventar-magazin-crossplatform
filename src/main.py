"""Punct de pornire pentru aplicația desktop Magazin."""

import sys

from PySide6.QtCore import QLocale
from PySide6.QtWidgets import QApplication

from magazin.ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Magazin componente PC")
    QLocale.setDefault(QLocale(QLocale.Language.Romanian, QLocale.Country.Romania))
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
