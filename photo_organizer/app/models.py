"""GUI-facing view models built up incrementally from ProgressEvent streams."""

from __future__ import annotations

from dataclasses import dataclass, field

from photo_organizer.engine.progress import ProgressEvent


@dataclass
class RunCounts:
    """Running tallies the GUI shows live while a pipeline is in progress."""

    current: int = 0
    total: int = 0
    stage: str = ""
    last_item: str = ""

    fuji_moved: int = 0
    photos_moved: int = 0
    raf_deleted: int = 0
    raf_failed: int = 0
    duplicates: int = 0
    flagged_dates: int = 0
    errors: int = 0
    dirs_removed: int = 0

    recent_log: list[str] = field(default_factory=list)

    def update(self, event: ProgressEvent, max_log: int = 200) -> None:
        if event.kind == "progress":
            self.current, self.total, self.stage = event.current, event.total, event.stage
            if event.item:
                self.last_item = event.item
            return

        if event.kind == "moved":
            category = event.payload.get("category")
            if category == "fuji":
                self.fuji_moved += 1
            else:
                self.photos_moved += 1
            self._log(f"[{'FUJI' if category == 'fuji' else 'PHOT'}] {event.item} -> {event.payload.get('dest', '')}", max_log)
        elif event.kind == "duplicate":
            self.duplicates += 1
            self._log(f"[DUP] {event.item} matches {event.payload.get('matched', '')}", max_log)
        elif event.kind == "raf_deleted":
            self.raf_deleted += 1
        elif event.kind == "raf_failed":
            self.raf_failed += 1
            self._log(f"[RAF ERR] {event.item}: {event.payload.get('reason', '')}", max_log)
        elif event.kind == "flagged_date":
            self.flagged_dates += 1
            self._log(f"[FLAGGED DATE] {event.item}", max_log)
        elif event.kind == "error":
            self.errors += 1
            self._log(f"[ERR] {event.item}: {event.payload.get('reason', '')}", max_log)
        elif event.kind == "dir_removed":
            self.dirs_removed += 1

    def _log(self, line: str, max_log: int) -> None:
        self.recent_log.append(line)
        if len(self.recent_log) > max_log:
            del self.recent_log[: len(self.recent_log) - max_log]
