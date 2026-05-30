"""
Photo organizer v2
- Deletes all RAF files (Step 2)
- Routes FUJIFILM files  → /Fuji/YYYY/MM/
- Routes all other files → /YYYY/MM/
- Renames: YYYY-MM-DD_original-filename.ext
- Deduplicates to /review/
- Cleans up empty folders

Usage:
  python organize_v2.py          # dry run
  python organize_v2.py --run    # live
"""

import os, sys, re, hashlib, shutil, logging
from datetime import datetime
from pathlib import Path

# ── silence exifread noise ──────────────────────────────────────────────────
logging.getLogger("exifread").setLevel(logging.CRITICAL)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

try:
    import exifread
    HAS_EXIFREAD = True
except ImportError:
    HAS_EXIFREAD = False

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# ── config ──────────────────────────────────────────────────────────────────
ROOT      = Path("E:/Crucial/BlueOcean")
FUJI_ROOT = ROOT / "Fuji"
REVIEW    = ROOT / "review"
REPORT    = ROOT / "organize_v2_report.txt"

DRY_RUN   = "--run" not in sys.argv

PHOTO_EXTS = {
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".tif",
    ".heic", ".heif", ".raw", ".cr2", ".nef", ".arw", ".dng",
    ".webp", ".mp4", ".mov", ".avi", ".mkv", ".3gp",
}

# Top-level folder names to never collect from (destinations + system)
SKIP_TOP = {"review", "fuji", ".claude"}

# ── helpers ─────────────────────────────────────────────────────────────────
def md5(path: Path, bs=65536) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        while chunk := f.read(bs):
            h.update(chunk)
    return h.hexdigest()


def parse_dt(s: str) -> datetime | None:
    for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S"):
        try:
            return datetime.strptime(s.strip(), fmt)
        except ValueError:
            pass
    return None


def exif_via_exifread(path: Path):
    """Return (datetime|None, make_str|None) via exifread."""
    if not HAS_EXIFREAD:
        return None, None
    try:
        with open(path, "rb") as f:
            tags = exifread.process_file(f, details=False)
        dt = None
        for k in ("EXIF DateTimeOriginal", "EXIF DateTimeDigitized", "Image DateTime"):
            if k in tags:
                dt = parse_dt(str(tags[k]))
                if dt:
                    break
        make = str(tags["Image Make"]).strip() if "Image Make" in tags else None
        return dt, make
    except Exception:
        return None, None


def exif_via_pil(path: Path):
    """Return (datetime|None, make_str|None) via Pillow (JPEG fallback)."""
    if not HAS_PIL:
        return None, None
    try:
        img = Image.open(path)
        raw = img._getexif()
        if not raw:
            return None, None
        dt = None
        for tag_id in (36867, 36868, 306):
            val = raw.get(tag_id)
            if val:
                dt = parse_dt(val)
                if dt:
                    break
        make = raw.get(271, "").strip() or None   # tag 271 = Make
        return dt, make
    except Exception:
        return None, None


def date_from_filename(name: str) -> datetime | None:
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


def fs_date(path: Path) -> datetime:
    st = path.stat()
    return min(datetime.fromtimestamp(st.st_ctime),
               datetime.fromtimestamp(st.st_mtime))


def get_metadata(path: Path):
    """Return (datetime, date_source, make_or_None)."""
    dt, make = exif_via_exifread(path)
    if dt:
        return dt, "EXIF", make

    if path.suffix.lower() in {".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".png"}:
        dt2, make2 = exif_via_pil(path)
        if dt2:
            return dt2, "EXIF(PIL)", make2 or make

    dt3 = date_from_filename(path.name)
    if dt3:
        return dt3, "filename", make   # make may still be known from exifread

    return fs_date(path), "filesystem", make


def is_fuji(make: str | None) -> bool:
    if not make:
        return False
    return "fuji" in make.lower()


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


def safe_move(src: Path, dst: Path):
    dst = unique_dest(dst)
    if not DRY_RUN:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
    return dst


# ── collection ───────────────────────────────────────────────────────────────
def collect(root: Path) -> tuple[list[Path], list[Path]]:
    """Return (raf_files, photo_files). Skips destination dirs."""
    raf_files, photo_files = [], []
    for dirpath, dirnames, filenames in os.walk(root):
        rel_parts = Path(dirpath).relative_to(root).parts

        # Skip top-level protected/destination dirs
        if rel_parts and rel_parts[0].lower() in SKIP_TOP:
            dirnames.clear()
            continue

        # Skip root-level YYYY or YYYY/MM dirs (already-processed destinations)
        if (len(rel_parts) >= 1 and re.fullmatch(r"\d{4}", rel_parts[0])):
            dirnames.clear()
            continue

        for fname in filenames:
            fpath = Path(dirpath) / fname
            ext = fpath.suffix.lower()
            if ext == ".raf":
                raf_files.append(fpath)
            elif ext in PHOTO_EXTS:
                photo_files.append(fpath)

    return raf_files, photo_files


# ── main ─────────────────────────────────────────────────────────────────────
def main():
    mode = "DRY RUN" if DRY_RUN else "LIVE"
    print(f"\n{'='*60}\nOrganize v2 — {mode}\n{'='*60}")

    if not DRY_RUN:
        REVIEW.mkdir(parents=True, exist_ok=True)

    # ── STEP 2: RAF deletion ─────────────────────────────────────────────────
    raf_list, photos = collect(ROOT)
    print(f"\nRAF files found   : {len(raf_list)}")
    print(f"Photo/video files : {len(photos)}")

    raf_deleted, raf_failed = [], []
    for f in raf_list:
        try:
            if not DRY_RUN:
                f.unlink()
            raf_deleted.append(f)
        except Exception as e:
            raf_failed.append((f, str(e)))

    print(f"RAF deleted       : {len(raf_deleted)}")

    # ── STEPS 3-6: Route, rename, dedup ─────────────────────────────────────
    total = len(photos)
    fuji_ok, fuji_fallback, fuji_dup = [], [], []
    other_ok, other_fallback, other_dup = [], [], []
    errors = []

    seen: dict[str, Path] = {}   # hash -> first destination

    for i, src in enumerate(photos, 1):
        if i % 2000 == 0:
            print(f"  {i}/{total} processed...")

        try:
            h = md5(src)

            # Duplicate?
            if h in seen:
                dst = unique_dest(REVIEW / src.name)
                if not DRY_RUN:
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(src), str(dst))
                entry = (src.name, str(dst.relative_to(ROOT)))
                if is_fuji(None):   # can't know make at dup stage cheaply
                    fuji_dup.append(entry)
                else:
                    other_dup.append(entry)
                continue

            # Metadata
            dt, source, make = get_metadata(src)
            fuji = is_fuji(make)

            # New filename
            prefix = dt.strftime("%Y-%m-%d")
            new_name = src.name if re.match(r"\d{4}-\d{2}-\d{2}_", src.name) \
                       else f"{prefix}_{src.name}"

            # Destination
            yy, mm = dt.strftime("%Y"), dt.strftime("%m")
            if fuji:
                dst = ROOT / "Fuji" / yy / mm / new_name
            else:
                dst = ROOT / yy / mm / new_name

            final = safe_move(src, dst)
            seen[h] = final

            fallback = source == "filesystem"
            record = (src.name, str(final.relative_to(ROOT)), make or "unknown", source)

            if fuji:
                (fuji_fallback if fallback else fuji_ok).append(record)
            else:
                (other_fallback if fallback else other_ok).append(record)

        except Exception as e:
            errors.append((str(src), str(e)))

    # ── STEP 7: Empty folder cleanup ─────────────────────────────────────────
    removed_dirs = []
    dir_errors   = []
    protected = {str(REVIEW).lower(), str(FUJI_ROOT).lower()}

    all_dirs = sorted(
        [d for d in ROOT.rglob("*") if d.is_dir()],
        key=lambda d: len(d.parts), reverse=True
    )
    for d in all_dirs:
        if str(d).lower() in protected:
            continue
        try:
            children = list(d.iterdir())
            if not children:
                if not DRY_RUN:
                    d.rmdir()
                removed_dirs.append(str(d.relative_to(ROOT)))
        except Exception as e:
            dir_errors.append((str(d.relative_to(ROOT)), str(e)))

    # ── STEP 8: Report ───────────────────────────────────────────────────────
    def section(title): return [f"\n{'='*60}", f"  {title}", f"{'='*60}"]

    lines = [
        f"ORGANIZE V2 REPORT — {mode}",
        f"Run: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Root: {ROOT}",
    ]

    lines += section("RAF DELETION")
    lines += [f"  Deleted : {len(raf_deleted)}", f"  Failed  : {len(raf_failed)}", ""]
    for f in raf_deleted:
        lines.append(f"  [DEL] {f.relative_to(ROOT)}")
    for f, r in raf_failed:
        lines.append(f"  [ERR] {f.relative_to(ROOT)}: {r}")

    lines += section("FUJIFILM FILES  →  /Fuji/YYYY/MM/")
    lines += [f"  Moved OK          : {len(fuji_ok)}",
              f"  Fallback date     : {len(fuji_fallback)}",
              f"  Duplicates/review : {len(fuji_dup)}", ""]
    if fuji_fallback:
        lines.append("  -- Fallback (filesystem date) --")
        for name, dest, make, src in fuji_fallback:
            lines.append(f"    {name}  ->  {dest}")
    if fuji_dup:
        lines.append("  -- Duplicates -> /review/ --")
        for name, dest in fuji_dup:
            lines.append(f"    {name}  ->  {dest}")

    lines += section("ALL OTHER FILES  →  /YYYY/MM/")
    lines += [f"  Moved OK          : {len(other_ok)}",
              f"  Fallback date     : {len(other_fallback)}",
              f"  Duplicates/review : {len(other_dup)}", ""]
    if other_fallback:
        lines.append("  -- Fallback (filesystem date) --")
        for name, dest, make, src in other_fallback[:500]:
            lines.append(f"    {name}  ->  {dest}")
        if len(other_fallback) > 500:
            lines.append(f"    ... and {len(other_fallback)-500} more")
    if other_dup:
        lines.append("  -- Duplicates -> /review/ --")
        for name, dest in other_dup[:200]:
            lines.append(f"    {name}  ->  {dest}")
        if len(other_dup) > 200:
            lines.append(f"    ... and {len(other_dup)-200} more")

    lines += section("EMPTY FOLDER CLEANUP")
    lines += [f"  Removed : {len(removed_dirs)}", ""]
    for d in removed_dirs:
        lines.append(f"  {d}")

    lines += section("ERRORS")
    lines += [f"  Count: {len(errors) + len(raf_failed) + len(dir_errors)}", ""]
    for f, r in errors:
        lines.append(f"  [FILE] {f}: {r}")
    for d, r in dir_errors:
        lines.append(f"  [DIR]  {d}: {r}")

    report_text = "\n".join(lines)
    REPORT.write_text(report_text, encoding="utf-8")

    # Console summary
    print(f"""
{'='*60}
SUMMARY
{'='*60}
RAF deleted          : {len(raf_deleted)} ({len(raf_failed)} failed)
Fuji files moved     : {len(fuji_ok) + len(fuji_fallback)}  (fallback: {len(fuji_fallback)}, dups: {len(fuji_dup)})
Other files moved    : {len(other_ok) + len(other_fallback)}  (fallback: {len(other_fallback)}, dups: {len(other_dup)})
Empty dirs removed   : {len(removed_dirs)}
Errors               : {len(errors)}
Report saved to      : {REPORT}
""")
    if DRY_RUN:
        print("Run with --run to execute for real.")


if __name__ == "__main__":
    main()
