"""Render selected registered PDF pages into immutable stage artifacts."""

import hashlib
import json
import math
import os
import re
import shutil
import tempfile
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO

import portalocker
import pypdfium2 as pdfium
from PIL import Image, UnidentifiedImageError

from rtr4_learning.models import BookManifest, StageArtifact, StageManifest
from rtr4_learning.paths import book_manifest_path, book_render_dir

_STAGE_NAME = "render"
_STAGE_VERSION = "2"
_LOCK_TIMEOUT_SECONDS = 30.0
_LOCK_CHECK_INTERVAL_SECONDS = 0.05
_PAGE_PART_PATTERN = re.compile(r"^[1-9]\d*(?:-[1-9]\d*)?$")
_MAX_REQUESTED_PAGES = 256
_MAX_PAGE_NUMBER_DIGITS = 9
_MAX_RENDER_SCALE = 8.0
_MAX_PAGE_PIXELS = 40_000_000
_MAX_TOTAL_PIXELS = 160_000_000


@dataclass(frozen=True)
class RenderResult:
    fingerprint: str
    output_dir: Path
    reused: bool


@dataclass(frozen=True)
class _VerifiedSource:
    path: Path
    stream: BinaryIO
    initial_handle_signature: tuple[int, int, int, int, int]
    initial_path_signature: tuple[int, int, int, int, int]

    def verify_unchanged(self) -> None:
        _ensure_source_unchanged(
            self.path,
            self.stream,
            self.initial_handle_signature,
            self.initial_path_signature,
        )


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
            if max(len(start_text), len(end_text)) > _MAX_PAGE_NUMBER_DIGITS:
                raise ValueError(
                    "pages contain an integer above the supported boundary"
                )
            start, end = int(start_text), int(end_text)
            if start > end:
                raise ValueError("pages range start must be <= end")
            if end - start + 1 > _MAX_REQUESTED_PAGES:
                raise ValueError(
                    f"pages selection may contain at most {_MAX_REQUESTED_PAGES} pages"
                )
            pages.update(range(start, end + 1))
        else:
            if len(part) > _MAX_PAGE_NUMBER_DIGITS:
                raise ValueError(
                    "pages contain an integer above the supported boundary"
                )
            pages.add(int(part))
        if len(pages) > _MAX_REQUESTED_PAGES:
            raise ValueError(
                f"pages selection may contain at most {_MAX_REQUESTED_PAGES} pages"
            )
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


def _sha256_stream(source: BinaryIO) -> str:
    digest = hashlib.sha256()
    source.seek(0)
    for chunk in iter(lambda: source.read(1024 * 1024), b""):
        digest.update(chunk)
    return digest.hexdigest()


def _stat_signature(metadata: os.stat_result) -> tuple[int, int, int, int, int]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )


def _path_signature(path: Path) -> tuple[int, int, int, int, int] | None:
    try:
        return _stat_signature(path.stat())
    except FileNotFoundError:
        return None


def _ensure_source_unchanged(
    path: Path,
    source: BinaryIO,
    initial_handle_signature: tuple[int, int, int, int, int],
    initial_path_signature: tuple[int, int, int, int, int],
) -> None:
    final_handle_signature = _stat_signature(os.fstat(source.fileno()))
    final_path_signature = _path_signature(path)
    if not (
        final_handle_signature == initial_handle_signature
        and final_path_signature == initial_path_signature
        and final_path_signature is not None
        and final_path_signature[:4] == final_handle_signature[:4]
    ):
        raise ValueError(f"PDF changed during rendering: {path}")


@contextmanager
def _verified_source(manifest: BookManifest) -> Iterator[_VerifiedSource]:
    path = Path(manifest.source_path)
    try:
        with path.open("rb") as source:
            initial_handle_signature = _stat_signature(os.fstat(source.fileno()))
            initial_path_signature = _path_signature(path)
            if (
                initial_path_signature is None
                or initial_path_signature[:4] != initial_handle_signature[:4]
            ):
                raise ValueError(f"PDF identity changed before rendering: {path}")
            source_sha256 = _sha256_stream(source)
            _ensure_source_unchanged(
                path, source, initial_handle_signature, initial_path_signature
            )
            if source_sha256 != manifest.source_sha256:
                raise ValueError(f"registered PDF SHA-256 mismatch: {path}")
            source.seek(0)
            verified = _VerifiedSource(
                path=path,
                stream=source,
                initial_handle_signature=initial_handle_signature,
                initial_path_signature=initial_path_signature,
            )
            try:
                yield verified
            finally:
                verified.verify_unchanged()
    except FileNotFoundError as error:
        raise ValueError(f"registered PDF is missing: {path}") from error


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
    if len(normalized) > _MAX_REQUESTED_PAGES:
        raise ValueError(
            f"page selection may contain at most {_MAX_REQUESTED_PAGES} pages"
        )
    if normalized[0] < 1 or normalized[-1] > page_count:
        raise ValueError(f"page selection must be within 1-{page_count}")
    return normalized


def _validate_scale(scale: float) -> float:
    try:
        normalized = float(scale)
    except (TypeError, ValueError) as error:
        raise ValueError("scale must be a positive finite number") from error
    if not math.isfinite(normalized) or not 0 < normalized <= _MAX_RENDER_SCALE:
        raise ValueError(
            f"scale must be a positive finite number no greater than {_MAX_RENDER_SCALE:g}"
        )
    return normalized


def _page_metadata(
    *,
    page_number: int,
    width_points: float,
    height_points: float,
    pixel_width: int,
    pixel_height: int,
    scale: float,
    fingerprint: str,
) -> dict[str, Any]:
    return {
        "source_page_number": page_number,
        "stage_fingerprint": fingerprint,
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
    source_path: Path,
    fingerprint: str,
) -> tuple[str, str, int]:
    try:
        page = document[page_number - 1]
    except (pdfium.PdfiumError, OSError) as error:
        raise ValueError(
            f"failed to read registered PDF {source_path} page {page_number}: {error}"
        ) from error
    bitmap = None
    try:
        width_points, height_points = page.get_size()
        bitmap = page.render(scale=scale)
        pixel_count = bitmap.width * bitmap.height
        if pixel_count > _MAX_PAGE_PIXELS:
            raise ValueError(
                f"page {page_number} exceeds pixel budget {_MAX_PAGE_PIXELS}"
            )
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
            fingerprint=fingerprint,
        )
        (pages_dir / f"p{page_number}.json").write_bytes(_json_bytes(metadata))
        return png_relative, json_relative, pixel_count
    except (pdfium.PdfiumError, OSError) as error:
        raise ValueError(
            f"failed to render registered PDF {source_path} page {page_number}: {error}"
        ) from error
    finally:
        if bitmap is not None:
            bitmap.close()
        page.close()


def _preflight_pixel_budget(
    document: pdfium.PdfDocument,
    pages: tuple[int, ...],
    scale: float,
    source_path: Path,
) -> None:
    total_pixels = 0
    for page_number in pages:
        try:
            page = document[page_number - 1]
            try:
                width_points, height_points = page.get_size()
            finally:
                page.close()
        except (pdfium.PdfiumError, OSError) as error:
            raise ValueError(
                f"failed to inspect registered PDF {source_path} page {page_number}: {error}"
            ) from error
        pixel_width = math.ceil(width_points * scale)
        pixel_height = math.ceil(height_points * scale)
        page_pixels = pixel_width * pixel_height
        if page_pixels > _MAX_PAGE_PIXELS:
            raise ValueError(
                f"page {page_number} exceeds pixel budget {_MAX_PAGE_PIXELS}"
            )
        total_pixels += page_pixels
        if total_pixels > _MAX_TOTAL_PIXELS:
            raise ValueError(f"render exceeds total pixel budget {_MAX_TOTAL_PIXELS}")


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
    if not (
        stage.stage == _STAGE_NAME
        and stage.version == _STAGE_VERSION
        and stage.fingerprint == fingerprint
        and stage.model_dump(mode="json")["inputs"] == expected_inputs
        and stage.outputs == expected_outputs
        and len(stage.artifacts) == len(expected_outputs)
    ):
        return False
    artifacts = {artifact.path: artifact for artifact in stage.artifacts}
    if len(artifacts) != len(stage.artifacts) or set(artifacts) != set(
        expected_outputs
    ):
        return False
    png_dimensions: dict[int, tuple[int, int]] = {}
    for relative in expected_outputs:
        artifact = artifacts[relative]
        artifact_path = output_dir / relative
        try:
            if artifact_path.stat().st_size != artifact.size:
                return False
            with artifact_path.open("rb") as source:
                if _sha256_stream(source) != artifact.sha256:
                    return False
            if relative.endswith(".png"):
                page_number = int(Path(relative).stem[1:])
                with Image.open(artifact_path) as image:
                    dimensions = image.size
                    image.verify()
                with Image.open(artifact_path) as image:
                    image.load()
                if dimensions != (artifact.pixel_width, artifact.pixel_height):
                    return False
                png_dimensions[page_number] = dimensions
        except (OSError, ValueError, UnidentifiedImageError):
            return False
    for page_number, dimensions in png_dimensions.items():
        if not _valid_page_metadata(
            output_dir / "pages" / f"p{page_number}.json",
            page_number,
            fingerprint,
            float(expected_inputs["scale"]),
            dimensions,
        ):
            return False
    return True


def _valid_page_metadata(
    path: Path,
    page_number: int,
    fingerprint: str,
    scale: float,
    pixel_dimensions: tuple[int, int],
) -> bool:
    try:
        metadata = json.loads(path.read_bytes())
        width_points = float(metadata["pdf_points"]["width"])
        height_points = float(metadata["pdf_points"]["height"])
        if not (
            math.isfinite(width_points)
            and width_points > 0
            and math.isfinite(height_points)
            and height_points > 0
        ):
            return False
        pixel_width, pixel_height = pixel_dimensions
        return (
            metadata["source_page_number"] == page_number
            and metadata["stage_fingerprint"] == fingerprint
            and metadata["render_scale"] == scale
            and metadata["coordinate_system"] == "top-left"
            and metadata["pixels"] == {"width": pixel_width, "height": pixel_height}
            and metadata["transforms"]["normalized_top_left_to_pixels"]
            == {
                "x_scale": pixel_width,
                "y_scale": pixel_height,
                "x_offset": 0.0,
                "y_offset": 0.0,
            }
            and metadata["transforms"]["normalized_top_left_to_pdf_points_top_left"]
            == {
                "x_scale": width_points,
                "y_scale": height_points,
                "x_offset": 0.0,
                "y_offset": 0.0,
            }
        )
    except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError):
        return False


def _artifact_records(
    stage_dir: Path, outputs: tuple[str, ...]
) -> tuple[StageArtifact, ...]:
    artifacts: list[StageArtifact] = []
    for relative in outputs:
        path = stage_dir / relative
        with path.open("rb") as source:
            sha256 = _sha256_stream(source)
        dimensions: tuple[int, int] | tuple[()] = ()
        if relative.endswith(".png"):
            try:
                with Image.open(path) as image:
                    image.load()
                    dimensions = image.size
            except (OSError, UnidentifiedImageError) as error:
                raise ValueError(f"rendered PNG is invalid: {path}: {error}") from error
        artifacts.append(
            StageArtifact(
                path=relative,
                size=path.stat().st_size,
                sha256=sha256,
                pixel_width=dimensions[0] if dimensions else None,
                pixel_height=dimensions[1] if dimensions else None,
            )
        )
    return tuple(artifacts)


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


@contextmanager
def _published_stage_guard(output_dir: Path) -> Iterator[dict[str, bool]]:
    state = {"published": False}
    try:
        yield state
    except BaseException:
        if state["published"] and output_dir.exists():
            shutil.rmtree(output_dir)
        raise


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

    source_path = Path(manifest.source_path)
    with ExitStack() as stack:
        stack.enter_context(_render_lock(render_root, fingerprint))
        publication = stack.enter_context(_published_stage_guard(output_dir))
        source = stack.enter_context(_verified_source(manifest))
        if output_dir.exists():
            if _is_complete_stage(output_dir, fingerprint, inputs, expected_outputs):
                return RenderResult(fingerprint, output_dir, reused=True)
            shutil.rmtree(output_dir)

        temporary_dir = Path(
            tempfile.mkdtemp(prefix=f".{fingerprint}.tmp-", dir=render_root)
        )
        try:
            pages_dir = temporary_dir / "pages"
            pages_dir.mkdir()
            try:
                document = pdfium.PdfDocument(source.stream)
            except (pdfium.PdfiumError, OSError) as error:
                raise ValueError(
                    f"registered PDF {source_path} is corrupt or unreadable: {error}"
                ) from error
            try:
                if len(document) != manifest.page_count:
                    raise ValueError(
                        f"registered PDF page count changed: {source_path}"
                    )
                _preflight_pixel_budget(
                    document,
                    normalized_pages,
                    normalized_scale,
                    source_path,
                )
                outputs: list[str] = []
                actual_total_pixels = 0
                for page_number in normalized_pages:
                    png_path, metadata_path, pixel_count = _render_page(
                        document=document,
                        page_number=page_number,
                        scale=normalized_scale,
                        pages_dir=pages_dir,
                        source_path=source_path,
                        fingerprint=fingerprint,
                    )
                    outputs.extend((png_path, metadata_path))
                    actual_total_pixels += pixel_count
                    if actual_total_pixels > _MAX_TOTAL_PIXELS:
                        raise ValueError(
                            f"render exceeds total pixel budget {_MAX_TOTAL_PIXELS}"
                        )
            finally:
                document.close()
            stage = StageManifest(
                stage=_STAGE_NAME,
                version=_STAGE_VERSION,
                fingerprint=fingerprint,
                inputs=inputs,
                outputs=tuple(outputs),
                artifacts=_artifact_records(temporary_dir, tuple(outputs)),
            )
            (temporary_dir / "stage.json").write_bytes(
                _json_bytes(stage.model_dump(mode="json"))
            )
            source.verify_unchanged()
            os.rename(temporary_dir, output_dir)
            publication["published"] = True
        finally:
            if temporary_dir.exists():
                shutil.rmtree(temporary_dir)
    return RenderResult(fingerprint, output_dir, reused=False)
