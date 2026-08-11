from __future__ import annotations

import hashlib
import json
from pathlib import Path

from fastapi.testclient import TestClient
from test_index import _pages

from rtr4_learning.api import create_app
from rtr4_learning.index import HashEmbeddingProvider, SearchIndex
from rtr4_learning.models import BookManifest, ChapterManifest
from rtr4_learning.settings import Settings

REPO_ROOT = Path(__file__).parents[2]


def _api_fixture(tmp_path):
    data_root = tmp_path / "data"
    book_root = data_root / "books/rtr4-cn"
    normalized_root = book_root / "normalized"
    normalized_root.mkdir(parents=True)
    source_root = tmp_path / "sources"
    source_root.mkdir()
    source_pdf = source_root / "RTR4.pdf"
    source_bytes = b"%PDF-1.4\nfixture"
    source_pdf.write_bytes(source_bytes)
    manifest = BookManifest(
        id="rtr4-cn",
        title="Real-Time Rendering 4th CN",
        source_path=str(source_pdf.resolve()),
        source_sha256=hashlib.sha256(source_bytes).hexdigest(),
        page_count=1250,
        chapters=(
            ChapterManifest(
                id="5",
                title="Shading Basics",
                start_page=104,
                end_page=154,
            ),
        ),
    )
    (book_root / "book.json").write_text(
        manifest.model_dump_json(indent=2),
        encoding="utf-8",
    )
    pages = _pages()
    (normalized_root / "pages.json").write_text(
        json.dumps([page.model_dump(mode="json") for page in pages]),
        encoding="utf-8",
    )
    index_path = book_root / "search.sqlite3"
    provider = HashEmbeddingProvider(dimensions=16)
    SearchIndex(index_path, embedding_provider=provider).rebuild(pages, chapter=5)
    settings = Settings(
        data_root=data_root,
        content_root=REPO_ROOT / "content",
        source_roots=(source_root,),
        embedding_dimensions=16,
    )
    return TestClient(create_app(settings)), book_root, source_pdf


def _client(tmp_path) -> TestClient:
    return _api_fixture(tmp_path)[0]


def test_health_book_page_and_block_endpoints(tmp_path) -> None:
    client = _client(tmp_path)

    assert client.get("/api/health").json() == {"status": "ok"}
    book = client.get("/api/books/rtr4-cn")
    page = client.get("/api/books/rtr4-cn/chapters/5/pages/105")
    block = client.get("/api/blocks/p105-formula-5.1", params={"book_id": "rtr4-cn"})

    assert book.status_code == 200
    assert book.json()["chapters"][0]["start_page"] == 104
    assert "source_path" not in book.json()
    assert "source_sha256" not in book.json()
    assert page.status_code == 200
    assert page.json()["page"] == 105
    assert block.status_code == 200
    assert block.json()["latex"].startswith("c_{shaded}")


def test_search_lesson_and_capabilities_endpoints(tmp_path) -> None:
    client = _client(tmp_path)

    search = client.get(
        "/api/search",
        params={"q": "Gooch", "chapter": 5, "book_id": "rtr4-cn"},
    )
    lesson = client.get("/api/lessons/chapter-05/section-5.1")
    capabilities = client.get("/api/capabilities")

    assert search.status_code == 200
    assert search.json()[0]["block_id"] == "p104-text-1"
    assert lesson.status_code == 200
    assert lesson.json()["lesson"]["section"] == "5.1"
    assert lesson.json()["shader"]["id"] == "gooch"
    assert "void main" in lesson.json()["shader_source"]
    assert "mainImage" in lesson.json()["browser_shader_source"]
    assert capabilities.json()["cloud_vision"] is False
    assert capabilities.json()["local_search"] is True


def test_api_rejects_unsafe_paths_and_missing_resources(tmp_path) -> None:
    client = _client(tmp_path)

    assert client.get("/api/books/../secrets").status_code in {404, 422}
    assert client.get("/api/books/missing").status_code == 404
    assert client.get("/api/lessons/../secret").status_code in {404, 422}


def test_source_pdf_is_hash_checked_and_confined_to_allowed_roots(tmp_path) -> None:
    client, book_root, _ = _api_fixture(tmp_path)
    partial = client.get(
        "/api/books/rtr4-cn/source",
        headers={"Range": "bytes=0-4"},
    )
    assert partial.status_code == 206
    assert partial.content == b"%PDF-"
    assert partial.headers["accept-ranges"] == "bytes"
    assert partial.headers["content-range"].startswith("bytes 0-4/")
    assert partial.headers["content-length"] == "5"
    invalid_range = client.get(
        "/api/books/rtr4-cn/source",
        headers={"Range": "bytes=9999-10000"},
    )
    assert invalid_range.status_code == 416

    secret = tmp_path / "secret.txt"
    secret.write_text("LOCAL_SECRET", encoding="utf-8")
    manifest_path = book_root / "book.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["source_path"] = str(secret)
    manifest["source_sha256"] = hashlib.sha256(secret.read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    assert client.get("/api/books/rtr4-cn/source").status_code == 403


def test_search_validates_query_and_maps_missing_or_corrupt_index(tmp_path) -> None:
    client, book_root, _ = _api_fixture(tmp_path)
    endpoint = "/api/search"

    assert client.get(endpoint, params={"q": "   ", "chapter": 5}).status_code == 422
    assert client.get(endpoint, params={"q": "x" * 257, "chapter": 5}).status_code == 422
    assert client.get(endpoint, params={"q": "Gooch", "chapter": 0}).status_code == 422

    index_path = book_root / "search.sqlite3"
    index_path.unlink()
    missing = client.get(endpoint, params={"q": "Gooch", "chapter": 5})
    assert missing.status_code == 404
    assert not index_path.exists()

    index_path.write_bytes(b"not a database")
    corrupt = client.get(endpoint, params={"q": "Gooch", "chapter": 5})
    assert corrupt.status_code == 500
    assert corrupt.json()["detail"] == "search index is invalid"


def test_search_maps_invalid_embedding_payload_to_controlled_error(tmp_path) -> None:
    import sqlite3

    client, book_root, _ = _api_fixture(tmp_path)
    index_path = book_root / "search.sqlite3"
    with sqlite3.connect(index_path) as connection:
        connection.execute(
            "UPDATE blocks SET embedding_json = 'null' WHERE id = 'p104-text-1'"
        )

    response = client.get("/api/search", params={"q": "Gooch", "chapter": 5})

    assert response.status_code == 500
    assert response.json()["detail"] == "search index is invalid"
