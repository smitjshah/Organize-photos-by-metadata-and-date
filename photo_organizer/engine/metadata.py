"""EXIF / filename / filesystem date and camera-make extraction.

Consolidates the logic that used to be duplicated verbatim between
sort_photos.py and organize_v2.py.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from pathlib import Path

try:
    import exifread
    import logging
    logging.getLogger("exifread").setLevel(logging.CRITICAL)
    HAS_EXIFREAD = True
except ImportError:
    HAS_EXIFREAD = False

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

_PIL_EXTS = {".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".png"}

_DT_FORMATS = ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S")

_FILENAME_DATE_PATTERNS = (
    r"(\d{4})[-_](\d{2})[-_](\d{2})",
    r"(\d{4})(\d{2})(\d{2})",
)


def _parse_dt(s: str) -> datetime | None:
    for fmt in _DT_FORMATS:
        try:
            return datetime.strptime(s.strip(), fmt)
        except ValueError:
            pass
    return None


def _exif_via_exifread(path: Path) -> tuple[datetime | None, str | None]:
    if not HAS_EXIFREAD:
        return None, None
    try:
        with open(path, "rb") as f:
            tags = exifread.process_file(f, details=False)
        dt = None
        for key in ("EXIF DateTimeOriginal", "EXIF DateTimeDigitized", "Image DateTime"):
            if key in tags:
                dt = _parse_dt(str(tags[key]))
                if dt:
                    break
        make = str(tags["Image Make"]).strip() if "Image Make" in tags else None
        return dt, make
    except Exception:
        return None, None


def _exif_via_pil(path: Path) -> tuple[datetime | None, str | None]:
    if not HAS_PIL:
        return None, None
    try:
        img = Image.open(path)
        raw = img._getexif()
        if not raw:
            return None, None
        dt = None
        for tag_id in (36867, 36868, 306):
            val = raw.get(tag_id)
            if val:
                dt = _parse_dt(val)
                if dt:
                    break
        make = (raw.get(271) or "").strip() or None
        return dt, make
    except Exception:
        return None, None


def _date_from_filename(name: str) -> datetime | None:
    for pat in _FILENAME_DATE_PATTERNS:
        m = re.search(pat, name)
        if m:
            try:
                y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
                if 1990 <= y <= 2100 and 1 <= mo <= 12 and 1 <= d <= 31:
                    return datetime(y, mo, d)
            except ValueError:
                pass
    return None


def _fs_date(path: Path) -> datetime:
    st = path.stat()
    return min(datetime.fromtimestamp(st.st_ctime), datetime.fromtimestamp(st.st_mtime))


def get_metadata(path: Path) -> tuple[datetime, str, str | None]:
    """Return (datetime, date_source, make_or_None).

    date_source is one of: "EXIF", "EXIF(PIL)", "filename", "filesystem".
    """
    dt, make = _exif_via_exifread(path)
    if dt:
        return dt, "EXIF", make

    if path.suffix.lower() in _PIL_EXTS:
        dt2, make2 = _exif_via_pil(path)
        if dt2:
            return dt2, "EXIF(PIL)", make2 or make

    dt3 = _date_from_filename(path.name)
    if dt3:
        return dt3, "filename", make

    return _fs_date(path), "filesystem", make


def is_fuji(make: str | None) -> bool:
    return bool(make and "fuji" in make.lower())


def is_suspicious_date(dt: datetime, date_source: str, path: Path) -> bool:
    """Flag implausible filename-parsed dates (e.g. Snapchat-2080090122.mp4).

    Only filename-sourced dates are checked -- EXIF/filesystem dates are
    trusted. A photo can never have been taken in the future, so the only
    reliable signal is "this date hasn't happened yet" (small buffer for
    clock skew). Comparing against the file's own filesystem mtime was
    considered and rejected: copying/importing an old archive today gives
    every file a recent mtime regardless of how old the photo actually is,
    so that comparison flags huge numbers of perfectly legitimate files.
    """
    if date_source != "filename":
        return False
    return dt > datetime.now() + timedelta(days=1)
