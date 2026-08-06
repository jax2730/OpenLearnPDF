"""Safe paths for generated book artifacts."""

import re
from pathlib import Path

_BOOK_ID_PATTERN = re.compile(r"^[a-z0-9]+(?:[-_][a-z0-9]+)*$")
_WINDOWS_RESERVED_NAMES = {
    "con",
    "prn",
    "aux",
    "nul",
    *(f"com{number}" for number in range(1, 10)),
    *(f"lpt{number}" for number in range(1, 10)),
}


def validate_book_id(book_id: str) -> str:
    """Return a stable artifact slug or reject unsafe path input."""
    windows_basename = book_id.split(".", maxsplit=1)[0].rstrip(" .").casefold()
    if windows_basename in _WINDOWS_RESERVED_NAMES:
        raise ValueError("book_id uses a Windows reserved basename")
    if not _BOOK_ID_PATTERN.fullmatch(book_id):
        raise ValueError(
            "book_id must be a lowercase slug containing letters, digits, '-' or '_'"
        )
    return book_id


def book_artifact_dir(data_root: Path | str, book_id: str) -> Path:
    root = Path(data_root).resolve()
    artifact_dir = root / "books" / validate_book_id(book_id)
    if not artifact_dir.is_relative_to(root):
        raise ValueError("book_id resolves outside data_root")
    return artifact_dir


def book_manifest_path(data_root: Path | str, book_id: str) -> Path:
    return book_artifact_dir(data_root, book_id) / "book.json"
