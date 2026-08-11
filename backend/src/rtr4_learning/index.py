"""SQLite FTS5 index for canonical document blocks."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sqlite3
import tempfile
from collections.abc import Mapping, Sequence
from contextlib import closing
from pathlib import Path
from typing import Protocol, runtime_checkable

from rtr4_learning.models import Block, PageDocument

_TOKEN = re.compile(r"[A-Za-z0-9.]+|[\u3400-\u9fff]+")


@runtime_checkable
class EmbeddingProvider(Protocol):
    def embed(self, text: str) -> tuple[float, ...]: ...


class HashEmbeddingProvider:
    """Small deterministic feature hash used by tests and local fallback."""

    def __init__(self, *, dimensions: int = 64) -> None:
        if dimensions <= 0:
            raise ValueError("embedding dimensions must be positive")
        self.dimensions = dimensions

    def embed(self, text: str) -> tuple[float, ...]:
        normalized = text.casefold().strip()
        features = list(_TOKEN.findall(normalized))
        features.extend(
            normalized[index : index + 2]
            for index in range(max(0, len(normalized) - 1))
            if not normalized[index : index + 2].isspace()
        )
        vector = [0.0] * self.dimensions
        for feature in features:
            digest = hashlib.sha256(feature.encode("utf-8")).digest()
            vector[int.from_bytes(digest[:8], "big") % self.dimensions] += 1.0
        norm = math.sqrt(sum(value * value for value in vector))
        if norm:
            vector = [value / norm for value in vector]
        return tuple(vector)


class SentenceTransformerEmbeddingProvider:
    """Optional lazy adapter; importing this module never downloads a model."""

    def __init__(
        self,
        model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    ) -> None:
        self.model_name = model_name
        self._model = None

    def embed(self, text: str) -> tuple[float, ...]:
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as error:
                raise RuntimeError(
                    "sentence-transformers is not installed"
                ) from error
            self._model = SentenceTransformer(self.model_name)
        encoded = self._model.encode(text, normalize_embeddings=True)
        return tuple(float(value) for value in encoded)


def _search_text(block: Block, context: str = "") -> str:
    return " ".join(
        value
        for value in (
            block.text,
            block.latex,
            block.number,
            block.type.value,
            context,
        )
        if value
    )


class SearchIndex:
    def __init__(self, path: str | Path, *, embedding_provider: EmbeddingProvider) -> None:
        self.path = Path(path)
        self.embedding_provider = embedding_provider

    @staticmethod
    def _create_schema(connection: sqlite3.Connection) -> None:
        connection.executescript(
            """
            PRAGMA journal_mode=DELETE;
            PRAGMA synchronous=FULL;
            CREATE TABLE blocks (
                id TEXT PRIMARY KEY,
                chapter INTEGER NOT NULL,
                page INTEGER NOT NULL,
                block_type TEXT NOT NULL,
                bbox_json TEXT NOT NULL,
                text TEXT,
                latex TEXT,
                number TEXT,
                source_excerpt TEXT NOT NULL,
                search_text TEXT NOT NULL,
                embedding_json TEXT NOT NULL
            ) WITHOUT ROWID;
            CREATE VIRTUAL TABLE blocks_fts USING fts5(
                id UNINDEXED,
                search_text,
                tokenize='unicode61'
            );
            """
        )

    def rebuild(self, pages: Sequence[PageDocument], *, chapter: int) -> None:
        if chapter <= 0:
            raise ValueError("chapter must be positive")
        self.rebuild_chapters({chapter: pages})

    def rebuild_chapters(
        self,
        chapters: Mapping[int, Sequence[PageDocument]],
    ) -> None:
        if any(chapter <= 0 for chapter in chapters):
            raise ValueError("chapters must be positive")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temp_name = tempfile.mkstemp(
            dir=self.path.parent,
            prefix=f".{self.path.name}.",
            suffix=".tmp",
        )
        os.close(descriptor)
        temp_path = Path(temp_name)
        temp_path.unlink()
        try:
            with closing(sqlite3.connect(temp_path)) as connection:
                self._create_schema(connection)
                all_blocks = [
                    block
                    for chapter in sorted(chapters)
                    for page in chapters[chapter]
                    for block in page.blocks
                ]
                captions_by_target: dict[str, list[str]] = {}
                for block in all_blocks:
                    if not block.text:
                        continue
                    for relation in block.relations:
                        if relation.type == "caption_of":
                            captions_by_target.setdefault(relation.target, []).append(
                                block.text
                            )

                embedding_dimensions: int | None = None
                for chapter in sorted(chapters):
                    for page in chapters[chapter]:
                        for block in page.blocks:
                            context = " ".join(captions_by_target.get(block.id, ()))
                            search_text = _search_text(block, context)
                            excerpt = (
                                block.text
                                or context
                                or block.latex
                                or block.number
                                or block.type.value
                            )
                            embedding = self.embedding_provider.embed(search_text)
                            if not embedding:
                                raise ValueError("embedding must not be empty")
                            if not all(math.isfinite(value) for value in embedding):
                                raise ValueError("embedding values must be finite")
                            if embedding_dimensions is None:
                                embedding_dimensions = len(embedding)
                            elif len(embedding) != embedding_dimensions:
                                raise ValueError(
                                    "embedding dimensions must be consistent"
                                )
                            values = (
                                block.id,
                                chapter,
                                block.page,
                                block.type.value,
                                json.dumps(
                                    block.bbox.model_dump(mode="json"),
                                    sort_keys=True,
                                    separators=(",", ":"),
                                ),
                                block.text,
                                block.latex,
                                block.number,
                                excerpt,
                                search_text,
                                json.dumps(embedding, separators=(",", ":")),
                            )
                            connection.execute(
                                """
                                INSERT INTO blocks VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                """,
                                values,
                            )
                            connection.execute(
                                "INSERT INTO blocks_fts(id, search_text) VALUES (?, ?)",
                                (block.id, search_text),
                            )
                connection.commit()
                connection.execute("VACUUM")
                connection.commit()
            os.replace(temp_path, self.path)
        finally:
            temp_path.unlink(missing_ok=True)
