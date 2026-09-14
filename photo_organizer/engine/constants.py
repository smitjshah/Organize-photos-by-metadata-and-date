"""Shared constants for the photo-organizer engine."""

PHOTO_EXTS = {
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".tif",
    ".heic", ".heif", ".raw", ".cr2", ".nef", ".arw", ".dng",
    ".webp", ".mp4", ".mov", ".avi", ".mkv", ".3gp",
}

RAF_EXT = ".raf"

# Top-level folder names organize_pipeline never descends into (destinations + system).
SKIP_TOP = {"review", "fuji", ".claude"}

# Windows MAX_PATH classic limit; paths at/above this are flagged rather than attempted.
MAX_PATH_WINDOWS = 260
