"""Render selected registered PDF pages into immutable stage artifacts."""

import hashlib
import json
import math
import os
import re
import shutil
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import portalocker
import pypdfium2 as pdfium

from rtr4_learning.models import BookManifest, StageManifest
from rtr4_learning.paths import book_manifest_path, book_render_dir

_STAGE_NAME = "render"
_STAGE_VERSION = "1"
_LOCK_TIMEOUT_SECONDS = 30.0
_LOCK_CHECK_INTERVAL_SECONDS = 0.05
_PAGE_PART_PATTERN = re.compile(r"^[1-9]\d*(?:-[1-9]\d*)?$")


@dataclass(frozen=True)
class RenderResult:
    fingerprint: str
    output_dir: Path
    reused: bool


def parse_page_selection(value: str) -> tuple[int, ...]:
    """Parse comma-separated one-based pages and inclusive ranges."""
    pages: set[int] = set()
    if not value:
        raise ValueError("pages must not be empty")
    for part in value.split(","):
        if not _PAGE_PART_PATTERN.fullmatch(part):
            raise ValueError("pages must use N or START-END comma-separated format")
        if "-" in part:
            start_text, end_text = part.split("-", maxsplit=1)
            start, end = int(start_text), int(end_text)
            if start > end:
                raise ValueError("pages range start must be <= end")
            pages.update(range(start, end + 1))
        else:
            pages.add(int(part))
    return tuple(sorted(pages))


def _canonical_json_bytes(value: dict[str, Any]) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _stage_inputs(
    manifest: BookManifest, pages: tuple[int, ...], scale: float
) -> dict[str, Any]:
    return {
        "source_sha256": manifest.source_sha256,
        "pages": list(pages),
        "scale": scale,
    }


def _fingerprint(inputs: dict[str, Any]) -> str:
    identity = {
        "stage": _STAGE_NAME,
        "version": _STAGE_VERSION,
        "inputs": inputs,
    }
    return hashlib.sha256(_canonical_json_bytes(identity)).hexdigest()


def _json_bytes(value: dict[str, Any]) -> bytes:
    return json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"


def _load_book(data_root: Path | str, book_id: str) -> BookManifest:
    path = book_manifest_path(data_root, book_id)
    try:
        return BookManifest.model_validate_json(path.read_bytes())
    except FileNotFoundError as error:
        raise ValueError(f"book is not registered: {book_id}") from error
    except ValueError as error:
        raise ValueError(f"invalid book manifest: {path}") from error


def _normalize_pages(pages: tuple[int, ...], page_count: int) -> tuple[int, ...]:
    if not pages:
        raise ValueError("page selection must not be empty")
    if any(isinstance(page, bool) or not isinstance(page, int) for page in pages):
        raise ValueError("page numbers must be integers")
    normalized = tuple(sorted(set(pages)))
    if normalized[0] < 1 or normalized[-1] > page_count:
        raise ValueError(f"page selection must be within 1-{page_count}")
    return normalized


def _validate_scale(scale: float) -> float:
    try:
        normalized = float(scale)
    except (TypeError, ValueError) as error:
        raise ValueError("scale must be a positive finite number") from error
    if not math.isfinite(normalized) or normalized <= 0:
        raise ValueError("scale must be a positive finite number")
    return normalized


def _page_metadata(
    *,
    page_number: int,
    width_points: float,
    height_points: float,
    pixel_width: int,
    pixel_height: int,
    scale: float,
) -> dict[str, Any]:
    return {
        "source_page_number": page_number,
        "pdf_points": {"width": width_points, "height": height_points},
        "pixels": {"width": pixel_width, "height": pixel_height},
        "render_scale": scale,
        "coordinate_system": "top-left",
        "transforms": {
            "normalized_top_left_to_pixels": {
                "x_scale": pixel_width,
                "y_scale": pixel_height,
                "x_offset": 0.0,
                "y_offset": 0.0,
            },
            "normalized_top_left_to_pdf_points_top_left": {
                "x_scale": width_points,
                "y_scale": height_points,
                "x_offset": 0.0,
                "y_offset": 0.0,
            },
        },
    }


def _render_page(
    *,
    document: pdfium.PdfDocument,
    page_number: int,
    scale: float,
    pages_dir: Path,
) -> tuple[str, str]:
    page = document[page_number - 1]
    bitmap = None
    try:
        width_points, height_points = page.get_size()
        bitmap = page.render(scale=scale)
        png_relative = f"pages/p{page_number}.png"
        json_relative = f"pages/p{page_number}.json"
        bitmap.to_pil().save(pages_dir / f"p{page_number}.png", format="PNG")
        metadata = _page_metadata(
            page_number=page_number,
            width_points=float(width_points),
            height_points=float(height_points),
            pixel_width=bitmap.width,
            pixel_height=bitmap.height,
            scale=scale,
        )
        (pages_dir / f"p{page_number}.json").write_bytes(_json_bytes(metadata))
        return png_relative, json_relative
    finally:
        if bitmap is not None:
            bitmap.close()
        page.close()


def _is_complete_stage(
    output_dir: Path,
    fingerprint: str,
    expected_inputs: dict[str, Any],
    expected_outputs: tuple[str, ...],
) -> bool:
    try:
        stage = StageManifest.model_validate_json(
            (output_dir / "stage.json").read_bytes()
        )
    except (OSError, ValueError):
        return False
    return (
        stage.stage == _STAGE_NAME
        and stage.version == _STAGE_VERSION
        and stage.fingerprint == fingerprint
        and stage.model_dump(mode="json")["inputs"] == expected_inputs
        and stage.outputs == expected_outputs
        and all((output_dir / relative).is_file() for relative in expected_outputs)
    )


@contextmanager
def _render_lock(render_root: Path, fingerprint: str) -> Iterator[None]:
    lock_path = render_root / f".{fingerprint}.render.lock"
    render_root.mkdir(parents=True, exist_ok=True)
    try:
        with portalocker.Lock(
            lock_path,
            mode="a+b",
            timeout=_LOCK_TIMEOUT_SECONDS,
            check_interval=_LOCK_CHECK_INTERVAL_SECONDS,
        ):
            yield
    except portalocker.exceptions.LockException as error:
        raise ValueError(f"timed out waiting for render lock: {lock_path}") from error


def render_pages(
    *,
    book_id: str,
    pages: tuple[int, ...],
    scale: float,
    data_root: Path | str,
) -> RenderResult:
    """Render requested pages and publish only a complete immutable stage."""
    manifest = _load_book(data_root, book_id)
    normalized_pages = _normalize_pages(pages, manifest.page_count)
    normalized_scale = _validate_scale(scale)
    inputs = _stage_inputs(manifest, normalized_pages, normalized_scale)
    fingerprint = _fingerprint(inputs)
    render_root = book_render_dir(data_root, book_id)
    output_dir = render_root / fingerprint
    expected_outputs = tuple(
        relative
        for page_number in normalized_pages
        for relative in (f"pages/p{page_number}.png", f"pages/p{page_number}.json")
    )

    with _render_lock(render_root, fingerprint):
        if output_dir.exists():
            if _is_complete_stage(
                output_dir, fingerprint, inputs, expected_outputs
            ):
                return RenderResult(fingerprint, output_dir, reused=True)
            raise ValueError(f"render stage exists but is incomplete or invalid: {output_dir}")

        temporary_dir = Path(
            tempfile.mkdtemp(prefix=f".{fingerprint}.tmp-", dir=render_root)
        )
        try:
            pages_dir = temporary_dir / "pages"
            pages_dir.mkdir()
            document = pdfium.PdfDocument(manifest.source_path)
            try:
                if len(document) != manifest.page_count:
                    raise ValueError("registered PDF page count changed")
                outputs: list[str] = []
                for page_number in normalized_pages:
                    outputs.extend(
                        _render_page(
                            document=document,
                            page_number=page_number,
                            scale=normalized_scale,
                            pages_dir=pages_dir,
                        )
                    )
            finally:
                document.close()
            stage = StageManifest(
                stage=_STAGE_NAME,
                version=_STAGE_VERSION,
                fingerprint=fingerprint,
                inputs=inputs,
                outputs=tuple(outputs),
            )
            (temporary_dir / "stage.json").write_bytes(
                _json_bytes(stage.model_dump(mode="json"))
            )
            os.rename(temporary_dir, output_dir)
        finally:
            if temporary_dir.exists():
                shutil.rmtree(temporary_dir)
    return RenderResult(fingerprint, output_dir, reused=False)
