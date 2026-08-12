from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from rtr4_learning.api import create_app
from rtr4_learning.index import HashEmbeddingProvider
from rtr4_learning.ingest import ingest_mineru_slice
from rtr4_learning.models import BlockType, BookManifest
from rtr4_learning.retrieval import retrieve
from rtr4_learning.settings import Settings
from rtr4_learning.teaching import load_lesson_bundle, validate_lesson_bundle

REPO_ROOT = Path(__file__).parents[3]


def _real_paths() -> tuple[Path, Path]:
    data_root = os.environ.get("RTR4_E2E_DATA_ROOT")
    probe_root = os.environ.get("RTR4_E2E_PROBE_ROOT")
    if not data_root or not probe_root:
        pytest.skip("set RTR4_E2E_DATA_ROOT and RTR4_E2E_PROBE_ROOT")
    data_path = Path(data_root)
    probe_path = Path(probe_root)
    if not data_path.is_dir() or not probe_path.is_dir():
        pytest.skip("RTR4 real data or MinerU probe is unavailable")
    return data_path, probe_path


def _render_pages_exist(data_root: Path) -> bool:
    render_root = data_root / "books/rtr4-cn/renders"
    for manifest_path in render_root.glob("*/stage.json"):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest["inputs"].get("pages") == [104, 105, 106]:
            page_root = manifest_path.parent / "pages"
            return all((page_root / f"p{page}.png").is_file() for page in range(104, 107))
    return False


def test_real_chapter5_three_page_slice_is_citation_consistent(tmp_path) -> None:
    source_data_root, probe_root = _real_paths()
    content_list = (
        probe_root
        / "RTR4-CN-v1.1/auto/RTR4-CN-v1.1_content_list_v2.json"
    )
    source_manifest_path = source_data_root / "books/rtr4-cn/book.json"
    data_root = tmp_path / "data"
    manifest_path = data_root / "books/rtr4-cn/book.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_bytes(source_manifest_path.read_bytes())

    result = ingest_mineru_slice(
        data_root=data_root,
        book_id="rtr4-cn",
        content_list=content_list,
        first_page=104,
        parser_version="3.4.4",
        chapter=5,
    )
    pages = result.pages
    blocks = {block.id: block for page in pages for block in page.blocks}

    assert _render_pages_exist(source_data_root)
    assert [page.page for page in pages] == [104, 105, 106]
    assert blocks["p105-formula-5.1"].latex
    assert blocks["p106-formula-5.2"].latex
    for number in ("5.2", "5.3"):
        figure = next(
            block
            for block in blocks.values()
            if block.type is BlockType.FIGURE and block.number == number
        )
        caption = next(
            block
            for block in blocks.values()
            if block.type is BlockType.FIGURE_CAPTION and block.number == number
        )
        assert any(
            relation.type == "caption_of" and relation.target == figure.id
            for relation in caption.relations
        )
    expected_refs = {
        "p104-paragraph-3": "p104-figure-5.1",
        "p105-paragraph-1": "p105-figure-5.2",
        "p105-paragraph-2": "p105-figure-5.2",
        "p105-paragraph-3": "p105-figure-5.3",
    }
    for source_id, target_id in expected_refs.items():
        assert any(
            relation.type == "refers_to" and relation.target == target_id
            for relation in blocks[source_id].relations
        )
    assert result.validation_issues == ()

    lesson, shader = load_lesson_bundle(
        REPO_ROOT / "content/rtr4-cn/chapter-05/section-5.1.json"
    )
    validate_lesson_bundle(lesson, shader, blocks)

    search = retrieve(
        result.index_path,
        "Gooch",
        chapter=5,
        embedding_provider=HashEmbeddingProvider(dimensions=64),
    )
    assert search[0].block_id == "p104-paragraph-6"
    assert search[0].block_type is BlockType.TEXT
    formula_search = retrieve(
        result.index_path,
        "5.1",
        chapter=5,
        embedding_provider=HashEmbeddingProvider(dimensions=64),
    )
    assert any(
        item.block_id == "p105-formula-5.1"
        and item.block_type is BlockType.FORMULA
        for item in formula_search[:5]
    )

    manifest = BookManifest.model_validate_json(
        (data_root / "books/rtr4-cn/book.json").read_text(encoding="utf-8")
    )
    settings = Settings(
        data_root=data_root,
        content_root=REPO_ROOT / "content",
        source_roots=(Path(manifest.source_path).parent,),
        embedding_dimensions=64,
    )
    client = TestClient(create_app(settings))
    api_page = client.get("/api/books/rtr4-cn/chapters/5/pages/105")
    api_block = client.get("/api/blocks/p105-formula-5.1")
    api_lesson = client.get("/api/lessons/chapter-05/section-5.1")
    api_search = client.get("/api/search", params={"q": "Gooch", "chapter": 5})

    assert api_page.status_code == 200
    assert api_block.json() == blocks["p105-formula-5.1"].model_dump(mode="json")
    assert api_lesson.status_code == 200
    assert api_search.status_code == 200
    assert api_search.json()[0]["block_id"] == search[0].block_id
