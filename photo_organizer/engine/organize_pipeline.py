"""One-time bulk pipeline: reorganize an entire existing ROOT tree.

Callback-driven refactor of organize_v2.py's main(). All previously
hardcoded module-level config (ROOT, FUJI_ROOT, REVIEW, DRY_RUN) is now
passed in as parameters.

Bug fix vs. the original script: the duplicate-detection branch used to
call is_fuji(None) (always False) to decide whether a duplicate belonged
in the fuji or "other" report bucket, because metadata wasn't looked up
until after the dedup check. This version reads metadata first, so
duplicates are attributed correctly.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from .collect import collect
from .dedup import md5
from .fsops import remove_empty_dirs, safe_move, unique_dest
from .metadata import get_metadata, is_fuji, is_suspicious_date
from .progress import CancelToken, NullReporter, ProgressEvent, ProgressReporter
from .report import OrganizeRunResult, build_organize_report

_DATE_PREFIX_RE = re.compile(r"^\d{4}-\d{2}-\d{2}_")


def process(
    root: Path,
    fuji_root: Path,
    review: Path,
    report_path: Path,
    dry_run: bool,
    reporter: ProgressReporter | None = None,
    cancel_token: CancelToken | None = None,
) -> OrganizeRunResult:
    reporter = reporter or NullReporter()
    cancel_token = cancel_token or CancelToken()

    result = OrganizeRunResult(dry_run=dry_run, root=root)

    if not dry_run:
        review.mkdir(parents=True, exist_ok=True)

    # Collect
    reporter.emit(ProgressEvent(stage="Scanning root", kind="info"))
    raf_list, photos = collect(root)
    reporter.emit(ProgressEvent(stage="Scanning root", kind="info", payload={"raf": len(raf_list), "photos": len(photos)}))

    # RAF deletion
    total_raf = len(raf_list)
    for i, f in enumerate(raf_list, 1):
        cancel_token.raise_if_cancelled()
        reporter.emit(ProgressEvent(stage="Deleting RAF files", kind="progress", current=i, total=total_raf, item=f.name))
        try:
            if not dry_run:
                f.unlink()
            result.raf_deleted.append(str(f.relative_to(root)))
            reporter.emit(ProgressEvent(stage="Deleting RAF files", kind="raf_deleted", item=f.name))
        except OSError as e:
            result.raf_failed.append((str(f.relative_to(root)), str(e)))
            reporter.emit(ProgressEvent(stage="Deleting RAF files", kind="raf_failed", item=f.name, payload={"reason": str(e)}))

    # Route, rename, dedup
    total = len(photos)
    seen: dict[str, Path] = {}

    for i, src in enumerate(photos, 1):
        cancel_token.raise_if_cancelled()
        reporter.emit(ProgressEvent(stage="Routing files", kind="progress", current=i, total=total, item=src.name))

        try:
            dt, date_src, make = get_metadata(src)
            fuji = is_fuji(make)
            h = md5(src)

            if h in seen:
                dst = unique_dest(review / src.name)
                if not dry_run:
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(src), str(dst))
                entry = (src.name, str(dst.relative_to(root)) if not dry_run else str(dst))
                (result.fuji_dup if fuji else result.other_dup).append(entry)
                reporter.emit(ProgressEvent(stage="Routing files", kind="duplicate", item=src.name, payload={"matched": str(seen[h])}))
                continue

            prefix = dt.strftime("%Y-%m-%d")
            new_name = src.name if _DATE_PREFIX_RE.match(src.name) else f"{prefix}_{src.name}"

            yy, mm = dt.strftime("%Y"), dt.strftime("%m")
            dst = (fuji_root if fuji else root) / yy / mm / new_name

            final = safe_move(src, dst, dry_run)
            seen[h] = final

            fallback = date_src == "filesystem"
            rel = str(final.relative_to(root)) if final.is_relative_to(root) else str(final)
            record = (src.name, rel)

            if fuji:
                (result.fuji_fallback if fallback else result.fuji_ok).append(record)
            else:
                (result.other_fallback if fallback else result.other_ok).append(record)

            if is_suspicious_date(dt, date_src, src):
                result.flagged_dates.append((src.name, rel, dt.strftime("%Y-%m-%d")))
                reporter.emit(ProgressEvent(stage="Routing files", kind="flagged_date", item=src.name, payload={"dest": rel}))

            reporter.emit(ProgressEvent(
                stage="Routing files", kind="moved", item=src.name,
                payload={"dest": rel, "category": "fuji" if fuji else "other", "date_source": date_src},
            ))

        except Exception as e:
            result.errors.append((str(src), str(e)))
            reporter.emit(ProgressEvent(stage="Routing files", kind="error", item=src.name, payload={"reason": str(e)}))

    # Empty folder cleanup
    reporter.emit(ProgressEvent(stage="Removing empty folders", kind="info"))
    protected = {review, fuji_root}
    removed = remove_empty_dirs(root, protected, dry_run)
    result.removed_dirs = [str(d.relative_to(root)) for d in removed]
    for d in removed:
        reporter.emit(ProgressEvent(stage="Removing empty folders", kind="dir_removed", item=str(d.relative_to(root))))

    # Save report
    report_text = build_organize_report(result)
    report_path.write_text(report_text, encoding="utf-8")

    return result
