"""QSettings-backed persistence for remembered folder paths and app prefs."""

from __future__ import annotations

from PySide6.QtCore import QSettings

ORG_NAME = "PhotoOrganizer"
APP_NAME = "PhotoOrganizer"


class AppSettings:
    def __init__(self) -> None:
        self._qs = QSettings(ORG_NAME, APP_NAME)

    def get_path(self, key: str) -> str:
        return str(self._qs.value(key, "", type=str))

    def set_path(self, key: str, value: str) -> None:
        self._qs.setValue(key, value)

    def clear_all(self) -> None:
        self._qs.clear()
