"""Ongoing-use pipeline: sort a flat SOURCE folder into FUJI/PHOTOS destinations.

Callback-driven refactor of sort_photos.py's process(). No printing; all
progress goes through a ProgressReporter so both the CLI wrapper and the GUI
can drive this the same way.
"""

from __future__ import annotations

import re
from pathlib import Path

from .constants import PHOTO_EXTS, RAF_EXT
from .dedup import build_size_index, find_duplicate
from .fsops import safe_move, delete_raf, unique_dest
from .metadata import get_metadata, is_fuji, is_suspicious_date
from .progress import CancelToken, NullReporter, ProgressEvent, ProgressReporter
from .report import SortRunResult, build_sort_report

_DATE_PREFIX_RE = re.compile(r"^\d{4}-\d{2}-\d{2}_")


def process(
    source: Path,
    fuji_dest: Path,
    photos_dest: Path,
    dry_run: bool,
    report_path: Path,
    reporter: ProgressReporter | None = None,
    cancel_token: CancelToken | None = None,
) -> SortRunResult:
    reporter = reporter or NullReporter()
    cancel_token = cancel_token or CancelToken()

    result = SortRunResult(dry_run=dry_run, source=source, fuji_dest=fuji_dest, photos_dest=photos_dest)

    # Step 1 — scan source (flat, non-recursive)
    reporter.emit(ProgressEvent(stage="Scanning source", kind="info"))
    source_files = [f for f in source.iterdir() if f.is_file()]
    raf_files = [f for f in source_files if f.suffix.lower() == RAF_EXT]
    photo_files = [
        f for f in source_files if f.suffix.lower() in PHOTO_EXTS and f.suffix.lower() != RAF_EXT
    ]

    # Step 2 — delete RAF files
    total_raf = len(raf_files)
    for i, f in enumerate(raf_files, 1):
        cancel_token.raise_if_cancelled()
        reporter.emit(ProgressEvent(stage="Deleting RAF files", kind="progress", current=i, total=total_raf, item=f.name))
        try:
            delete_raf(f, dry_run)
            result.raf_deleted.append(f.name)
            reporter.emit(ProgressEvent(stage="Deleting RAF files", kind="raf_deleted", item=f.name))
        except OSError as e:
            result.raf_failed.append((f.name, str(e)))
            reporter.emit(ProgressEvent(stage="Deleting RAF files", kind="raf_failed", item=f.name, payload={"reason": str(e)}))

    # Step 3 — index destinations (size-based, fast)
    reporter.emit(ProgressEvent(stage="Indexing Fuji dest", kind="info"))
    fuji_size_idx = build_size_index(fuji_dest)
    reporter.emit(ProgressEvent(stage="Indexing Photos dest", kind="info"))
    photos_size_idx = build_size_index(photos_dest)

    # Steps 4-5 — route, rename, move
    review_dir = source / "review"
    fuji_new_dirs: set[str] = set()
    photos_new_dirs: set[str] = set()

    total = len(photo_files)
    for i, src_file in enumerate(photo_files, 1):
        cancel_token.raise_if_cancelled()
        reporter.emit(ProgressEvent(stage="Routing files", kind="progress", current=i, total=total, item=src_file.name))

        try:
            dt, date_src, make = get_metadata(src_file)
            fuji = is_fuji(make)
            dest_root = fuji_dest if fuji else photos_dest
            size_idx = fuji_size_idx if fuji else photos_size_idx

            date_prefix = dt.strftime("%Y-%m-%d")
            new_name = src_file.name if _DATE_PREFIX_RE.match(src_file.name) else f"{date_prefix}_{src_file.name}"

            yy, mm = dt.strftime("%Y"), dt.strftime("%m")
            dest_dir = dest_root / yy / mm
            dest_path = dest_dir / new_name

            matched = find_duplicate(src_file, size_idx)
            if matched:
                dup_dest = unique_dest(review_dir / src_file.name)
                if not dry_run:
                    review_dir.mkdir(parents=True, exist_ok=True)
                    safe_move(src_file, dup_dest, dry_run=False)
                result.duplicates.append((src_file.name, str(matched)))
                reporter.emit(ProgressEvent(
                    stage="Routing files", kind="duplicate", item=src_file.name,
                    payload={"matched": str(matched)},
                ))
                continue

            final = safe_move(src_file, dest_path, dry_run)

            try:
                sz = final.stat().st_size if final.exists() else src_file.stat().st_size
                size_idx.setdefault(sz, []).append(final)
            except OSError:
                pass

            record = (src_file.name, str(src_file), str(final))
            category = "fuji" if fuji else "photos"
            if fuji:
                result.fuji_moved.append(record)
                fuji_new_dirs.add(str(dest_dir))
            else:
                result.photos_moved.append(record)
                photos_new_dirs.add(str(dest_dir))

            if date_src == "filesystem":
                (result.fuji_fallback if fuji else result.photos_fallback).append((src_file.name, str(final)))
            if is_suspicious_date(dt, date_src, src_file):
                result.flagged_dates.append((src_file.name, str(final), dt.strftime("%Y-%m-%d")))
                reporter.emit(ProgressEvent(stage="Routing files", kind="flagged_date", item=src_file.name, payload={"dest": str(final)}))

            reporter.emit(ProgressEvent(
                stage="Routing files", kind="moved", item=src_file.name,
                payload={"dest": str(final), "category": category, "date_source": date_src},
            ))

        except Exception as e:
            result.errors.append((src_file.name, str(e)))
            reporter.emit(ProgressEvent(stage="Routing files", kind="error", item=src_file.name, payload={"reason": str(e)}))

    result.fuji_new_dirs = sorted(fuji_new_dirs)
    result.photos_new_dirs = sorted(photos_new_dirs)

    # Step 6 — verify source is clear
    remaining = [f for f in source.iterdir() if f.is_file() or (f.is_dir() and f.name != "review")]
    if not dry_run:
        result.source_leftovers = [str(f) for f in remaining]

    reporter.emit(ProgressEvent(stage="Verifying source", kind="info", payload={"remaining": len(remaining)}))

    # Save report
    report_text = build_sort_report(result)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report_text, encoding="utf-8")

    return result
