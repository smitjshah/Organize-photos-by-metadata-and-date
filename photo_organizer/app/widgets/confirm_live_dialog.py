"""Final confirmation before a live (destructive) run.

Shown only after a dry run has completed (see app.state.DryRunGateState).
Always modal by design -- this is the one deliberate blocking interruption
in the app, since RAF files are permanently deleted and a live run can move
tens of thousands of files.
"""

from __future__ import annotations

from PySide6.QtWidgets import QMessageBox, QWidget


def confirm_live_run(parent: QWidget | None, summary_lines: list[str]) -> bool:
    """Show the confirmation dialog. Returns True only if the user explicitly confirms."""
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Warning)
    box.setWindowTitle("Confirm live run")
    box.setText(
        "This will permanently delete .RAF files (not sent to the Recycle Bin) "
        "and move files on disk based on the preview below."
    )
    box.setInformativeText("\n".join(summary_lines))
    run_btn = box.addButton("Run Live", QMessageBox.ButtonRole.AcceptRole)
    box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
    box.setDefaultButton(run_btn)
    box.exec()
    return box.clickedButton() is run_btn
