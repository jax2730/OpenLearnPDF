from __future__ import annotations

import json
import sqlite3

import pytest
from pydantic import ValidationError
from test_index import _chapter6_pages, _pages

from rtr4_learning.index import HashEmbeddingProvider, SearchIndex
from rtr4_learning.retrieval import retrieve


def _index(tmp_path):
    provider = HashEmbeddingProvider(dimensions=16)
    index = SearchIndex(tmp_path / "search.sqlite3", embedding_provider=provider)
    index.rebuild_chapters({5: _pages(), 6: _chapter6_pages()})
    return index, provider


def test_retrieves_gooch_formula_and_chinese_topics(tmp_path) -> None:
    index, provider = _index(tmp_path)

    gooch = retrieve(index.path, "Gooch 着色", chapter=5, embedding_provider=provider)
    assert {result.page for result in gooch} >= {104, 106}
    assert retrieve(index.path, "方程 5.1", chapter=5, embedding_provider=provider)[0].block_id == "p105-formula-5.1"
    assert retrieve(index.path, "逐顶点着色", chapter=5, embedding_provider=provider)[0].block_id == "p120-figure-5.9"


def test_chapter_filter_and_citation_payload(tmp_path) -> None:
    index, provider = _index(tmp_path)
    results = retrieve(
        index.path,
        "Gooch",
        chapter=5,
        embedding_provider=provider,
    )
    chapter_six = retrieve(
        index.path,
        "Gooch",
        chapter=6,
        embedding_provider=provider,
    )

    assert {result.block_id for result in chapter_six} == {"p200-text-1"}
    assert all(result.block_id != "p200-text-1" for result in results)
    result = results[0]
    assert result.block_id == "p104-text-1"
    assert result.page == 104
    assert result.bbox.x0 == 0.1
    assert result.block_type.value == "text"
    assert result.source_excerpt == "Gooch 着色使用冷暖颜色表达表面朝向。"
    assert result.latex is None
    assert result.score > 0
    assert set(result.score_components.model_dump()) == {
        "lexical",
        "embedding",
        "type_bonus",
    }
    with pytest.raises(ValidationError):
        result.score_components.lexical = 999  # type: ignore[misc]


def test_missing_index_is_not_created(tmp_path) -> None:
    missing = tmp_path / "missing.sqlite3"

    with pytest.raises(FileNotFoundError):
        retrieve(
            missing,
            "Gooch",
            chapter=5,
            embedding_provider=HashEmbeddingProvider(dimensions=16),
        )

    assert not missing.exists()


def test_corrupt_or_missing_fts_schema_is_not_silently_ignored(tmp_path) -> None:
    index, provider = _index(tmp_path)
    with sqlite3.connect(index.path) as connection:
        connection.execute("DROP TABLE blocks_fts")

    with pytest.raises(sqlite3.OperationalError, match="blocks_fts"):
        retrieve(
            index.path,
            "Gooch",
            chapter=5,
            embedding_provider=provider,
        )


@pytest.mark.parametrize("payload", ["null", json.dumps([10**1000])])
def test_invalid_embedding_json_is_rejected_at_retrieval_boundary(
    tmp_path, payload: str
) -> None:
    index, provider = _index(tmp_path)
    with sqlite3.connect(index.path) as connection:
        connection.execute(
            "UPDATE blocks SET embedding_json = ? WHERE id = 'p104-text-1'",
            (payload,),
        )

    with pytest.raises(ValueError, match="stored embedding"):
        retrieve(
            index.path,
            "Gooch",
            chapter=5,
            embedding_provider=provider,
        )
