"""Dry-run-before-live gate state machine.

One instance per flow screen (Sort New Photos, Sort From Scratch) since each
flow has an independent folder selection and dry-run history. See the plan
section "Dry-run gate state machine" for the full rationale.

States:
    NO_DRY_RUN            -- initial, or after any folder path changed
    DRY_RUN_IN_PROGRESS   -- a dry run is currently running
    DRY_RUN_COMPLETE      -- Live is unlocked, for exactly this path snapshot
    LIVE_RUN_IN_PROGRESS  -- a live run is currently running
    LIVE_RUN_COMPLETE     -- must dry-run again before any further live run
"""

from __future__ import annotations

from enum import Enum, auto
from typing import Any

_STATUS_TEXT = {
    "NO_DRY_RUN": "Not previewed yet",
    "DRY_RUN_IN_PROGRESS": "Previewing…",
    "DRY_RUN_COMPLETE": "Preview complete — ready for live run",
    "LIVE_RUN_IN_PROGRESS": "Running live — do not close the app",
    "LIVE_RUN_COMPLETE": "Live run complete",
}


class GateState(Enum):
    NO_DRY_RUN = auto()
    DRY_RUN_IN_PROGRESS = auto()
    DRY_RUN_COMPLETE = auto()
    LIVE_RUN_IN_PROGRESS = auto()
    LIVE_RUN_COMPLETE = auto()


class DryRunGateState:
    def __init__(self) -> None:
        self.state: GateState = GateState.NO_DRY_RUN
        self._paths_snapshot: tuple[Any, ...] | None = None

    @property
    def live_enabled(self) -> bool:
        return self.state == GateState.DRY_RUN_COMPLETE

    @property
    def controls_enabled(self) -> bool:
        """Whether Dry Run / folder pickers should be interactable (i.e. not mid-run)."""
        return self.state not in (GateState.DRY_RUN_IN_PROGRESS, GateState.LIVE_RUN_IN_PROGRESS)

    @property
    def status_text(self) -> str:
        return _STATUS_TEXT[self.state.name]

    def on_paths_changed(self) -> None:
        if self.state == GateState.DRY_RUN_COMPLETE:
            self.state = GateState.NO_DRY_RUN
            self._paths_snapshot = None

    def start_dry_run(self) -> None:
        self.state = GateState.DRY_RUN_IN_PROGRESS

    def dry_run_finished(self, paths_snapshot: tuple[Any, ...]) -> None:
        self.state = GateState.DRY_RUN_COMPLETE
        self._paths_snapshot = paths_snapshot

    def dry_run_aborted(self) -> None:
        self.state = GateState.NO_DRY_RUN
        self._paths_snapshot = None

    def can_start_live(self, current_paths: tuple[Any, ...]) -> bool:
        """Defensive re-check: the path snapshot must still match what was dry-run."""
        return self.state == GateState.DRY_RUN_COMPLETE and self._paths_snapshot == current_paths

    def start_live_run(self) -> None:
        self.state = GateState.LIVE_RUN_IN_PROGRESS

    def live_run_finished(self) -> None:
        self.state = GateState.LIVE_RUN_COMPLETE
        self._paths_snapshot = None

    def live_run_aborted(self) -> None:
        self.state = GateState.NO_DRY_RUN
        self._paths_snapshot = None
