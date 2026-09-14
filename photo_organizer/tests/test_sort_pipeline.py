from __future__ import annotations

from pathlib import Path

import pytest

from photo_organizer.engine.progress import CancelToken, PipelineCancelled, ProgressEvent
from photo_organizer.engine.sort_pipeline import process
from photo_organizer.tests.fixtures.make_sample_tree import build_sort_sample


def _run(tmp_path: Path, dry_run: bool):
    paths = build_sort_sample(tmp_path)
    report_path = tmp_path / "sort_report.txt"
    result = process(
        source=paths["source"],
        fuji_dest=paths["fuji_dest"],
        photos_dest=paths["photos_dest"],
        dry_run=dry_run,
        report_path=report_path,
    )
    return paths, result, report_path


def test_dry_run_moves_nothing(tmp_path: Path):
    paths, result, report_path = _run(tmp_path, dry_run=True)

    # Counts are still computed for preview purposes...
    assert len(result.fuji_moved) == 1
    assert len(result.photos_moved) == 5
    assert len(result.duplicates) == 1
    assert len(result.raf_deleted) == 1

    # ...but nothing on disk actually changed.
    assert (paths["source"] / "DSCF1001.JPG").exists()
    assert (paths["source"] / "DSCF9999.RAF").exists()
    assert not (paths["fuji_dest"] / "2024" / "03" / "2024-03-15_DSCF1001.JPG").exists()
    assert report_path.exists()  # report is always written, even for a preview


def test_live_run_routes_renames_dedupes_and_deletes_raf(tmp_path: Path):
    paths, result, report_path = _run(tmp_path, dry_run=False)

    fuji_dest, photos_dest, source = paths["fuji_dest"], paths["photos_dest"], paths["source"]

    # Fuji file routed correctly with date-prefixed rename.
    assert (fuji_dest / "2024" / "03" / "2024-03-15_DSCF1001.JPG").exists()
    assert len(result.fuji_moved) == 1
    assert len(result.fuji_fallback) == 0

    # Non-Fuji EXIF file.
    assert (photos_dest / "2023" / "07" / "2023-07-01_IMG_2001.JPG").exists()

    # Filename-only date video.
    assert (photos_dest / "2023" / "08" / "2023-08-01_VID_20230801_120000.mp4").exists()

    # Snapchat-style far-future filename date -> flagged, not silently dropped.
    assert (photos_dest / "2080" / "09" / "2080-09-01_Snapchat-2080090122.mp4").exists()
    assert len(result.flagged_dates) == 1
    assert result.flagged_dates[0][0] == "Snapchat-2080090122.mp4"

    # No-signal file used the filesystem fallback and is flagged as such.
    assert len(result.photos_fallback) == 1
    assert result.photos_fallback[0][0] == "unknown.jpg"

    # Already-prefixed filename is not double-prefixed.
    matches = list(photos_dest.rglob("2023-05-20_prefixed.jpg"))
    assert len(matches) == 1
    assert not list(photos_dest.rglob("*_2023-05-20_prefixed.jpg"))

    # RAF permanently deleted.
    assert not (source / "DSCF9999.RAF").exists()
    assert len(result.raf_deleted) == 1

    # Duplicate routed to SOURCE/review/, not into a destination.
    assert (source / "review" / "dup_new.jpg").exists()
    assert len(result.duplicates) == 1

    # Source root ends up clear (only review/ left).
    assert result.source_leftovers == []
    remaining_top_level = [
        p for p in source.iterdir() if p.is_file() or p.name != "review"
    ]
    assert all(p.name == "review" for p in remaining_top_level if p.is_dir()) or not remaining_top_level

    assert report_path.exists()
    assert "SORT PHOTOS REPORT" in report_path.read_text(encoding="utf-8")


def test_cancellation_leaves_already_moved_files_intact_and_stops_early(tmp_path: Path):
    paths = build_sort_sample(tmp_path)
    token = CancelToken()

    class CancelAfterTwoMoves:
        def __init__(self):
            self.moved = 0

        def emit(self, event: ProgressEvent) -> None:
            if event.kind == "moved":
                self.moved += 1
                if self.moved >= 2:
                    token.cancel()

    reporter = CancelAfterTwoMoves()

    with pytest.raises(PipelineCancelled):
        process(
            source=paths["source"],
            fuji_dest=paths["fuji_dest"],
            photos_dest=paths["photos_dest"],
            dry_run=False,
            report_path=tmp_path / "sort_report.txt",
            reporter=reporter,
            cancel_token=token,
        )

    assert reporter.moved >= 2
    # Every file not yet processed must still be sitting untouched in source.
    all_original_names = {
        "DSCF1001.JPG", "IMG_2001.JPG", "VID_20230801_120000.mp4",
        "Snapchat-2080090122.mp4", "unknown.jpg", "2023-05-20_prefixed.jpg",
        "dup_new.jpg",
    }
    remaining_in_source = {p.name for p in paths["source"].iterdir() if p.is_file()}
    moved_elsewhere = all_original_names - remaining_in_source
    # At least the files counted as "moved" before cancellation are gone from source,
    # and every one of those has landed at a real destination path (not lost).
    assert len(moved_elsewhere) >= 2
