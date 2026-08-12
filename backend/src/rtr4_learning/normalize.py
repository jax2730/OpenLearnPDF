"""Normalize MinerU content-list-v2 payloads into canonical page documents."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any

from rtr4_learning.models import (
    Block,
    BlockSource,
    BlockType,
    BoundingBox,
    PageDocument,
)

_EQUATION_NUMBER = re.compile(r"\\tag\s*\{([^{}]+)\}")
_FIGURE_NUMBER = re.compile(r"(?:图|Figure)\s*([0-9]+(?:\.[0-9]+)*)", re.IGNORECASE)


class _IdAllocator:
    def __init__(self, page: int) -> None:
        self.page = page
        self.counts: defaultdict[str, int] = defaultdict(int)
        self.used: set[str] = set()

    def allocate(self, kind: str, preferred: str | None = None) -> str:
        self.counts[kind] += 1
        local_key = preferred or str(self.counts[kind])
        local_key = re.sub(r"[^A-Za-z0-9._-]+", "-", local_key).strip("-")
        if not local_key:
            local_key = str(self.counts[kind])
        candidate = f"p{self.page}-{kind}-{local_key}"
        suffix = 2
        while candidate in self.used:
            candidate = f"p{self.page}-{kind}-{local_key}-{suffix}"
            suffix += 1
        self.used.add(candidate)
        return candidate


def _text_parts(parts: object) -> str | None:
    if not isinstance(parts, list):
        return None
    output: list[str] = []
    for part in parts:
        if not isinstance(part, dict):
            continue
        content = part.get("content")
        if not isinstance(content, str):
            continue
        if part.get("type") == "equation_inline":
            output.append(f"${content}$")
        else:
            output.append(content)
    text = "".join(output).strip()
    return text or None


def _normalized_bbox(raw: object) -> BoundingBox:
    if (
        not isinstance(raw, list)
        or len(raw) != 4
        or not all(isinstance(value, int | float) for value in raw)
    ):
        raise ValueError("MinerU block bbox must contain four numeric coordinates")
    x0, y0, x1, y1 = (float(value) for value in raw)
    if not (0 <= x0 < x1 <= 1000 and 0 <= y0 < y1 <= 1000):
        raise ValueError(
            "MinerU v2 bbox must satisfy "
            "0 <= x0 < x1 <= 1000 and 0 <= y0 < y1 <= 1000"
        )
    return BoundingBox(
        x0=x0 / 1000,
        y0=y0 / 1000,
        x1=x1 / 1000,
        y1=y1 / 1000,
    )


def _source(
    *,
    parser_version: str,
    raw_artifact: str,
    raw_page_index: int,
    raw_block_index: int,
) -> BlockSource:
    return BlockSource(
        parser="mineru",
        version=parser_version,
        confidence=0.5,
        model="pipeline",
        raw_artifact=raw_artifact,
        raw_block_id=f"{raw_page_index}:{raw_block_index}",
    )


def _content(block: Mapping[str, Any]) -> Mapping[str, Any]:
    content = block.get("content", {})
    return content if isinstance(content, dict) else {}


def _asset_path(content: Mapping[str, Any]) -> str | None:
    image_source = content.get("image_source")
    if not isinstance(image_source, dict):
        return None
    path = image_source.get("path")
    return path if isinstance(path, str) and path.strip() else None


def _list_text(items: object) -> str | None:
    if not isinstance(items, list):
        return None
    texts = [
        text
        for item in items
        if isinstance(item, dict)
        if (text := _text_parts(item.get("item_content")))
    ]
    return "\n".join(texts) or None


def normalize_mineru_content_list(
    payload: Sequence[Sequence[Mapping[str, Any]]],
    *,
    first_page: int,
    page_sizes: Mapping[int, tuple[float, float]],
    raw_artifact: str,
    parser_version: str,
) -> tuple[PageDocument, ...]:
    """Convert MinerU page arrays without mutating the source payload."""
    pages: list[PageDocument] = []
    for raw_page_index, raw_blocks in enumerate(payload):
        page_number = first_page + raw_page_index
        if page_number not in page_sizes:
            raise ValueError(f"missing parser page size for page {page_number}")
        width, height = page_sizes[page_number]
        if width <= 0 or height <= 0:
            raise ValueError("parser page dimensions must be positive")
        allocator = _IdAllocator(page_number)
        normalized_blocks: list[Block] = []

        for raw_block_index, raw_block in enumerate(raw_blocks):
            block_type = raw_block.get("type")
            content = _content(raw_block)
            bbox = _normalized_bbox(raw_block.get("bbox"))
            source = _source(
                parser_version=parser_version,
                raw_artifact=raw_artifact,
                raw_page_index=raw_page_index,
                raw_block_index=raw_block_index,
            )

            if block_type == "title":
                normalized_blocks.append(
                    Block(
                        id=allocator.allocate("heading"),
                        type=BlockType.HEADING,
                        page=page_number,
                        bbox=bbox,
                        text=_text_parts(content.get("title_content")),
                        source=source,
                    )
                )
                continue

            if block_type == "paragraph":
                normalized_blocks.append(
                    Block(
                        id=allocator.allocate("paragraph"),
                        type=BlockType.TEXT,
                        page=page_number,
                        bbox=bbox,
                        text=_text_parts(content.get("paragraph_content")),
                        source=source,
                    )
                )
                continue

            if block_type == "equation_interline":
                latex = content.get("math_content")
                latex = latex if isinstance(latex, str) and latex.strip() else None
                number_match = _EQUATION_NUMBER.search(latex or "")
                number = number_match.group(1).strip() if number_match else None
                normalized_blocks.append(
                    Block(
                        id=allocator.allocate("formula", number),
                        type=BlockType.FORMULA,
                        page=page_number,
                        bbox=bbox,
                        latex=latex,
                        number=number,
                        asset_path=_asset_path(content),
                        source=source,
                    )
                )
                continue

            if block_type == "image":
                caption = _text_parts(content.get("image_caption"))
                number_match = _FIGURE_NUMBER.search(caption or "")
                number = number_match.group(1) if number_match else None
                normalized_blocks.append(
                    Block(
                        id=allocator.allocate("figure", number),
                        type=BlockType.FIGURE,
                        page=page_number,
                        bbox=bbox,
                        number=number,
                        asset_path=_asset_path(content),
                        source=source,
                    )
                )
                if caption:
                    normalized_blocks.append(
                        Block(
                            id=allocator.allocate("figure_caption", number),
                            type=BlockType.FIGURE_CAPTION,
                            page=page_number,
                            bbox=bbox,
                            text=caption,
                            number=number,
                            source=source,
                        )
                    )
                continue

            if block_type == "table":
                html = content.get("html")
                normalized_blocks.append(
                    Block(
                        id=allocator.allocate("table"),
                        type=BlockType.TABLE,
                        page=page_number,
                        bbox=bbox,
                        html=html if isinstance(html, str) and html.strip() else None,
                        asset_path=_asset_path(content),
                        source=source,
                    )
                )
                continue

            if block_type == "chart":
                normalized_blocks.append(
                    Block(
                        id=allocator.allocate("figure"),
                        type=BlockType.FIGURE,
                        page=page_number,
                        bbox=bbox,
                        asset_path=_asset_path(content),
                        source=source,
                    )
                )
                continue

            if block_type in {"code", "algorithm"}:
                normalized_blocks.append(
                    Block(
                        id=allocator.allocate("code"),
                        type=BlockType.CODE,
                        page=page_number,
                        bbox=bbox,
                        text=_text_parts(content.get(f"{block_type}_content")),
                        source=source,
                    )
                )
                continue

            if block_type in {"list", "index"}:
                normalized_blocks.append(
                    Block(
                        id=allocator.allocate("list"),
                        type=BlockType.LIST,
                        page=page_number,
                        bbox=bbox,
                        text=_list_text(content.get("list_items")),
                        source=source,
                    )
                )
                continue

            if block_type in {"page_aside_text", "page_footnote"}:
                normalized_blocks.append(
                    Block(
                        id=allocator.allocate("text"),
                        type=BlockType.TEXT,
                        page=page_number,
                        bbox=bbox,
                        text=_text_parts(content.get(f"{block_type}_content")),
                        source=source,
                    )
                )
                continue

            if block_type in {"page_footer", "page_number", "page_header"}:
                canonical_type = (
                    BlockType.PAGE_HEADER
                    if block_type == "page_header"
                    else BlockType.PAGE_FOOTER
                )
                content_key = f"{block_type}_content"
                normalized_blocks.append(
                    Block(
                        id=allocator.allocate(canonical_type.value),
                        type=canonical_type,
                        page=page_number,
                        bbox=bbox,
                        text=_text_parts(content.get(content_key)),
                        source=source,
                    )
                )
                continue

            raise ValueError(f"unsupported MinerU block type: {block_type!r}")

        pages.append(
            PageDocument(
                page=page_number,
                blocks=tuple(normalized_blocks),
                width_points=width,
                height_points=height,
            )
        )
    return tuple(pages)


def normalized_pages_json(pages: Sequence[PageDocument]) -> str:
    """Serialize normalized pages deterministically for cache fingerprints."""
    payload = [page.model_dump(mode="json") for page in pages]
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
