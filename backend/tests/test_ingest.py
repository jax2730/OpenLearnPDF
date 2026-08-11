from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pytest
from pypdf import PdfWriter

import rtr4_learning.ingest as ingest_module
from rtr4_learning.ingest import ingest_mineru_slice
from rtr4_learning.stages.register import register_book


def _write_pdf(path: Path, *, width: float = 595) -> None:
    writer = PdfWriter()
    writer.add_blank_page(width=width, height=842)
    with path.open("wb") as stream:
        writer.write(stream)


def _fixture(tmp_path: Path):
    source = tmp_path / "book.pdf"
    _write_pdf(source)
    data_root = tmp_path / "data"
    register_book(
        book_id="sample",
        pdf_path=source,
        chapter="5:1-1",
        data_root=data_root,
    )
    probe_root = tmp_path / "probe"
    raw_path = probe_root / "book/auto/book_content_list_v2.json"
    raw_path.parent.mkdir(parents=True)
    payload = [
        [
            {
                "type": "paragraph",
                "content": {
                    "paragraph_content": [
                        {"type": "text", "content": "old evidence"}
                    ]
                },
                "bbox": [100, 100, 900, 200],
            }
        ]
    ]
    raw_path.write_text(json.dumps(payload), encoding="utf-8")
    _write_probe(probe_root, raw_path, source)
    return data_root, source, probe_root, raw_path, payload


def _write_probe(probe_root: Path, raw_path: Path, source: Path) -> None:
    relative = raw_path.relative_to(probe_root)
    (probe_root / "probe.json").write_text(
        json.dumps(
            {
                "status": "succeeded",
                "source_pdf": str(source.resolve()),
                "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                "canonical_pages": [1],
                "toolchain": {"packages": {"mineru": "3.4.4"}},
                "artifacts": [
                    {
                        "path": str(relative),
                        "bytes": raw_path.stat().st_size,
                        "sha256": hashlib.sha256(raw_path.read_bytes()).hexdigest(),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def _ingest(data_root: Path, raw_path: Path):
    return ingest_mineru_slice(
        data_root=data_root,
        book_id="sample",
        content_list=raw_path,
        first_page=1,
        parser_version="3.4.4",
        chapter=5,
    )


def test_file_identity_ignores_access_time_changes() -> None:
    before = SimpleNamespace(
        st_dev=1,
        st_ino=2,
        st_mode=3,
        st_size=4,
        st_mtime_ns=5,
        st_ctime_ns=6,
        st_atime_ns=7,
    )
    after = SimpleNamespace(**{**vars(before), "st_atime_ns": 8})

    assert ingest_module._file_identity(before) == ingest_module._file_identity(after)


def test_ingest_rejects_registered_pdf_replaced_after_registration(tmp_path) -> None:
    data_root, source, _, raw_path, _ = _fixture(tmp_path)
    _write_pdf(source, width=596)

    with pytest.raises(ValueError, match="SHA-256"):
        _ingest(data_root, raw_path)


def test_ingest_rejects_probe_bound_to_another_source(tmp_path) -> None:
    data_root, _, probe_root, raw_path, _ = _fixture(tmp_path)
    probe = json.loads((probe_root / "probe.json").read_text(encoding="utf-8"))
    probe["source_pdf"] = str((tmp_path / "other.pdf").resolve())
    (probe_root / "probe.json").write_text(json.dumps(probe), encoding="utf-8")

    with pytest.raises(ValueError, match="probe source"):
        _ingest(data_root, raw_path)


def test_ingest_rejects_same_length_content_list_tampering(tmp_path) -> None:
    data_root, _, _, raw_path, _ = _fixture(tmp_path)
    raw_path.write_text(
        raw_path.read_text(encoding="utf-8").replace("old evidence", "new evidence"),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="artifact SHA-256"):
        _ingest(data_root, raw_path)


def test_concurrent_ingest_serializes_active_publish(tmp_path, monkeypatch) -> None:
    data_root, _, _, raw_path, _ = _fixture(tmp_path)
    real_atomic_write = ingest_module._atomic_write_text
    state_lock = threading.Lock()
    active_writers = 0

    def reject_overlap(path: Path, content: str) -> None:
        nonlocal active_writers
        if path.name != "active.json":
            real_atomic_write(path, content)
            return
        with state_lock:
            active_writers += 1
            overlap = active_writers > 1
        try:
            if overlap:
                raise PermissionError("synthetic concurrent active publish")
            time.sleep(0.05)
            real_atomic_write(path, content)
        finally:
            with state_lock:
                active_writers -= 1

    monkeypatch.setattr(ingest_module, "_atomic_write_text", reject_overlap)

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: _ingest(data_root, raw_path), range(2)))

    assert results[0].normalized_path == results[1].normalized_path


def test_parallel_processes_publish_same_build_without_failures(tmp_path) -> None:
    data_root, _, _, raw_path, _ = _fixture(tmp_path)
    _ingest(data_root, raw_path)
    code = (
        "from rtr4_learning.ingest import ingest_mineru_slice;"
        f"ingest_mineru_slice(data_root={str(data_root)!r},book_id='sample',"
        f"content_list={str(raw_path)!r},first_page=1,parser_version='3.4.4',"
        "chapter=5)"
    )

    for _ in range(4):
        processes = [
            subprocess.Popen(
                [sys.executable, "-c", code],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            for _ in range(4)
        ]
        completed = [process.communicate(timeout=30) for process in processes]
        assert all(process.returncode == 0 for process in processes), completed


def test_failed_active_pointer_publish_keeps_previous_bundle(tmp_path, monkeypatch) -> None:
    data_root, source, probe_root, raw_path, payload = _fixture(tmp_path)
    first = _ingest(data_root, raw_path)
    active_path = data_root / "books/sample/active.json"
    active_before = active_path.read_bytes()
    pages_before = first.normalized_path.read_bytes()

    payload[0][0]["content"]["paragraph_content"][0]["content"] = "new evidence"
    raw_path.write_text(json.dumps(payload), encoding="utf-8")
    _write_probe(probe_root, raw_path, source)
    real_atomic_write = ingest_module._atomic_write_text

    def fail_active(path: Path, content: str) -> None:
        if path.name == "active.json":
            raise OSError("synthetic pointer failure")
        real_atomic_write(path, content)

    monkeypatch.setattr(ingest_module, "_atomic_write_text", fail_active)

    with pytest.raises(OSError, match="synthetic pointer failure"):
        _ingest(data_root, raw_path)

    assert active_path.read_bytes() == active_before
    active = json.loads(active_before)
    old_pages = data_root / "books/sample/builds" / active["build_id"] / "normalized/pages.json"
    assert old_pages.read_bytes() == pages_before
