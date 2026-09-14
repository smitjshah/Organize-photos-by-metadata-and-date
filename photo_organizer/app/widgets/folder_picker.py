"""Reusable labeled folder-picker row with optional QSettings persistence."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel, CaptionLabel, FluentIcon, LineEdit, PushButton

from photo_organizer.app.settings import AppSettings


class FolderPickerRow(QWidget):
    """A label + text field + Browse button, remembering its last value if given a settings key."""

    pathChanged = Signal()

    def __init__(self, label: str, settings_key: str | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._settings = AppSettings() if settings_key else None
        self._settings_key = settings_key

        self.edit = LineEdit()
        self.edit.setPlaceholderText(f"Select the {label.lower()} folder…")
        self.browse_btn = PushButton(FluentIcon.FOLDER, "Browse…")
        self.browse_btn.clicked.connect(self._browse)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(self.edit, 1)
        row.addWidget(self.browse_btn, 0)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(BodyLabel(label))
        layout.addLayout(row)

        if self._settings and self._settings_key:
            saved = self._settings.get_path(self._settings_key)
            if saved:
                self.edit.setText(saved)

        self.edit.textChanged.connect(self._on_text_changed)

    def _browse(self) -> None:
        start_dir = self.edit.text().strip() or str(Path.home())
        path = QFileDialog.getExistingDirectory(self, "Select folder", start_dir)
        if path:
            self.edit.setText(path)

    def _on_text_changed(self, text: str) -> None:
        if self._settings and self._settings_key:
            self._settings.set_path(self._settings_key, text.strip())
        self.pathChanged.emit()

    def path(self) -> Path | None:
        text = self.edit.text().strip()
        return Path(text) if text else None

    def set_enabled_all(self, enabled: bool) -> None:
        self.edit.setEnabled(enabled)
        self.browse_btn.setEnabled(enabled)
