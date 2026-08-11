"""Hybrid lexical and embedding retrieval with source citations."""

from __future__ import annotations

import json
import math
import re
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Annotated

from pydantic import Field, PositiveInt

from rtr4_learning.index import EmbeddingProvider
from rtr4_learning.models import (
    BlockType,
    BoundingBox,
    ContractModel,
    StableBlockId,
)

_TOKEN = re.compile(r"[A-Za-z0-9.]+|[\u3400-\u9fff]+")
_NUMBER = re.compile(r"\b[0-9]+(?:\.[0-9]+)+\b")


class ScoreComponents(ContractModel):
    lexical: Annotated[float, Field(ge=0, le=1)]
    embedding: Annotated[float, Field(ge=0, le=1)]
    type_bonus: Annotated[float, Field(ge=0, le=1)]


class RetrievalResult(ContractModel):
    block_id: StableBlockId
    page: PositiveInt
    bbox: BoundingBox
    block_type: BlockType
    source_excerpt: str
    latex: str | None = None
    score: Annotated[float, Field(ge=0, le=1)]
    score_components: ScoreComponents


def _cosine(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    if len(left) != len(right):
        raise ValueError("embedding dimensions must match")
    denominator = math.sqrt(sum(x * x for x in left)) * math.sqrt(
        sum(y * y for y in right)
    )
    if not denominator:
        return 0.0
    return max(0.0, sum(x * y for x, y in zip(left, right, strict=True)) / denominator)


def _stored_embedding(raw: str) -> tuple[float, ...]:
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as error:
        raise ValueError("stored embedding is invalid JSON") from error
    if not isinstance(parsed, list) or not parsed:
        raise ValueError("stored embedding must be a non-empty array")
    converted: list[float] = []
    for value in parsed:
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise ValueError(  # noqa: TRY004 - corrupt persisted data, not caller type
                "stored embedding must contain finite numbers"
            )
        try:
            number = float(value)
        except (OverflowError, TypeError, ValueError) as error:
            raise ValueError(
                "stored embedding must contain finite numbers"
            ) from error
        if not math.isfinite(number):
            raise ValueError("stored embedding must contain finite numbers")
        converted.append(number)
    return tuple(converted)


def _lexical_score(query: str, search_text: str, *, fts_hit: bool) -> float:
    query_folded = query.casefold().strip()
    text_folded = search_text.casefold()
    tokens = _TOKEN.findall(query_folded)
    if not tokens:
        return 0.0
    matched = sum(1 for token in tokens if token in text_folded)
    score = matched / len(tokens)
    if query_folded and query_folded in text_folded:
        score += 0.5
    if fts_hit:
        score += 0.25
    return min(score / 1.75, 1.0)


def _fts_hits(connection: sqlite3.Connection, query: str) -> set[str]:
    tokens = [token for token in _TOKEN.findall(query) if token]
    if not tokens:
        return set()
    expression = " OR ".join(f'"{token.replace(chr(34), chr(34) * 2)}"' for token in tokens)
    rows = connection.execute(
        "SELECT id FROM blocks_fts WHERE blocks_fts MATCH ?",
        (expression,),
    )
    return {row[0] for row in rows}


def retrieve(
    index_path: str | Path,
    query: str,
    *,
    chapter: int,
    embedding_provider: EmbeddingProvider,
    limit: int = 10,
) -> tuple[RetrievalResult, ...]:
    if limit <= 0:
        return ()
    query_embedding = embedding_provider.embed(query)
    numbers = set(_NUMBER.findall(query))
    results: list[RetrievalResult] = []

    path = Path(index_path)
    if not path.is_file():
        raise FileNotFoundError(path)
    uri = f"{path.resolve().as_uri()}?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as connection:
        connection.row_factory = sqlite3.Row
        fts_hits = _fts_hits(connection, query)
        rows = connection.execute(
            "SELECT * FROM blocks WHERE chapter = ? ORDER BY page, id",
            (chapter,),
        )
        for row in rows:
            lexical = _lexical_score(
                query,
                row["search_text"],
                fts_hit=row["id"] in fts_hits,
            )
            stored_embedding = _stored_embedding(row["embedding_json"])
            embedding = _cosine(query_embedding, stored_embedding)
            type_bonus = 0.0
            if (
                row["block_type"] == BlockType.FORMULA.value
                and row["number"] in numbers
            ):
                type_bonus = 1.0
            elif row["block_type"] == BlockType.FIGURE.value and lexical > 0:
                type_bonus = 0.5
            score = 0.65 * lexical + 0.3 * embedding + 0.05 * type_bonus
            if score <= 0:
                continue
            results.append(
                RetrievalResult(
                    block_id=row["id"],
                    page=row["page"],
                    bbox=BoundingBox.model_validate(json.loads(row["bbox_json"])),
                    block_type=BlockType(row["block_type"]),
                    source_excerpt=row["source_excerpt"],
                    latex=row["latex"],
                    score=score,
                    score_components=ScoreComponents(
                        lexical=lexical,
                        embedding=embedding,
                        type_bonus=type_bonus,
                    ),
                )
            )

    results.sort(key=lambda result: (-result.score, result.page, result.block_id))
    return tuple(results[:limit])
