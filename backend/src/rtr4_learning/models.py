"""Canonical document contracts shared by pipeline stages."""

from collections.abc import Mapping
from enum import Enum
from pathlib import Path
from types import MappingProxyType
from typing import Annotated, TypeAlias

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    NonNegativeInt,
    PositiveInt,
    field_serializer,
    field_validator,
    model_validator,
)

StableBlockId = Annotated[
    str,
    Field(pattern=r"^p[1-9]\d*-[a-z][a-z0-9_-]*-[A-Za-z0-9][A-Za-z0-9._-]*$"),
]
Confidence = Annotated[float, Field(ge=0.0, le=1.0)]
NormalizedCoordinate = Annotated[float, Field(ge=0.0, le=1.0)]
JsonScalar: TypeAlias = str | bool | int | float | None
ImmutableJson: TypeAlias = (
    JsonScalar | tuple["ImmutableJson", ...] | Mapping[str, "ImmutableJson"]
)


def _freeze_json(value: JsonValue) -> ImmutableJson:
    if isinstance(value, dict):
        return MappingProxyType(
            {key: _freeze_json(item) for key, item in value.items()}
        )
    if isinstance(value, list):
        return tuple(_freeze_json(item) for item in value)
    return value


def _thaw_json(value: ImmutableJson) -> JsonValue:
    if isinstance(value, Mapping):
        return {key: _thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_json(item) for item in value]
    return value


class ContractModel(BaseModel):
    model_config = ConfigDict(
        allow_inf_nan=False,
        extra="forbid",
        frozen=True,
        validate_default=True,
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
    correction_artifact: str | None = None
    correction_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")] | None = None
    correction_evidence: str | None = None
    enrichment_artifact: str | None = None
    enrichment_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")] | None = None
    enrichment_evidence: str | None = None


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
    relations: tuple[Relation, ...] = Field(default_factory=tuple)
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
            self.latex
            and self.latex.strip()
            or self.asset_path
            and self.asset_path.strip()
        ):
            raise ValueError("formula block requires latex or asset_path")
        return self


class PageDocument(ContractModel):
    page: PositiveInt
    blocks: tuple[Block, ...] = Field(default_factory=tuple)
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
    pages: tuple[str, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def validate_page_range(self) -> "ChapterManifest":
        if self.start_page > self.end_page:
            raise ValueError("chapter start_page must be <= end_page")
        return self


class BookManifest(ContractModel):
    id: Annotated[str, Field(min_length=1)]
    title: Annotated[str, Field(min_length=1)]
    source_path: Annotated[str, Field(min_length=1)]
    source_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    page_count: PositiveInt
    chapters: tuple[ChapterManifest, ...] = Field(default_factory=tuple)

    @field_validator("id", "title")
    @classmethod
    def strip_non_blank_identity(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("book identity fields must not be blank")
        return value

    @field_validator("source_path")
    @classmethod
    def validate_absolute_source_path(cls, value: str) -> str:
        if not Path(value).is_absolute():
            raise ValueError("source_path must be absolute")
        return value

    @model_validator(mode="after")
    def validate_chapters(self) -> "BookManifest":
        if any(chapter.end_page > self.page_count for chapter in self.chapters):
            raise ValueError("chapter end_page must be <= book page_count")
        chapter_ids = [chapter.id for chapter in self.chapters]
        if len(chapter_ids) != len(set(chapter_ids)):
            raise ValueError("book chapter IDs must be unique")
        return self


class StageManifest(ContractModel):
    stage: Annotated[str, Field(min_length=1)]
    version: Annotated[str, Field(min_length=1)]
    fingerprint: Annotated[str, Field(min_length=1)]
    inputs: Mapping[str, JsonValue] = Field(default_factory=dict)
    outputs: tuple[str, ...] = Field(default_factory=tuple)
    artifacts: tuple["StageArtifact", ...] = Field(default_factory=tuple)

    @field_validator("inputs")
    @classmethod
    def freeze_inputs(
        cls, value: Mapping[str, JsonValue]
    ) -> Mapping[str, ImmutableJson]:
        return MappingProxyType(
            {key: _freeze_json(item) for key, item in value.items()}
        )

    @field_serializer("inputs")
    def serialize_inputs(
        self, value: Mapping[str, ImmutableJson]
    ) -> dict[str, JsonValue]:
        return {key: _thaw_json(item) for key, item in value.items()}


class StageArtifact(ContractModel):
    path: Annotated[str, Field(min_length=1)]
    size: NonNegativeInt
    sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    pixel_width: PositiveInt | None = None
    pixel_height: PositiveInt | None = None

    @field_validator("path")
    @classmethod
    def validate_relative_artifact_path(cls, value: str) -> str:
        path = Path(value)
        if path.is_absolute() or ".." in path.parts or "\\" in value:
            raise ValueError("artifact path must be a safe POSIX-style relative path")
        return value

    @model_validator(mode="after")
    def validate_pixel_dimensions(self) -> "StageArtifact":
        if (self.pixel_width is None) != (self.pixel_height is None):
            raise ValueError("artifact pixel dimensions must be provided together")
        return self
