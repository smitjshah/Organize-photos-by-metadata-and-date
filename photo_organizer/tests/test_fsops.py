from __future__ import annotations

import re
from pathlib import Path

from photo_organizer.engine.fsops import (
    DATE_PREFIX_RE_SRC,
    is_path_too_long,
    remove_empty_dirs,
    safe_move,
    unique_dest,
)
from photo_organizer.tests.fixtures.make_sample_tree import make_bytes_file


def test_unique_dest_returns_same_path_when_free(tmp_path: Path):
    dest = tmp_path / "photo.jpg"
    assert unique_dest(dest) == dest


def test_unique_dest_suffixes_on_collision(tmp_path: Path):
    dest = tmp_path / "photo.jpg"
    make_bytes_file(dest, b"x")
    assert unique_dest(dest) == tmp_path / "photo_1.jpg"

    make_bytes_file(tmp_path / "photo_1.jpg", b"x")
    assert unique_dest(dest) == tmp_path / "photo_2.jpg"


def test_date_prefix_regex_matches_already_prefixed_names():
    assert re.match(DATE_PREFIX_RE_SRC, "2024-03-15_IMG_0001.jpg")
    assert not re.match(DATE_PREFIX_RE_SRC, "IMG_0001.jpg")


def test_safe_move_dry_run_does_not_touch_filesystem(tmp_path: Path):
    src = tmp_path / "src.jpg"
    make_bytes_file(src, b"x")
    dest = tmp_path / "dest" / "src.jpg"

    final = safe_move(src, dest, dry_run=True)

    assert final == dest
    assert src.exists()
    assert not dest.exists()


def test_safe_move_live_moves_and_creates_dirs(tmp_path: Path):
    src = tmp_path / "src.jpg"
    make_bytes_file(src, b"x")
    dest = tmp_path / "dest" / "2024" / "03" / "src.jpg"

    final = safe_move(src, dest, dry_run=False)

    assert final == dest
    assert dest.exists()
    assert not src.exists()


def test_safe_move_deduplicates_name_on_collision(tmp_path: Path):
    dest = tmp_path / "dest" / "src.jpg"
    make_bytes_file(dest, b"existing")

    src = tmp_path / "src.jpg"
    make_bytes_file(src, b"new")

    final = safe_move(src, dest, dry_run=False)

    assert final == tmp_path / "dest" / "src_1.jpg"
    assert final.exists()
    assert dest.read_bytes() == b"existing"


def test_is_path_too_long():
    assert is_path_too_long(Path("a" * 300))
    assert not is_path_too_long(Path("short.jpg"))


def test_remove_empty_dirs_bottom_up_skips_protected(tmp_path: Path):
    root = tmp_path / "root"
    empty1 = root / "a" / "b"
    empty1.mkdir(parents=True)
    protected = root / "review"
    protected.mkdir(parents=True)
    kept = root / "c"
    kept.mkdir(parents=True)
    make_bytes_file(kept / "file.jpg", b"x")

    removed = remove_empty_dirs(root, protected={protected}, dry_run=False)

    removed_set = set(removed)
    assert empty1 in removed_set
    assert (root / "a") in removed_set
    assert protected not in removed_set
    assert protected.exists()
    assert kept in {} or kept.exists()  # kept dir untouched (has a file)


def test_remove_empty_dirs_dry_run_leaves_filesystem_untouched(tmp_path: Path):
    root = tmp_path / "root"
    empty = root / "a"
    empty.mkdir(parents=True)

    removed = remove_empty_dirs(root, protected=set(), dry_run=True)

    assert empty in removed
    assert empty.exists()  # dry run: reported but not actually removed
