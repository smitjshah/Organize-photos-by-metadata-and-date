# Photo Organizer — Desktop App

A Windows desktop app that wraps `sort_photos.py` and `organize_v2.py` behind
a modern Fluent-styled UI with folder pickers instead of command-line flags.
Same two workflows as the scripts, same underlying engine
(`photo_organizer/engine/`) — nothing about what the tool *does* changed,
only how you drive it.

---

## Two ways to run it

| Way | What you need | When to use it |
|---|---|---|
| **Built `.exe`** | Nothing — it's self-contained | Everyday use |
| **From source** (`python -m photo_organizer.app.main`) | Python 3.10+ and the dependencies installed | Development, or if you want to modify the app |

---

## Running the built `.exe`

```
dist\PhotoOrganizer.exe
```

Just double-click it. It bundles Python, PySide6, the Fluent UI toolkit,
`exifread`, and `Pillow` — nothing needs to be installed on the machine you
run it on. There's no console window; if it doesn't visibly appear, check
the Windows taskbar.

If you don't have a built `.exe` yet, see [Building the .exe](#building-the-exe) below.

---

## Running from source (development)

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux/macOS

# 2. Install dependencies
pip install -e ".[dev]"
# or, without editable install:
pip install exifread pillow PySide6 "PySide6-Fluent-Widgets[full]"

# 3. Launch the app
python -m photo_organizer.app.main
```

---

## Using the app

### Home screen
Two cards, one per workflow:

- **Sort New Photos** — the ongoing-use flow (equivalent to `sort_photos.py`)
- **Sort From Scratch** — the one-time bulk-reorganize flow (equivalent to `organize_v2.py`)

Click **Get Started** on either card to open that screen. You can also jump
directly between screens using the left navigation pane at any time.

### Sort New Photos screen

1. Pick three folders (each has a **Browse…** button that opens the normal
   Windows folder picker):
   - **Source** — the flat folder you dropped new camera imports into
   - **Fuji destination** — your existing Fuji library root
   - **Photos destination** — your existing library root for everything else
2. Click **Dry Run**. This previews what would happen — nothing is moved or
   deleted. Progress (current stage, a progress bar, live running counts,
   and a scrolling log of Fuji/Photo/Duplicate/Flagged/Error events) appears
   below the buttons.
3. When the dry run finishes, a summary appears (files moved, duplicates,
   flagged dates, RAF deleted, errors) along with **Open Report** and
   **Open Fuji/Photos Folder** buttons.
4. **Run Live** only becomes clickable once a dry run has completed *for
   the exact folders currently selected* — see [The dry-run safety gate](#the-dry-run-safety-gate)
   below. Clicking it shows a confirmation dialog summarizing what will
   happen (including an explicit warning that `.RAF` files are permanently
   deleted, not sent to the Recycle Bin) before anything actually runs.
5. While a run is in progress, a **Cancel** button appears. Cancelling stops
   the run cleanly after the file currently being processed — anything
   already moved stays moved, nothing is left half-written — and forces a
   fresh dry run before you can run live again.

Your three folder paths are remembered between runs (and between app
restarts) so you don't have to re-pick them every time.

### Sort From Scratch screen

1. Pick a single **Root** folder — the existing messy library you want to
   reorganize in one pass.
2. The screen shows the derived paths it will use, read-only:
   - Fuji destination: `ROOT\Fuji`
   - Review (duplicates): `ROOT\review`
   - Report: `ROOT\organize_v2_report.txt`

   These aren't separately editable in this version — Sort From Scratch is
   meant for a single self-contained root, and this avoids accidentally
   pointing the Fuji destination or review folder somewhere unrelated. If
   you need them somewhere else, use `organize_v2.py` directly from the
   command line with the equivalent CLI flags described in
   [`organize_v2.md`](organize_v2.md).
3. **Dry Run**, review the summary, then **Run Live** — same gate,
   confirmation dialog, live progress, and cancel behavior as Sort New
   Photos, described above.

### The dry-run safety gate

Because a live run permanently deletes `.RAF` files and can move tens of
thousands of files, **Run Live is locked until a dry run has completed for
the exact folder selection currently on screen**:

- Change any folder path after a dry run → Live relocks immediately.
- Cancel a run, or have one fail → Live relocks; you need a fresh dry run.
- After a live run completes, Live relocks again — you must dry-run again
  before running live a second time, even against the same folders (their
  contents just changed).

This is deliberate and can't be bypassed from the UI. If you're certain of
what you're doing and want to skip the gate, use the CLI scripts directly
(`--dry-run` is optional there, not required).

### Reports and remembered settings

- Reports are written to the exact same locations as the CLI scripts:
  `SOURCE\sort_report.txt` for Sort New Photos, `ROOT\organize_v2_report.txt`
  for Sort From Scratch.
- Remembered folder paths are stored per-Windows-user via `QSettings`
  (`HKEY_CURRENT_USER\Software\PhotoOrganizer\PhotoOrganizer` or an INI file
  under your user profile, depending on build) — nothing is written inside
  the photo folders themselves except the report file.

---

## Building the `.exe`

Requires the dev dependencies (`pip install -e ".[dev,build]"` or
`pip install pyinstaller` on top of the runtime deps above).

```powershell
# From the repo root
powershell -File photo_organizer\packaging\build.ps1
```

or manually:

```bash
pyinstaller photo_organizer/packaging/photo_organizer.spec --noconfirm
```

Output: `dist\PhotoOrganizer.exe` (single file, ~100 MB — it bundles the
Python runtime, Qt, and the Fluent UI toolkit's acrylic-effect dependencies).
Double-click it once to confirm it launches before distributing it.

To change the app icon, replace `photo_organizer/app/resources/icon.ico`
(and `icon.png`) and rebuild — the icon is used both for the `.exe` file
itself and the running window.

---

## Running the test suite

```bash
QT_QPA_PLATFORM=offscreen python -m pytest photo_organizer/tests -q
```

(`QT_QPA_PLATFORM=offscreen` lets the GUI tests run without a visible
display — needed on CI or when working over a remote session; not needed on
Windows PowerShell if you drop the prefix and run pytest directly, since a
real display is normally available there. On Windows PowerShell:
`$env:QT_QPA_PLATFORM="offscreen"; python -m pytest photo_organizer/tests -q`.)

Covers: EXIF/date/filename-fallback logic, deduplication, the dry-run gate
state machine, both pipelines end-to-end (dry run + live run, on a synthetic
sample tree), and headless GUI smoke tests that drive the real screens
through a full dry-run → live-run → cancel cycle.

---

## Project layout

```
photo_organizer/
  engine/       # all business logic (EXIF reading, routing, dedup, reports) —
                # shared by the GUI and the sort_photos.py / organize_v2.py CLIs
  app/          # PySide6 + Fluent-widgets GUI
    main.py       # entry point — window shell + navigation
    workers.py    # background QThread workers driving the engine
    state.py      # the dry-run safety gate state machine
    widgets/      # the individual screens and reusable components
  packaging/    # PyInstaller spec + build script
  tests/        # pytest suite (engine logic + headless GUI smoke tests)
sort_photos.py    # CLI — thin wrapper over photo_organizer.engine
organize_v2.py    # CLI — thin wrapper over photo_organizer.engine
```

---

## See also

- [`sort_photos.md`](sort_photos.md) — full CLI reference for `sort_photos.py`
- [`organize_v2.md`](organize_v2.md) — full CLI reference for `organize_v2.py`
