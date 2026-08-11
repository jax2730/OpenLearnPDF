from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from rtr4_learning.models import BlockType
from rtr4_learning.normalize import (
    normalize_mineru_content_list,
    normalized_pages_json,
)

FIXTURE_PATH = (
    Path(__file__).parent
    / "fixtures"
    / "mineru"
    / "probe-104-106-content-list-v2.json"
)
PAGE_SIZES = {page: (595.0, 842.0) for page in (104, 105, 106)}
RAW_ARTIFACT = "data/probes/rtr4-content-list-v2.json"


def _load_fixture() -> list[list[dict[str, object]]]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _normalize():
    return normalize_mineru_content_list(
        _load_fixture(),
        first_page=104,
        page_sizes=PAGE_SIZES,
        raw_artifact=RAW_ARTIFACT,
        parser_version="3.4.4",
    )


def test_normalizes_formula_coordinates_number_and_provenance() -> None:
    pages = _normalize()
    formula = next(
        block
        for block in pages[1].blocks
        if block.type is BlockType.FORMULA and block.number == "5.1"
    )

    assert [page.page for page in pages] == [104, 105, 106]
    assert formula.id == "p105-formula-5.1"
    assert formula.latex == r"a=b\tag{5.1}"
    assert formula.asset_path == "images/representative-equation-5-1.jpg"
    assert formula.bbox.x0 == pytest.approx(262 / 1000)
    assert formula.bbox.y0 == pytest.approx(847 / 1000)
    assert formula.bbox.x1 == pytest.approx(734 / 1000)
    assert formula.bbox.y1 == pytest.approx(868 / 1000)
    assert pages[1].width_points == 595
    assert pages[1].height_points == 842
    assert formula.source.raw_artifact == RAW_ARTIFACT
    assert formula.source.raw_block_id == "1:1"


def test_splits_figure_and_caption_into_separate_blocks() -> None:
    page = _normalize()[0]
    figure = next(block for block in page.blocks if block.type is BlockType.FIGURE)
    caption = next(
        block for block in page.blocks if block.type is BlockType.FIGURE_CAPTION
    )

    assert figure.id == "p104-figure-5.3"
    assert figure.number == "5.3"
    assert figure.asset_path == "images/representative-figure.jpg"
    assert caption.id == "p104-figure_caption-5.3"
    assert caption.number == "5.3"
    assert caption.text == "图5.3：示例图。"
    assert figure.source.raw_block_id == caption.source.raw_block_id == "0:1"


def test_normalization_is_stable_deterministic_and_does_not_mutate_raw() -> None:
    raw = _load_fixture()
    original = copy.deepcopy(raw)

    first = normalize_mineru_content_list(
        raw,
        first_page=104,
        page_sizes=PAGE_SIZES,
        raw_artifact=RAW_ARTIFACT,
        parser_version="3.4.4",
    )
    second = _normalize()

    assert raw == original
    assert [block.id for page in first for block in page.blocks] == [
        block.id for page in second for block in page.blocks
    ]
    assert next(
        block.id
        for block in first[2].blocks
        if block.type is BlockType.TEXT
    ) == "p106-paragraph-1"
    assert normalized_pages_json(first) == normalized_pages_json(second)


def test_normalizes_all_mineru_v2_block_families() -> None:
    text_part = [{"type": "text", "content": "sample"}]
    payload = [[
        {
            "type": "table",
            "content": {
                "image_source": {"path": "images/table.jpg"},
                "html": "<table><tr><td>x</td></tr></table>",
            },
            "bbox": [10, 10, 100, 100],
        },
        {
            "type": "chart",
            "content": {"image_source": {"path": "images/chart.jpg"}},
            "bbox": [110, 10, 200, 100],
        },
        {
            "type": "code",
            "content": {"code_content": text_part},
            "bbox": [210, 10, 300, 100],
        },
        {
            "type": "algorithm",
            "content": {"algorithm_content": text_part},
            "bbox": [310, 10, 400, 100],
        },
        {
            "type": "list",
            "content": {"list_items": [{"item_content": text_part}]},
            "bbox": [410, 10, 500, 100],
        },
        {
            "type": "index",
            "content": {"list_items": [{"item_content": text_part}]},
            "bbox": [510, 10, 600, 100],
        },
        {
            "type": "page_aside_text",
            "content": {"page_aside_text_content": text_part},
            "bbox": [610, 10, 700, 100],
        },
        {
            "type": "page_footnote",
            "content": {"page_footnote_content": text_part},
            "bbox": [710, 10, 800, 100],
        },
    ]]

    page = normalize_mineru_content_list(
        payload,
        first_page=1,
        page_sizes={1: (595.0, 842.0)},
        raw_artifact=RAW_ARTIFACT,
        parser_version="3.4.4",
    )[0]

    assert [block.type for block in page.blocks] == [
        BlockType.TABLE,
        BlockType.FIGURE,
        BlockType.CODE,
        BlockType.CODE,
        BlockType.LIST,
        BlockType.LIST,
        BlockType.TEXT,
        BlockType.TEXT,
    ]
    assert page.blocks[0].html == "<table><tr><td>x</td></tr></table>"
    assert page.blocks[1].asset_path == "images/chart.jpg"
    assert [block.text for block in page.blocks[2:]] == [
        "sample",
        "sample",
        "sample",
        "sample",
        "sample",
        "sample",
    ]
