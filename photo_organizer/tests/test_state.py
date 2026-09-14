from __future__ import annotations

from photo_organizer.app.state import DryRunGateState, GateState


def test_initial_state_locks_live():
    gate = DryRunGateState()
    assert gate.state == GateState.NO_DRY_RUN
    assert gate.live_enabled is False


def test_dry_run_completion_unlocks_live_for_matching_paths():
    gate = DryRunGateState()
    paths = ("src", "fuji", "photos")

    gate.start_dry_run()
    assert gate.live_enabled is False
    assert gate.controls_enabled is False

    gate.dry_run_finished(paths)
    assert gate.live_enabled is True
    assert gate.can_start_live(paths) is True
    assert gate.can_start_live(("other",)) is False


def test_path_change_relocks_live():
    gate = DryRunGateState()
    paths = ("src", "fuji", "photos")
    gate.start_dry_run()
    gate.dry_run_finished(paths)
    assert gate.live_enabled is True

    gate.on_paths_changed()

    assert gate.live_enabled is False
    assert gate.state == GateState.NO_DRY_RUN


def test_dry_run_abort_returns_to_no_dry_run():
    gate = DryRunGateState()
    gate.start_dry_run()
    gate.dry_run_aborted()
    assert gate.state == GateState.NO_DRY_RUN
    assert gate.live_enabled is False


def test_live_run_lifecycle_forces_fresh_dry_run_after_completion():
    gate = DryRunGateState()
    paths = ("a", "b", "c")
    gate.start_dry_run()
    gate.dry_run_finished(paths)

    gate.start_live_run()
    assert gate.live_enabled is False
    assert gate.controls_enabled is False

    gate.live_run_finished()
    assert gate.state == GateState.LIVE_RUN_COMPLETE
    assert gate.live_enabled is False
    assert gate.can_start_live(paths) is False  # must dry-run again


def test_live_run_failure_forces_fresh_dry_run():
    gate = DryRunGateState()
    paths = ("a", "b", "c")
    gate.start_dry_run()
    gate.dry_run_finished(paths)
    gate.start_live_run()

    gate.live_run_aborted()

    assert gate.state == GateState.NO_DRY_RUN
    assert gate.can_start_live(paths) is False
