"""Headless GUI smoke test for the Sort From Scratch screen and the main window shell."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from photo_organizer.app.state import GateState
from photo_organizer.app.widgets.sort_scratch_screen import SortFromScratchScreen
from photo_organizer.tests.fixtures.make_sample_tree import build_organize_sample
from photo_organizer.tests.test_gui_smoke import _pump_until


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_dry_run_then_live_run_via_scratch_screen(qapp, tmp_path: Path):
    paths = build_organize_sample(tmp_path)

    screen = SortFromScratchScreen()
    screen.root_row.edit.setText(str(paths["root"]))

    assert "Fuji" in screen.derived_label.text()
    assert screen.live_btn.isEnabled() is False

    screen.dry_run_btn.click()
    finished = _pump_until(lambda: screen._gate.live_enabled or not screen._worker.isRunning())
    assert finished
    assert screen._gate.live_enabled is True

    # Dry run must not have touched the filesystem.
    assert not (paths["root"] / "Fuji" / "2024" / "03" / "2024-03-15_DSCF2001.JPG").exists()

    screen._start_run(dry_run=False)
    finished = _pump_until(lambda: screen._gate.state == GateState.LIVE_RUN_COMPLETE or not screen._worker.isRunning())
    assert finished
    assert screen._gate.state == GateState.LIVE_RUN_COMPLETE
    assert screen.live_btn.isEnabled() is False

    assert (paths["root"] / "Fuji" / "2024" / "03" / "2024-03-15_DSCF2001.JPG").exists()
    assert not (paths["root"] / "DSCF9998.RAF").exists()
    # Pre-existing already-sorted content is left alone.
    assert (paths["root"] / "2020" / "01" / "already-sorted.jpg").exists()

    screen._worker.wait(5000)


def test_main_window_constructs_and_navigates(qapp):
    from photo_organizer.app.main import MainWindow

    window = MainWindow()
    assert window.stackedWidget.currentWidget() is not None

    def switch_and_settle(widget):
        window.switchTo(widget)
        _pump_until(lambda: window.stackedWidget.currentWidget() is widget, timeout_ms=1000)

    switch_and_settle(window.sort_new_screen)
    assert window.stackedWidget.currentWidget() is window.sort_new_screen

    switch_and_settle(window.sort_scratch_screen)
    assert window.stackedWidget.currentWidget() is window.sort_scratch_screen

    switch_and_settle(window.home_screen)
    assert window.stackedWidget.currentWidget() is window.home_screen
