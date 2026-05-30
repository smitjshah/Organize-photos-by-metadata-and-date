# 📷 Photo Library Organizer

A set of Python scripts that organise a large personal photo/video library —
reading EXIF metadata, renaming files by date, routing Fujifilm shots to a
dedicated folder, deduplicating across destinations, and cleaning up empty
folders.

---

## Scripts

| Script | Purpose |
|---|---|
| [`sort_photos.py`](sort_photos.py) | **Ongoing use** — drop new imports into a source folder and sort them into the correct destination |
| [`organize_v2.py`](organize_v2.py) | **One-time bulk run** — reorganise an entire existing photo root, routing Fuji separately |

---

## Folder structure produced

```
photo-root/
  Fuji/
    2023/ 2024/ 2025/ 2026/
      01/ 02/ … 12/
        YYYY-MM-DD_DSCF0001.JPG
  2013/ 2014/ … 2026/        ← all other cameras
    01/ 02/ … 12/
      YYYY-MM-DD_IMG_4021.jpg
  review/                     ← exact duplicates (nothing deleted)
  Source_Unsorted_Photos/     ← drop new files here, run sort_photos.py
```

---

## Requirements

```bash
pip install exifread pillow
```

Both scripts work on **Windows and Linux/macOS** with Python 3.10+.

- `exifread` — primary EXIF reader (date + camera make)
- `pillow`   — fallback EXIF reader for JPEGs that exifread misses
- Both are optional; the scripts fall back gracefully without them

---

## Quick start

```bash
# 1. One-time bulk organise of an existing messy folder
python organize_v2.py          # dry run first — no files moved
python organize_v2.py --run    # live run

# 2. Ongoing — drop new camera imports into source, then:
python sort_photos.py \
  --source  /path/to/Source_Unsorted_Photos \
  --fuji    /path/to/Fuji \
  --photos  /path/to/Pics \
  --dry-run                    # preview
python sort_photos.py \
  --source  /path/to/Source_Unsorted_Photos \
  --fuji    /path/to/Fuji \
  --photos  /path/to/Pics     # live
```

---

## See also

- [`sort_photos.md`](sort_photos.md) — full reference for `sort_photos.py`
- [`organize_v2.md`](organize_v2.md) — full reference for `organize_v2.py`
