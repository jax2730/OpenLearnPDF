"""Register a PDF source without copying it into generated artifacts."""

import hashlib
import json
import os
import re
import tempfile
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import BinaryIO

from pypdf import PdfReader
from pypdf.errors import FileNotDecryptedError, PdfReadError

from rtr4_learning.models import BookManifest, ChapterManifest
from rtr4_learning.paths import book_manifest_path, validate_book_id

_CHAPTER_PATTERN = re.compile(
    r"^(?P<id>[A-Za-z0-9][A-Za-z0-9._-]*):(?P<start>[1-9]\d*)-(?P<end>[1-9]\d*)$"
)
_LOCK_TIMEOUT_SECONDS = 5.0
_LOCK_POLL_SECONDS = 0.02
_LOCK_STALE_SECONDS = 600.0


def _sha256_file(source: BinaryIO) -> str:
    digest = hashlib.sha256()
    source.seek(0)
    for chunk in iter(lambda: source.read(1024 * 1024), b""):
        digest.update(chunk)
    return digest.hexdigest()


def _stat_signature(metadata: os.stat_result) -> tuple[int, int, int, int]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_size,
        metadata.st_mtime_ns,
    )


def _path_signature(path: Path) -> tuple[int, int, int, int] | None:
    try:
        return _stat_signature(path.stat())
    except FileNotFoundError:
        return None


def _ensure_source_unchanged(
    path: Path,
    source: BinaryIO,
    initial_signature: tuple[int, int, int, int],
) -> None:
    final_handle_signature = _stat_signature(os.fstat(source.fileno()))
    final_path_signature = _path_signature(path)
    if not (
        final_handle_signature == initial_signature
        and final_path_signature == initial_signature
    ):
        raise ValueError(f"PDF changed during registration: {path}")


def _read_pdf_snapshot(path: Path) -> tuple[str, int]:
    with path.open("rb") as source:
        initial_signature = _stat_signature(os.fstat(source.fileno()))
        if _path_signature(path) != initial_signature:
            raise ValueError(f"PDF changed during registration: {path}")
        header = source.read(5)
        source.seek(0)
        if header != b"%PDF-":
            _ensure_source_unchanged(path, source, initial_signature)
            raise ValueError(f"PDF {path} is corrupt or encrypted")
        source_sha256 = _sha256_file(source)
        source.seek(0)
        try:
            page_count = len(PdfReader(source).pages)
        except (FileNotDecryptedError, PdfReadError) as error:
            _ensure_source_unchanged(path, source, initial_signature)
            raise ValueError(f"PDF {path} is corrupt or encrypted") from error
        _ensure_source_unchanged(path, source, initial_signature)
    return source_sha256, page_count


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


def _manifest_bytes(manifest: BookManifest) -> bytes:
    return (
        json.dumps(
            manifest.model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
        ).encode("utf-8")
        + b"\n"
    )


def _write_manifest_atomically(path: Path, payload: bytes) -> None:
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


def _pid_is_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if pid == os.getpid():
        return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _lock_is_stale(path: Path, payload: bytes) -> bool:
    try:
        lock_data = json.loads(payload)
        created_at = float(lock_data["created_at"])
        pid = int(lock_data["pid"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        try:
            created_at = path.stat().st_mtime
        except FileNotFoundError:
            return False
        pid = -1
    return time.time() - created_at >= _LOCK_STALE_SECONDS and not _pid_is_alive(pid)


def _try_remove_stale_lock(path: Path) -> bool:
    try:
        initial_metadata = path.stat()
    except FileNotFoundError:
        return True
    if time.time() - initial_metadata.st_mtime < _LOCK_STALE_SECONDS:
        return False
    try:
        first_payload = path.read_bytes()
        first_signature = _stat_signature(path.stat())
    except FileNotFoundError:
        return True
    if not _lock_is_stale(path, first_payload):
        return False
    try:
        if path.read_bytes() != first_payload:
            return False
        if _stat_signature(path.stat()) != first_signature:
            return False
        path.unlink()
    except FileNotFoundError:
        pass
    return True


@contextmanager
def _book_lock(manifest_path: Path) -> Iterator[None]:
    lock_path = (
        manifest_path.parent.parent / f".{manifest_path.parent.name}.register.lock"
    )
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + _LOCK_TIMEOUT_SECONDS
    owner_payload = json.dumps(
        {
            "pid": os.getpid(),
            "created_at": time.time(),
            "token": uuid.uuid4().hex,
        },
        separators=(",", ":"),
    ).encode("utf-8")
    while True:
        try:
            descriptor = os.open(
                lock_path,
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                0o600,
            )
        except FileExistsError:
            if _try_remove_stale_lock(lock_path):
                continue
            if time.monotonic() >= deadline:
                raise ValueError(
                    f"timed out waiting for book registration lock: {lock_path}"
                )
            time.sleep(_LOCK_POLL_SECONDS)
            continue
        try:
            os.write(descriptor, owner_payload)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        break
    try:
        yield
    finally:
        try:
            if lock_path.read_bytes() == owner_payload:
                lock_path.unlink()
        except FileNotFoundError:
            pass


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
    source_sha256, page_count = _read_pdf_snapshot(canonical_pdf_path)
    manifest = BookManifest(
        id=book_id,
        title=title if title is not None else book_id,
        source_path=str(canonical_pdf_path),
        source_sha256=source_sha256,
        page_count=page_count,
        chapters=(_parse_chapter(chapter, page_count),),
    )
    manifest_path = book_manifest_path(data_root, book_id)
    payload = _manifest_bytes(manifest)
    with _book_lock(manifest_path):
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        if manifest_path.exists():
            try:
                existing_manifest = BookManifest.model_validate_json(
                    manifest_path.read_bytes()
                )
            except ValueError as error:
                raise ValueError(
                    f"existing book manifest conflict: {manifest_path} is invalid"
                ) from error
            if existing_manifest != manifest:
                raise ValueError(
                    f"existing book manifest conflict for book_id {book_id}"
                )
            return manifest
        _write_manifest_atomically(manifest_path, payload)
    return manifest
