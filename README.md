# 📷 Photo Library Organizer

Organises a large personal photo/video library — reading EXIF metadata,
renaming files by date, routing Fujifilm shots to a dedicated folder,
deduplicating across destinations, and cleaning up empty folders.

Two ways to use it:

- **Desktop app** — a Fluent-styled Windows GUI, packaged as a single
  `.exe`. Same two workflows as the scripts below, driven with folder
  pickers instead of command-line flags. See [`GUI.md`](GUI.md).
- **Command-line scripts** — `sort_photos.py` and `organize_v2.py`, unchanged
  in behavior from before. See below and their linked reference docs.

Both share the exact same underlying logic
(`photo_organizer/engine/`) — the GUI isn't a reimplementation, it's a
different front end on the same code.

---

## Scripts / workflows

| Workflow | CLI script | GUI screen | Purpose |
|---|---|---|---|
| Ongoing use | [`sort_photos.py`](sort_photos.py) | Sort New Photos | Drop new imports into a source folder and sort them into the correct destination |
| One-time bulk run | [`organize_v2.py`](organize_v2.py) | Sort From Scratch | Reorganise an entire existing photo root, routing Fuji separately |

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

**For the scripts** (or to run the GUI from source):

```bash
pip install exifread pillow
```

**To also run or build the desktop GUI:**

```bash
pip install PySide6 "PySide6-Fluent-Widgets[full]"
pip install pyinstaller   # only needed to build the .exe yourself
```

Or install everything at once from the project's `pyproject.toml`:

```bash
pip install -e ".[dev,build]"
```

Works on **Windows and Linux/macOS** with Python 3.10+ (the desktop GUI is
built/tested for Windows; the underlying engine and CLI scripts are
cross-platform). `exifread` and `pillow` are both optional at runtime —
everything falls back gracefully without them (with reduced date/camera
accuracy), but they're strongly recommended.

- `exifread` — primary EXIF reader (date + camera make)
- `pillow`   — fallback EXIF reader for JPEGs that exifread misses

---

## Quick start

### Desktop app

```
dist\PhotoOrganizer.exe          # if already built — just double-click it
```

```bash
# or run/build from source — see GUI.md for full details
python -m photo_organizer.app.main                                   # run
pyinstaller photo_organizer/packaging/photo_organizer.spec --noconfirm  # build
```

Full walkthrough (screens, the dry-run safety gate, building the `.exe`,
running the test suite): **[`GUI.md`](GUI.md)**.

### Command line

```bash
# 1. One-time bulk organise of an existing messy folder
python organize_v2.py --root E:\Photos              # dry run first — no files moved
python organize_v2.py --root E:\Photos --run         # live run

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

## Project layout

```
photo_organizer/
  engine/       # business logic shared by the GUI and both CLI scripts
  app/          # the PySide6 + Fluent-widgets desktop GUI
  packaging/    # PyInstaller spec + build script for the .exe
  tests/        # pytest suite (engine logic + headless GUI smoke tests)
sort_photos.py    # CLI — thin wrapper over photo_organizer.engine
organize_v2.py    # CLI — thin wrapper over photo_organizer.engine
```

---

## See also

- [`GUI.md`](GUI.md) — desktop app: how to run it, use it, and build the `.exe`
- [`sort_photos.md`](sort_photos.md) — full CLI reference for `sort_photos.py`
- [`organize_v2.md`](organize_v2.md) — full CLI reference for `organize_v2.py`
