"""Read-only FastAPI endpoints for cited RTR4 learning data."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import sqlite3
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import StreamingResponse

from rtr4_learning.index import HashEmbeddingProvider
from rtr4_learning.models import Block, BookManifest, PageDocument
from rtr4_learning.paths import (
    _is_link_or_reparse_point,
    book_artifact_dir,
    book_manifest_path,
    validate_book_id,
)
from rtr4_learning.retrieval import RetrievalResult, retrieve
from rtr4_learning.settings import Settings
from rtr4_learning.teaching import load_lesson_bundle

_CONTENT_SLUG = re.compile(r"^[a-z0-9]+(?:[.-][a-z0-9]+)*$")
_LOGGER = logging.getLogger(__name__)


def _public_manifest(manifest: BookManifest) -> dict[str, object]:
    return {
        "id": manifest.id,
        "title": manifest.title,
        "page_count": manifest.page_count,
        "chapters": [chapter.model_dump(mode="json") for chapter in manifest.chapters],
    }


def _not_found(message: str) -> HTTPException:
    return HTTPException(status_code=404, detail=message)


def _manifest(settings: Settings, book_id: str) -> BookManifest:
    try:
        validate_book_id(book_id)
        path = book_manifest_path(settings.data_root, book_id)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    if not path.is_file():
        raise _not_found("book not found")
    try:
        return BookManifest.model_validate_json(path.read_text(encoding="utf-8"))
    except ValueError as error:
        raise HTTPException(status_code=500, detail="book manifest is invalid") from error


def _pages(settings: Settings, book_id: str) -> tuple[PageDocument, ...]:
    path = book_artifact_dir(settings.data_root, book_id) / "normalized/pages.json"
    if not path.is_file():
        raise _not_found("normalized pages not found")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return tuple(PageDocument.model_validate(page) for page in payload)
    except (json.JSONDecodeError, ValueError, TypeError) as error:
        raise HTTPException(status_code=500, detail="normalized pages are invalid") from error


def _content_path(root: Path, chapter_slug: str, section_slug: str) -> Path:
    if not _CONTENT_SLUG.fullmatch(chapter_slug) or not _CONTENT_SLUG.fullmatch(
        section_slug
    ):
        raise HTTPException(status_code=422, detail="invalid content slug")
    path = (root / "rtr4-cn" / chapter_slug / f"{section_slug}.json").resolve()
    if not path.is_relative_to(root):
        raise HTTPException(status_code=422, detail="content path escapes content root")
    return path


def create_app(settings: Settings) -> FastAPI:
    app = FastAPI(title="RTR4 Learning API", version="0.1.0")
    verified_sources: dict[tuple[object, ...], bool] = {}
    verified_sources_lock = threading.Lock()

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/books/{book_id}")
    def get_book(book_id: str) -> dict[str, object]:
        return _public_manifest(_manifest(settings, book_id))

    @app.get(
        "/api/books/{book_id}/chapters/{chapter_id}/pages/{page_number}",
        response_model=PageDocument,
    )
    def get_page(book_id: str, chapter_id: str, page_number: int) -> PageDocument:
        manifest = _manifest(settings, book_id)
        chapter = next(
            (chapter for chapter in manifest.chapters if chapter.id == chapter_id),
            None,
        )
        if chapter is None:
            raise _not_found("chapter not found")
        if not chapter.start_page <= page_number <= chapter.end_page:
            raise _not_found("page is outside chapter")
        page = next(
            (page for page in _pages(settings, book_id) if page.page == page_number),
            None,
        )
        if page is None:
            raise _not_found("page not found")
        return page

    @app.get("/api/blocks/{block_id}", response_model=Block)
    def get_block(block_id: str, book_id: str = Query("rtr4-cn")) -> Block:
        _manifest(settings, book_id)
        block = next(
            (
                block
                for page in _pages(settings, book_id)
                for block in page.blocks
                if block.id == block_id
            ),
            None,
        )
        if block is None:
            raise _not_found("block not found")
        return block

    @app.get("/api/search", response_model=list[RetrievalResult])
    def search(
        q: Annotated[str, Query(min_length=1, max_length=256)],
        chapter: Annotated[int, Query(ge=1)],
        book_id: str = Query("rtr4-cn"),
        limit: int = Query(10, ge=1, le=50),
    ) -> tuple[RetrievalResult, ...]:
        _manifest(settings, book_id)
        if not q.strip():
            raise HTTPException(status_code=422, detail="query must not be blank")
        path = book_artifact_dir(settings.data_root, book_id) / "search.sqlite3"
        try:
            return retrieve(
                path,
                q,
                chapter=chapter,
                embedding_provider=HashEmbeddingProvider(
                    dimensions=settings.embedding_dimensions
                ),
                limit=limit,
            )
        except FileNotFoundError as error:
            raise _not_found("search index not found") from error
        except (sqlite3.DatabaseError, ValueError, json.JSONDecodeError) as error:
            _LOGGER.exception("search index failure for %s", path)
            raise HTTPException(
                status_code=500, detail="search index is invalid"
            ) from error

    @app.get("/api/lessons/{chapter_slug}/{section_slug}")
    def get_lesson(chapter_slug: str, section_slug: str) -> dict[str, object]:
        path = _content_path(settings.content_root, chapter_slug, section_slug)
        if not path.is_file():
            raise _not_found("lesson not found")
        try:
            lesson, shader = load_lesson_bundle(path)
        except (OSError, ValueError) as error:
            raise HTTPException(status_code=500, detail="lesson bundle is invalid") from error
        return {"lesson": lesson, "shader": shader}

    @app.get("/api/books/{book_id}/source")
    def get_source_pdf(book_id: str, request: Request):
        manifest = _manifest(settings, book_id)
        path = Path(manifest.source_path)
        if not path.is_file():
            raise _not_found("source PDF not found")
        resolved = path.resolve()
        allowed_root = next(
            (root for root in settings.source_roots if resolved.is_relative_to(root)),
            None,
        )
        if allowed_root is None:
            raise HTTPException(status_code=403, detail="source PDF is outside allowed roots")
        current = path
        while current != allowed_root and current.is_relative_to(allowed_root):
            if _is_link_or_reparse_point(current):
                raise HTTPException(status_code=403, detail="source PDF path is indirect")
            current = current.parent

        source = path.open("rb")
        try:
            if source.read(5) != b"%PDF-":
                raise HTTPException(status_code=500, detail="registered source is not a PDF")
            metadata = os.fstat(source.fileno())
            signature = (
                str(resolved),
                metadata.st_dev,
                metadata.st_ino,
                metadata.st_size,
                metadata.st_mtime_ns,
                metadata.st_ctime_ns,
                manifest.source_sha256,
            )
            with verified_sources_lock:
                verified = signature in verified_sources
            if not verified:
                source.seek(0)
                digest = hashlib.sha256()
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    digest.update(chunk)
                if os.fstat(source.fileno()) != metadata:
                    raise HTTPException(
                        status_code=409, detail="registered source changed during verification"
                    )
                if digest.hexdigest() != manifest.source_sha256:
                    raise HTTPException(
                        status_code=409, detail="registered source hash changed"
                    )
                with verified_sources_lock:
                    verified_sources.clear()
                    verified_sources[signature] = True
            source.seek(0)
        except BaseException:
            source.close()
            raise

        size = metadata.st_size
        start = 0
        end = size - 1
        status_code = 200
        range_header = request.headers.get("range")
        if range_header:
            match = re.fullmatch(r"bytes=(\d*)-(\d*)", range_header.strip())
            if match is None or not any(match.groups()):
                source.close()
                return Response(
                    status_code=416,
                    headers={"Content-Range": f"bytes */{size}"},
                )
            start_text, end_text = match.groups()
            if not start_text:
                suffix = int(end_text)
                if suffix <= 0:
                    source.close()
                    return Response(
                        status_code=416,
                        headers={"Content-Range": f"bytes */{size}"},
                    )
                start = max(0, size - suffix)
            else:
                start = int(start_text)
                if end_text:
                    end = min(int(end_text), size - 1)
            if start >= size or start > end:
                source.close()
                return Response(
                    status_code=416,
                    headers={"Content-Range": f"bytes */{size}"},
                )
            status_code = 206

        length = end - start + 1
        source.seek(start)

        def stream() -> Iterator[bytes]:
            remaining = length
            try:
                while remaining:
                    chunk = source.read(min(1024 * 1024, remaining))
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    yield chunk
            finally:
                source.close()

        headers = {
            "Accept-Ranges": "bytes",
            "Content-Length": str(length),
            "Content-Disposition": f'inline; filename="{path.name.replace(chr(34), "")}"',
        }
        if status_code == 206:
            headers["Content-Range"] = f"bytes {start}-{end}/{size}"
        return StreamingResponse(
            stream(),
            media_type="application/pdf",
            headers=headers,
            status_code=status_code,
        )

    @app.get("/api/capabilities")
    def capabilities() -> dict[str, bool]:
        return {
            "local_search": True,
            "cloud_vision": bool(settings.vision_api_key),
        }

    return app
