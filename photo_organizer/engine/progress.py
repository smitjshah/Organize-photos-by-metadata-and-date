"""Progress reporting protocol shared by the engine, the CLI wrappers, and the GUI.

Engine pipelines never print or otherwise talk to stdout directly -- they
emit ProgressEvent objects through a ProgressReporter. A CLI wrapper can
implement a reporter that prints to the console (reproducing the old
sort_photos.py / organize_v2.py console UX); the GUI implements one that
re-emits Qt signals from a worker thread. Tests use the default NullReporter.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

EventKind = Literal[
    "progress",      # generic i/total tick for a named stage
    "moved",          # a file was routed+renamed+moved to its destination
    "duplicate",       # a file matched an existing/seen file, routed to review/
    "fallback",         # a moved file used the filesystem-date fallback
    "flagged_date",      # a moved file's filename-parsed date looks implausible
    "raf_deleted",        # a .RAF file was deleted
    "raf_failed",          # a .RAF file failed to delete
    "dir_removed",           # an empty directory was removed (organize flow)
    "error",                  # a file could not be processed
    "info",                    # free-text status line, no numeric progress
]


@dataclass(frozen=True)
class ProgressEvent:
    stage: str
    kind: EventKind
    current: int = 0
    total: int = 0
    item: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)


class ProgressReporter(Protocol):
    def emit(self, event: ProgressEvent) -> None: ...


class NullReporter:
    """No-op reporter; used by default so pipelines are callable headlessly (tests, CLI-less)."""

    def emit(self, event: ProgressEvent) -> None:  # noqa: D401
        pass


class PipelineCancelled(Exception):
    """Raised internally when a CancelToken is tripped mid-pipeline."""


class CancelToken:
    """Cooperative cancellation flag. Checked between file operations, never mid-move."""

    def __init__(self) -> None:
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    @property
    def is_cancelled(self) -> bool:
        return self._cancelled

    def raise_if_cancelled(self) -> None:
        if self._cancelled:
            raise PipelineCancelled()
