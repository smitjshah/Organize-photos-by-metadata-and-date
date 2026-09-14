"""Test-wide fixtures.

Redirects QSettings to a temp INI file for the whole test session so tests
never read or write the developer machine's real registry-backed app
settings (FolderPickerRow persists last-used paths via QSettings).
"""

from __future__ import annotations

import os
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QSettings


@pytest.fixture(autouse=True, scope="session")
def _isolated_qsettings():
    tmp_dir = tempfile.mkdtemp(prefix="photo_organizer_qsettings_")
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, tmp_dir)
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    yield
