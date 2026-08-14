"""Pure report helpers for the optional pdf-inspector evaluation probe."""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
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
