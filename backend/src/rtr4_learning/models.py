"""Canonical document contracts shared by pipeline stages."""

from enum import Enum
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    PositiveInt,
    model_validator,
)

StableBlockId = Annotated[
    str,
    Field(pattern=r"^p[1-9]\d*-[a-z][a-z0-9_-]*-[A-Za-z0-9][A-Za-z0-9._-]*$"),
]
Confidence = Annotated[float, Field(ge=0.0, le=1.0)]
NormalizedCoordinate = Annotated[float, Field(ge=0.0, le=1.0)]


class ContractModel(BaseModel):
    model_config = ConfigDict(
        allow_inf_nan=False,
        extra="forbid",
        validate_assignment=True,
    )


class BlockType(str, Enum):
    TEXT = "text"
    HEADING = "heading"
    FORMULA = "formula"
    FIGURE = "figure"
    FIGURE_CAPTION = "figure_caption"
    TABLE = "table"
    CODE = "code"
    LIST = "list"
    PAGE_HEADER = "page_header"
    PAGE_FOOTER = "page_footer"


class BoundingBox(ContractModel):
    """Normalized top-left rectangle, including both zero and one."""

    x0: NormalizedCoordinate
    y0: NormalizedCoordinate
    x1: NormalizedCoordinate
    y1: NormalizedCoordinate

    @model_validator(mode="after")
    def validate_rectangle_order(self) -> "BoundingBox":
        if self.x0 >= self.x1 or self.y0 >= self.y1:
            raise ValueError("bbox must satisfy x0 < x1 and y0 < y1")
        return self


class Relation(ContractModel):
    type: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]*$")]
    target: StableBlockId


class BlockSource(ContractModel):
    """Parser provenance for one normalized block."""

    parser: Annotated[str, Field(min_length=1)]
    version: Annotated[str, Field(min_length=1)]
    confidence: Confidence
    model: str | None = None
    raw_artifact: str | None = None
    raw_block_id: str | int | None = None


class Block(ContractModel):
    id: StableBlockId
    type: BlockType
    page: PositiveInt
    bbox: BoundingBox
    text: str | None = None
    latex: str | None = None
    html: str | None = None
    number: str | None = None
    asset_path: str | None = None
    relations: list[Relation] = Field(default_factory=list)
    source: BlockSource

    @model_validator(mode="after")
    def validate_id_page(self) -> "Block":
        id_page = int(self.id.split("-", maxsplit=1)[0][1:])
        if id_page != self.page:
            raise ValueError("block id page must match block page")
        return self

    @model_validator(mode="after")
    def validate_formula_representation(self) -> "Block":
        if self.type is BlockType.FORMULA and not (
            self.latex and self.latex.strip() or self.asset_path and self.asset_path.strip()
        ):
            raise ValueError("formula block requires latex or asset_path")
        return self


class PageDocument(ContractModel):
    page: PositiveInt
    blocks: list[Block] = Field(default_factory=list)
    width_points: Annotated[float, Field(gt=0)] | None = None
    height_points: Annotated[float, Field(gt=0)] | None = None

    @model_validator(mode="after")
    def validate_block_pages(self) -> "PageDocument":
        if any(block.page != self.page for block in self.blocks):
            raise ValueError("all blocks must belong to the document page")
        return self


class ChapterManifest(ContractModel):
    id: Annotated[str, Field(min_length=1)]
    title: str
    start_page: PositiveInt
    end_page: PositiveInt
    pages: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_page_range(self) -> "ChapterManifest":
        if self.start_page > self.end_page:
            raise ValueError("chapter start_page must be <= end_page")
        return self


class BookManifest(ContractModel):
    id: Annotated[str, Field(min_length=1)]
    title: str
    source_path: Annotated[str, Field(min_length=1)]
    source_sha256: Annotated[str, Field(min_length=1)]
    page_count: PositiveInt
    chapters: list[ChapterManifest] = Field(default_factory=list)


class StageManifest(ContractModel):
    stage: Annotated[str, Field(min_length=1)]
    version: Annotated[str, Field(min_length=1)]
    fingerprint: Annotated[str, Field(min_length=1)]
    inputs: dict[str, JsonValue] = Field(default_factory=dict)
    outputs: list[str] = Field(default_factory=list)
