"""Small shared contract for raw document parsers."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Annotated, Protocol

from pydantic import Field, field_validator

from rtr4_learning.models import ContractModel

StrictPositivePage = Annotated[int, Field(strict=True, gt=0)]


def canonical_pages(pages: Iterable[int]) -> tuple[int, ...]:
    """Return sorted, unique, contiguous one-based PDF page numbers."""
    values = tuple(pages)
    if not values:
        raise ValueError("pages must not be empty")
    if any(
        isinstance(page, bool) or not isinstance(page, int) or page <= 0
        for page in values
    ):
        raise ValueError("pages must contain positive one-based integers")
    canonical = tuple(sorted(set(values)))
    if canonical[-1] - canonical[0] + 1 != len(canonical):
        raise ValueError("pages must form one contiguous range")
    return canonical


class RawParseResult(ContractModel):
    """Immutable pointers to one parser's unnormalized output artifacts."""

    parser_name: Annotated[str, Field(min_length=1)]
    parser_version: Annotated[str, Field(min_length=1)]
    requested_pages: tuple[StrictPositivePage, ...]
    raw_json_path: Path
    markdown_path: Path
    asset_dir: Path
    fingerprint: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]

    @field_validator("requested_pages")
    @classmethod
    def validate_requested_pages(cls, value: tuple[int, ...]) -> tuple[int, ...]:
        return canonical_pages(value)

    @field_validator("raw_json_path", "markdown_path", "asset_dir")
    @classmethod
    def validate_absolute_artifact_path(cls, value: Path) -> Path:
        if not value.is_absolute():
            raise ValueError("raw parser artifact paths must be absolute")
        return value


class DocumentParser(Protocol):
    """Parser boundary; outputs stay raw until the normalization stage."""

    parser_name: str
    parser_version: str

    def parse(
        self,
        *,
        source_path: Path | str | None = None,
        pages: Iterable[int],
        output_dir: Path | str | None = None,
    ) -> RawParseResult: ...
