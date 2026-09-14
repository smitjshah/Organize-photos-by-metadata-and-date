"""Sort From Scratch screen — the one-time bulk-reorganize flow (wraps organize_pipeline)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import (
    CaptionLabel,
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
from photo_organizer.app.workers import OrganizeWorker


class SortFromScratchScreen(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("sortFromScratchScreen")

        title = SubtitleLabel("Sort From Scratch")

        self.root_row = FolderPickerRow("Root", settings_key="sort_scratch/root_path")
        self.derived_label = CaptionLabel("")
        self.derived_label.setWordWrap(True)
        self.root_row.pathChanged.connect(self._update_derived_label)

        picker_card = CardWidget()
        picker_layout = QVBoxLayout(picker_card)
        picker_layout.setSpacing(10)
        picker_layout.addWidget(self.root_row)
        picker_layout.addWidget(self.derived_label)

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
        self.root_row.pathChanged.connect(self._on_paths_changed)

        self._worker: OrganizeWorker | None = None
        self._gate = DryRunGateState()
        self._last_result = None
        self._update_derived_label()
        self._refresh_gate_ui()

    def _derived_paths(self, root: Path) -> tuple[Path, Path, Path]:
        return root / "Fuji", root / "review", root / "organize_v2_report.txt"

    def _update_derived_label(self) -> None:
        root = self.root_row.path()
        if root is None:
            self.derived_label.setText("")
            return
        fuji_root, review, report_path = self._derived_paths(root)
        self.derived_label.setText(f"Fuji: {fuji_root}\nReview: {review}\nReport: {report_path}")

    def _current_paths(self) -> tuple[Path | None]:
        return (self.root_row.path(),)

    def _on_paths_changed(self) -> None:
        self._update_derived_label()
        self._gate.on_paths_changed()
        self._refresh_gate_ui()

    def _refresh_gate_ui(self) -> None:
        self.live_btn.setEnabled(self._gate.live_enabled)
        self.live_btn.setToolTip("" if self._gate.live_enabled else "Run a dry run first to preview changes before running live")
        self.dry_run_btn.setEnabled(self._gate.controls_enabled)
        self.root_row.set_enabled_all(self._gate.controls_enabled)
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
                f"Files to move: {r.total_moved} (Fuji: {len(r.fuji_ok) + len(r.fuji_fallback)}, "
                f"Other: {len(r.other_ok) + len(r.other_fallback)})",
                f".RAF files that will be permanently deleted: {len(r.raf_deleted)}",
                f"Duplicates that will move to review/: {len(r.fuji_dup) + len(r.other_dup)}",
                f"Flagged (implausible) dates: {len(r.flagged_dates)}",
            ]
        if confirm_live_run(self, summary_lines):
            self._start_run(dry_run=False)

    def _start_run(self, dry_run: bool) -> None:
        root = self.root_row.path()
        if not root:
            InfoBar.warning(
                title="Missing folder",
                content="Please select a Root folder.",
                parent=self,
                position=InfoBarPosition.TOP,
                duration=4000,
            )
            return

        fuji_root, review, report_path = self._derived_paths(root)

        self.progress_view.reset()
        self.summary_view.clear()
        self._gate.start_dry_run() if dry_run else self._gate.start_live_run()
        self._refresh_gate_ui()

        self._worker = OrganizeWorker(root, fuji_root, review, report_path, dry_run)
        self._worker.progressed.connect(self.progress_view.update_from_event)
        self._worker.finished_run.connect(lambda result: self._on_finished(result, dry_run, root, fuji_root, report_path))
        self._worker.failed.connect(lambda msg: self._on_failed(msg, dry_run))
        self._worker.cancelled.connect(lambda: self._on_cancelled(dry_run))
        self._worker.start()

    def _cancel_run(self) -> None:
        if self._worker:
            self._worker.request_cancel()

    def _on_finished(self, result, dry_run: bool, root: Path, fuji_root: Path, report_path: Path) -> None:
        self._last_result = result
        if dry_run:
            self._gate.dry_run_finished(self._current_paths())
        else:
            self._gate.live_run_finished()
        self._refresh_gate_ui()

        self.summary_view.show_summary(
            [
                f"Fuji moved: {len(result.fuji_ok) + len(result.fuji_fallback)}",
                f"Other moved: {len(result.other_ok) + len(result.other_fallback)}",
                f"Duplicates: {len(result.fuji_dup) + len(result.other_dup)}",
                f"Flagged dates: {len(result.flagged_dates)}",
                f"RAF deleted: {len(result.raf_deleted)}",
                f"Empty dirs removed: {len(result.removed_dirs)}",
                f"Errors: {len(result.errors)}",
            ],
            report_path=report_path,
            open_folders={"Root Folder": root, "Fuji Folder": fuji_root},
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
