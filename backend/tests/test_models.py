import pytest
from pydantic import ValidationError

from rtr4_learning.models import Block, BlockSource, BlockType, BoundingBox, Relation


def formula_block(**overrides: object) -> Block:
    values: dict[str, object] = {
        "id": "p105-equation-5.1",
        "type": BlockType.FORMULA,
        "page": 105,
        "bbox": BoundingBox(x0=0.1, y0=0.5, x1=0.9, y1=0.6),
        "latex": r"c_{shaded}=s c_{highlight}",
        "number": "5.1",
        "asset_path": "blocks/p105-equation-5.1.png",
        "relations": [Relation(type="explained_by", target="p106-paragraph-2")],
        "source": BlockSource(parser="fixture", version="1", confidence=0.9),
    }
    values.update(overrides)
    return Block(**values)


def test_formula_block_round_trips() -> None:
    block = formula_block()

    assert Block.model_validate_json(block.model_dump_json()) == block


@pytest.mark.parametrize(
    ("field", "value"),
    [("x0", -0.1), ("y0", -0.1), ("x1", 1.1), ("y1", 1.1)],
)
def test_bbox_rejects_out_of_range_coordinates(field: str, value: float) -> None:
    coordinates = {"x0": 0.0, "y0": 0.0, "x1": 1.0, "y1": 1.0}
    coordinates[field] = value

    with pytest.raises(ValidationError):
        BoundingBox(**coordinates)


@pytest.mark.parametrize(
    "coordinates",
    [
        {"x0": 0.8, "y0": 0.1, "x1": 0.2, "y1": 0.9},
        {"x0": 0.1, "y0": 0.8, "x1": 0.9, "y1": 0.2},
    ],
)
def test_bbox_rejects_reversed_rectangle(coordinates: dict[str, float]) -> None:
    with pytest.raises(ValidationError):
        BoundingBox(**coordinates)


def test_formula_requires_latex_or_asset() -> None:
    with pytest.raises(ValidationError):
        formula_block(latex=None, asset_path=None)


def test_figure_caption_relation_requires_stable_target_id() -> None:
    with pytest.raises(ValidationError):
        Block(
            id="p105-figure-caption-1",
            type=BlockType.FIGURE_CAPTION,
            page=105,
            bbox=BoundingBox(x0=0.1, y0=0.5, x1=0.9, y1=0.6),
            text="图 5.1 示例",
            relations=[Relation(type="caption_of", target="figure one")],
            source=BlockSource(parser="fixture", version="1", confidence=0.9),
        )


@pytest.mark.parametrize("page", [0, -1])
def test_page_must_be_positive(page: int) -> None:
    with pytest.raises(ValidationError):
        formula_block(page=page)


@pytest.mark.parametrize("confidence", [-0.01, 1.01])
def test_confidence_must_be_between_zero_and_one(confidence: float) -> None:
    with pytest.raises(ValidationError):
        BlockSource(parser="fixture", version="1", confidence=confidence)
