"""QThread workers that run the engine pipelines off the GUI thread.

Standard PySide6 long-task pattern: do the work in QThread.run(), never touch
widgets from here, only emit Qt signals. Qt marshals signal emission across
threads automatically (queued connection) as long as the receiver lives in a
different thread, which is the case here (receiver = a GUI widget).

High-frequency "progress"/"moved" events are throttled to a fixed rate before
crossing into a Qt signal, since organize_pipeline can process 80k+ files and
emitting one signal per file would flood the GUI event queue. Counters are
still updated on every event (correctness), only the signal emission rate is
capped (responsiveness). Non-progress "significant" events (duplicate, error,
raf_*, flagged_date) always flush immediately since they're comparatively
rare and the user wants to see them as they happen.
"""

from __future__ import annotations

import time
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from photo_organizer.app.models import RunCounts
from photo_organizer.engine.organize_pipeline import process as organize_process
from photo_organizer.engine.progress import CancelToken, PipelineCancelled, ProgressEvent, ProgressReporter
from photo_organizer.engine.sort_pipeline import process as sort_process

_ALWAYS_FLUSH_KINDS = {"duplicate", "error", "raf_deleted", "raf_failed", "flagged_date", "dir_removed", "info"}
_THROTTLE_SECONDS = 0.1  # ~10 signal emissions/sec cap for progress/moved


class _ThrottledSignalReporter(ProgressReporter):
    """Accumulates into a RunCounts and re-emits via a callback at a capped rate."""

    def __init__(self, counts: RunCounts, on_flush) -> None:
        self._counts = counts
        self._on_flush = on_flush
        self._last_emit = 0.0

    def emit(self, event: ProgressEvent) -> None:
        self._counts.update(event)
        now = time.monotonic()
        if event.kind in _ALWAYS_FLUSH_KINDS or (now - self._last_emit) >= _THROTTLE_SECONDS:
            self._last_emit = now
            self._on_flush(event)


class _BaseWorker(QThread):
    progressed = Signal(object, object)  # (ProgressEvent, RunCounts snapshot)
    finished_run = Signal(object)  # RunResult (SortRunResult | OrganizeRunResult)
    failed = Signal(str)
    cancelled = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.counts = RunCounts()
        self._cancel_token = CancelToken()

    def request_cancel(self) -> None:
        self._cancel_token.cancel()

    def _make_reporter(self) -> _ThrottledSignalReporter:
        return _ThrottledSignalReporter(self.counts, lambda ev: self.progressed.emit(ev, self.counts))

    def _run_pipeline(self, fn, /, **kwargs) -> None:
        reporter = self._make_reporter()
        try:
            result = fn(reporter=reporter, cancel_token=self._cancel_token, **kwargs)
            # Always deliver a final snapshot even if the last real event was throttled.
            self.progressed.emit(ProgressEvent(stage="Done", kind="info"), self.counts)
            self.finished_run.emit(result)
        except PipelineCancelled:
            self.cancelled.emit()
        except Exception as e:  # noqa: BLE001 - surface any pipeline failure to the GUI
            self.failed.emit(str(e))


class SortWorker(_BaseWorker):
    def __init__(self, source: Path, fuji_dest: Path, photos_dest: Path, dry_run: bool, report_path: Path, parent=None) -> None:
        super().__init__(parent)
        self.source = source
        self.fuji_dest = fuji_dest
        self.photos_dest = photos_dest
        self.dry_run = dry_run
        self.report_path = report_path

    def run(self) -> None:
        self._run_pipeline(
            sort_process,
            source=self.source,
            fuji_dest=self.fuji_dest,
            photos_dest=self.photos_dest,
            dry_run=self.dry_run,
            report_path=self.report_path,
        )


class OrganizeWorker(_BaseWorker):
    def __init__(self, root: Path, fuji_root: Path, review: Path, report_path: Path, dry_run: bool, parent=None) -> None:
        super().__init__(parent)
        self.root = root
        self.fuji_root = fuji_root
        self.review = review
        self.report_path = report_path
        self.dry_run = dry_run

    def run(self) -> None:
        self._run_pipeline(
            organize_process,
            root=self.root,
            fuji_root=self.fuji_root,
            review=self.review,
            report_path=self.report_path,
            dry_run=self.dry_run,
        )
