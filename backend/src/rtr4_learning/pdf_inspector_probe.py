"""Pure report helpers for the optional pdf-inspector evaluation probe."""

from __future__ import annotations

import hashlib
import importlib
import importlib.metadata
import json
import math
import os
import shutil
import tempfile
import time
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _value(source: object, name: str, default: Any = None) -> Any:
    if isinstance(source, Mapping):
        return source.get(name, default)
    return getattr(source, name, default)


def to_zero_based_pages(pages: Iterable[int]) -> tuple[int, ...]:
    """Validate one-based PDF pages and return sorted zero-based indexes."""
    values = tuple(pages)
    if not values:
        raise ValueError("pages must not be empty")
    if any(
        isinstance(page, bool) or not isinstance(page, int) or page <= 0
        for page in values
    ):
        raise ValueError("pages must contain positive one-based integers")
    return tuple(page - 1 for page in sorted(set(values)))


def _invalid_geometry(item: object) -> bool:
    values = (_value(item, name) for name in ("x", "y", "width", "height"))
    return any(
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not math.isfinite(value)
        or value < 0
        for value in values
    )


def build_probe_report(
    *,
    requested_pages: Iterable[int],
    classification: object,
    page_markdown: Sequence[object],
    positioned_items: Sequence[object],
    expected_anchors: Mapping[int, Sequence[str]],
) -> dict[str, object]:
    """Build deterministic quality evidence from upstream-shaped values."""
    pages = tuple(page + 1 for page in to_zero_based_pages(requested_pages))
    markdown_by_page = {
        int(_value(page, "page")) + 1: page for page in page_markdown
    }
    if any(page not in markdown_by_page for page in pages):
        raise ValueError("pdf-inspector did not return all requested pages")

    items_by_page: dict[int, list[object]] = {page: [] for page in pages}
    for item in positioned_items:
        page = int(_value(item, "page", 0))
        if page in items_by_page:
            items_by_page[page].append(item)

    classified_ocr_pages = {
        int(page) for page in _value(classification, "pages_needing_ocr", [])
    }
    page_reports: list[dict[str, object]] = []
    for page_number in pages:
        markdown_page = markdown_by_page[page_number]
        markdown = str(_value(markdown_page, "markdown", ""))
        page_items = items_by_page[page_number]
        searchable = "\n".join(
            [markdown, *(str(_value(item, "text", "")) for item in page_items)]
        ).casefold()
        anchors = tuple(expected_anchors.get(page_number, ()))
        missing_anchors = [
            anchor for anchor in anchors if anchor.casefold() not in searchable
        ]
        invalid_geometry_count = sum(_invalid_geometry(item) for item in page_items)
        image_placeholder_count = sum(
            str(_value(item, "item_type", "")).casefold() == "image"
            or str(_value(item, "text", "")).startswith("[Image:")
            for item in page_items
        )
        needs_ocr = bool(_value(markdown_page, "needs_ocr", False)) or (
            page_number in classified_ocr_pages
        )
        page_reports.append(
            {
                "page": page_number,
                "route": "mineru" if needs_ocr else "native_text",
                "needs_ocr": needs_ocr,
                "ocr_reason": _value(markdown_page, "ocr_reason"),
                "markdown_chars": len(markdown),
                "positioned_item_count": len(page_items),
                "image_placeholder_count": image_placeholder_count,
                "invalid_geometry_count": invalid_geometry_count,
                "missing_anchors": missing_anchors,
            }
        )

    has_encoding_issues = bool(
        _value(classification, "has_encoding_issues", False)
    )
    has_invalid_geometry = any(
        page["invalid_geometry_count"] for page in page_reports
    )
    if has_encoding_issues or has_invalid_geometry:
        recommendation = "reject_cjk_quality"
    elif any(
        page["needs_ocr"] or page["missing_anchors"] for page in page_reports
    ):
        recommendation = "routing_preflight_only"
    else:
        recommendation = "native_text_candidate"

    return {
        "schema_version": 1,
        "requested_pages": list(pages),
        "pdf_type": str(_value(classification, "pdf_type", "unknown")),
        "confidence": float(_value(classification, "confidence", 0.0)),
        "page_count": int(_value(classification, "page_count", 0)),
        "has_encoding_issues": has_encoding_issues,
        "capabilities": {
            "native_text": "supported",
            "formula_semantics": "unsupported",
            "image_understanding": "unsupported",
        },
        "pages": page_reports,
        "recommendation": recommendation,
    }


def sha256_file(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
    """Hash a source file without copying it into probe output."""
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_pdf_inspector() -> object:
    """Load the optional native dependency with an actionable error."""
    try:
        return importlib.import_module("pdf_inspector")
    except ModuleNotFoundError as error:
        raise RuntimeError(
            "pdf-inspector is not installed; run scripts/probe-pdf-inspector.ps1"
        ) from error


def package_version(pdf_inspector: object) -> str:
    """Return module version, falling back to installed distribution metadata."""
    module_version = str(_value(pdf_inspector, "__version__", "")).strip()
    if module_version:
        return module_version
    try:
        return importlib.metadata.version("pdf-inspector")
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


def _classification_dict(classification: object) -> dict[str, object]:
    return {
        name: _value(classification, name, default)
        for name, default in (
            ("pdf_type", "unknown"),
            ("confidence", 0.0),
            ("page_count", 0),
            ("processing_time_ms", None),
            ("pages_needing_ocr", []),
            ("ocr_reasons_by_page", []),
            ("title", None),
            ("is_complex_layout", False),
            ("pages_with_tables", []),
            ("pages_with_columns", []),
            ("has_encoding_issues", False),
        )
    }


def _item_dict(item: object) -> dict[str, object]:
    return {
        name: _value(item, name, default)
        for name, default in (
            ("text", ""),
            ("x", 0.0),
            ("y", 0.0),
            ("width", 0.0),
            ("height", 0.0),
            ("font", ""),
            ("font_size", 0.0),
            ("page", 0),
            ("is_bold", False),
            ("is_italic", False),
            ("is_underline", False),
            ("is_strikeout", False),
            ("item_type", "text"),
            ("mcid", None),
        )
    }


def _page_artifacts(
    page_markdown: Sequence[object], positioned_items: Sequence[object]
) -> list[dict[str, object]]:
    items_by_page: dict[int, list[dict[str, object]]] = {}
    for item in positioned_items:
        page = int(_value(item, "page", 0))
        items_by_page.setdefault(page, []).append(_item_dict(item))
    return [
        {
            "page": int(_value(page, "page")) + 1,
            "markdown": str(_value(page, "markdown", "")),
            "needs_ocr": bool(_value(page, "needs_ocr", False)),
            "ocr_reason": _value(page, "ocr_reason"),
            "positioned_items": items_by_page.get(
                int(_value(page, "page")) + 1, []
            ),
        }
        for page in page_markdown
    ]


def _json_default(value: object) -> object:
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "page") and hasattr(value, "reasons"):
        return {"page": value.page, "reasons": list(value.reasons)}
    raise TypeError(f"cannot serialize {type(value).__name__}")


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, default=_json_default) + "\n",
        encoding="utf-8",
    )


def _report_markdown(report: Mapping[str, object]) -> str:
    rows = [
        "# PDF Inspector RTR4 Probe",
        "",
        f"- Recommendation: `{report['recommendation']}`",
        f"- PDF type: `{report['pdf_type']}`",
        f"- Confidence: `{report['confidence']}`",
        "- Formula semantics: unsupported",
        "- Image understanding: unsupported",
        "",
        "| Page | Route | OCR | Missing anchors | Invalid geometry |",
        "|---:|---|---|---|---:|",
    ]
    for page in report["pages"]:  # type: ignore[union-attr]
        missing = ", ".join(page["missing_anchors"]) or "-"
        rows.append(
            f"| {page['page']} | {page['route']} | {page['needs_ocr']} | "
            f"{missing} | {page['invalid_geometry_count']} |"
        )
    return "\n".join(rows) + "\n"


def run_probe(
    *,
    source_path: Path | str,
    output_dir: Path | str,
    requested_pages: Iterable[int],
    expected_anchors: Mapping[int, Sequence[str]],
    pdf_inspector: object | None = None,
) -> dict[str, object]:
    """Run selected-page extraction and atomically publish probe evidence."""
    source = Path(source_path).resolve()
    output = Path(output_dir).resolve()
    if not source.is_file():
        raise FileNotFoundError(f"source PDF not found: {source}")
    with source.open("rb") as stream:
        if stream.read(5) != b"%PDF-":
            raise ValueError(f"source does not have a PDF header: {source}")
    if output.exists():
        raise FileExistsError(f"probe output already exists: {output}")

    one_based_pages = tuple(page + 1 for page in to_zero_based_pages(requested_pages))
    zero_based_pages = list(to_zero_based_pages(one_based_pages))
    native = pdf_inspector or load_pdf_inspector()
    started_at = datetime.now(UTC)
    stopwatch = time.perf_counter()
    classification = native.detect_pdf(str(source))
    page_result = native.extract_pages_markdown(
        str(source), pages=zero_based_pages
    )
    page_markdown = list(_value(page_result, "pages", []))
    positioned_items = list(
        native.extract_text_with_positions(str(source), pages=list(one_based_pages))
    )
    elapsed_ms = round((time.perf_counter() - stopwatch) * 1000, 3)
    report = build_probe_report(
        requested_pages=one_based_pages,
        classification=classification,
        page_markdown=page_markdown,
        positioned_items=positioned_items,
        expected_anchors=expected_anchors,
    )
    report["elapsed_ms"] = elapsed_ms

    classification_data = _classification_dict(classification)
    pages_data = _page_artifacts(page_markdown, positioned_items)
    installed_version = package_version(native)
    run_data = {
        "source_path": str(source),
        "source_sha256": sha256_file(source),
        "requested_pages": list(one_based_pages),
        "pdf_inspector_version": installed_version,
        "started_at": started_at.isoformat(),
        "finished_at": datetime.now(UTC).isoformat(),
        "elapsed_ms": elapsed_ms,
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".pdf-inspector-", dir=output.parent))
    try:
        _write_json(temporary / "classification.json", classification_data)
        _write_json(temporary / "pages.json", pages_data)
        _write_json(temporary / "report.json", report)
        (temporary / "report.md").write_text(
            _report_markdown(report), encoding="utf-8"
        )
        _write_json(temporary / "run.json", run_data)
        os.replace(temporary, output)
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return report
