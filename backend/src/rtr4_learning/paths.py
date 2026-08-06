"""Safe paths for generated book artifacts."""

import re
from pathlib import Path

_BOOK_ID_PATTERN = re.compile(r"^[a-z0-9]+(?:[-_][a-z0-9]+)*$")


def validate_book_id(book_id: str) -> str:
    """Return a stable artifact slug or reject unsafe path input."""
    if not _BOOK_ID_PATTERN.fullmatch(book_id):
        raise ValueError(
            "book_id must be a lowercase slug containing letters, digits, '-' or '_'"
        )
    return book_id


def book_artifact_dir(data_root: Path | str, book_id: str) -> Path:
    root = Path(data_root).resolve()
    artifact_dir = (root / "books" / validate_book_id(book_id)).resolve()
    if not artifact_dir.is_relative_to(root):
        raise ValueError("book_id resolves outside data_root")
    return artifact_dir


def book_manifest_path(data_root: Path | str, book_id: str) -> Path:
    return book_artifact_dir(data_root, book_id) / "book.json"
