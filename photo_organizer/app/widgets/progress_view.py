"""Shared live-progress panel: stage/status, progress bar, running counts, log tail."""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import CaptionLabel, ListWidget, ProgressBar, StrongBodyLabel

from photo_organizer.app.models import RunCounts
from photo_organizer.engine.progress import ProgressEvent


class ProgressView(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.status_label = CaptionLabel("")
        self.progress_bar = ProgressBar()
        self.progress_bar.setRange(0, 100)

        self.counts_label = StrongBodyLabel("")
        self.log_list = ListWidget()
        self.log_list.setMaximumHeight(220)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(self.status_label)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.counts_label)
        layout.addWidget(self.log_list, 1)

        self.reset()

    def reset(self) -> None:
        self.status_label.setText("")
        self.progress_bar.setValue(0)
        self.counts_label.setText("")
        self.log_list.clear()

    def update_from_event(self, event: ProgressEvent, counts: RunCounts) -> None:
        if counts.total:
            self.progress_bar.setValue(int(100 * counts.current / counts.total))
        self.status_label.setText(f"{counts.stage} — {counts.last_item}" if counts.stage else "")
        self.counts_label.setText(
            f"Fuji: {counts.fuji_moved}   Photos: {counts.photos_moved}   "
            f"Duplicates: {counts.duplicates}   Flagged dates: {counts.flagged_dates}   "
            f"RAF deleted: {counts.raf_deleted}   Errors: {counts.errors}"
        )
        if counts.recent_log:
            self.log_list.clear()
            self.log_list.addItems(counts.recent_log[-200:])
            self.log_list.scrollToBottom()
