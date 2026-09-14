# sort_photos.py

Sort new, unsorted photos from a flat **source** folder into two
organised destinations — one for Fujifilm files, one for everything else.
Designed for regular use after each camera import. Prefer a GUI? See
[`GUI.md`](GUI.md) — the "Sort New Photos" screen is this same workflow
with folder pickers instead of these flags.

This script is a thin CLI wrapper — all the actual logic lives in
`photo_organizer/engine/sort_pipeline.py`, shared with the desktop app.

---

## Usage

```bash
# Windows
python sort_photos.py --source "E:\Photos\New" --fuji "E:\Photos\Fuji" --photos "E:\Photos\Pics"
python sort_photos.py --source "E:\Photos\New" --fuji "E:\Photos\Fuji" --photos "E:\Photos\Pics" --dry-run

# Linux / macOS
python3 sort_photos.py --source ~/Photos/New --fuji ~/Photos/Fuji --photos ~/Photos/Pics
```

---

## Arguments

| Argument | Required | Default | Description |
|---|---|---|---|
| `--source` | ✅ | — | Flat folder containing new, unsorted photos/videos |
| `--fuji` | ✅ | — | Destination root for Fujifilm files (sorted into `YYYY/MM/`) |
| `--photos` | ✅ | — | Destination root for all other files (sorted into `YYYY/MM/`) |
| `--dry-run` | — | off | Preview only — no files moved or deleted |
| `--report` | — | `SOURCE/sort_report.txt` | Path to save the text report |

---

## What it does — step by step

### Step 1 — Scan source (flat, non-recursive)
Reads every file in `SOURCE/` (top level only). Reports counts by extension.
Sub-folders inside source are ignored except for the `/review/` folder it
creates itself.

### Step 2 — Delete RAF files
Any file with extension `.RAF` or `.raf` (case-insensitive) is **permanently
deleted** before anything else is processed. This keeps Fujifilm RAW files out
of the destination — only the processed JPEGs travel forward.

All deleted paths are listed in the final report.

### Step 3 — Index destinations (size-based, fast)
Builds a `{file_size: [paths]}` index for both destination trees using only
`stat()` calls — **no MD5 at this stage**. For 80 000+ existing files this
takes a few minutes but is much faster than hashing everything.

MD5 is only computed later, and only when a size collision is found between a
new source file and an existing destination file.

### Step 4 — Read EXIF metadata
For each file in source, extracts:

| Field | Tags checked (in order) |
|---|---|
| Date | `DateTimeOriginal` → `DateTimeDigitized` → `DateTime` → filename pattern → filesystem ctime/mtime |
| Camera make | `Image Make` (EXIF) → Pillow tag 271 |

Date source priority:
1. **EXIF** (via `exifread`) — most accurate
2. **EXIF via Pillow** — fallback for some JPEGs
3. **Filename** — if name contains `YYYYMMDD` or `YYYY-MM-DD`
4. **Filesystem** — `min(ctime, mtime)` — least reliable, flagged in report

### Step 5 — Route by camera make

| Make field | Destination |
|---|---|
| Contains `fuji` or `fujifilm` (case-insensitive) | `FUJI/YYYY/MM/` |
| Anything else, or Make missing | `PHOTOS/YYYY/MM/` |

Files are renamed before moving:
```
original-filename.jpg  →  YYYY-MM-DD_original-filename.jpg
```
If the filename already starts with `YYYY-MM-DD_` the prefix is not doubled.

Naming conflicts (same destination path already exists) are resolved by
appending `_1`, `_2`, … to the stem.

### Step 6 — Duplicate check before moving
Before each file is moved, its content is compared against the destination:

1. Look up its size in the destination index
2. If one or more same-size files exist, compute MD5 of the source file and
   each candidate
3. If a match is found → move the source file to `SOURCE/review/` and log it
4. If no match → move to the correct `YYYY/MM/` subfolder and update the
   in-memory index (so later files in the same run can also detect duplicates
   against freshly moved files)

### Step 7 — Verify source is clear
After all files are processed, the script checks that `SOURCE/` contains only
the `/review/` subfolder (plus the report file). Any remaining files are listed
as errors.

In `--dry-run` mode this step notes that files remain as expected (nothing was
moved).

---

## Flagged / suspicious dates

A filename-parsed date (`YYYYMMDD` / `YYYY-MM-DD` pattern) that lands more
than a day in the future is flagged rather than treated the same as any
other date — the classic case is a filename like `Snapchat-2080090122.mp4`,
where the regex grabs the first 8-digit run and produces a bogus year-2080
date. The file is still routed and renamed using that date (nothing is
blocked), but it's called out:

- Listed in its own **FLAGGED DATES** section in the report file
- Counted separately in the summary (`Flagged dates: N`)
- Shown live in the desktop app's progress log and post-run summary

EXIF dates and the filesystem-fallback date are never flagged this way —
only filename-parsed dates, since that's the only source prone to this kind
of misparse.

---

## Progress display

The script auto-detects whether it is running in an interactive terminal or a
pipe/background process and adjusts accordingly.

### Interactive terminal (TTY)
Live animated bar that overwrites itself in place:
```
  Indexing Fuji dest           [████████████████░░░░░░░░░░░░░░░░]  50.0%  3496/6992  DSCF4703.JPG
```

### Pipe / background / redirect
Milestone-only lines printed at 0 % → 10 % → 25 % → 50 % → 75 % → 90 % → 100 %:
```
  Indexing Fuji dest             0.0%  (   1/6992)
  Indexing Fuji dest            25.0%  (1748/6992)
  Indexing Fuji dest            50.0%  (3496/6992)
  Indexing Fuji dest           100.0%  (6992/6992)
```
This prevents the output flood that occurs when `\r` carriage-return is
interpreted as a newline in captured stdout.

---

## Output example — empty source

```
================================================================
  SORT PHOTOS  ·  Initialising
================================================================

================================================================
  SURVEY
================================================================
  Source folder:  /Photos/Source_Unsorted_Photos
    Total files            0  ← nothing to process
    RAF files              0

  Fuji destination:
    Status                 EXISTS  —  6,992 files already present
    Year folders           2023, 2024, 2025, 2026

  Photos destination:
    Status                 EXISTS  —  81,013 files already present
    Year folders           2013, 2014, … 2026

================================================================
  RESULT
================================================================
  SOURCE IS EMPTY — nothing to sort.

  Drop new photos/videos flat into:
    /Photos/Source_Unsorted_Photos
  Then re-run this script.
```

---

## Output example — files present (dry run)

```
================================================================
  SORT PHOTOS  —  DRY RUN
================================================================
  Source               /Photos/Source_Unsorted_Photos
  Fuji dest            /Photos/Fuji
  Photos dest          /Photos/Pics

================================================================
  STEP 1 / 6  ·  Scanning source folder
================================================================
  Total files                  8
    .jpg             5
    .heic            2
    .raf             1
  RAF files                    1
  Photo / video files          7

================================================================
  STEP 2 / 6  ·  Deleting RAF files
================================================================
  Deleting RAFs          100.0%  (1/1)
  ✔  Deleted: 1   Failed: 0

================================================================
  STEP 3 / 6  ·  Indexing destinations  (size-based, fast)
================================================================
  Fuji dest                   100.0%  (6992/6992)
  ✔  Fuji dest  : 6,992 files indexed (size-based, O(1) lookup)
  Photos dest                 100.0%  (81013/81013)
  ✔  Photos dest: 81,013 files indexed (size-based, O(1) lookup)

================================================================
  STEP 4-5 / 6  ·  Reading EXIF · Routing · Renaming · Moving
================================================================
  Processing 7 file(s)…

  [FUJI]  DSCF4801.JPG
          → 2025/05/2025-05-14_DSCF4801.JPG
  [FUJI]  DSCF4802.JPG
          → 2025/05/2025-05-14_DSCF4802.JPG
  [PHOT]  IMG_20250510_143201.jpg
          → 2025/05/2025-05-10_IMG_20250510_143201.jpg
  [DUP]   DSCF4702.JPG
          matched → /Photos/Fuji/2025/04/2025-04-09_DSCF4702.JPG
  …

================================================================
  STEP 6 / 6  ·  Verifying source is clear
================================================================
  DRY RUN — files not moved, source unchanged (expected).

================================================================
  SUMMARY
================================================================
  Mode:                            DRY RUN — no changes made
  Elapsed:                         12.4s
  ----------------------------------------------------------------
  RAF deleted:                     1  (0 failed)
  ----------------------------------------------------------------
  Fuji files moved:                2
    ↳ filesystem date:             0
    ↳ new subfolders:              1
  ----------------------------------------------------------------
  Photo files moved:               4
    ↳ filesystem date:             0
    ↳ new subfolders:              1
  ----------------------------------------------------------------
  Duplicates → /review/:           1
  Flagged dates:                   0
  Errors:                          0

  Re-run without --dry-run to apply changes.
  Report saved → /Photos/Source_Unsorted_Photos/sort_report.txt
```

---

## Report file

A plain-text report is saved to `SOURCE/sort_report.txt` (or `--report`
path) after every run. It contains:

- RAF files deleted (full paths)
- Every Fuji file moved (source → destination)
- Every other file moved (source → destination)
- Files that used filesystem date fallback
- Files with a flagged (implausible) filename-parsed date
- Duplicates with the path of the existing matched file
- Source verification result
- All errors

---

## Notes

- **RAF files are permanently deleted** — not moved to trash. Confirm you
  have processed your RAWs in Lightroom / Capture One before running.
- **Nothing in the destinations is ever touched.** The script only reads
  them to build the duplicate index.
- The `/review/` folder is created inside `SOURCE/`, not in the
  destinations.
- Re-running the script on the same source folder is safe — any file that
  was already moved to a destination will be detected as a duplicate and
  placed in `/review/`.

---

## Dependencies

```bash
pip install exifread pillow
```

| Library | Role | Fallback if missing |
|---|---|---|
| `exifread` | Read DateTimeOriginal + Make from EXIF | Date from filename / filesystem |
| `pillow` | JPEG EXIF fallback (tag IDs 36867, 271) | Skipped silently |

Or use the GUI instead — see [`GUI.md`](GUI.md).
