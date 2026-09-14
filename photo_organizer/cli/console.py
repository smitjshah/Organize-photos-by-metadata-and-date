"""Console rendering for the CLI wrappers: TTY-aware progress bars + a
ProgressReporter implementation that turns engine events into console output,
reproducing the pre-refactor sort_photos.py / organize_v2.py console UX.
"""

from __future__ import annotations

import os
import sys

from photo_organizer.engine.progress import ProgressEvent, ProgressReporter

BAR_LEN = 32
DIVIDER = "=" * 64
THIN_DIV = "-" * 64

IS_TTY = hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


def _supports_colour() -> bool:
    if not IS_TTY:
        return False
    if sys.platform == "win32":
        return bool(os.environ.get("WT_SESSION") or os.environ.get("ANSICON") or os.environ.get("TERM_PROGRAM"))
    return True


USE_COLOUR = _supports_colour()


def _c(text: str, code: str) -> str:
    return f"\033[{code}m{text}\033[0m" if USE_COLOUR else text


def green(t: str) -> str: return _c(t, "32")
def yellow(t: str) -> str: return _c(t, "33")
def red(t: str) -> str: return _c(t, "31")
def bold(t: str) -> str: return _c(t, "1")
def cyan(t: str) -> str: return _c(t, "36")
def dim(t: str) -> str: return _c(t, "2")
def magenta(t: str) -> str: return _c(t, "35")


_NON_TTY_MILESTONES = (0, 10, 25, 50, 75, 90, 100)


class ConsoleUI:
    """Stateful console renderer: progress bars, step headers, plain lines."""

    def __init__(self) -> None:
        self._pb_active = False
        self._pb_last_pct = -1.0

    def progress_bar(self, current: int, total: int, stage: str = "", item: str = "") -> None:
        if total <= 0:
            return
        pct = 100.0 * current / total
        w = len(str(total))

        if IS_TTY:
            filled = int(BAR_LEN * pct / 100)
            bar_str = "█" * filled + "░" * (BAR_LEN - filled)
            bar_col = (green if current >= total else yellow)(bar_str) if USE_COLOUR else bar_str
            item_tr = (item[:36] + "…") if len(item) > 37 else item
            item_part = dim(f"  {item_tr}") if item_tr else ""
            stage_col = cyan(f"{stage:<28}") if stage else " " * 28
            count = f"{current:>{w}}/{total}"
            sys.stdout.write(f"\r  {stage_col} [{bar_col}] {pct:5.1f}%  {count}{item_part}   ")
            sys.stdout.flush()
            self._pb_active = True
            if current >= total:
                sys.stdout.write("\n")
                sys.stdout.flush()
                self._pb_active = False
                self._pb_last_pct = -1.0
        else:
            for m in _NON_TTY_MILESTONES:
                if self._pb_last_pct < m <= pct:
                    print(f"  {stage:<28}  {pct:5.1f}%  ({current:>{w}}/{total})")
                    sys.stdout.flush()
                    self._pb_last_pct = pct
                    break
            if current >= total and self._pb_last_pct < 100.0:
                print(f"  {stage:<28}  100.0%  ({total}/{total})")
                sys.stdout.flush()
                self._pb_last_pct = -1.0

    def pb_clear(self) -> None:
        if self._pb_active and IS_TTY:
            sys.stdout.write("\r" + " " * 120 + "\r")
            sys.stdout.flush()
            self._pb_active = False

    def print_step(self, label: str) -> None:
        self.pb_clear()
        print(f"\n{bold(DIVIDER)}")
        print(f"  {bold(label)}")
        print(bold(DIVIDER))

    def pprint(self, text: str = "") -> None:
        self.pb_clear()
        print(text)


class ConsoleReporter(ProgressReporter):
    """Translates engine ProgressEvents into console output via a ConsoleUI."""

    def __init__(self, ui: ConsoleUI | None = None) -> None:
        self.ui = ui or ConsoleUI()
        self._last_stage: str | None = None

    def _maybe_print_step(self, stage: str) -> None:
        if stage != self._last_stage:
            self.ui.print_step(stage)
            self._last_stage = stage

    def emit(self, event: ProgressEvent) -> None:
        ui = self.ui

        if event.kind == "progress":
            self._maybe_print_step(event.stage)
            ui.progress_bar(event.current, event.total, stage=event.stage, item=event.item or "")
            return

        if event.kind == "info":
            self._maybe_print_step(event.stage)
            return

        if event.kind == "moved":
            category = event.payload.get("category", "")
            tag = cyan("[FUJI]") if category == "fuji" else green("[PHOT]")
            fall = f"  {yellow('← filesystem date')}" if event.payload.get("date_source") == "filesystem" else ""
            ui.pprint(f"  {tag}  {event.item}")
            ui.pprint(f"         → {event.payload.get('dest', '')}{fall}")
            return

        if event.kind == "duplicate":
            ui.pprint(f"  {yellow('[DUP]')}  {event.item}")
            ui.pprint(f"         matched → {dim(str(event.payload.get('matched', '')))}")
            return

        if event.kind == "raf_deleted":
            ui.pprint(f"  {red('[RAF DEL]')}  {event.item}")
            return

        if event.kind == "raf_failed":
            ui.pprint(f"  {red('[RAF ERR]')}  {event.item}: {event.payload.get('reason', '')}")
            return

        if event.kind == "flagged_date":
            ui.pprint(f"  {magenta('[FLAGGED DATE]')}  {event.item}")
            return

        if event.kind == "dir_removed":
            ui.pprint(f"  {dim('[RMDIR]')}  {event.item}")
            return

        if event.kind == "error":
            ui.pprint(f"  {red('[ERR]')}  {event.item}: {event.payload.get('reason', '')}")
            return
