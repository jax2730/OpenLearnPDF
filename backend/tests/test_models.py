import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from rtr4_learning.models import (
    Block,
    BlockSource,
    BlockType,
    BookManifest,
    BoundingBox,
    ChapterManifest,
    PageDocument,
    Relation,
    StageManifest,
)


def valid_book_manifest(**overrides: object) -> BookManifest:
    values: dict[str, object] = {
        "id": "rtr4-cn",
        "title": "Real-Time Rendering 4th Edition",
        "source_path": str(Path(__file__).resolve()),
        "source_sha256": "a" * 64,
        "page_count": 154,
        "chapters": [
            ChapterManifest(
                id="5",
                title="5",
                start_page=104,
                end_page=154,
            )
        ],
    }
    values.update(overrides)
    return BookManifest(**values)


@pytest.mark.parametrize("field", ["id", "title"])
@pytest.mark.parametrize("value", ["", "   "])
def test_book_identity_fields_reject_blank_values(field: str, value: str) -> None:
    with pytest.raises(ValidationError):
        valid_book_manifest(**{field: value})


def test_book_source_path_must_be_absolute() -> None:
    with pytest.raises(ValidationError):
        valid_book_manifest(source_path="books/rtr4.pdf")


@pytest.mark.parametrize(
    "source_sha256",
    ["a" * 63, "a" * 65, "G" * 64, "A" * 64],
)
def test_book_source_sha256_must_be_lowercase_hex(source_sha256: str) -> None:
    with pytest.raises(ValidationError):
        valid_book_manifest(source_sha256=source_sha256)


def test_book_chapter_must_not_exceed_page_count() -> None:
    chapter = ChapterManifest(id="5", title="5", start_page=104, end_page=154)

    with pytest.raises(ValidationError, match="page_count"):
        valid_book_manifest(page_count=153, chapters=[chapter])


def test_book_chapter_ids_must_be_unique() -> None:
    chapters = [
        ChapterManifest(id="5", title="5", start_page=104, end_page=120),
        ChapterManifest(id="5", title="Duplicate", start_page=121, end_page=154),
    ]

    with pytest.raises(ValidationError, match="chapter IDs"):
        valid_book_manifest(chapters=chapters)


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


@pytest.mark.parametrize(
    "coordinates",
    [
        {"x0": 0.2, "y0": 0.1, "x1": 0.2, "y1": 0.9},
        {"x0": 0.1, "y0": 0.2, "x1": 0.9, "y1": 0.2},
        {"x0": 0.2, "y0": 0.2, "x1": 0.2, "y1": 0.2},
    ],
)
def test_bbox_rejects_zero_area_rectangle(coordinates: dict[str, float]) -> None:
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


def test_block_id_page_must_match_block_page() -> None:
    with pytest.raises(ValidationError):
        formula_block(id="p104-equation-5.1")


def test_page_document_rejects_blocks_from_another_page() -> None:
    with pytest.raises(ValidationError):
        PageDocument(page=106, blocks=[formula_block()])


@pytest.mark.parametrize("confidence", [-0.01, 1.01])
def test_confidence_must_be_between_zero_and_one(confidence: float) -> None:
    with pytest.raises(ValidationError):
        BlockSource(parser="fixture", version="1", confidence=confidence)


def test_contract_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        BoundingBox(x0=0, y0=0, x1=1, y1=1, coordinate_system="bottom-left")


def test_invalid_bbox_assignment_preserves_original_state() -> None:
    bbox = BoundingBox(x0=0.1, y0=0.2, x1=0.9, y1=0.8)
    original = bbox.model_copy(deep=True)

    with pytest.raises(ValidationError):
        bbox.x1 = 0.0

    assert bbox == original


def test_block_page_assignment_preserves_original_state() -> None:
    block = formula_block()
    original = block.model_copy(deep=True)

    with pytest.raises(ValidationError):
        block.page = 104

    assert block == original


def test_structural_collections_cannot_be_modified_in_place() -> None:
    block = formula_block()
    page = PageDocument(page=105, blocks=[block])

    with pytest.raises(AttributeError):
        block.relations.append(Relation(type="refers_to", target="p105-figure-1"))
    with pytest.raises(AttributeError):
        page.blocks.append(block)


def test_page_document_tuple_fields_round_trip_as_json_arrays() -> None:
    page = PageDocument(page=105, blocks=[formula_block()])
    payload = page.model_dump_json()

    assert isinstance(json.loads(payload)["blocks"], list)
    assert PageDocument.model_validate_json(payload) == page


def test_stage_inputs_nested_json_round_trips() -> None:
    manifest = StageManifest(
        stage="normalize",
        version="1",
        fingerprint="abc123",
        inputs={
            "pages": [104, 105],
            "config": {"enabled": True, "threshold": 0.9},
            "label": None,
        },
        outputs=["pages/105.json"],
    )

    dumped = manifest.model_dump(mode="json")
    assert isinstance(dumped["inputs"], dict)
    assert isinstance(dumped["inputs"]["pages"], list)
    assert isinstance(dumped["outputs"], list)
    assert isinstance(json.loads(manifest.model_dump_json())["outputs"], list)
    assert StageManifest.model_validate_json(manifest.model_dump_json()) == manifest


def stage_manifest_with_nested_inputs() -> StageManifest:
    return StageManifest(
        stage="normalize",
        version="1",
        fingerprint="abc123",
        inputs={"pages": [104, 105], "config": {"enabled": True}},
    )


def test_stage_inputs_top_level_mapping_is_immutable() -> None:
    manifest = stage_manifest_with_nested_inputs()
    original = manifest.model_dump_json()

    with pytest.raises(TypeError):
        manifest.inputs["x"] = 1

    assert manifest.model_dump_json() == original


def test_stage_inputs_nested_array_is_immutable() -> None:
    manifest = stage_manifest_with_nested_inputs()
    original = manifest.model_dump_json()

    with pytest.raises(AttributeError):
        manifest.inputs["pages"].append(106)

    assert manifest.model_dump_json() == original


def test_stage_inputs_nested_mapping_is_immutable() -> None:
    manifest = stage_manifest_with_nested_inputs()
    original = manifest.model_dump_json()

    with pytest.raises(TypeError):
        manifest.inputs["config"]["enabled"] = False

    assert manifest.model_dump_json() == original


@pytest.mark.parametrize(
    "unsafe_value", [object(), float("nan"), float("inf"), -float("inf")]
)
def test_stage_inputs_reject_non_json_values(unsafe_value: object) -> None:
    with pytest.raises(ValidationError):
        StageManifest(
            stage="normalize",
            version="1",
            fingerprint="abc123",
            inputs={"nested": {"unsafe": unsafe_value}},
        )
