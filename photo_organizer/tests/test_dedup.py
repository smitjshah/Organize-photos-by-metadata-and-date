from __future__ import annotations

from pathlib import Path

from photo_organizer.engine.dedup import build_size_index, find_duplicate, md5
from photo_organizer.tests.fixtures.make_sample_tree import make_bytes_file


def test_build_size_index_groups_by_size(tmp_path: Path):
    dest = tmp_path / "dest"
    make_bytes_file(dest / "a.jpg", b"12345")
    make_bytes_file(dest / "sub" / "b.jpg", b"12345")
    make_bytes_file(dest / "c.jpg", b"1")

    index = build_size_index(dest)

    assert len(index[5]) == 2
    assert len(index[1]) == 1


def test_build_size_index_missing_dir_returns_empty(tmp_path: Path):
    assert build_size_index(tmp_path / "does-not-exist") == {}


def test_find_duplicate_no_size_collision_returns_none(tmp_path: Path):
    dest = tmp_path / "dest"
    make_bytes_file(dest / "a.jpg", b"12345")
    index = build_size_index(dest)

    src = tmp_path / "new.jpg"
    make_bytes_file(src, b"different-size-content")

    assert find_duplicate(src, index) is None


def test_find_duplicate_size_collision_but_different_content(tmp_path: Path):
    dest = tmp_path / "dest"
    make_bytes_file(dest / "a.jpg", b"AAAAA")
    index = build_size_index(dest)

    src = tmp_path / "new.jpg"
    make_bytes_file(src, b"BBBBB")  # same size, different content -> md5 differs

    assert find_duplicate(src, index) is None


def test_find_duplicate_matches_on_md5(tmp_path: Path):
    dest = tmp_path / "dest"
    existing = dest / "a.jpg"
    make_bytes_file(existing, b"identical-bytes")
    index = build_size_index(dest)

    src = tmp_path / "new.jpg"
    make_bytes_file(src, b"identical-bytes")

    match = find_duplicate(src, index)
    assert match == existing
    assert md5(src) == md5(existing)
