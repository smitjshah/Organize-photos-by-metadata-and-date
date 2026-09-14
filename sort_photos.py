#!/usr/bin/env python3
"""
sort_photos.py — Route new unsorted photos into Fuji / Photos destinations.

Thin CLI wrapper over photo_organizer.engine.sort_pipeline — all business
logic (EXIF reading, routing, renaming, deduplication) lives there so the
desktop GUI and this CLI share exactly one implementation.

Usage:
    python sort_photos.py --source /path/to/source --fuji /path/to/fuji --photos /path/to/photos
    python sort_photos.py --source /path/to/source --fuji /path/to/fuji --photos /path/to/photos --dry-run

Arguments:
    --source      Flat folder containing new, unsorted photos/videos
    --fuji        Destination root for Fujifilm files  (sorted into YYYY/MM/)
    --photos      Destination root for all other files (sorted into YYYY/MM/)
    --dry-run     Preview what would happen — no files are moved or deleted
    --report      Path to save the text report (default: SOURCE/sort_report.txt)
    --help        Show this help message
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from photo_organizer.engine.metadata import HAS_EXIFREAD, HAS_PIL
from photo_organizer.engine.sort_pipeline import process
from photo_organizer.cli.console import ConsoleReporter, ConsoleUI, bold, cyan, dim, green, red, yellow, DIVIDER


def show_empty_source(ui: ConsoleUI, source: Path, fuji_dest: Path, photos_dest: Path) -> None:
    ui.print_step("SURVEY")

    def _dest_info(label: str, path: Path) -> None:
        ui.pprint(f"  {bold(label)}")
        if path.exists():
            fc = sum(1 for f in path.rglob("*") if f.is_file())
            ui.pprint(f"    {'Status':<22} {green('EXISTS')}  —  {fc:,} files already present")
            yr_dirs = sorted(d.name for d in path.iterdir() if d.is_dir())
            if yr_dirs:
                ui.pprint(f"    {'Year folders':<22} {', '.join(yr_dirs)}")
        else:
            ui.pprint(f"    {'Status':<22} {dim('Does not exist yet (will be created on first run)')}")
        ui.pprint("")

    ui.pprint(f"  {bold('Source folder:')}  {source}")
    ui.pprint(f"    {'Total files':<22} {yellow('0  ← nothing to process')}")
    ui.pprint("")
    _dest_info("Fuji destination:", fuji_dest)
    _dest_info("Photos destination:", photos_dest)

    ui.print_step("RESULT")
    ui.pprint(f"  {yellow('SOURCE IS EMPTY — nothing to sort.')}")
    ui.pprint("")
    ui.pprint("  Drop new photos/videos flat into:")
    ui.pprint(f"    {cyan(str(source))}")
    ui.pprint("  Then re-run this script.")
    ui.pprint("")


def print_summary(ui: ConsoleUI, result, dry_run: bool, report_path: Path) -> None:
    ui.print_step("SUMMARY")

    def kv(label: str, value, w: int = 32) -> None:
        ui.pprint(f"  {label:<{w}} {value}")

    kv("Mode:", yellow("DRY RUN — no changes made") if dry_run else green("LIVE"))
    ui.pprint(f"  {'-' * 64}")
    kv("RAF deleted:", f"{len(result.raf_deleted)}  ({len(result.raf_failed)} failed)")
    ui.pprint(f"  {'-' * 64}")
    kv("Fuji files moved:", len(result.fuji_moved))
    kv("  ↳ filesystem date:", len(result.fuji_fallback))
    kv("  ↳ new subfolders:", len(result.fuji_new_dirs))
    ui.pprint(f"  {'-' * 64}")
    kv("Photo files moved:", len(result.photos_moved))
    kv("  ↳ filesystem date:", len(result.photos_fallback))
    kv("  ↳ new subfolders:", len(result.photos_new_dirs))
    ui.pprint(f"  {'-' * 64}")
    kv("Duplicates → /review/:", len(result.duplicates))
    kv("Flagged dates:", len(result.flagged_dates))
    kv("Errors:", len(result.errors))

    if dry_run:
        ui.pprint(f"\n  {yellow('Re-run without --dry-run to apply changes.')}")

    ui.pprint(f"\n  Report saved → {cyan(str(report_path))}")
    ui.pprint("")


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(
        description="Sort unsorted photos into Fuji / Photos destinations.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--source", required=True, help="Flat folder containing new, unsorted photos/videos")
    parser.add_argument("--fuji", required=True, help="Destination root for Fujifilm files (YYYY/MM/)")
    parser.add_argument("--photos", required=True, help="Destination root for all other files (YYYY/MM/)")
    parser.add_argument("--dry-run", action="store_true", help="Preview only — no files are moved or deleted")
    parser.add_argument("--report", default=None, help="Path to save text report (default: SOURCE/sort_report.txt)")
    args = parser.parse_args()

    source = Path(args.source).expanduser().resolve()
    fuji_dest = Path(args.fuji).expanduser().resolve()
    photos_dest = Path(args.photos).expanduser().resolve()
    report_path = Path(args.report).expanduser().resolve() if args.report else source / "sort_report.txt"

    ui = ConsoleUI()
    ui.pprint(f"\n{bold(DIVIDER)}")
    ui.pprint(f"  {bold('SORT PHOTOS')}  ·  Initialising")
    ui.pprint(bold(DIVIDER))

    if not HAS_EXIFREAD:
        ui.pprint(f"  {yellow('WARN')} exifread not installed — date/make extraction limited.")
        ui.pprint("       Install: pip install exifread")
    if not HAS_PIL:
        ui.pprint(f"  {yellow('WARN')} Pillow not installed — JPEG EXIF fallback disabled.")
        ui.pprint("       Install: pip install pillow")

    if not source.exists():
        ui.pprint(f"\n  {red('ERROR')} SOURCE not found: {source}")
        sys.exit(1)
    if not source.is_dir():
        ui.pprint(f"\n  {red('ERROR')} SOURCE is not a directory: {source}")
        sys.exit(1)

    source_files = [f for f in source.iterdir() if f.is_file()]
    if not source_files:
        show_empty_source(ui, source, fuji_dest, photos_dest)
        sys.exit(0)

    mode_label = "DRY RUN" if args.dry_run else "LIVE"
    ui.pprint(f"\n{bold(DIVIDER)}")
    ui.pprint(f"  {bold('SORT PHOTOS')}  —  {yellow(mode_label)}")
    ui.pprint(bold(DIVIDER))
    ui.pprint(f"  {'Source':<20} {source}")
    ui.pprint(f"  {'Fuji dest':<20} {fuji_dest}")
    ui.pprint(f"  {'Photos dest':<20} {photos_dest}")

    reporter = ConsoleReporter(ui)
    result = process(
        source=source,
        fuji_dest=fuji_dest,
        photos_dest=photos_dest,
        dry_run=args.dry_run,
        report_path=report_path,
        reporter=reporter,
    )

    print_summary(ui, result, args.dry_run, report_path)


if __name__ == "__main__":
    main()
