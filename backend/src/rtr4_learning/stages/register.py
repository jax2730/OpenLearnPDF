"""Register a PDF source without copying it into generated artifacts."""

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path

from pypdf import PdfReader

from rtr4_learning.models import BookManifest, ChapterManifest
from rtr4_learning.paths import book_manifest_path, validate_book_id

_CHAPTER_PATTERN = re.compile(
    r"^(?P<id>[A-Za-z0-9][A-Za-z0-9._-]*):(?P<start>[1-9]\d*)-(?P<end>[1-9]\d*)$"
)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parse_chapter(value: str, page_count: int) -> ChapterManifest:
    match = _CHAPTER_PATTERN.fullmatch(value)
    if match is None:
        raise ValueError("chapter must use ID:START-END format")
    start_page = int(match["start"])
    end_page = int(match["end"])
    if start_page > end_page:
        raise ValueError("chapter start page must be <= end page")
    if end_page > page_count:
        raise ValueError("chapter end page exceeds PDF page_count")
    chapter_id = match["id"]
    return ChapterManifest(
        id=chapter_id,
        title=chapter_id,
        start_page=start_page,
        end_page=end_page,
    )


def _write_manifest_atomically(path: Path, manifest: BookManifest) -> None:
    payload = json.dumps(
        manifest.model_dump(mode="json"),
        ensure_ascii=False,
        indent=2,
    ).encode("utf-8") + b"\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=path.parent, prefix=f".{path.name}.", delete=False
        ) as temporary:
            temporary.write(payload)
            temporary.flush()
            os.fsync(temporary.fileno())
            temporary_path = Path(temporary.name)
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def register_book(
    *,
    book_id: str,
    pdf_path: Path | str,
    chapter: str,
    data_root: Path | str,
    title: str | None = None,
) -> BookManifest:
    """Write deterministic source identity and chapter metadata."""
    validate_book_id(book_id)
    canonical_pdf_path = Path(pdf_path).resolve(strict=True)
    if not canonical_pdf_path.is_file():
        raise ValueError("pdf_path must be a file")
    page_count = len(PdfReader(canonical_pdf_path).pages)
    manifest = BookManifest(
        id=book_id,
        title=title if title is not None else book_id,
        source_path=str(canonical_pdf_path),
        source_sha256=_sha256_file(canonical_pdf_path),
        page_count=page_count,
        chapters=(_parse_chapter(chapter, page_count),),
    )
    _write_manifest_atomically(book_manifest_path(data_root, book_id), manifest)
    return manifest
