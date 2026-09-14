"""Plain-text report builders for both flows."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


def _section(title: str) -> list[str]:
    return ["", "=" * 64, f"  {title}", "=" * 64]


@dataclass
class SortRunResult:
    dry_run: bool
    source: Path
    fuji_dest: Path
    photos_dest: Path
    raf_deleted: list[str] = field(default_factory=list)
    raf_failed: list[tuple[str, str]] = field(default_factory=list)
    fuji_moved: list[tuple[str, str, str]] = field(default_factory=list)
    fuji_fallback: list[tuple[str, str]] = field(default_factory=list)
    fuji_new_dirs: list[str] = field(default_factory=list)
    photos_moved: list[tuple[str, str, str]] = field(default_factory=list)
    photos_fallback: list[tuple[str, str]] = field(default_factory=list)
    photos_new_dirs: list[str] = field(default_factory=list)
    duplicates: list[tuple[str, str]] = field(default_factory=list)
    errors: list[tuple[str, str]] = field(default_factory=list)
    source_leftovers: list[str] = field(default_factory=list)
    flagged_dates: list[tuple[str, str, str]] = field(default_factory=list)  # name, dest, parsed date

    @property
    def total_moved(self) -> int:
        return len(self.fuji_moved) + len(self.photos_moved)


def build_sort_report(r: SortRunResult) -> str:
    lines = [
        f"SORT PHOTOS REPORT  ({'DRY RUN' if r.dry_run else 'LIVE'})",
        f"Run       : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Source    : {r.source}",
        f"Fuji dest : {r.fuji_dest}",
        f"Photos dst: {r.photos_dest}",
    ]

    lines += _section("RAF DELETION")
    lines += [f"  Deleted : {len(r.raf_deleted)}", f"  Failed  : {len(r.raf_failed)}"]
    for p in r.raf_deleted:
        lines.append(f"    [DEL] {p}")
    for p, reason in r.raf_failed:
        lines.append(f"    [ERR] {p}: {reason}")

    lines += _section(f"FUJI DESTINATION  [{r.fuji_dest}]")
    lines += [
        f"  Files moved       : {len(r.fuji_moved)}",
        f"  New subfolders    : {len(r.fuji_new_dirs)}",
        f"  Filesystem fallbk : {len(r.fuji_fallback)}",
    ]
    if r.fuji_new_dirs:
        lines.append("  -- New subfolders --")
        lines += [f"    {d}" for d in r.fuji_new_dirs]
    if r.fuji_fallback:
        lines.append("  -- Fallback (filesystem date used) --")
        lines += [f"    {name}  ->  {dest}" for name, dest in r.fuji_fallback]
    if r.fuji_moved:
        lines.append("  -- Files moved --")
        lines += [f"    {name}  ->  {dest}" for name, _, dest in r.fuji_moved]

    lines += _section(f"PHOTOS DESTINATION  [{r.photos_dest}]")
    lines += [
        f"  Files moved       : {len(r.photos_moved)}",
        f"  New subfolders    : {len(r.photos_new_dirs)}",
        f"  Filesystem fallbk : {len(r.photos_fallback)}",
    ]
    if r.photos_new_dirs:
        lines.append("  -- New subfolders --")
        lines += [f"    {d}" for d in r.photos_new_dirs]
    if r.photos_fallback:
        lines.append("  -- Fallback (filesystem date used) --")
        lines += [f"    {name}  ->  {dest}" for name, dest in r.photos_fallback]
    if r.photos_moved:
        lines.append("  -- Files moved --")
        lines += [f"    {name}  ->  {dest}" for name, _, dest in r.photos_moved]

    lines += _section("DUPLICATES  [SOURCE/review/]")
    lines.append(f"  Total skipped : {len(r.duplicates)}")
    for src_name, existing in r.duplicates:
        lines.append(f"    {src_name}  =>  matched: {existing}")

    lines += _section("FLAGGED DATES  (filename-parsed date looks implausible)")
    lines.append(f"  Total flagged : {len(r.flagged_dates)}")
    for name, dest, parsed in r.flagged_dates:
        lines.append(f"    {name}  ->  {dest}  (parsed date: {parsed})")

    lines += _section("SOURCE VERIFICATION")
    if r.source_leftovers:
        lines.append(f"  WARNING — {len(r.source_leftovers)} unprocessed file(s) remain in SOURCE root:")
        lines += [f"    {f}" for f in r.source_leftovers]
    else:
        lines.append("  OK — SOURCE root is clear")

    lines += _section("ERRORS")
    lines.append(f"  Total : {len(r.errors)}")
    for name, reason in r.errors:
        lines.append(f"    {name}: {reason}")

    return "\n".join(lines)


@dataclass
class OrganizeRunResult:
    dry_run: bool
    root: Path
    raf_deleted: list[str] = field(default_factory=list)
    raf_failed: list[tuple[str, str]] = field(default_factory=list)
    fuji_ok: list[tuple[str, str]] = field(default_factory=list)
    fuji_fallback: list[tuple[str, str]] = field(default_factory=list)
    fuji_dup: list[tuple[str, str]] = field(default_factory=list)
    other_ok: list[tuple[str, str]] = field(default_factory=list)
    other_fallback: list[tuple[str, str]] = field(default_factory=list)
    other_dup: list[tuple[str, str]] = field(default_factory=list)
    removed_dirs: list[str] = field(default_factory=list)
    errors: list[tuple[str, str]] = field(default_factory=list)
    dir_errors: list[tuple[str, str]] = field(default_factory=list)
    flagged_dates: list[tuple[str, str, str]] = field(default_factory=list)

    @property
    def total_moved(self) -> int:
        return len(self.fuji_ok) + len(self.fuji_fallback) + len(self.other_ok) + len(self.other_fallback)


def build_organize_report(r: OrganizeRunResult) -> str:
    mode = "DRY RUN" if r.dry_run else "LIVE"
    lines = [
        f"ORGANIZE V2 REPORT — {mode}",
        f"Run : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Root: {r.root}",
    ]

    lines += _section("RAF DELETION")
    lines += [f"  Deleted : {len(r.raf_deleted)}", f"  Failed  : {len(r.raf_failed)}", ""]
    lines += [f"  [DEL] {p}" for p in r.raf_deleted]
    lines += [f"  [ERR] {p}: {reason}" for p, reason in r.raf_failed]

    lines += _section("FUJIFILM FILES  →  /Fuji/YYYY/MM/")
    lines += [
        f"  Moved OK          : {len(r.fuji_ok)}",
        f"  Fallback date     : {len(r.fuji_fallback)}",
        f"  Duplicates/review : {len(r.fuji_dup)}",
        "",
    ]
    if r.fuji_fallback:
        lines.append("  -- Fallback (filesystem date) --")
        lines += [f"    {name}  ->  {dest}" for name, dest in r.fuji_fallback]
    if r.fuji_dup:
        lines.append("  -- Duplicates -> /review/ --")
        lines += [f"    {name}  ->  {dest}" for name, dest in r.fuji_dup]

    lines += _section("ALL OTHER FILES  →  /YYYY/MM/")
    lines += [
        f"  Moved OK          : {len(r.other_ok)}",
        f"  Fallback date     : {len(r.other_fallback)}",
        f"  Duplicates/review : {len(r.other_dup)}",
        "",
    ]
    if r.other_fallback:
        lines.append("  -- Fallback (filesystem date) --")
        lines += [f"    {name}  ->  {dest}" for name, dest in r.other_fallback[:500]]
        if len(r.other_fallback) > 500:
            lines.append(f"    ... and {len(r.other_fallback) - 500} more")
    if r.other_dup:
        lines.append("  -- Duplicates -> /review/ --")
        lines += [f"    {name}  ->  {dest}" for name, dest in r.other_dup[:200]]
        if len(r.other_dup) > 200:
            lines.append(f"    ... and {len(r.other_dup) - 200} more")

    lines += _section("FLAGGED DATES  (filename-parsed date looks implausible)")
    lines.append(f"  Total flagged : {len(r.flagged_dates)}")
    for name, dest, parsed in r.flagged_dates:
        lines.append(f"    {name}  ->  {dest}  (parsed date: {parsed})")

    lines += _section("EMPTY FOLDER CLEANUP")
    lines += [f"  Removed : {len(r.removed_dirs)}", ""]
    lines += [f"  {d}" for d in r.removed_dirs]

    lines += _section("ERRORS")
    lines += [f"  Count: {len(r.errors) + len(r.raf_failed) + len(r.dir_errors)}", ""]
    lines += [f"  [FILE] {f}: {reason}" for f, reason in r.errors]
    lines += [f"  [DIR]  {d}: {reason}" for d, reason in r.dir_errors]

    return "\n".join(lines)
