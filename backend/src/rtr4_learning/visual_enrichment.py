"""Source-reviewed visual enrichment policy."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator, model_validator

from rtr4_learning.models import BoundingBox, ContractModel

_FIXED_FIGURES = (
    ("5.6", 112),
    ("5.15", 126),
    ("5.16", 126),
    ("5.18", 128),
    ("5.22", 130),
    ("5.23", 131),
    ("5.41", 153),
)


class VisualFigure(ContractModel):
    number: Annotated[str, Field(pattern=r"^5\.[0-9]+$")]
    page: Annotated[int, Field(ge=104, le=154)]
    bbox: BoundingBox
    caption: Annotated[str, Field(min_length=1)]
    crop_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    evidence: Annotated[str, Field(min_length=1)]

    @field_validator("bbox", mode="before")
    @classmethod
    def parse_bbox(cls, value: object) -> object:
        if isinstance(value, list) and len(value) == 4:
            return dict(zip(("x0", "y0", "x1", "y1"), value, strict=True))
        return value


class VisualEnrichmentPolicy(ContractModel):
    schema_version: int
    render_scale: Annotated[int, Field(ge=1, le=8)]
    figures: tuple[VisualFigure, ...]

    @model_validator(mode="after")
    def fixed_chapter_policy(self) -> VisualEnrichmentPolicy:
        if self.schema_version != 1:
            raise ValueError("visual enrichment schema_version must be 1")
        if tuple((figure.number, figure.page) for figure in self.figures) != _FIXED_FIGURES:
            raise ValueError("visual enrichment figures do not match chapter 5 policy")
        return self


def load_visual_enrichments(path: str | Path) -> VisualEnrichmentPolicy:
    payload = json.loads(Path(path).read_bytes())
    return VisualEnrichmentPolicy.model_validate(payload)
