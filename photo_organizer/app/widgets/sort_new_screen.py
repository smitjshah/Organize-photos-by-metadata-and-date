"""Sort New Photos screen — the ongoing-use flow (wraps sort_pipeline)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import (
    CardWidget,
    FluentIcon,
    InfoBar,
    InfoBarPosition,
    PrimaryPushButton,
    PushButton,
    SubtitleLabel,
    ToolTipFilter,
)

from photo_organizer.app.state import DryRunGateState
from photo_organizer.app.widgets.confirm_live_dialog import confirm_live_run
from photo_organizer.app.widgets.folder_picker import FolderPickerRow
from photo_organizer.app.widgets.progress_view import ProgressView
from photo_organizer.app.widgets.summary_view import SummaryView
from photo_organizer.app.workers import SortWorker
from photo_organizer.engine.progress import ProgressEvent


class SortNewPhotosScreen(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("sortNewPhotosScreen")

        title = SubtitleLabel("Sort New Photos")

        self.source_row = FolderPickerRow("Source", settings_key="sort_new/source_path")
        self.fuji_row = FolderPickerRow("Fuji destination", settings_key="sort_new/fuji_path")
        self.photos_row = FolderPickerRow("Photos destination", settings_key="sort_new/photos_path")

        picker_card = CardWidget()
        picker_layout = QVBoxLayout(picker_card)
        picker_layout.setSpacing(14)
        picker_layout.addWidget(self.source_row)
        picker_layout.addWidget(self.fuji_row)
        picker_layout.addWidget(self.photos_row)

        self.dry_run_btn = PrimaryPushButton(FluentIcon.SYNC, "Dry Run")
        self.live_btn = PushButton(FluentIcon.PLAY, "Run Live")
        self.live_btn.setEnabled(False)
        self.live_btn.installEventFilter(ToolTipFilter(self.live_btn, showDelay=300))
        self.cancel_btn = PushButton(FluentIcon.CANCEL, "Cancel")
        self.cancel_btn.setVisible(False)

        btn_row = QHBoxLayout()
        btn_row.addWidget(self.dry_run_btn)
        btn_row.addWidget(self.live_btn)
        btn_row.addWidget(self.cancel_btn)
        btn_row.addStretch(1)

        self.progress_view = ProgressView()
        self.summary_view = SummaryView()

        result_card = CardWidget()
        result_layout = QVBoxLayout(result_card)
        result_layout.addWidget(self.progress_view)
        result_layout.addWidget(self.summary_view)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        layout.addWidget(title)
        layout.addWidget(picker_card)
        layout.addLayout(btn_row)
        layout.addWidget(result_card, 1)

        self.dry_run_btn.clicked.connect(lambda: self._start_run(dry_run=True))
        self.live_btn.clicked.connect(self._confirm_and_run_live)
        self.cancel_btn.clicked.connect(self._cancel_run)
        for row in (self.source_row, self.fuji_row, self.photos_row):
            row.pathChanged.connect(self._on_paths_changed)

        self._worker: SortWorker | None = None
        self._gate = DryRunGateState()
        self._last_result = None
        self._refresh_gate_ui()

    def _current_paths(self) -> tuple[Path | None, Path | None, Path | None]:
        return (self.source_row.path(), self.fuji_row.path(), self.photos_row.path())

    def _on_paths_changed(self) -> None:
        self._gate.on_paths_changed()
        self._refresh_gate_ui()

    def _refresh_gate_ui(self) -> None:
        self.live_btn.setEnabled(self._gate.live_enabled)
        self.live_btn.setToolTip("" if self._gate.live_enabled else "Run a dry run first to preview changes before running live")
        self.dry_run_btn.setEnabled(self._gate.controls_enabled)
        for row in (self.source_row, self.fuji_row, self.photos_row):
            row.set_enabled_all(self._gate.controls_enabled)
        self.cancel_btn.setVisible(not self._gate.controls_enabled)

    def _confirm_and_run_live(self) -> None:
        paths = self._current_paths()
        if not self._gate.can_start_live(paths):
            self._on_paths_changed()
            return

        summary_lines: list[str] = []
        if self._last_result is not None:
            r = self._last_result
            summary_lines = [
                f"Files to move: {len(r.fuji_moved) + len(r.photos_moved)} "
                f"(Fuji: {len(r.fuji_moved)}, Photos: {len(r.photos_moved)})",
                f".RAF files that will be permanently deleted: {len(r.raf_deleted)}",
                f"Duplicates that will move to review/: {len(r.duplicates)}",
                f"Flagged (implausible) dates: {len(r.flagged_dates)}",
            ]
        if confirm_live_run(self, summary_lines):
            self._start_run(dry_run=False)

    def _start_run(self, dry_run: bool) -> None:
        source, fuji, photos = self._current_paths()
        if not (source and fuji and photos):
            InfoBar.warning(
                title="Missing folders",
                content="Please select Source, Fuji dest, and Photos dest.",
                parent=self,
                position=InfoBarPosition.TOP,
                duration=4000,
            )
            return

        self.progress_view.reset()
        self.summary_view.clear()
        self._gate.start_dry_run() if dry_run else self._gate.start_live_run()
        self._refresh_gate_ui()

        report_path = source / "sort_report.txt"
        self._worker = SortWorker(source, fuji, photos, dry_run, report_path)
        self._worker.progressed.connect(self.progress_view.update_from_event)
        self._worker.finished_run.connect(lambda result: self._on_finished(result, dry_run, source, fuji, photos, report_path))
        self._worker.failed.connect(lambda msg: self._on_failed(msg, dry_run))
        self._worker.cancelled.connect(lambda: self._on_cancelled(dry_run))
        self._worker.start()

    def _cancel_run(self) -> None:
        if self._worker:
            self._worker.request_cancel()

    def _on_finished(self, result, dry_run: bool, source: Path, fuji: Path, photos: Path, report_path: Path) -> None:
        self._last_result = result
        if dry_run:
            self._gate.dry_run_finished(self._current_paths())
        else:
            self._gate.live_run_finished()
        self._refresh_gate_ui()

        self.summary_view.show_summary(
            [
                f"Fuji moved: {len(result.fuji_moved)}",
                f"Photos moved: {len(result.photos_moved)}",
                f"Duplicates: {len(result.duplicates)}",
                f"Flagged dates: {len(result.flagged_dates)}",
                f"RAF deleted: {len(result.raf_deleted)}",
                f"Errors: {len(result.errors)}",
            ],
            report_path=report_path,
            open_folders={"Fuji Folder": fuji, "Photos Folder": photos},
        )

    def _on_failed(self, message: str, dry_run: bool) -> None:
        self._gate.dry_run_aborted() if dry_run else self._gate.live_run_aborted()
        self._refresh_gate_ui()
        InfoBar.error(title="Run failed", content=message, parent=self, position=InfoBarPosition.TOP, duration=6000)

    def _on_cancelled(self, dry_run: bool) -> None:
        self._gate.dry_run_aborted() if dry_run else self._gate.live_run_aborted()
        self._refresh_gate_ui()
        InfoBar.info(
            title="Cancelled",
            content="Run a fresh dry run before retrying.",
            parent=self,
            position=InfoBarPosition.TOP,
            duration=4000,
        )
