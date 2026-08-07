from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from rtr4_learning.parsers.base import RawParseResult, canonical_pages
from rtr4_learning.parsers.fixture import FixtureParser

FIXTURE_DIR = Path(__file__).parents[1] / "fixtures" / "mineru"


def test_raw_parse_result_is_frozen_and_validates_fingerprint() -> None:
    result = RawParseResult(
        parser_name="fixture",
        parser_version="1",
        requested_pages=(105,),
        raw_json_path=FIXTURE_DIR / "page-105.json",
        markdown_path=FIXTURE_DIR / "page-105.md",
        asset_dir=FIXTURE_DIR / "assets",
        fingerprint="a" * 64,
    )

    with pytest.raises(ValidationError):
        result.parser_name = "changed"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        RawParseResult(
            parser_name="fixture",
            parser_version="1",
            requested_pages=(105,),
            raw_json_path=FIXTURE_DIR / "page-105.json",
            markdown_path=FIXTURE_DIR / "page-105.md",
            asset_dir=FIXTURE_DIR / "assets",
            fingerprint="ABC123",
        )


@pytest.mark.parametrize("pages", [(), (0,), (-1,), (1, 3)])
def test_canonical_pages_reject_invalid_or_non_contiguous_pages(
    pages: tuple[int, ...],
) -> None:
    with pytest.raises(ValueError):
        canonical_pages(pages)


def test_canonical_pages_sorts_and_deduplicates_contiguous_pages() -> None:
    assert canonical_pages([106, 105, 105, 104]) == (104, 105, 106)


def test_fixture_parser_loads_deterministic_raw_artifacts_without_mutation() -> None:
    parser = FixtureParser(FIXTURE_DIR)
    raw_path = FIXTURE_DIR / "page-105.json"
    before = raw_path.read_bytes()

    first = parser.parse(pages=[105, 105])
    second = parser.parse(pages=[105])

    assert first == second
    assert first.parser_name == "fixture"
    assert first.requested_pages == (105,)
    assert first.raw_json_path == raw_path.resolve()
    assert first.markdown_path == (FIXTURE_DIR / "page-105.md").resolve()
    assert first.asset_dir == (FIXTURE_DIR / "assets").resolve()
    assert first.raw_json_path.is_file()
    assert first.markdown_path.is_file()
    assert first.asset_dir.is_dir()
    assert len(first.fingerprint) == 64
    assert first.fingerprint == first.fingerprint.lower()
    assert raw_path.read_bytes() == before

    payload = json.loads(before)
    blocks = payload["pdf_info"][0]["para_blocks"]
    assert payload["pdf_info"][0]["page_idx"] == 104
    assert {block["type"] for block in blocks} >= {
        "text",
        "interline_equation",
        "image",
        "image_caption",
    }
    assert blocks[1]["latex"]
    assert blocks[2]["asset_path"] == "assets/page-105-figure.svg"
    assert all(len(block["bbox"]) == 4 for block in blocks)


def test_fixture_fingerprint_tracks_fixture_content(tmp_path: Path) -> None:
    fixture_dir = tmp_path / "fixture"
    fixture_dir.mkdir()
    (fixture_dir / "assets").mkdir()
    (fixture_dir / "page-105.md").write_text("before", encoding="utf-8")
    (fixture_dir / "page-105.json").write_text(
        '{"pdf_info":[{"page_idx":104,"para_blocks":[]}]}', encoding="utf-8"
    )

    before = FixtureParser(fixture_dir).parse(pages=[105]).fingerprint
    (fixture_dir / "page-105.md").write_text("after", encoding="utf-8")
    after = FixtureParser(fixture_dir).parse(pages=[105]).fingerprint

    assert before != after
    assert (
        before
        == hashlib.sha256(
            json.dumps(
                {
                    "asset_dir": str((fixture_dir / "assets").resolve()),
                    "markdown_sha256": hashlib.sha256(b"before").hexdigest(),
                    "pages": [105],
                    "parser": "fixture",
                    "raw_json_sha256": hashlib.sha256(
                        (fixture_dir / "page-105.json").read_bytes()
                    ).hexdigest(),
                    "version": "1",
                },
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
    )


def test_fixture_parser_rejects_unsupported_page() -> None:
    with pytest.raises(ValueError, match="page 105"):
        FixtureParser(FIXTURE_DIR).parse(pages=[104])
