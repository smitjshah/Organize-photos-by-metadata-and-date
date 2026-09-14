"""Recursive file collection for the "sort from scratch" (organize) flow."""

from __future__ import annotations

import os
import re
from pathlib import Path

from .constants import PHOTO_EXTS, RAF_EXT, SKIP_TOP


def collect(root: Path) -> tuple[list[Path], list[Path]]:
    """Return (raf_files, photo_files) under root.

    Skips SKIP_TOP directories (review/, fuji/, .claude/) and any top-level
    YYYY directory, since those are already-processed destinations.
    """
    raf_files: list[Path] = []
    photo_files: list[Path] = []

    for dirpath, dirnames, filenames in os.walk(root):
        rel_parts = Path(dirpath).relative_to(root).parts

        if rel_parts and rel_parts[0].lower() in SKIP_TOP:
            dirnames.clear()
            continue

        if rel_parts and re.fullmatch(r"\d{4}", rel_parts[0]):
            dirnames.clear()
            continue

        for fname in filenames:
            fpath = Path(dirpath) / fname
            ext = fpath.suffix.lower()
            if ext == RAF_EXT:
                raf_files.append(fpath)
            elif ext in PHOTO_EXTS:
                photo_files.append(fpath)

    return raf_files, photo_files
