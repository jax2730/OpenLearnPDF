from __future__ import annotations

import json
from itertools import pairwise
from pathlib import Path

from rtr4_learning.models import (
    Block,
    BlockSource,
    BlockType,
    BoundingBox,
    PageDocument,
)
from rtr4_learning.normalize import normalize_mineru_content_list
from rtr4_learning.relations import link_relations

FIXTURE_PATH = (
    Path(__file__).parent
    / "fixtures"
    / "mineru"
    / "probe-104-106-content-list-v2.json"
)
PAGE_SIZES = {page: (595.0, 842.0) for page in (104, 105, 106)}


def _normalized_pages():
    raw = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    return normalize_mineru_content_list(
        raw,
        first_page=104,
        page_sizes=PAGE_SIZES,
        raw_artifact="data/probes/rtr4-content-list-v2.json",
        parser_version="3.4.4",
    )


def _targets(block, relation_type: str) -> set[str]:
    return {
        relation.target
        for relation in block.relations
        if relation.type == relation_type
    }


def test_links_caption_to_figure_and_explicit_references() -> None:
    pages = link_relations(_normalized_pages())
    blocks = [block for page in pages for block in page.blocks]
    caption = next(block for block in blocks if block.type is BlockType.FIGURE_CAPTION)
    explanation = next(block for block in pages[2].blocks if block.type is BlockType.TEXT)

    assert _targets(caption, "caption_of") == {"p104-figure-5.3"}
    assert _targets(explanation, "refers_to") == {
        "p104-figure-5.3",
        "p105-formula-5.1",
    }


def test_links_reading_order_and_section_membership_without_mutating_input() -> None:
    original = _normalized_pages()
    linked = link_relations(original)
    heading_id = next(
        block.id
        for block in linked[0].blocks
        if block.type is BlockType.HEADING
    )

    assert all(not block.relations for page in original for block in page.blocks)
    ordered = [block for page in linked for block in page.blocks]
    for current, following in pairwise(ordered):
        assert _targets(current, "next_block") == {following.id}
    assert not _targets(ordered[-1], "next_block")

    for page in linked:
        for block in page.blocks:
            if block.type is not BlockType.HEADING:
                assert _targets(block, "belongs_to_section") == {heading_id}


def test_duplicate_figure_numbers_link_each_caption_to_its_own_figure() -> None:
    raw = [[
        {
            "type": "image",
            "content": {
                "image_source": {"path": "images/first.jpg"},
                "image_caption": [{"type": "text", "content": "Figure 5.3 first"}],
            },
            "bbox": [10, 10, 100, 100],
        },
        {
            "type": "image",
            "content": {
                "image_source": {"path": "images/second.jpg"},
                "image_caption": [{"type": "text", "content": "Figure 5.3 second"}],
            },
            "bbox": [110, 10, 200, 100],
        },
    ]]
    pages = normalize_mineru_content_list(
        raw,
        first_page=1,
        page_sizes={1: (595.0, 842.0)},
        raw_artifact="probe.json",
        parser_version="3.4.4",
    )
    captions = [
        block
        for block in link_relations(pages)[0].blocks
        if block.type is BlockType.FIGURE_CAPTION
    ]

    assert [_targets(block, "caption_of") for block in captions] == [
        {"p1-figure-5.3"},
        {"p1-figure-5.3-2"},
    ]


def test_reference_matching_requires_a_word_boundary_and_known_target() -> None:
    raw = [[
        {
            "type": "image",
            "content": {
                "image_source": {"path": "images/figure.jpg"},
                "image_caption": [{"type": "text", "content": "Figure 5.3"}],
            },
            "bbox": [10, 10, 100, 100],
        },
        {
            "type": "paragraph",
            "content": {
                "paragraph_content": [{
                    "type": "text",
                    "content": "configure 5.3 and Figure 5.4",
                }],
            },
            "bbox": [10, 110, 500, 200],
        },
    ]]
    pages = normalize_mineru_content_list(
        raw,
        first_page=1,
        page_sizes={1: (595.0, 842.0)},
        raw_artifact="probe.json",
        parser_version="3.4.4",
    )
    paragraph = next(
        block
        for block in link_relations(pages)[0].blocks
        if block.type is BlockType.TEXT
    )

    assert not _targets(paragraph, "refers_to")


def test_numbered_caption_does_not_fall_back_to_wrong_previous_figure() -> None:
    source = BlockSource(parser="mineru", version="3.4.4", confidence=0.5)
    bbox = BoundingBox(x0=0.1, y0=0.1, x1=0.2, y1=0.2)
    page = PageDocument(
        page=1,
        blocks=(
            Block(
                id="p1-figure-5.3",
                type=BlockType.FIGURE,
                page=1,
                bbox=bbox,
                number="5.3",
                source=source,
            ),
            Block(
                id="p1-figure_caption-5.4",
                type=BlockType.FIGURE_CAPTION,
                page=1,
                bbox=bbox,
                text="Figure 5.4",
                number="5.4",
                source=source,
            ),
        ),
    )

    caption = link_relations((page,))[0].blocks[1]

    assert not _targets(caption, "caption_of")
