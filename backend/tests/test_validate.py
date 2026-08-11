from __future__ import annotations

from rtr4_learning.models import (
    Block,
    BlockSource,
    BlockType,
    BoundingBox,
    PageDocument,
    Relation,
)
from rtr4_learning.validate import validate_pages


def _source() -> BlockSource:
    return BlockSource(parser="fixture", version="1", confidence=0.9)


def _bbox() -> BoundingBox:
    return BoundingBox(x0=0.1, y0=0.1, x1=0.9, y1=0.2)


def _codes(*pages: PageDocument) -> set[str]:
    return {issue.code for issue in validate_pages(pages)}


def test_reports_invalid_formula_representation_and_suspicious_latex() -> None:
    missing = Block.model_construct(
        id="p1-formula-1",
        type=BlockType.FORMULA,
        page=1,
        bbox=_bbox(),
        latex=None,
        asset_path=None,
        number="1",
        text=None,
        html=None,
        relations=(),
        source=_source(),
    )
    replacement = Block(
        id="p1-formula-2",
        type=BlockType.FORMULA,
        page=1,
        bbox=_bbox(),
        latex="x�y",
        number="2",
        source=_source(),
    )
    too_short = Block(
        id="p1-formula-3",
        type=BlockType.FORMULA,
        page=1,
        bbox=_bbox(),
        latex="x",
        number="3",
        source=_source(),
    )

    invalid_page = PageDocument.model_construct(
        page=1,
        blocks=(missing, replacement, too_short),
        width_points=None,
        height_points=None,
    )

    assert _codes(invalid_page) == {
        "formula_missing_representation",
        "formula_replacement_character",
        "formula_implausibly_short",
    }


def test_reports_bbox_caption_reference_and_duplicate_id_issues() -> None:
    invalid_bbox = BoundingBox.model_construct(x0=-0.1, y0=0.1, x1=1.1, y1=0.2)
    text = Block.model_construct(
        id="p1-text-1",
        type=BlockType.TEXT,
        page=1,
        bbox=invalid_bbox,
        text="See Figure 9.9 and Equation 9.8.",
        latex=None,
        html=None,
        number=None,
        asset_path=None,
        relations=(),
        source=_source(),
    )
    caption = Block(
        id="p1-figure_caption-9.9",
        type=BlockType.FIGURE_CAPTION,
        page=1,
        bbox=_bbox(),
        text="Figure 9.9",
        number="9.9",
        source=_source(),
    )
    duplicate = Block(
        id="p1-text-1",
        type=BlockType.TEXT,
        page=1,
        bbox=_bbox(),
        text="duplicate",
        source=_source(),
    )

    assert _codes(PageDocument(page=1, blocks=(text, caption, duplicate))) == {
        "bbox_out_of_range",
        "caption_without_target",
        "unknown_explicit_reference",
        "duplicate_block_id",
    }


def test_accepts_valid_caption_and_reference_relations() -> None:
    figure = Block(
        id="p1-figure-5.3",
        type=BlockType.FIGURE,
        page=1,
        bbox=_bbox(),
        number="5.3",
        source=_source(),
    )
    caption = Block(
        id="p1-figure_caption-5.3",
        type=BlockType.FIGURE_CAPTION,
        page=1,
        bbox=_bbox(),
        text="Figure 5.3",
        number="5.3",
        relations=(Relation(type="caption_of", target=figure.id),),
        source=_source(),
    )
    explanation = Block(
        id="p1-text-1",
        type=BlockType.TEXT,
        page=1,
        bbox=_bbox(),
        text="Figure 5.3 explains the vectors.",
        relations=(Relation(type="refers_to", target=figure.id),),
        source=_source(),
    )

    assert not validate_pages((PageDocument(page=1, blocks=(figure, caption, explanation)),))
