"""Safe paths for generated book artifacts."""

import os
import re
import stat
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


def _is_link_or_reparse_point(path: Path) -> bool:
    if path.is_symlink():
        return True
    is_junction = getattr(path, "is_junction", None)
    if is_junction is not None and is_junction():
        return True
    try:
        attributes = getattr(path.lstat(), "st_file_attributes", 0)
    except FileNotFoundError:
        return False
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return bool(attributes & reparse_flag)


def _comparison_path(path: Path) -> str:
    value = os.path.normcase(os.path.abspath(path))
    if value.startswith("\\\\?\\unc\\"):
        return "\\\\" + value[8:]
    if value.startswith("\\\\?\\"):
        return value[4:]
    return value


def _ensure_contained(root: Path, candidate: Path) -> None:
    canonical_candidate = candidate.resolve(strict=False)
    root_value = _comparison_path(root)
    candidate_value = _comparison_path(canonical_candidate)
    try:
        common_path = os.path.commonpath((root_value, candidate_value))
    except ValueError as error:
        raise ValueError("book artifact path resolves outside data_root") from error
    if common_path != root_value:
        raise ValueError("book artifact path resolves outside data_root")


def book_artifact_dir(data_root: Path | str, book_id: str) -> Path:
    root = Path(data_root).resolve()
    books_dir = root / "books"
    artifact_dir = books_dir / validate_book_id(book_id)
    for component in (books_dir, artifact_dir):
        if _is_link_or_reparse_point(component):
            raise ValueError(
                f"book artifact path contains a symlink, junction or reparse point: {component}"
            )
    _ensure_contained(root, artifact_dir)
    return artifact_dir


def book_manifest_path(data_root: Path | str, book_id: str) -> Path:
    return book_artifact_dir(data_root, book_id) / "book.json"
