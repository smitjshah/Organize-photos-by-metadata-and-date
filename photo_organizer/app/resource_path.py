"""Resolve app-owned resource paths both in dev and inside a PyInstaller onefile bundle."""

from __future__ import annotations

import sys
from pathlib import Path


def resource_path(rel: str) -> Path:
    if hasattr(sys, "_MEIPASS"):
        base = Path(sys._MEIPASS) / "photo_organizer" / "app"  # type: ignore[attr-defined]
    else:
        base = Path(__file__).resolve().parent
    return base / rel
