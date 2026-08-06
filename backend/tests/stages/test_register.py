import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest
from pypdf import PdfWriter

from rtr4_learning.paths import book_manifest_path
from rtr4_learning.stages.register import register_book


def create_pdf(path: Path, page_count: int = 154) -> None:
    writer = PdfWriter()
    for _ in range(page_count):
        writer.add_blank_page(width=612, height=792)
    with path.open("wb") as output:
        writer.write(output)


def test_register_book_writes_deterministic_manifest_without_copying_pdf(
    tmp_path: Path,
) -> None:
    pdf_path = tmp_path / "source.pdf"
    data_root = tmp_path / "data"
    create_pdf(pdf_path)
    expected_hash = hashlib.sha256(pdf_path.read_bytes()).hexdigest()

    register_book(
        book_id="rtr4-cn",
        pdf_path=pdf_path,
        chapter="5:104-154",
        data_root=data_root,
    )
    manifest_path = book_manifest_path(data_root, "rtr4-cn")
    first_bytes = manifest_path.read_bytes()
    manifest = json.loads(first_bytes)

    assert manifest_path.is_file()
    assert manifest["source_sha256"] == expected_hash
    assert len(manifest["source_sha256"]) == 64
    assert manifest["source_path"] == str(pdf_path.resolve())
    assert manifest["page_count"] == 154
    assert manifest["chapters"][0]["id"] == "5"
    assert manifest["chapters"][0]["start_page"] == 104
    assert manifest["chapters"][0]["end_page"] == 154
    assert list(data_root.rglob("*.pdf")) == []

    register_book(
        book_id="rtr4-cn",
        pdf_path=pdf_path,
        chapter="5:104-154",
        data_root=data_root,
    )

    assert manifest_path.read_bytes() == first_bytes


@pytest.mark.parametrize("book_id", ["..", "../escape", r"..\escape", "/absolute"])
def test_register_book_rejects_unsafe_book_ids(tmp_path: Path, book_id: str) -> None:
    pdf_path = tmp_path / "source.pdf"
    create_pdf(pdf_path)

    with pytest.raises(ValueError, match="book_id"):
        register_book(
            book_id=book_id,
            pdf_path=pdf_path,
            chapter="5:104-154",
            data_root=tmp_path / "data",
        )


@pytest.mark.parametrize("chapter", ["5:155-154", "5:104-155", "bad"])
def test_register_book_rejects_invalid_chapter_ranges(
    tmp_path: Path, chapter: str
) -> None:
    pdf_path = tmp_path / "source.pdf"
    create_pdf(pdf_path)

    with pytest.raises(ValueError, match="chapter"):
        register_book(
            book_id="rtr4-cn",
            pdf_path=pdf_path,
            chapter=chapter,
            data_root=tmp_path / "data",
        )


def test_register_cli_writes_manifest(tmp_path: Path) -> None:
    pdf_path = tmp_path / "source.pdf"
    data_root = tmp_path / "data"
    create_pdf(pdf_path)

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "rtr4_learning.cli",
            "register",
            "--book-id",
            "rtr4-cn",
            "--pdf",
            str(pdf_path),
            "--chapter",
            "5:104-154",
            "--data-root",
            str(data_root),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert book_manifest_path(data_root, "rtr4-cn").is_file()
