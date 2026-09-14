"""Shared post-run summary panel: counts + "Open report" / "Open folder" actions."""

from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel, PushButton, FluentIcon


class SummaryView(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.text_label = BodyLabel("")
        self.text_label.setWordWrap(True)

        self._actions_layout = QHBoxLayout()
        self._actions_layout.setContentsMargins(0, 0, 0, 0)
        self._action_buttons: list[PushButton] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self.text_label)
        layout.addLayout(self._actions_layout)

        self.clear()

    def clear(self) -> None:
        self.text_label.setText("")
        self._clear_actions()

    def _clear_actions(self) -> None:
        for btn in self._action_buttons:
            self._actions_layout.removeWidget(btn)
            btn.deleteLater()
        self._action_buttons = []

    def show_summary(self, lines: list[str], report_path: Path | None, open_folders: dict[str, Path] | None = None) -> None:
        self.text_label.setText("   ".join(lines))
        self._clear_actions()

        if report_path is not None:
            btn = PushButton(FluentIcon.DOCUMENT, "Open Report")
            btn.clicked.connect(lambda: self._open_path(report_path))
            self._actions_layout.addWidget(btn)
            self._action_buttons.append(btn)

        for label, path in (open_folders or {}).items():
            btn = PushButton(FluentIcon.FOLDER, f"Open {label}")
            btn.clicked.connect(lambda checked=False, p=path: self._open_path(p))
            self._actions_layout.addWidget(btn)
            self._action_buttons.append(btn)

    @staticmethod
    def _open_path(path: Path) -> None:
        try:
            os.startfile(str(path))  # noqa: S606 - user-initiated, Windows-only app
        except OSError:
            pass
