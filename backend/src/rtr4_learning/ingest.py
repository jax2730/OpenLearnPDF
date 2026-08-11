"""Materialize normalized, validated and indexed MinerU slice artifacts."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import portalocker
from pypdf import PdfReader

from rtr4_learning.index import HashEmbeddingProvider, SearchIndex
from rtr4_learning.models import BookManifest, PageDocument
from rtr4_learning.normalize import (
    normalize_mineru_content_list,
    normalized_pages_json,
)
from rtr4_learning.paths import book_artifact_dir, book_manifest_path
from rtr4_learning.relations import link_relations
from rtr4_learning.validate import ValidationIssue, validate_pages

_LOCK_TIMEOUT_SECONDS = 30.0
_LOCK_CHECK_INTERVAL_SECONDS = 0.02


@dataclass(frozen=True, slots=True)
class SliceBuildResult:
    pages: tuple[PageDocument, ...]
    validation_issues: tuple[ValidationIssue, ...]
    normalized_path: Path
    validation_path: Path
    index_path: Path


def _file_identity(metadata: object) -> tuple[int, ...]:
    return tuple(
        int(getattr(metadata, name))
        for name in (
            "st_dev",
            "st_ino",
            "st_mode",
            "st_size",
            "st_mtime_ns",
            "st_ctime_ns",
        )
    )


@contextmanager
def _book_lock(book_root: Path) -> Iterator[None]:
    lock_path = book_root / ".ingest.lock"
    try:
        with portalocker.Lock(
            lock_path,
            mode="a+b",
            timeout=_LOCK_TIMEOUT_SECONDS,
            check_interval=_LOCK_CHECK_INTERVAL_SECONDS,
        ):
            yield
    except portalocker.exceptions.LockException as error:
        raise ValueError(
            f"timed out waiting for book ingest lock: {lock_path}"
        ) from error


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    temp_path = Path(temp_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)


def _verified_page_sizes(
    manifest: BookManifest, first_page: int, count: int
) -> dict[int, tuple[float, float]]:
    if first_page <= 0 or count <= 0:
        raise ValueError("MinerU slice page range must be positive and non-empty")
    last_page = first_page + count - 1
    if last_page > manifest.page_count:
        raise ValueError("MinerU slice exceeds registered PDF page count")
    source_path = Path(manifest.source_path)
    with source_path.open("rb") as source:
        before = os.fstat(source.fileno())
        digest = hashlib.sha256()
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
        if digest.hexdigest() != manifest.source_sha256:
            raise ValueError("registered PDF SHA-256 does not match current source")
        if _file_identity(os.fstat(source.fileno())) != _file_identity(before):
            raise ValueError("registered PDF changed during verification")
        source.seek(0)
        reader = PdfReader(source)
        sizes = {
            page_number: (
                float(reader.pages[page_number - 1].mediabox.width),
                float(reader.pages[page_number - 1].mediabox.height),
            )
            for page_number in range(first_page, last_page + 1)
        }
        if _file_identity(os.fstat(source.fileno())) != _file_identity(before):
            raise ValueError("registered PDF changed while reading page sizes")
    return sizes


def _validate_probe(
    raw_path: Path,
    manifest: BookManifest,
    first_page: int,
    parser_version: str,
) -> tuple[bytes, list[int]]:
    probe_root = raw_path.parents[2]
    probe_path = probe_root / "probe.json"
    if not probe_path.is_file():
        raise ValueError("MinerU content list is not inside a recorded probe")
    try:
        probe = json.loads(probe_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError("MinerU probe metadata is invalid JSON") from error
    if probe.get("status") != "succeeded":
        raise ValueError("MinerU probe did not succeed")
    probe_source = Path(str(probe.get("source_pdf", ""))).resolve()
    if probe_source != Path(manifest.source_path).resolve():
        raise ValueError("MinerU probe source does not match registered PDF")
    if probe.get("source_sha256") != manifest.source_sha256:
        raise ValueError("MinerU probe source SHA-256 does not match registered PDF")
    recorded_pages = probe.get("canonical_pages")
    if not isinstance(recorded_pages, list) or not all(
        isinstance(page, int) for page in recorded_pages
    ):
        raise ValueError("MinerU probe pages are invalid")
    if recorded_pages != list(range(first_page, first_page + len(recorded_pages))):
        raise ValueError("MinerU probe pages do not match requested slice")
    recorded_version = (
        probe.get("toolchain", {}).get("packages", {}).get("mineru")
    )
    if recorded_version != parser_version:
        raise ValueError("MinerU probe version does not match parser version")
    try:
        relative = raw_path.relative_to(probe_root)
    except ValueError as error:
        raise ValueError("MinerU content list escapes probe root") from error
    artifact = next(
        (
            item
            for item in probe.get("artifacts", [])
            if Path(str(item.get("path", ""))) == relative
        ),
        None,
    )
    raw_bytes = raw_path.read_bytes()
    if artifact is None or artifact.get("bytes") != len(raw_bytes):
        raise ValueError("MinerU content list does not match probe artifact manifest")
    if artifact.get("sha256") != hashlib.sha256(raw_bytes).hexdigest():
        raise ValueError("MinerU probe artifact SHA-256 does not match content list")
    return raw_bytes, recorded_pages


def ingest_mineru_slice(
    *,
    data_root: str | Path,
    book_id: str,
    content_list: str | Path,
    first_page: int,
    parser_version: str,
    chapter: int,
    embedding_dimensions: int = 64,
) -> SliceBuildResult:
    """Build canonical slice artifacts without modifying raw MinerU output."""
    if chapter <= 0:
        raise ValueError("chapter must be positive")
    raw_path = Path(content_list).resolve()
    if not raw_path.is_file():
        raise FileNotFoundError(raw_path)
    manifest_path = book_manifest_path(data_root, book_id)
    manifest = BookManifest.model_validate_json(
        manifest_path.read_text(encoding="utf-8")
    )
    raw_bytes, expected_pages = _validate_probe(
        raw_path,
        manifest,
        first_page,
        parser_version,
    )
    try:
        payload = json.loads(raw_bytes)
    except json.JSONDecodeError as error:
        raise ValueError("MinerU content list is invalid JSON") from error
    if not isinstance(payload, list) or not payload:
        raise ValueError("MinerU content list must contain pages")

    canonical_pages = list(range(first_page, first_page + len(payload)))
    if canonical_pages != expected_pages:
        raise ValueError("MinerU probe page count does not match content list")
    pages = link_relations(
        normalize_mineru_content_list(
            payload,
            first_page=first_page,
            page_sizes=_verified_page_sizes(manifest, first_page, len(payload)),
            raw_artifact=str(raw_path),
            parser_version=parser_version,
        )
    )
    issues = validate_pages(pages)
    if issues:
        summary = ", ".join(f"{issue.code}:{issue.block_id}" for issue in issues)
        raise ValueError(f"normalized MinerU slice failed validation: {summary}")

    book_root = book_artifact_dir(data_root, book_id)
    fingerprint_payload = {
        "schema_version": 1,
        "source_sha256": manifest.source_sha256,
        "raw_sha256": hashlib.sha256(raw_bytes).hexdigest(),
        "pages": canonical_pages,
        "parser_version": parser_version,
        "chapter": chapter,
        "embedding_dimensions": embedding_dimensions,
    }
    build_id = hashlib.sha256(
        json.dumps(
            fingerprint_payload, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()
    with _book_lock(book_root):
        builds_root = book_root / "builds"
        builds_root.mkdir(parents=True, exist_ok=True)
        build_root = builds_root / build_id
        temp_root: Path | None = None
        try:
            if not build_root.is_dir():
                temp_root = Path(
                    tempfile.mkdtemp(prefix=f".{build_id}.tmp-", dir=builds_root)
                )
                normalized_path = temp_root / "normalized/pages.json"
                validation_path = temp_root / "normalized/validation.json"
                index_path = temp_root / "search.sqlite3"
                _atomic_write_text(normalized_path, normalized_pages_json(pages))
                _atomic_write_text(
                    validation_path,
                    json.dumps([], ensure_ascii=False, separators=(",", ":")),
                )
                SearchIndex(
                    index_path,
                    embedding_provider=HashEmbeddingProvider(
                        dimensions=embedding_dimensions
                    ),
                ).rebuild(pages, chapter=chapter)
                try:
                    os.rename(temp_root, build_root)
                    temp_root = None
                except FileExistsError:
                    pass
            required = (
                build_root / "normalized/pages.json",
                build_root / "normalized/validation.json",
                build_root / "search.sqlite3",
            )
            if any(not path.is_file() for path in required):
                raise ValueError("published MinerU build is incomplete")
            _atomic_write_text(
                book_root / "active.json",
                json.dumps(
                    {"schema_version": 1, "build_id": build_id},
                    separators=(",", ":"),
                ),
            )
        finally:
            if temp_root is not None:
                shutil.rmtree(temp_root, ignore_errors=True)

    normalized_path = build_root / "normalized/pages.json"
    validation_path = build_root / "normalized/validation.json"
    index_path = build_root / "search.sqlite3"

    return SliceBuildResult(
        pages=pages,
        validation_issues=issues,
        normalized_path=normalized_path,
        validation_path=validation_path,
        index_path=index_path,
    )
