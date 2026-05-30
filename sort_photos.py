#!/usr/bin/env python3
"""
sort_photos.py — Route new unsorted photos into Fuji / Photos destinations.

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

import os
import sys
import re
import hashlib
import shutil
import argparse
import logging
import time
from datetime import datetime
from pathlib import Path

# ── optional dependencies ────────────────────────────────────────────────────
try:
    import exifread
    logging.getLogger("exifread").setLevel(logging.CRITICAL)
    HAS_EXIFREAD = True
except ImportError:
    HAS_EXIFREAD = False

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# ── constants ─────────────────────────────────────────────────────────────────
PHOTO_EXTS = {
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".tif",
    ".heic", ".heif", ".raw", ".cr2", ".nef", ".arw", ".dng",
    ".webp", ".mp4", ".mov", ".avi", ".mkv", ".3gp",
}

BAR_LEN  = 32
DIVIDER  = "=" * 64
THIN_DIV = "-" * 64

# ── TTY / colour detection ─────────────────────────────────────────────────────
IS_TTY = hasattr(sys.stdout, "isatty") and sys.stdout.isatty()

def _supports_colour():
    if not IS_TTY:
        return False
    if sys.platform == "win32":
        return bool(os.environ.get("WT_SESSION") or os.environ.get("ANSICON")
                    or os.environ.get("TERM_PROGRAM"))
    return True

USE_COLOUR = _supports_colour()

def _c(text, code):  return f"\033[{code}m{text}\033[0m" if USE_COLOUR else text
def green(t):   return _c(t, "32")
def yellow(t):  return _c(t, "33")
def red(t):     return _c(t, "31")
def bold(t):    return _c(t, "1")
def cyan(t):    return _c(t, "36")
def dim(t):     return _c(t, "2")
def magenta(t): return _c(t, "35")


# ── progress bar ──────────────────────────────────────────────────────────────
_pb_active   = False          # True when a \r bar is mid-line (TTY only)
_pb_last_pct = -1.0           # last milestone printed in non-TTY mode
_NON_TTY_MILESTONES = (0, 10, 25, 50, 75, 90, 100)

def progress_bar(current: int, total: int, stage: str = "",
                 item: str = "", done: bool = False):
    """
    TTY mode  — in-place overwrite with \\r; one live bar line.
    Pipe mode — milestone-only lines at 0 / 10 / 25 / 50 / 75 / 90 / 100 %.

        TTY:   [████████████░░░░░░░░░░░░░░░░░░░░]  38.4%   4/6  file.jpg
        Pipe:    Indexing Fuji dest  ...  25.0%  (1748/6992)
    """
    global _pb_active, _pb_last_pct

    if total <= 0:
        return

    pct = 100.0 * current / total
    w   = len(str(total))

    if IS_TTY:
        # ── live overwrite bar ─────────────────────────────────────────────
        filled    = int(BAR_LEN * pct / 100)
        bar_str   = "█" * filled + "░" * (BAR_LEN - filled)
        bar_col   = (green if current >= total else yellow)(bar_str) \
                    if USE_COLOUR else bar_str
        item_tr   = (item[:36] + "…") if len(item) > 37 else item
        item_part = dim(f"  {item_tr}") if item_tr else ""
        stage_col = cyan(f"{stage:<28}") if stage else " " * 28
        count     = f"{current:>{w}}/{total}"

        sys.stdout.write(
            f"\r  {stage_col} [{bar_col}] {pct:5.1f}%  {count}{item_part}   "
        )
        sys.stdout.flush()
        _pb_active = True

        if done or current >= total:
            sys.stdout.write("\n")
            sys.stdout.flush()
            _pb_active   = False
            _pb_last_pct = -1.0

    else:
        # ── milestone-only lines (pipe / background) ───────────────────────
        for m in _NON_TTY_MILESTONES:
            if _pb_last_pct < m <= pct:
                print(f"  {stage:<28}  {pct:5.1f}%  ({current:>{w}}/{total})")
                sys.stdout.flush()
                _pb_last_pct = pct
                break

        if done or current >= total:
            # always print 100% completion line
            if _pb_last_pct < 100.0:
                print(f"  {stage:<28}  100.0%  ({total}/{total})")
                sys.stdout.flush()
            _pb_last_pct = -1.0          # reset for next bar


def pb_clear():
    """Erase a live TTY bar before printing a normal message line."""
    global _pb_active
    if _pb_active and IS_TTY:
        sys.stdout.write("\r" + " " * 120 + "\r")
        sys.stdout.flush()
        _pb_active = False


def print_step(label: str):
    """Print a bold section header, clearing any progress bar first."""
    pb_clear()
    print(f"\n{bold(DIVIDER)}")
    print(f"  {bold(label)}")
    print(bold(DIVIDER))


def pprint(text: str):
    pb_clear()
    print(text)


# ── EXIF helpers ──────────────────────────────────────────────────────────────
def _parse_dt(s: str):
    for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S"):
        try:
            return datetime.strptime(s.strip(), fmt)
        except ValueError:
            pass
    return None


def _exif_via_exifread(path: Path):
    if not HAS_EXIFREAD:
        return None, None
    try:
        with open(path, "rb") as f:
            tags = exifread.process_file(f, details=False)
        dt = None
        for key in ("EXIF DateTimeOriginal", "EXIF DateTimeDigitized", "Image DateTime"):
            if key in tags:
                dt = _parse_dt(str(tags[key]))
                if dt:
                    break
        make = str(tags["Image Make"]).strip() if "Image Make" in tags else None
        return dt, make
    except Exception:
        return None, None


def _exif_via_pil(path: Path):
    if not HAS_PIL:
        return None, None
    try:
        img  = Image.open(path)
        raw  = img._getexif()
        if not raw:
            return None, None
        dt = None
        for tag_id in (36867, 36868, 306):
            val = raw.get(tag_id)
            if val:
                dt = _parse_dt(val)
                if dt:
                    break
        make = (raw.get(271) or "").strip() or None
        return dt, make
    except Exception:
        return None, None


def _date_from_filename(name: str):
    for pat in (r"(\d{4})[-_](\d{2})[-_](\d{2})", r"(\d{4})(\d{2})(\d{2})"):
        m = re.search(pat, name)
        if m:
            try:
                y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
                if 1990 <= y <= 2100 and 1 <= mo <= 12 and 1 <= d <= 31:
                    return datetime(y, mo, d)
            except ValueError:
                pass
    return None


def _fs_date(path: Path) -> datetime:
    st = path.stat()
    return min(datetime.fromtimestamp(st.st_ctime),
               datetime.fromtimestamp(st.st_mtime))


def get_metadata(path: Path):
    """Return (datetime, date_source, make|None)."""
    dt, make = _exif_via_exifread(path)
    if dt:
        return dt, "EXIF", make
    if path.suffix.lower() in {".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".png"}:
        dt2, make2 = _exif_via_pil(path)
        if dt2:
            return dt2, "EXIF(PIL)", make2 or make
    dt3 = _date_from_filename(path.name)
    if dt3:
        return dt3, "filename", make
    return _fs_date(path), "filesystem", make


def is_fuji(make):
    return bool(make and "fuji" in make.lower())


# ── fast duplicate detection (size-first, MD5 only on collision) ─────────────
def md5(path: Path, bs: int = 65536) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        while chunk := f.read(bs):
            h.update(chunk)
    return h.hexdigest()


def build_size_index(dest_root: Path, label: str) -> dict:
    """
    Build {file_size_bytes: [Path, ...]} for dest_root.
    Uses only stat() — no MD5 — so it's fast even for 80k files.
    """
    index: dict[int, list] = {}
    if not dest_root.exists():
        return index

    all_files = [f for f in dest_root.rglob("*") if f.is_file()]
    total     = len(all_files)

    if total == 0:
        pprint(f"  {label}: empty, nothing to index")
        return index

    for i, f in enumerate(all_files, 1):
        progress_bar(i, total, stage=label, item=f.name)
        try:
            sz = f.stat().st_size
            index.setdefault(sz, []).append(f)
        except Exception:
            pass

    pprint(f"  {green('✔')}  {label}: {total:,} files indexed "
           f"{dim('(size-based, O(1) lookup)')}")
    return index


def find_duplicate(src: Path, size_index: dict):
    """
    Check src against the size index.
    Returns the matching destination Path if duplicate, else None.
    MD5 is only computed when a size collision exists.
    """
    try:
        sz = src.stat().st_size
    except Exception:
        return None
    candidates = size_index.get(sz, [])
    if not candidates:
        return None
    try:
        src_hash = md5(src)
    except Exception:
        return None
    for cand in candidates:
        try:
            if md5(cand) == src_hash:
                return cand
        except Exception:
            pass
    return None


def unique_dest(dest: Path) -> Path:
    if not dest.exists():
        return dest
    stem, suf = dest.stem, dest.suffix
    i = 1
    while True:
        cand = dest.parent / f"{stem}_{i}{suf}"
        if not cand.exists():
            return cand
        i += 1


# ── report builder ────────────────────────────────────────────────────────────
def _section(title: str) -> list:
    return ["", "=" * 64, f"  {title}", "=" * 64]


def build_report(
    dry_run, source, fuji_dest, photos_dest,
    raf_deleted, raf_failed,
    fuji_moved, fuji_fallback, fuji_new_dirs,
    photos_moved, photos_fallback, photos_new_dirs,
    duplicates, errors, source_leftovers,
) -> str:
    lines = [
        f"SORT PHOTOS REPORT  ({'DRY RUN' if dry_run else 'LIVE'})",
        f"Run       : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Source    : {source}",
        f"Fuji dest : {fuji_dest}",
        f"Photos dst: {photos_dest}",
    ]

    lines += _section("RAF DELETION")
    lines += [f"  Deleted : {len(raf_deleted)}", f"  Failed  : {len(raf_failed)}"]
    for p in raf_deleted:   lines.append(f"    [DEL] {p}")
    for p, r in raf_failed: lines.append(f"    [ERR] {p}: {r}")

    lines += _section(f"FUJI DESTINATION  [{fuji_dest}]")
    lines += [f"  Files moved       : {len(fuji_moved)}",
              f"  New subfolders    : {len(fuji_new_dirs)}",
              f"  Filesystem fallbk : {len(fuji_fallback)}"]
    if fuji_new_dirs:
        lines.append("  -- New subfolders --")
        for d in fuji_new_dirs: lines.append(f"    {d}")
    if fuji_fallback:
        lines.append("  -- Fallback (filesystem date used) --")
        for name, dest in fuji_fallback: lines.append(f"    {name}  ->  {dest}")
    if fuji_moved:
        lines.append("  -- Files moved --")
        for name, _, dest in fuji_moved: lines.append(f"    {name}  ->  {dest}")

    lines += _section(f"PHOTOS DESTINATION  [{photos_dest}]")
    lines += [f"  Files moved       : {len(photos_moved)}",
              f"  New subfolders    : {len(photos_new_dirs)}",
              f"  Filesystem fallbk : {len(photos_fallback)}"]
    if photos_new_dirs:
        lines.append("  -- New subfolders --")
        for d in photos_new_dirs: lines.append(f"    {d}")
    if photos_fallback:
        lines.append("  -- Fallback (filesystem date used) --")
        for name, dest in photos_fallback: lines.append(f"    {name}  ->  {dest}")
    if photos_moved:
        lines.append("  -- Files moved --")
        for name, _, dest in photos_moved: lines.append(f"    {name}  ->  {dest}")

    lines += _section("DUPLICATES  [SOURCE/review/]")
    lines.append(f"  Total skipped : {len(duplicates)}")
    for src_name, existing in duplicates:
        lines.append(f"    {src_name}  =>  matched: {existing}")

    lines += _section("SOURCE VERIFICATION")
    if source_leftovers:
        lines.append(f"  WARNING — {len(source_leftovers)} unprocessed file(s) remain in SOURCE root:")
        for f in source_leftovers: lines.append(f"    {f}")
    else:
        lines.append("  OK — SOURCE root is clear")

    lines += _section("ERRORS")
    lines.append(f"  Total : {len(errors)}")
    for name, reason in errors: lines.append(f"    {name}: {reason}")

    return "\n".join(lines)


# ── empty-source display ──────────────────────────────────────────────────────
def show_empty_source(source: Path, fuji_dest: Path, photos_dest: Path):
    print_step("SURVEY")

    def _dest_info(label, path):
        pprint(f"  {bold(label)}")
        if path.exists():
            fc = sum(1 for f in path.rglob("*") if f.is_file())
            pprint(f"    {'Status':<22} {green('EXISTS')}  —  {fc:,} files already present")
            yr_dirs = sorted(d.name for d in path.iterdir() if d.is_dir())
            if yr_dirs:
                pprint(f"    {'Year folders':<22} {', '.join(yr_dirs)}")
        else:
            pprint(f"    {'Status':<22} {dim('Does not exist yet (will be created on first run)')}")
        pprint("")

    pprint(f"  {bold('Source folder:')}  {source}")
    pprint(f"    {'Total files':<22} {yellow('0  ← nothing to process')}")
    pprint(f"    {'RAF files':<22} 0")
    pprint("")
    _dest_info("Fuji destination:",   fuji_dest)
    _dest_info("Photos destination:", photos_dest)

    print_step("RESULT")
    pprint(f"  {yellow('SOURCE IS EMPTY — nothing to sort.')}")
    pprint("")
    pprint("  Drop new photos/videos flat into:")
    pprint(f"    {cyan(str(source))}")
    pprint("  Then re-run this script.")
    pprint("")


# ── core processing ───────────────────────────────────────────────────────────
def process(source: Path, fuji_dest: Path, photos_dest: Path,
            dry_run: bool, report_path: Path):

    mode_label = "DRY RUN" if dry_run else "LIVE"
    pprint(f"\n{bold(DIVIDER)}")
    pprint(f"  {bold('SORT PHOTOS')}  —  {yellow(mode_label)}")
    pprint(bold(DIVIDER))
    pprint(f"  {'Source':<20} {source}")
    pprint(f"  {'Fuji dest':<20} {fuji_dest}")
    pprint(f"  {'Photos dest':<20} {photos_dest}")

    t_start = time.time()

    # ── Step 1 ────────────────────────────────────────────────────────────────
    print_step("STEP 1 / 6  ·  Scanning source folder")

    source_files = [f for f in source.iterdir() if f.is_file()]
    raf_files    = [f for f in source_files if f.suffix.lower() == ".raf"]
    photo_files  = [f for f in source_files
                    if f.suffix.lower() in PHOTO_EXTS and f.suffix.lower() != ".raf"]
    other_files  = [f for f in source_files
                    if f.suffix.lower() not in PHOTO_EXTS | {".raf"}]

    pprint(f"  {'Total files':<28} {len(source_files)}")

    ext_counts: dict[str, int] = {}
    for f in source_files:
        ext_counts[f.suffix.lower() or "(none)"] = \
            ext_counts.get(f.suffix.lower() or "(none)", 0) + 1
    for ext, cnt in sorted(ext_counts.items(), key=lambda x: -x[1]):
        pprint(f"    {ext:<16} {cnt}")

    pprint(f"  {'RAF files':<28} "
           f"{red(str(len(raf_files))) if raf_files else green('0  (none found)')}")
    pprint(f"  {'Photo / video files':<28} {len(photo_files)}")
    if other_files:
        pprint(f"  {yellow('Non-photo files (skipped)'):<28} {len(other_files)}")

    # ── Step 2 ────────────────────────────────────────────────────────────────
    print_step("STEP 2 / 6  ·  Deleting RAF files")

    raf_deleted, raf_failed = [], []
    if not raf_files:
        pprint(f"  {green('No RAF files found — skipping.')}")
    else:
        total_raf = len(raf_files)
        for i, f in enumerate(raf_files, 1):
            progress_bar(i, total_raf, stage="Deleting RAFs", item=f.name)
            try:
                if not dry_run:
                    f.unlink()
                raf_deleted.append(f.name)
            except Exception as e:
                raf_failed.append((f.name, str(e)))
        pprint(f"  {green('✔')}  Deleted: {len(raf_deleted)}   "
               f"Failed: {red(str(len(raf_failed))) if raf_failed else '0'}")

    # ── Step 3: Build destination indexes ─────────────────────────────────────
    print_step("STEP 3 / 6  ·  Indexing destinations  (size-based, fast)")
    pprint(f"  {dim('Only MD5-hashes on size collision — skips re-hashing all existing files.')}")
    pprint("")

    fuji_size_idx   = build_size_index(fuji_dest,   "Fuji dest  ")
    photos_size_idx = build_size_index(photos_dest, "Photos dest")

    # ── Steps 4-5: Route, rename, move ────────────────────────────────────────
    print_step("STEP 4-5 / 6  ·  Reading EXIF · Routing · Renaming · Moving")

    review_dir = source / "review"
    fuji_moved,   fuji_fallback,   fuji_new_dirs_set   = [], [], set()
    photos_moved, photos_fallback, photos_new_dirs_set = [], [], set()
    duplicates, errors = [], []

    total = len(photo_files)
    pprint(f"  Processing {total} file(s)…\n")

    for i, src_file in enumerate(photo_files, 1):
        progress_bar(i, total, stage="Routing files", item=src_file.name)

        try:
            dt, date_src, make = get_metadata(src_file)
            fuji      = is_fuji(make)
            dest_root = fuji_dest   if fuji else photos_dest
            size_idx  = fuji_size_idx if fuji else photos_size_idx

            date_prefix = dt.strftime("%Y-%m-%d")
            new_name    = (src_file.name
                           if re.match(r"\d{4}-\d{2}-\d{2}_", src_file.name)
                           else f"{date_prefix}_{src_file.name}")

            yy, mm   = dt.strftime("%Y"), dt.strftime("%m")
            dest_dir  = dest_root / yy / mm
            dest_path = unique_dest(dest_dir / new_name)

            # Duplicate check
            matched = find_duplicate(src_file, size_idx)
            if matched:
                pb_clear()
                pprint(f"  {yellow('[DUP]')}  {src_file.name}")
                pprint(f"         matched → {dim(str(matched))}")
                if not dry_run:
                    review_dir.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(src_file),
                                str(unique_dest(review_dir / src_file.name)))
                duplicates.append((src_file.name, str(matched)))
                continue

            # Move
            route_tag  = cyan("[FUJI]") if fuji else green("[PHOT]")
            fall_tag   = f"  {yellow('← filesystem date')}" \
                         if date_src == "filesystem" else ""
            pb_clear()
            pprint(f"  {route_tag}  {src_file.name}")
            pprint(f"         → {yy}/{mm}/{new_name}{fall_tag}")

            if not dry_run:
                if not dest_dir.exists():
                    dest_dir.mkdir(parents=True, exist_ok=True)
                shutil.move(str(src_file), str(dest_path))

            # Update in-memory size index so later files can detect each other
            try:
                sz = dest_path.stat().st_size if dest_path.exists() \
                     else src_file.stat().st_size
                size_idx.setdefault(sz, []).append(dest_path)
            except Exception:
                pass

            record = (src_file.name, str(src_file), str(dest_path))
            if fuji:
                fuji_moved.append(record)
                fuji_new_dirs_set.add(str(dest_dir))
                if date_src == "filesystem":
                    fuji_fallback.append((src_file.name, str(dest_path)))
            else:
                photos_moved.append(record)
                photos_new_dirs_set.add(str(dest_dir))
                if date_src == "filesystem":
                    photos_fallback.append((src_file.name, str(dest_path)))

        except Exception as e:
            pb_clear()
            pprint(f"  {red('[ERR]')}  {src_file.name}: {e}")
            errors.append((src_file.name, str(e)))

    # ── Step 6: Verify source ─────────────────────────────────────────────────
    print_step("STEP 6 / 6  ·  Verifying source is clear")

    remaining = [f for f in source.iterdir()
                 if f.is_file() or (f.is_dir() and f.name != "review")]

    if dry_run:
        # In dry-run nothing is moved, so files naturally remain — not a warning
        pprint(f"  {yellow('DRY RUN')} — files not moved, source unchanged (expected).")
        if remaining:
            pprint(f"  {len(remaining)} file(s) would remain in /review/ or be moved on live run.")
    elif remaining:
        pprint(f"  {red('WARNING')} — {len(remaining)} item(s) still in SOURCE root:")
        for f in remaining:
            pprint(f"    {red('!')} {f.name}")
    else:
        pprint(f"  {green('✔')}  SOURCE root is clear"
               + (f"  {dim('(/review/ folder present)')}"
                  if review_dir.exists() else ""))

    # ── Summary ───────────────────────────────────────────────────────────────
    elapsed = time.time() - t_start
    print_step("SUMMARY")

    def kv(label, value, w=32): pprint(f"  {label:<{w}} {value}")

    kv("Mode:",
       yellow("DRY RUN — no changes made") if dry_run else green("LIVE"))
    kv("Elapsed:",         f"{elapsed:.1f}s")
    pprint(f"  {THIN_DIV}")
    kv("RAF deleted:",     f"{len(raf_deleted)}  ({len(raf_failed)} failed)")
    pprint(f"  {THIN_DIV}")
    kv("Fuji files moved:",    len(fuji_moved))
    kv("  ↳ filesystem date:", len(fuji_fallback) or "0")
    kv("  ↳ new subfolders:",  len(fuji_new_dirs_set) or "0")
    pprint(f"  {THIN_DIV}")
    kv("Photo files moved:",   len(photos_moved))
    kv("  ↳ filesystem date:", len(photos_fallback) or "0")
    kv("  ↳ new subfolders:",  len(photos_new_dirs_set) or "0")
    pprint(f"  {THIN_DIV}")
    kv("Duplicates → /review/:", len(duplicates))
    kv("Errors:",               len(errors))

    if dry_run:
        pprint(f"\n  {yellow('Re-run without --dry-run to apply changes.')}")

    # ── Save report ────────────────────────────────────────────────────────────
    report_text = build_report(
        dry_run, source, fuji_dest, photos_dest,
        raf_deleted, raf_failed,
        fuji_moved, fuji_fallback, sorted(fuji_new_dirs_set),
        photos_moved, photos_fallback, sorted(photos_new_dirs_set),
        duplicates, errors, remaining,
    )
    try:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(report_text, encoding="utf-8")
        pprint(f"\n  Report saved → {cyan(str(report_path))}")
    except Exception as e:
        pprint(f"\n  {red('Could not save report:')} {e}")

    pprint("")


# ── entry point ───────────────────────────────────────────────────────────────
def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(
        description="Sort unsorted photos into Fuji / Photos destinations.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--source",  required=True,
                        help="Flat folder containing new, unsorted photos/videos")
    parser.add_argument("--fuji",    required=True,
                        help="Destination root for Fujifilm files (YYYY/MM/)")
    parser.add_argument("--photos",  required=True,
                        help="Destination root for all other files (YYYY/MM/)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview only — no files are moved or deleted")
    parser.add_argument("--report",  default=None,
                        help="Path to save text report (default: SOURCE/sort_report.txt)")
    args = parser.parse_args()

    source      = Path(args.source).expanduser().resolve()
    fuji_dest   = Path(args.fuji).expanduser().resolve()
    photos_dest = Path(args.photos).expanduser().resolve()
    report_path = (Path(args.report).expanduser().resolve()
                   if args.report else source / "sort_report.txt")

    # Header
    pprint(f"\n{bold(DIVIDER)}")
    pprint(f"  {bold('SORT PHOTOS')}  ·  Initialising")
    pprint(bold(DIVIDER))

    if not HAS_EXIFREAD:
        pprint(f"  {yellow('WARN')} exifread not installed — date/make extraction limited.")
        pprint("       Install: pip install exifread")
    if not HAS_PIL:
        pprint(f"  {yellow('WARN')} Pillow not installed — JPEG EXIF fallback disabled.")
        pprint("       Install: pip install pillow")

    if not source.exists():
        pprint(f"\n  {red('ERROR')} SOURCE not found: {source}")
        sys.exit(1)
    if not source.is_dir():
        pprint(f"\n  {red('ERROR')} SOURCE is not a directory: {source}")
        sys.exit(1)

    source_files = [f for f in source.iterdir() if f.is_file()]
    if not source_files:
        show_empty_source(source, fuji_dest, photos_dest)
        sys.exit(0)

    process(source, fuji_dest, photos_dest, args.dry_run, report_path)


if __name__ == "__main__":
    main()
