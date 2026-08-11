"""Application paths and local capability settings."""

from __future__ import annotations

from pathlib import Path

from pydantic import PositiveInt, field_validator

from rtr4_learning.models import ContractModel


class Settings(ContractModel):
    data_root: Path
    content_root: Path
    source_roots: tuple[Path, ...] = ()
    embedding_dimensions: PositiveInt = 64
    vision_api_key: str | None = None

    @field_validator("data_root", "content_root")
    @classmethod
    def resolve_roots(cls, value: Path) -> Path:
        return value.resolve()

    @field_validator("source_roots")
    @classmethod
    def resolve_source_roots(cls, value: tuple[Path, ...]) -> tuple[Path, ...]:
        return tuple(path.resolve() for path in value)
