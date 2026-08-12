import hashlib
import json
import multiprocessing
import os
import re
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pytest
from pypdf import PdfWriter

import rtr4_learning.stages.register as register_module
from rtr4_learning.paths import _comparison_path, book_manifest_path, validate_book_id
from rtr4_learning.stages.register import _book_lock, _stat_signature, register_book


def create_pdf(path: Path, page_count: int = 154) -> None:
    writer = PdfWriter()
    for _ in range(page_count):
        writer.add_blank_page(width=612, height=792)
    with path.open("wb") as output:
        writer.write(output)


def register_in_child(pdf_path: str, data_root: str) -> None:
    register_book(
        book_id="rtr4-cn",
        pdf_path=pdf_path,
        chapter="5:104-154",
        data_root=data_root,
    )


def hold_book_lock_in_child(data_root: str, ready: object) -> None:
    manifest_path = book_manifest_path(data_root, "rtr4-cn")
    with _book_lock(manifest_path):
        ready.set()  # type: ignore[attr-defined]
        time.sleep(60)


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


def test_register_book_rejects_pdf_changed_during_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pdf_path = tmp_path / "source.pdf"
    replacement_path = tmp_path / "replacement.pdf"
    data_root = tmp_path / "data"
    create_pdf(pdf_path, page_count=154)
    create_pdf(replacement_path, page_count=155)
    replacement_bytes = replacement_path.read_bytes()

    def replace_during_read(_source: object) -> SimpleNamespace:
        pdf_path.write_bytes(replacement_bytes)
        return SimpleNamespace(pages=[None] * 154)

    monkeypatch.setattr(register_module, "PdfReader", replace_during_read)

    with pytest.raises(ValueError, match="changed during registration"):
        register_book(
            book_id="rtr4-cn",
            pdf_path=pdf_path,
            chapter="5:104-154",
            data_root=data_root,
        )

    assert not book_manifest_path(data_root, "rtr4-cn").exists()


def test_concurrent_identical_registration_is_serialized_and_idempotent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pdf_path = tmp_path / "source.pdf"
    data_root = tmp_path / "data"
    create_pdf(pdf_path)
    original_replace = os.replace
    counter_lock = threading.Lock()
    active_replaces = 0
    max_active_replaces = 0

    def observed_replace(source: Path | str, destination: Path | str) -> None:
        nonlocal active_replaces, max_active_replaces
        with counter_lock:
            active_replaces += 1
            max_active_replaces = max(max_active_replaces, active_replaces)
        try:
            time.sleep(0.03)
            original_replace(source, destination)
        finally:
            with counter_lock:
                active_replaces -= 1

    monkeypatch.setattr(register_module.os, "replace", observed_replace)

    def register_once() -> bytes:
        register_book(
            book_id="rtr4-cn",
            pdf_path=pdf_path,
            chapter="5:104-154",
            data_root=data_root,
        )
        return book_manifest_path(data_root, "rtr4-cn").read_bytes()

    with ThreadPoolExecutor(max_workers=8) as executor:
        payloads = list(executor.map(lambda _index: register_once(), range(16)))

    assert len(set(payloads)) == 1
    assert max_active_replaces == 1
    assert (data_root / "books" / ".rtr4-cn.register.lock").is_file()


def test_register_book_rejects_existing_manifest_conflict(tmp_path: Path) -> None:
    first_pdf = tmp_path / "first.pdf"
    second_pdf = tmp_path / "second.pdf"
    data_root = tmp_path / "data"
    create_pdf(first_pdf, page_count=154)
    create_pdf(second_pdf, page_count=155)
    register_book(
        book_id="rtr4-cn",
        pdf_path=first_pdf,
        chapter="5:104-154",
        data_root=data_root,
    )
    original = book_manifest_path(data_root, "rtr4-cn").read_bytes()

    with pytest.raises(ValueError, match="conflict"):
        register_book(
            book_id="rtr4-cn",
            pdf_path=second_pdf,
            chapter="5:104-154",
            data_root=data_root,
        )

    assert book_manifest_path(data_root, "rtr4-cn").read_bytes() == original


def test_register_book_rejects_existing_chapter_conflict(tmp_path: Path) -> None:
    pdf_path = tmp_path / "source.pdf"
    data_root = tmp_path / "data"
    create_pdf(pdf_path)
    register_book(
        book_id="rtr4-cn",
        pdf_path=pdf_path,
        chapter="5:104-154",
        data_root=data_root,
    )

    with pytest.raises(ValueError, match="conflict"):
        register_book(
            book_id="rtr4-cn",
            pdf_path=pdf_path,
            chapter="5:104-153",
            data_root=data_root,
        )


def test_multiprocess_identical_registration_is_idempotent(tmp_path: Path) -> None:
    pdf_path = tmp_path / "source.pdf"
    data_root = tmp_path / "data"
    create_pdf(pdf_path)
    context = multiprocessing.get_context("spawn")
    processes = [
        context.Process(
            target=register_in_child,
            args=(str(pdf_path), str(data_root)),
        )
        for _ in range(4)
    ]

    for process in processes:
        process.start()
    for process in processes:
        process.join(timeout=20)

    assert [process.exitcode for process in processes] == [0] * len(processes)
    manifest_path = book_manifest_path(data_root, "rtr4-cn")
    first_bytes = manifest_path.read_bytes()
    assert all(manifest_path.read_bytes() == first_bytes for _ in range(4))


def test_terminated_lock_holder_releases_os_lock(tmp_path: Path) -> None:
    pdf_path = tmp_path / "source.pdf"
    data_root = tmp_path / "data"
    create_pdf(pdf_path)
    context = multiprocessing.get_context("spawn")
    ready = context.Event()
    holder = context.Process(
        target=hold_book_lock_in_child,
        args=(str(data_root), ready),
    )
    holder.start()
    assert ready.wait(timeout=10)
    holder.terminate()
    holder.join(timeout=10)
    assert holder.exitcode is not None

    started_at = time.monotonic()
    register_book(
        book_id="rtr4-cn",
        pdf_path=pdf_path,
        chapter="5:104-154",
        data_root=data_root,
    )

    assert time.monotonic() - started_at < 2.0


def test_book_artifacts_reject_symlink_escape(tmp_path: Path) -> None:
    pdf_path = tmp_path / "source.pdf"
    data_root = tmp_path / "data"
    outside = tmp_path / "outside"
    create_pdf(pdf_path)
    data_root.mkdir()
    outside.mkdir()
    try:
        os.symlink(outside, data_root / "books", target_is_directory=True)
    except OSError as error:
        pytest.skip(f"directory symlink unavailable: {error}")

    with pytest.raises(ValueError, match="symlink|junction|reparse|outside"):
        register_book(
            book_id="rtr4-cn",
            pdf_path=pdf_path,
            chapter="5:104-154",
            data_root=data_root,
        )

    assert not (outside / "rtr4-cn" / "book.json").exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows junction test")
def test_book_artifacts_reject_windows_junction_escape(tmp_path: Path) -> None:
    pdf_path = tmp_path / "source.pdf"
    data_root = tmp_path / "data"
    outside = tmp_path / "outside"
    create_pdf(pdf_path)
    data_root.mkdir()
    outside.mkdir()
    books_path = data_root / "books"
    result = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(books_path), str(outside)],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        pytest.skip(f"junction unavailable: {result.stderr or result.stdout}")

    with pytest.raises(ValueError, match="symlink|junction|reparse|outside"):
        register_book(
            book_id="rtr4-cn",
            pdf_path=pdf_path,
            chapter="5:104-154",
            data_root=data_root,
        )

    assert not (outside / "rtr4-cn" / "book.json").exists()


def test_source_signature_includes_ctime(tmp_path: Path) -> None:
    pdf_path = tmp_path / "source.pdf"
    create_pdf(pdf_path, page_count=1)
    metadata = pdf_path.stat()

    signature = _stat_signature(metadata)

    assert signature[-1] == metadata.st_ctime_ns
    assert len(signature) == 5


@pytest.mark.skipif(os.name != "nt", reason="Windows extended path test")
@pytest.mark.parametrize(
    ("extended", "expected"),
    [
        (r"\\?\C:\data\books", r"c:\data\books"),
        (r"\\?\UNC\server\share\books", r"\\server\share\books"),
    ],
)
def test_comparison_path_normalizes_windows_extended_prefix(
    extended: str, expected: str
) -> None:
    assert _comparison_path(Path(extended)) == expected


@pytest.mark.parametrize(
    "book_id",
    [
        "con",
        "CON",
        "con.txt",
        "prn",
        "aux",
        "nul",
        "com1",
        "COM9.log",
        "lpt1",
        "lpt9.txt",
    ],
)
def test_book_id_rejects_windows_reserved_basename(book_id: str) -> None:
    with pytest.raises(ValueError, match="reserved"):
        validate_book_id(book_id)


@pytest.mark.parametrize("kind", ["corrupt", "encrypted"])
def test_register_book_reports_unreadable_pdf_as_value_error(
    tmp_path: Path, kind: str
) -> None:
    pdf_path = tmp_path / f"{kind}.pdf"
    if kind == "corrupt":
        pdf_path.write_bytes(b"not a PDF")
    else:
        writer = PdfWriter()
        writer.add_blank_page(width=612, height=792)
        writer.encrypt("secret")
        with pdf_path.open("wb") as output:
            writer.write(output)

    with pytest.raises(
        ValueError,
        match=rf"{re.escape(str(pdf_path.resolve()))}.*corrupt or encrypted",
    ):
        register_book(
            book_id="rtr4-cn",
            pdf_path=pdf_path,
            chapter="1:1-1",
            data_root=tmp_path / "data",
        )


def test_register_cli_reports_corrupt_pdf_without_traceback(tmp_path: Path) -> None:
    pdf_path = tmp_path / "corrupt.pdf"
    pdf_path.write_bytes(b"not a PDF")

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
            "1:1-1",
            "--data-root",
            str(tmp_path / "data"),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert str(pdf_path.resolve()) in result.stderr
    assert "corrupt or encrypted" in result.stderr
    assert "Traceback" not in result.stderr
    assert "invalid pdf header" not in result.stderr
    assert "EOF marker" not in result.stderr
