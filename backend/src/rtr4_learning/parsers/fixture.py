"""Deterministic raw parser fixture used without external parser installs."""

from __future__ import annotations

import hashlib
import json
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
        if not asset_dir.is_dir():
            raise FileNotFoundError(f"fixture asset directory not found: {asset_dir}")

        identity = {
            "asset_dir": str(asset_dir),
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
