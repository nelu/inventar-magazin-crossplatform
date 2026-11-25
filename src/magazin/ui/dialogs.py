from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QFileDialog, QMessageBox, QWidget

from .components import AUTHOR, named


def message(parent: QWidget, title: str, text: str, *, confirm: bool = False) -> bool:
    box = named(QMessageBox(parent), "confirmationDialog" if confirm else "messageDialog")
    box.setWindowTitle(f"{title} | {AUTHOR}")
    box.setIcon(QMessageBox.Icon.Question if confirm else QMessageBox.Icon.Warning)
    box.setTextFormat(Qt.TextFormat.PlainText)
    box.setText(text)
    if confirm:
        yes = box.addButton("Da", QMessageBox.ButtonRole.YesRole)
        no = box.addButton("Nu", QMessageBox.ButtonRole.NoRole)
        box.setDefaultButton(no)
        box.setEscapeButton(no)
    else:
        box.addButton("Închide", QMessageBox.ButtonRole.AcceptRole)
    box.exec()
    accepted = confirm and box.clickedButton() == yes
    box.deleteLater()
    return accepted


def error(parent: QWidget, exc: Exception) -> None:
    message(parent, "Operație nereușită", str(exc))


def choose_file(parent: QWidget, title: str, current: Path | None, *, save: bool) -> Path | None:
    picker = named(QFileDialog(parent), "fileDialog")
    picker.setOption(QFileDialog.Option.DontUseNativeDialog)
    picker.setOption(QFileDialog.Option.ReadOnly)
    picker.setOption(QFileDialog.Option.DontConfirmOverwrite)
    picker.setWindowTitle(f"{title} | {AUTHOR}")
    picker.setNameFilter("Fișiere CSV (*.csv);;Toate fișierele (*)")
    picker.setAcceptMode(QFileDialog.AcceptMode.AcceptSave if save else QFileDialog.AcceptMode.AcceptOpen)
    picker.setFileMode(QFileDialog.FileMode.AnyFile if save else QFileDialog.FileMode.ExistingFile)
    picker.setLabelText(QFileDialog.DialogLabel.Accept, "Salvează" if save else "Deschide")
    picker.setLabelText(QFileDialog.DialogLabel.Reject, "Anulează")
    picker.setLabelText(QFileDialog.DialogLabel.FileName, "Nume fișier:")
    picker.setLabelText(QFileDialog.DialogLabel.FileType, "Tip fișier:")
    if current:
        picker.setDirectory(str(current.parent))
    if save:
        picker.setDefaultSuffix("csv")
    path = Path(picker.selectedFiles()[0]) if picker.exec() == QDialog.DialogCode.Accepted else None
    picker.deleteLater()
    if save and path and path.exists() and not message(
        parent, "Înlocuire fișier", f"Înlocuiești fișierul {path}?", confirm=True
    ):
        return None
    return path
