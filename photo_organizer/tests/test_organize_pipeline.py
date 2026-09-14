from __future__ import annotations

from pathlib import Path

from photo_organizer.engine.organize_pipeline import process
from photo_organizer.tests.fixtures.make_sample_tree import build_organize_sample


def _run(tmp_path: Path, dry_run: bool):
    paths = build_organize_sample(tmp_path)
    report_path = tmp_path / "organize_v2_report.txt"
    result = process(
        root=paths["root"],
        fuji_root=paths["fuji_root"],
        review=paths["review"],
        report_path=report_path,
        dry_run=dry_run,
    )
    return paths, result, report_path


def test_collect_skips_protected_and_already_sorted_dirs(tmp_path: Path):
    paths, result, report_path = _run(tmp_path, dry_run=True)
    root = paths["root"]

    # Pre-existing YYYY dir must never be touched or reported as processed.
    assert (root / "2020" / "01" / "already-sorted.jpg").exists()
    all_processed_names = {n for n, _ in result.fuji_ok + result.other_ok + result.fuji_fallback + result.other_fallback}
    assert "already-sorted.jpg" not in all_processed_names


def test_dry_run_reports_but_does_not_move(tmp_path: Path):
    paths, result, report_path = _run(tmp_path, dry_run=True)
    root = paths["root"]

    assert (root / "DSCF2001.JPG").exists()
    assert (root / "DSCF9998.RAF").exists()
    assert not (root / "Fuji" / "2024" / "03" / "2024-03-15_DSCF2001.JPG").exists()
    assert report_path.exists()


def test_live_run_routes_and_fixes_fuji_duplicate_attribution(tmp_path: Path):
    paths, result, report_path = _run(tmp_path, dry_run=False)
    root, fuji_root = paths["root"], paths["fuji_root"]

    # Fuji file routed under Fuji/YYYY/MM.
    assert (fuji_root / "2024" / "03" / "2024-03-15_DSCF2001.JPG").exists()

    # Non-Fuji EXIF file routed under root/YYYY/MM.
    assert (root / "2023" / "07" / "2023-07-01_IMG_3001.JPG").exists()

    # Filename-date video.
    assert (root / "2023" / "08" / "2023-08-01_VID_20230801_120000.mp4").exists()

    # Snapchat far-future filename date -> flagged.
    assert (root / "2080" / "09" / "2080-09-01_Snapchat-2080090122.mp4").exists()
    assert any(name == "Snapchat-2080090122.mp4" for name, _, _ in result.flagged_dates)

    # Filesystem-fallback file.
    assert any(name == "unknown.jpg" for name, _ in result.fuji_fallback + result.other_fallback)

    # RAF deleted.
    assert not (root / "DSCF9998.RAF").exists()
    assert len(result.raf_deleted) == 1

    # Exactly one duplicate pair collapses to one dedup event, and — this is the
    # regression test for the fuji/other misattribution bug fix — it must be
    # attributed to fuji_dup (both copies carry real Fuji EXIF), not other_dup.
    assert len(result.fuji_dup) + len(result.other_dup) == 1
    assert len(result.fuji_dup) == 1
    assert len(result.other_dup) == 0

    # The duplicate itself ended up in review/, the "winner" ended up in Fuji/.
    review_names = {p.name for p in paths["review"].rglob("*") if p.is_file()}
    assert {"DSCF2002.JPG", "DSCF2002_copy.JPG"} & review_names
    fuji_names = {p.name for p in fuji_root.rglob("*") if p.is_file()}
    assert {"2024-04-01_DSCF2002.JPG", "2024-04-01_DSCF2002_copy.JPG"} & fuji_names

    # Pre-existing already-sorted content under root/2020 is left completely alone.
    assert (root / "2020" / "01" / "already-sorted.jpg").exists()

    assert report_path.exists()
    text = report_path.read_text(encoding="utf-8")
    assert "ORGANIZE V2 REPORT" in text
    assert "FLAGGED DATES" in text
