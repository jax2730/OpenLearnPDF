from __future__ import annotations

import sqlite3

import pytest

from rtr4_learning.index import HashEmbeddingProvider, SearchIndex
from rtr4_learning.models import (
    Block,
    BlockSource,
    BlockType,
    BoundingBox,
    PageDocument,
    Relation,
)


def _pages() -> tuple[PageDocument, ...]:
    source = BlockSource(parser="fixture", version="1", confidence=1)
    bbox = BoundingBox(x0=0.1, y0=0.1, x1=0.9, y1=0.2)
    return (
        PageDocument(
            page=104,
            blocks=(
                Block(
                    id="p104-text-1",
                    type=BlockType.TEXT,
                    page=104,
                    bbox=bbox,
                    text="Gooch 着色使用冷暖颜色表达表面朝向。",
                    source=source,
                ),
            ),
        ),
        PageDocument(
            page=105,
            blocks=(
                Block(
                    id="p105-formula-5.1",
                    type=BlockType.FORMULA,
                    page=105,
                    bbox=bbox,
                    latex=r"c_{shaded}=s c_{highlight}+(1-s)c_{surface}",
                    number="5.1",
                    source=source,
                ),
            ),
        ),
        PageDocument(
            page=106,
            blocks=(
                Block(
                    id="p106-text-1",
                    type=BlockType.TEXT,
                    page=106,
                    bbox=bbox,
                    text="Gooch 方程中的点积、插值和反射向量在其他着色模型中也常见。",
                    source=source,
                ),
            ),
        ),
        PageDocument(
            page=120,
            blocks=(
                Block(
                    id="p120-figure-5.9",
                    type=BlockType.FIGURE,
                    page=120,
                    bbox=bbox,
                    number="5.9",
                    source=source,
                ),
                Block(
                    id="p120-figure_caption-5.9",
                    type=BlockType.FIGURE_CAPTION,
                    page=120,
                    bbox=bbox,
                    text="Figure 5.9 compares 逐顶点着色 and 逐像素着色 frequency.",
                    number="5.9",
                    relations=(
                        Relation(type="caption_of", target="p120-figure-5.9"),
                    ),
                    source=source,
                ),
            ),
        ),
    )


def _chapter6_pages() -> tuple[PageDocument, ...]:
    source = BlockSource(parser="fixture", version="1", confidence=1)
    bbox = BoundingBox(x0=0.1, y0=0.1, x1=0.9, y1=0.2)
    return (
        PageDocument(
            page=200,
            blocks=(
                Block(
                    id="p200-text-1",
                    type=BlockType.TEXT,
                    page=200,
                    bbox=bbox,
                    text="Gooch is mentioned outside chapter five.",
                    source=source,
                ),
            ),
        ),
    )


def test_rebuild_creates_fts_rows_and_is_deterministic(tmp_path) -> None:
    path = tmp_path / "search.sqlite3"
    index = SearchIndex(path, embedding_provider=HashEmbeddingProvider(dimensions=16))
    index.rebuild_chapters({5: _pages(), 6: _chapter6_pages()})
    first = path.read_bytes()
    index.rebuild_chapters({5: _pages(), 6: _chapter6_pages()})

    with sqlite3.connect(path) as connection:
        count = connection.execute("SELECT COUNT(*) FROM blocks").fetchone()[0]
        fts_count = connection.execute("SELECT COUNT(*) FROM blocks_fts").fetchone()[0]

    assert count == 6
    assert fts_count == 6
    assert path.read_bytes() == first


def test_hash_embedding_is_stable_and_has_fixed_dimensions() -> None:
    provider = HashEmbeddingProvider(dimensions=24)

    assert provider.embed("Gooch 着色") == provider.embed("Gooch 着色")
    assert len(provider.embed("Gooch 着色")) == 24
    assert provider.embed("Gooch 着色") != provider.embed("透明度")


def test_sentence_transformer_adapter_defaults_to_multilingual_model() -> None:
    from rtr4_learning.index import SentenceTransformerEmbeddingProvider

    provider = SentenceTransformerEmbeddingProvider()

    assert "multilingual" in provider.model_name.casefold()


@pytest.mark.parametrize(
    "provider",
    [
        type("EmptyProvider", (), {"embed": lambda self, text: ()})(),
        type(
            "ChangingProvider",
            (),
            {
                "calls": 0,
                "embed": lambda self, text: (
                    setattr(self, "calls", self.calls + 1)
                    or ((1.0,) if self.calls == 1 else (1.0, 2.0))
                ),
            },
        )(),
        type("NonFiniteProvider", (), {"embed": lambda self, text: (float("nan"),)})(),
    ],
)
def test_rebuild_rejects_invalid_embeddings_without_replacing_old_index(
    tmp_path, provider
) -> None:
    path = tmp_path / "search.sqlite3"
    valid = SearchIndex(path, embedding_provider=HashEmbeddingProvider(dimensions=8))
    valid.rebuild(_pages(), chapter=5)
    original = path.read_bytes()

    with pytest.raises(ValueError, match="embedding"):
        SearchIndex(path, embedding_provider=provider).rebuild(_pages(), chapter=5)

    assert path.read_bytes() == original
