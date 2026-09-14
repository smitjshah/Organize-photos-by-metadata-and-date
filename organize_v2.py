#!/usr/bin/env python3
"""
Photo organizer v2

Thin CLI wrapper over photo_organizer.engine.organize_pipeline — all business
logic lives there so the desktop GUI and this CLI share exactly one
implementation. Previously ROOT / FUJI_ROOT / REVIEW / DRY_RUN were hardcoded
module-level globals; they are now CLI arguments.

- Deletes all RAF files
- Routes FUJIFILM files  → ROOT/Fuji/YYYY/MM/
- Routes all other files → ROOT/YYYY/MM/
- Renames: YYYY-MM-DD_original-filename.ext
- Deduplicates to ROOT/review/
- Cleans up empty folders

Usage:
  python organize_v2.py --root E:\\Photos          # dry run
  python organize_v2.py --root E:\\Photos --run     # live
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from photo_organizer.engine.organize_pipeline import process
from photo_organizer.cli.console import ConsoleReporter, ConsoleUI, bold, cyan, green, red, yellow, DIVIDER

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def print_summary(ui: ConsoleUI, result, dry_run: bool, report_path: Path) -> None:
    mode = "DRY RUN" if dry_run else "LIVE"
    fuji_total = len(result.fuji_ok) + len(result.fuji_fallback)
    other_total = len(result.other_ok) + len(result.other_fallback)
    ui.pprint(f"""
{bold(DIVIDER)}
SUMMARY  —  {yellow(mode) if dry_run else green(mode)}
{bold(DIVIDER)}
RAF deleted          : {len(result.raf_deleted)} ({len(result.raf_failed)} failed)
Fuji files moved     : {fuji_total}  (fallback: {len(result.fuji_fallback)}, dups: {len(result.fuji_dup)})
Other files moved    : {other_total}  (fallback: {len(result.other_fallback)}, dups: {len(result.other_dup)})
Flagged dates        : {len(result.flagged_dates)}
Empty dirs removed   : {len(result.removed_dirs)}
Errors               : {len(result.errors) + len(result.dir_errors)}
Report saved to      : {report_path}
""")
    if dry_run:
        ui.pprint("Run with --run to execute for real.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="One-time bulk reorganize of an existing photo root.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--root", required=True, help="Root of the photo library to reorganize")
    parser.add_argument("--run", action="store_true", help="Live run (default is dry run — no files moved/deleted)")
    parser.add_argument("--report", default=None, help="Path to save text report (default: ROOT/organize_v2_report.txt)")
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    fuji_root = root / "Fuji"
    review = root / "review"
    report_path = Path(args.report).expanduser().resolve() if args.report else root / "organize_v2_report.txt"
    dry_run = not args.run

    ui = ConsoleUI()

    if not root.exists() or not root.is_dir():
        ui.pprint(f"\n  {red('ERROR')} ROOT not found or not a directory: {root}")
        sys.exit(1)

    ui.pprint(f"\n{'=' * 60}\nOrganize v2 — {yellow('DRY RUN') if dry_run else green('LIVE')}\n{'=' * 60}")
    ui.pprint(f"  {'Root':<12} {root}")
    ui.pprint(f"  {'Fuji dest':<12} {fuji_root}")
    ui.pprint(f"  {'Review':<12} {review}")

    reporter = ConsoleReporter(ui)
    result = process(
        root=root,
        fuji_root=fuji_root,
        review=review,
        report_path=report_path,
        dry_run=dry_run,
        reporter=reporter,
    )

    print_summary(ui, result, dry_run, report_path)


if __name__ == "__main__":
    main()
