# organize_v2.py

One-time bulk organiser for an existing messy photo root. Scans the entire
folder tree, routes Fujifilm files to a dedicated `/Fuji/` tree and everything
else to root-level `YYYY/MM/` folders, renames files with a date prefix,
deduplicates, and cleans up empty folders.

Run this **once** on a large unorganised archive. For ongoing imports of new
photos use [`sort_photos.py`](sort_photos.md) instead.

---

## Usage

```bash
# Always dry-run first — no files are moved or deleted
python organize_v2.py

# Live run — files are moved
python organize_v2.py --run
```

The root folder is hardcoded inside the script:

```python
ROOT      = Path("E:/Crucial/BlueOcean")   # ← change to your path
FUJI_ROOT = ROOT / "Fuji"
REVIEW    = ROOT / "review"
```

Edit these three lines before running.

---

## What it does — step by step

### Step 1 — Collect files
Walks the entire `ROOT` tree recursively, collecting every photo/video file.

**Skipped automatically:**
- `ROOT/review/` — duplicate holding area
- `ROOT/Fuji/` — Fuji destination (already processed)
- `ROOT/YYYY/` at the root level — non-Fuji destination (already processed)
- `.claude/` and other system folders

Supported extensions: `.jpg .jpeg .png .gif .bmp .tiff .tif .heic .heif .raw
.cr2 .nef .arw .dng .webp .mp4 .mov .avi .mkv .3gp`

### Step 2 — Delete RAF files
Every `.RAF` / `.raf` file found anywhere in the tree is **permanently
deleted** before any sorting begins. All deleted paths are logged.

### Step 3 — Build destination hash index
An MD5 hash index of every file already in the Fuji and non-Fuji destinations
is built upfront. New files are checked against this before being moved.

### Step 4 — Read EXIF metadata
For each file:

| Field | Priority order |
|---|---|
| **Date** | `DateTimeOriginal` → `DateTimeDigitized` → `DateTime` → filename pattern (`YYYYMMDD` / `YYYY-MM-DD`) → `min(ctime, mtime)` |
| **Camera make** | `Image Make` EXIF tag → Pillow tag 271 |

### Step 5 — Route by camera make

| Make field (case-insensitive) | Destination |
|---|---|
| Contains `fuji` or `fujifilm` | `ROOT/Fuji/YYYY/MM/` |
| Anything else, or Make missing | `ROOT/YYYY/MM/` |

### Step 6 — Rename and move
Files are renamed before moving:
```
IMG_4021.JPG  →  2024-03-15_IMG_4021.JPG
```
If the file already starts with `YYYY-MM-DD_` the prefix is not doubled.
Naming conflicts are resolved with a `_1`, `_2`, … suffix.

### Step 7 — Deduplicate
If a file's MD5 matches an already-seen file (in destinations or already moved
during this run), the duplicate is moved to `ROOT/review/`. Nothing is
deleted.

### Step 8 — Remove empty folders
After all files are moved, the tree is walked bottom-up and every empty folder
is removed. `ROOT/review/` is preserved even if empty.

---

## Output

```
============================================================
Organize v2 — DRY RUN
============================================================

RAF files found   : 1364
Photo/video files : 89421
RAF deleted       : 1364
  2000/89421 processed...
  4000/89421 processed...
  …

============================================================
SUMMARY
============================================================
RAF deleted          : 1364 (0 failed)
Fuji files moved     : 6992  (fallback: 0, dups: 0)
Other files moved    : 81013  (fallback: 37, dups: 1412)
Empty dirs removed   : 595
Errors               : 4
Report saved to      : ROOT/organize_v2_report.txt
```

A full plain-text report is saved to `ROOT/organize_v2_report.txt`.

---

## Report sections

| Section | Contents |
|---|---|
| **RAF DELETION** | Every deleted `.RAF` path; any failures |
| **FUJIFILM FILES → /Fuji/** | Count, fallback-date files, duplicates sent to `/review/` |
| **ALL OTHER FILES → /YYYY/MM/** | Count, fallback-date files, duplicates |
| **EMPTY FOLDER CLEANUP** | Every folder removed |
| **ERRORS** | Files that could not be processed + reason |

---

## Date fallback behaviour

| Source | Meaning | Flagged in report |
|---|---|---|
| EXIF `DateTimeOriginal` | Shot timestamp embedded by camera | No |
| EXIF `DateTimeDigitized` | Digitisation timestamp | No |
| Filename pattern | e.g. `IMG_20231014_…` or `2023-10-14_…` | No |
| Filesystem `min(ctime, mtime)` | Copy/backup date — least reliable | **Yes** |

Files using filesystem fallback are listed separately so you can review them.

---

## Known limitations

- **Windows MAX_PATH (260 chars)** — files with very long paths (deep
  music/download folders) cannot be read or moved. They are listed in the
  Errors section and left in place.
- **No EXIF in video files** — `.mp4`, `.mov`, `.mkv` etc. rarely carry
  standard EXIF. Most end up using the filename date or filesystem fallback.
- **Anomalous years** — filenames like `Snapchat-2080090122.mp4` can produce
  far-future dates (2080, 2065) because the script parses the first valid
  `YYYYMMDD` it finds. These files land in `2080/09/` etc. and can be
  manually corrected.

---

## Dependencies

```bash
pip install exifread pillow
```

Python 3.10+ required (uses the walrus operator `:=` in MD5 reading).

---

## Differences from sort_photos.py

| | `organize_v2.py` | `sort_photos.py` |
|---|---|---|
| **Intended use** | One-time bulk reorganise | Ongoing per-import |
| **Source** | Entire ROOT tree (recursive) | Single flat folder |
| **Destination** | Sets up ROOT/Fuji + ROOT/YYYY | Uses pre-existing destinations |
| **Duplicate check** | MD5 of everything upfront | Size-first, MD5 only on collision |
| **Progress** | Console count every 2 000 files | Animated bar (TTY) / milestones (pipe) |
| **Empty folder cleanup** | Included (Step 8) | Not included |
| **RAF deletion** | Included | Included |
