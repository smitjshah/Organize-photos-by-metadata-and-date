"""Headless GUI smoke test: proves the QThread -> Qt signal -> widget update
pattern actually works end-to-end (no UI freeze, correct final state),
without needing a visible display. Uses Qt's offscreen platform plugin.
"""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication

from photo_organizer.app.widgets.sort_new_screen import SortNewPhotosScreen
from photo_organizer.tests.fixtures.make_sample_tree import build_sort_sample


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _pump_until(condition, timeout_ms: int = 15000) -> bool:
    loop = QEventLoop()
    timer = QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(loop.quit)

    def check():
        if condition():
            loop.quit()

    poll = QTimer()
    poll.timeout.connect(check)
    poll.start(20)
    timer.start(timeout_ms)
    loop.exec()
    poll.stop()
    return condition()


def test_dry_run_completes_and_unlocks_live_button(qapp, tmp_path: Path):
    paths = build_sort_sample(tmp_path)

    window = SortNewPhotosScreen()
    window.source_row.edit.setText(str(paths["source"]))
    window.fuji_row.edit.setText(str(paths["fuji_dest"]))
    window.photos_row.edit.setText(str(paths["photos_dest"]))

    assert window.live_btn.isEnabled() is False

    window.dry_run_btn.click()

    finished = _pump_until(lambda: window._gate.live_enabled or not window._worker.isRunning())

    assert finished, "worker did not finish within timeout"
    assert window._gate.live_enabled is True
    assert window.live_btn.isEnabled() is True
    assert window.progress_view.progress_bar.value() > 0

    # Dry run must not have touched the filesystem.
    assert (paths["source"] / "DSCF1001.JPG").exists()
    assert not (paths["fuji_dest"] / "2024" / "03" / "2024-03-15_DSCF1001.JPG").exists()

    window._worker.wait(5000)


def test_changing_a_path_relocks_live_button(qapp, tmp_path: Path):
    paths = build_sort_sample(tmp_path)

    window = SortNewPhotosScreen()
    window.source_row.edit.setText(str(paths["source"]))
    window.fuji_row.edit.setText(str(paths["fuji_dest"]))
    window.photos_row.edit.setText(str(paths["photos_dest"]))

    window.dry_run_btn.click()
    _pump_until(lambda: window._gate.live_enabled)
    assert window.live_btn.isEnabled() is True

    window.fuji_row.edit.setText(str(paths["fuji_dest"]) + "_changed")

    assert window.live_btn.isEnabled() is False
    assert window._gate.live_enabled is False

    window._worker.wait(5000)


def test_cancel_button_stops_live_run_and_relocks_gate(qapp, tmp_path: Path):
    from photo_organizer.app.state import GateState
    from photo_organizer.tests.fixtures.make_sample_tree import make_bytes_file

    paths = build_sort_sample(tmp_path)
    # Pad the source with enough extra files that the live run takes long enough
    # for the GUI event loop to actually get a turn and click Cancel mid-run --
    # the original handful of files complete before Qt ever schedules a signal.
    for i in range(400):
        make_bytes_file(paths["source"] / f"extra_{i:04d}.jpg", f"padding-{i}".encode())

    window = SortNewPhotosScreen()
    window.source_row.edit.setText(str(paths["source"]))
    window.fuji_row.edit.setText(str(paths["fuji_dest"]))
    window.photos_row.edit.setText(str(paths["photos_dest"]))

    window.dry_run_btn.click()
    _pump_until(lambda: window._gate.live_enabled)
    window._worker.wait(5000)

    moved_count = {"n": 0}

    def maybe_cancel(event, counts):
        if event.kind == "moved":
            moved_count["n"] += 1
            if moved_count["n"] >= 1:
                window.cancel_btn.click()

    window._start_run(dry_run=False)
    window._worker.progressed.connect(maybe_cancel)

    finished = _pump_until(lambda: window._gate.state == GateState.NO_DRY_RUN or not window._worker.isRunning())
    assert finished
    assert window._gate.state == GateState.NO_DRY_RUN
    assert window.live_btn.isEnabled() is False  # cancellation forces a fresh dry run

    window._worker.wait(5000)


def test_live_run_after_dry_run_moves_files_and_relocks_gate(qapp, tmp_path: Path):
    from photo_organizer.app.state import GateState

    paths = build_sort_sample(tmp_path)

    window = SortNewPhotosScreen()
    window.source_row.edit.setText(str(paths["source"]))
    window.fuji_row.edit.setText(str(paths["fuji_dest"]))
    window.photos_row.edit.setText(str(paths["photos_dest"]))

    window.dry_run_btn.click()
    _pump_until(lambda: window._gate.live_enabled)
    window._worker.wait(5000)
    assert not (paths["fuji_dest"] / "2024" / "03" / "2024-03-15_DSCF1001.JPG").exists()

    # Bypass the modal confirmation dialog (interactive-only) and go straight to the
    # live run the gate already unlocked -- exercises the same _start_run() path.
    window._start_run(dry_run=False)
    finished = _pump_until(lambda: window._gate.state == GateState.LIVE_RUN_COMPLETE or not window._worker.isRunning())

    assert finished, "live worker did not finish within timeout"
    assert window._gate.state == GateState.LIVE_RUN_COMPLETE
    assert window.live_btn.isEnabled() is False  # must dry-run again before another live run
    assert (paths["fuji_dest"] / "2024" / "03" / "2024-03-15_DSCF1001.JPG").exists()
    assert not (paths["source"] / "DSCF9999.RAF").exists()

    window._worker.wait(5000)
