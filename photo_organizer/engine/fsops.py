"""Filesystem operations: unique naming, moves, RAF deletion, empty-dir cleanup."""

from __future__ import annotations

import shutil
from pathlib import Path

from .constants import MAX_PATH_WINDOWS

DATE_PREFIX_RE_SRC = r"^\d{4}-\d{2}-\d{2}_"


def unique_dest(dest: Path) -> Path:
    """Return dest, or dest with a _1/_2/... suffix if it already exists."""
    if not dest.exists():
        return dest
    stem, suf = dest.stem, dest.suffix
    i = 1
    while True:
        cand = dest.parent / f"{stem}_{i}{suf}"
        if not cand.exists():
            return cand
        i += 1


def is_path_too_long(path: Path) -> bool:
    return len(str(path)) >= MAX_PATH_WINDOWS


def safe_move(src: Path, dest: Path, dry_run: bool) -> Path:
    """Move src to a unique path under dest's parent, creating dirs as needed.

    Returns the final destination path (post de-collision). No-op filesystem
    change when dry_run is True.
    """
    final = unique_dest(dest)
    if not dry_run:
        final.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(final))
    return final


def delete_raf(path: Path, dry_run: bool) -> None:
    if not dry_run:
        path.unlink()


def remove_empty_dirs(root: Path, protected: set[Path], dry_run: bool) -> list[Path]:
    """Bottom-up removal of empty directories under root, skipping `protected`.

    Returns the list of directories removed (or that would be removed, in
    dry-run mode).
    """
    removed: list[Path] = []
    all_dirs = sorted(
        (d for d in root.rglob("*") if d.is_dir()),
        key=lambda d: len(d.parts),
        reverse=True,
    )
    for d in all_dirs:
        if d in protected:
            continue
        try:
            if not any(d.iterdir()):
                if not dry_run:
                    d.rmdir()
                removed.append(d)
        except OSError:
            pass
    return removed
