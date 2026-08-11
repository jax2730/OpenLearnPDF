"""Deterministic visual-enrichment request cache and provider contracts."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType
from typing import Annotated, Literal, Protocol, runtime_checkable

from pydantic import Field, field_serializer, field_validator

from rtr4_learning.models import ContractModel, ImmutableJson, JsonValue

CacheKey = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
_CACHE_KEY = re.compile(r"^[0-9a-f]{64}$")


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


def _canonical_options(options: Mapping[str, JsonValue]) -> str:
    return json.dumps(
        {key: _thaw_json(value) for key, value in options.items()},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def enrichment_cache_key(
    crop_bytes: bytes,
    *,
    provider: str,
    model: str,
    prompt_version: str,
    options: Mapping[str, JsonValue],
) -> str:
    """Hash crop content and every inference-affecting option."""
    digest = hashlib.sha256()
    for value in (
        crop_bytes,
        provider.encode("utf-8"),
        model.encode("utf-8"),
        prompt_version.encode("utf-8"),
        _canonical_options(options).encode("utf-8"),
    ):
        digest.update(len(value).to_bytes(8, "big"))
        digest.update(value)
    return digest.hexdigest()


class EnrichmentRequest(ContractModel):
    key: CacheKey
    crop_sha256: CacheKey
    provider: Annotated[str, Field(min_length=1)]
    model: Annotated[str, Field(min_length=1)]
    prompt_version: Annotated[str, Field(min_length=1)]
    options: Mapping[str, JsonValue] = Field(default_factory=dict)
    status: Literal["pending"] = "pending"

    @field_validator("options")
    @classmethod
    def freeze_options(
        cls, value: Mapping[str, JsonValue]
    ) -> Mapping[str, ImmutableJson]:
        return MappingProxyType(
            {key: _freeze_json(item) for key, item in value.items()}
        )

    @field_serializer("options")
    def serialize_options(
        self, value: Mapping[str, ImmutableJson]
    ) -> dict[str, JsonValue]:
        return {key: _thaw_json(item) for key, item in value.items()}


class EnrichmentResult(ContractModel):
    key: CacheKey
    status: Literal["succeeded", "failed", "unavailable"]
    latex: str | None = None
    description: str | None = None
    error: str | None = None


@runtime_checkable
class VisionEnricher(Protocol):
    available: bool
    model: str

    def enrich(
        self,
        request: EnrichmentRequest,
        crop_bytes: bytes,
    ) -> EnrichmentResult: ...


class UnavailableVisionEnricher:
    available = False
    model = "unavailable"

    def __init__(self, *, reason: str) -> None:
        self.reason = reason

    def enrich(
        self,
        request: EnrichmentRequest,
        crop_bytes: bytes,
    ) -> EnrichmentResult:
        del crop_bytes
        return EnrichmentResult(
            key=request.key,
            status="unavailable",
            error=self.reason,
        )


class OpenAICompatibleVisionEnricher:
    """Configuration shell; live calls remain explicitly disabled in MVP."""

    available = True
    live_calls_enabled = False

    def __init__(self, *, endpoint: str, api_key: str, model: str) -> None:
        if not endpoint.strip() or not api_key.strip() or not model.strip():
            raise ValueError("endpoint, API key, and model must be non-empty")
        self.endpoint = endpoint
        self.api_key = api_key
        self.model = model

    def enrich(
        self,
        request: EnrichmentRequest,
        crop_bytes: bytes,
    ) -> EnrichmentResult:
        del crop_bytes
        return EnrichmentResult(
            key=request.key,
            status="unavailable",
            error="live vision calls are disabled",
        )


class EnrichmentQueue:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.requests_dir = self.root / "requests"
        self.results_dir = self.root / "results"

    @staticmethod
    def _path_for(directory: Path, key: str) -> Path:
        if not _CACHE_KEY.fullmatch(key):
            raise ValueError("cache key must be 64 lowercase hex characters")
        directory.mkdir(parents=True, exist_ok=True)
        root = directory.resolve()
        path = (directory / f"{key}.json").resolve()
        if not path.is_relative_to(root):
            raise ValueError("cache path escapes queue directory")
        return path

    @staticmethod
    def _json_text(value: ContractModel) -> str:
        return json.dumps(
            value.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )

    @staticmethod
    def _write_temp(path: Path, content: str) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temp_name = tempfile.mkstemp(
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
        )
        temp_path = Path(temp_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
        except BaseException:
            temp_path.unlink(missing_ok=True)
            raise
        return temp_path

    @classmethod
    def _publish_new(cls, path: Path, content: str) -> bool:
        temp_path = cls._write_temp(path, content)
        try:
            try:
                os.link(temp_path, path)
            except FileExistsError:
                return False
            return True
        finally:
            temp_path.unlink(missing_ok=True)

    @classmethod
    def _replace(cls, path: Path, content: str) -> None:
        temp_path = cls._write_temp(path, content)
        try:
            os.replace(temp_path, path)
        finally:
            temp_path.unlink(missing_ok=True)

    @staticmethod
    def _load_request(path: Path, expected: EnrichmentRequest) -> EnrichmentRequest:
        request = EnrichmentRequest.model_validate_json(path.read_text(encoding="utf-8"))
        if request != expected:
            raise ValueError("cached request identity does not match requested inputs")
        return request

    def enqueue(
        self,
        crop_bytes: bytes,
        *,
        provider: str,
        model: str,
        prompt_version: str,
        options: Mapping[str, JsonValue],
    ) -> tuple[EnrichmentRequest, bool]:
        key = enrichment_cache_key(
            crop_bytes,
            provider=provider,
            model=model,
            prompt_version=prompt_version,
            options=options,
        )
        request = EnrichmentRequest(
            key=key,
            crop_sha256=hashlib.sha256(crop_bytes).hexdigest(),
            provider=provider,
            model=model,
            prompt_version=prompt_version,
            options={key: _thaw_json(value) for key, value in options.items()},
        )
        path = self._path_for(self.requests_dir, key)
        created = self._publish_new(path, self._json_text(request))
        if created:
            return request, True
        return self._load_request(path, request), False

    def save_result(self, result: EnrichmentResult) -> Path:
        path = self._path_for(self.results_dir, result.key)
        self._replace(path, self._json_text(result))
        return path

    def load_result(self, key: str) -> EnrichmentResult | None:
        path = self._path_for(self.results_dir, key)
        if not path.exists():
            return None
        result = EnrichmentResult.model_validate_json(path.read_text(encoding="utf-8"))
        if result.key != key:
            raise ValueError("cached result key does not match requested key")
        return result
