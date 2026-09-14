"""Synthetic file-tree builders used by pipeline tests and for manual GUI smoke testing.

Run directly to materialize a sample tree on disk for manual testing:
    python -m photo_organizer.tests.fixtures.make_sample_tree <output_dir> [sort|organize]
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image


def make_jpeg(path: Path, make: str | None = None, date_taken: str | None = None) -> None:
    """Write a tiny valid JPEG, optionally with Make (tag 271) / DateTime (tag 306) EXIF."""
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (8, 8), color=(200, 30, 30))
    exif = img.getexif()
    if make:
        exif[271] = make
    if date_taken:
        exif[306] = date_taken
    img.save(path, "JPEG", exif=exif)


def make_bytes_file(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def build_sort_sample(base: Path) -> dict[str, Path]:
    """Build a SOURCE / FUJI_DEST / PHOTOS_DEST tree for sort_pipeline tests.

    Composition:
      - Fuji JPEG with EXIF date            -> should route to fuji_dest/2024/03/
      - Non-Fuji JPEG with EXIF date         -> should route to photos_dest/2023/07/
      - Video with filename-only date        -> photos_dest/2023/08/, flagged as "filename" source
      - Snapchat-style far-future filename   -> photos_dest/2080/09/, flagged as suspicious date
      - No-signal file (fs-date fallback)    -> photos_dest/<mtime year>/<mtime month>/, fallback flagged
      - Already-prefixed filename            -> prefix must not be doubled
      - .RAF file                            -> deleted
      - Duplicate: a photos_dest file that already contains identical bytes to a new source file
    """
    source = base / "source"
    fuji_dest = base / "fuji_dest"
    photos_dest = base / "photos_dest"
    for d in (source, fuji_dest, photos_dest):
        d.mkdir(parents=True, exist_ok=True)

    make_jpeg(source / "DSCF1001.JPG", make="FUJIFILM", date_taken="2024:03:15 10:00:00")
    make_jpeg(source / "IMG_2001.JPG", make="Canon", date_taken="2023:07:01 09:30:00")
    make_bytes_file(source / "VID_20230801_120000.mp4", b"fake-video-bytes-filename-date")
    make_bytes_file(source / "Snapchat-2080090122.mp4", b"fake-video-bytes-snapchat")
    make_bytes_file(source / "unknown.jpg", b"no-exif-no-filename-date")
    make_jpeg(source / "2023-05-20_prefixed.jpg", make="Canon", date_taken="2023:05:20 08:00:00")
    make_bytes_file(source / "DSCF9999.RAF", b"raw-fuji-file")

    dup_bytes = b"duplicate-content-shared-between-source-and-dest"
    make_bytes_file(source / "dup_new.jpg", dup_bytes)
    make_bytes_file(photos_dest / "2022" / "01" / "2022-01-01_dup_existing.jpg", dup_bytes)

    return {"source": source, "fuji_dest": fuji_dest, "photos_dest": photos_dest}


def build_organize_sample(base: Path) -> dict[str, Path]:
    """Build a single ROOT tree for organize_pipeline tests.

    Composition mirrors build_sort_sample but flat under one root, plus:
      - a pre-existing top-level YYYY dir (already-processed, must be skipped by collect())
      - a pre-existing review/ and Fuji/ dir (protected, must be skipped)
      - a Fuji duplicate pair (regression test for the fuji/other dedup-attribution bug fix)
    """
    root = base / "root"
    root.mkdir(parents=True, exist_ok=True)

    make_jpeg(root / "DSCF2001.JPG", make="FUJIFILM", date_taken="2024:03:15 10:00:00")
    make_jpeg(root / "IMG_3001.JPG", make="Canon", date_taken="2023:07:01 09:30:00")
    make_bytes_file(root / "VID_20230801_120000.mp4", b"fake-video-bytes-filename-date")
    make_bytes_file(root / "Snapchat-2080090122.mp4", b"fake-video-bytes-snapchat")
    make_bytes_file(root / "unknown.jpg", b"no-exif-no-filename-date")
    make_bytes_file(root / "DSCF9998.RAF", b"raw-fuji-file")

    make_jpeg(root / "DSCF2002.JPG", make="FUJIFILM", date_taken="2024:04:01 10:00:00")
    make_bytes_file(root / "DSCF2002_copy.JPG", (root / "DSCF2002.JPG").read_bytes())

    # Already-processed / protected dirs collect() must skip
    (root / "2020" / "01").mkdir(parents=True, exist_ok=True)
    make_bytes_file(root / "2020" / "01" / "already-sorted.jpg", b"should-not-be-touched")
    (root / "review").mkdir(parents=True, exist_ok=True)
    (root / "Fuji").mkdir(parents=True, exist_ok=True)

    return {"root": root, "fuji_root": root / "Fuji", "review": root / "review"}


if __name__ == "__main__":
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "sample_tree")
    flow = sys.argv[2] if len(sys.argv) > 2 else "sort"
    if flow == "organize":
        paths = build_organize_sample(out)
    else:
        paths = build_sort_sample(out)
    for k, v in paths.items():
        print(f"{k}: {v}")
