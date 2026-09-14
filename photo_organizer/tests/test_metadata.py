from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from photo_organizer.engine.metadata import (
    _date_from_filename,
    _parse_dt,
    get_metadata,
    is_fuji,
    is_suspicious_date,
)
from photo_organizer.tests.fixtures.make_sample_tree import make_bytes_file, make_jpeg


def test_parse_dt_accepts_exif_and_iso_formats():
    assert _parse_dt("2024:03:15 10:00:00") == datetime(2024, 3, 15, 10, 0, 0)
    assert _parse_dt("2024-03-15 10:00:00") == datetime(2024, 3, 15, 10, 0, 0)
    assert _parse_dt("not a date") is None


def test_date_from_filename_dash_and_compact_patterns():
    assert _date_from_filename("2023-07-01_IMG.jpg") == datetime(2023, 7, 1)
    assert _date_from_filename("IMG_20230701_120000.jpg") == datetime(2023, 7, 1)
    assert _date_from_filename("no_date_here.jpg") is None


def test_date_from_filename_snapchat_far_future_case():
    # Known limitation: the regex grabs the first 8-digit run, producing a bogus
    # far-future date for filenames like Snapchat exports.
    dt = _date_from_filename("Snapchat-2080090122.mp4")
    assert dt == datetime(2080, 9, 1)


def test_is_fuji_case_insensitive_and_none_safe():
    assert is_fuji("FUJIFILM") is True
    assert is_fuji("fuji") is True
    assert is_fuji("Canon") is False
    assert is_fuji(None) is False
    assert is_fuji("") is False


def test_is_suspicious_date_flags_far_future_filename_date(tmp_path: Path):
    f = tmp_path / "Snapchat-2080090122.mp4"
    make_bytes_file(f, b"x")
    dt = datetime(2080, 9, 1)
    assert is_suspicious_date(dt, "filename", f) is True


def test_is_suspicious_date_ignores_exif_and_filesystem_sources(tmp_path: Path):
    f = tmp_path / "whatever.jpg"
    make_bytes_file(f, b"x")
    dt = datetime(2080, 9, 1)
    assert is_suspicious_date(dt, "EXIF", f) is False
    assert is_suspicious_date(dt, "filesystem", f) is False


def test_is_suspicious_date_accepts_plausible_recent_filename_date(tmp_path: Path):
    f = tmp_path / "2024-03-15_IMG.jpg"
    make_bytes_file(f, b"x")
    assert is_suspicious_date(datetime(2024, 3, 15), "filename", f) is False


def test_get_metadata_reads_exif_make_and_date(tmp_path: Path):
    f = tmp_path / "DSCF1001.JPG"
    make_jpeg(f, make="FUJIFILM", date_taken="2024:03:15 10:00:00")

    dt, source, make = get_metadata(f)

    assert dt == datetime(2024, 3, 15, 10, 0, 0)
    assert source in ("EXIF", "EXIF(PIL)")
    assert make is not None and "fuji" in make.lower()


def test_get_metadata_falls_back_to_filename(tmp_path: Path):
    f = tmp_path / "VID_20230801_120000.mp4"
    make_bytes_file(f, b"no-exif-video-bytes")

    dt, source, make = get_metadata(f)

    assert dt == datetime(2023, 8, 1)
    assert source == "filename"


def test_get_metadata_falls_back_to_filesystem_when_no_signal(tmp_path: Path):
    f = tmp_path / "unknown.jpg"
    make_bytes_file(f, b"no-exif-no-filename-date")

    dt, source, make = get_metadata(f)

    assert source == "filesystem"
    assert dt <= datetime.now() + timedelta(minutes=1)
