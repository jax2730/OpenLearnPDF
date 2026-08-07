"""Deterministic raw parser fixture used without external parser installs."""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from rtr4_learning.parsers.base import RawParseResult, canonical_pages


def _canonical_json_bytes(value: dict[str, Any]) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _is_link_or_reparse_point(path: Path) -> bool:
    if path.is_symlink():
        return True
    is_junction = getattr(path, "is_junction", None)
    return bool(is_junction is not None and is_junction())


def _asset_references(value: object) -> Iterable[str]:
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "asset_path" and isinstance(item, str):
                yield item
            else:
                yield from _asset_references(item)
    elif isinstance(value, list):
        for item in value:
            yield from _asset_references(item)


def _validate_asset_reference(
    fixture_dir: Path, asset_dir: Path, reference: str
) -> None:
    if not reference.strip():
        raise ValueError("fixture asset reference must not be empty")
    candidate = (fixture_dir / reference).resolve(strict=False)
    try:
        common = os.path.commonpath((str(asset_dir), str(candidate)))
    except ValueError as error:
        raise ValueError("fixture asset reference escapes asset directory") from error
    if os.path.normcase(common) != os.path.normcase(str(asset_dir)):
        raise ValueError("fixture asset reference escapes asset directory")
    reference_path = fixture_dir / reference
    if _is_link_or_reparse_point(reference_path) or not reference_path.is_file():
        raise ValueError("fixture asset reference must target an ordinary file")


def _asset_hashes(asset_dir: Path) -> list[dict[str, str]]:
    assets: list[dict[str, str]] = []
    for path in sorted(asset_dir.rglob("*"), key=lambda item: item.as_posix()):
        if _is_link_or_reparse_point(path):
            raise ValueError("fixture asset directory must not contain links")
        if path.is_dir():
            continue
        if not path.is_file():
            raise ValueError("fixture asset must be an ordinary file")
        assets.append(
            {
                "path": path.relative_to(asset_dir.parent).as_posix(),
                "sha256": _sha256(path.read_bytes()),
            }
        )
    return assets


class FixtureParser:
    """Load the sanitized page-105 MinerU-shaped fixture in place."""

    parser_name = "fixture"
    parser_version = "1"

    def __init__(self, fixture_dir: Path | str) -> None:
        self.fixture_dir = Path(fixture_dir).resolve()

    def parse(
        self,
        *,
        pages: Iterable[int],
        source_path: Path | str | None = None,
        output_dir: Path | str | None = None,
    ) -> RawParseResult:
        del source_path, output_dir
        requested_pages = canonical_pages(pages)
        if requested_pages != (105,):
            raise ValueError("fixture parser supports only page 105")

        raw_json_path = self.fixture_dir / "page-105.json"
        markdown_path = self.fixture_dir / "page-105.md"
        asset_dir = self.fixture_dir / "assets"
        raw_payload = raw_json_path.read_bytes()
        markdown_payload = markdown_path.read_bytes()
        if _is_link_or_reparse_point(asset_dir) or not asset_dir.is_dir():
            raise ValueError("fixture asset directory must be an ordinary directory")
        raw_document = json.loads(raw_payload)
        for reference in _asset_references(raw_document):
            _validate_asset_reference(self.fixture_dir, asset_dir, reference)

        identity = {
            "assets": _asset_hashes(asset_dir),
            "markdown_sha256": _sha256(markdown_payload),
            "pages": list(requested_pages),
            "parser": self.parser_name,
            "raw_json_sha256": _sha256(raw_payload),
            "version": self.parser_version,
        }
        return RawParseResult(
            parser_name=self.parser_name,
            parser_version=self.parser_version,
            requested_pages=requested_pages,
            raw_json_path=raw_json_path,
            markdown_path=markdown_path,
            asset_dir=asset_dir,
            fingerprint=_sha256(_canonical_json_bytes(identity)),
        )
