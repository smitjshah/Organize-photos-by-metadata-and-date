"""Duplicate detection helpers.

Two strategies are used by the two flows:
  - sort_pipeline: size-first index against an existing destination tree,
    MD5 only computed on a size collision (fast for 80k+ existing files).
  - organize_pipeline: whole-tree MD5 index built incrementally as files
    are processed (the source tree isn't pre-populated with duplicates
    the way an ongoing destination is, so upfront hashing is acceptable).
"""

from __future__ import annotations

import hashlib
from pathlib import Path


def md5(path: Path, bs: int = 65536) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        while chunk := f.read(bs):
            h.update(chunk)
    return h.hexdigest()


def build_size_index(dest_root: Path) -> dict[int, list[Path]]:
    """Build {file_size_bytes: [Path, ...]} for dest_root using only stat()."""
    index: dict[int, list[Path]] = {}
    if not dest_root.exists():
        return index
    for f in dest_root.rglob("*"):
        if not f.is_file():
            continue
        try:
            sz = f.stat().st_size
            index.setdefault(sz, []).append(f)
        except OSError:
            pass
    return index


def find_duplicate(src: Path, size_index: dict[int, list[Path]]) -> Path | None:
    """Return the matching destination Path if src is a duplicate, else None.

    MD5 is only computed when a size collision exists against the index.
    """
    try:
        sz = src.stat().st_size
    except OSError:
        return None
    candidates = size_index.get(sz, [])
    if not candidates:
        return None
    try:
        src_hash = md5(src)
    except OSError:
        return None
    for cand in candidates:
        try:
            if md5(cand) == src_hash:
                return cand
        except OSError:
            pass
    return None
