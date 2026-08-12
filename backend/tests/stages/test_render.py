import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from pypdf import PdfWriter

from rtr4_learning.paths import book_manifest_path
from rtr4_learning.stages.register import register_book
from rtr4_learning.stages.render import parse_page_selection, render_pages


def create_registered_pdf(tmp_path: Path) -> tuple[Path, Path]:
    pdf_path = tmp_path / "source.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=300)
    writer.add_blank_page(width=400, height=500)
    with pdf_path.open("wb") as output:
        writer.write(output)
    data_root = tmp_path / "data"
    register_book(
        book_id="sample",
        pdf_path=pdf_path,
        chapter="1:1-2",
        data_root=data_root,
    )
    return pdf_path, data_root


def create_pdf(path: Path, dimensions: tuple[tuple[float, float], ...]) -> None:
    writer = PdfWriter()
    for width, height in dimensions:
        writer.add_blank_page(width=width, height=height)
    with path.open("wb") as output:
        writer.write(output)


def test_render_page_writes_png_metadata_and_manifest(tmp_path: Path) -> None:
    _pdf_path, data_root = create_registered_pdf(tmp_path)

    result = render_pages(book_id="sample", pages=(1,), scale=2, data_root=data_root)

    png_path = result.output_dir / "pages" / "p1.png"
    metadata_path = result.output_dir / "pages" / "p1.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    stage = json.loads((result.output_dir / "stage.json").read_text(encoding="utf-8"))
    assert result.reused is False
    assert png_path.is_file()
    assert metadata_path.is_file()
    assert metadata["source_page_number"] == 1
    assert metadata["pdf_points"] == {"width": 200.0, "height": 300.0}
    assert metadata["pixels"]["width"] > 0
    assert metadata["pixels"]["height"] > 0
    assert metadata["coordinate_system"] == "top-left"
    assert metadata["transforms"]["normalized_top_left_to_pixels"] == {
        "x_scale": metadata["pixels"]["width"],
        "y_scale": metadata["pixels"]["height"],
        "x_offset": 0.0,
        "y_offset": 0.0,
    }
    assert metadata["transforms"]["normalized_top_left_to_pdf_points_top_left"] == {
        "x_scale": 200.0,
        "y_scale": 300.0,
        "x_offset": 0.0,
        "y_offset": 0.0,
    }
    assert stage["stage"] == "render"
    assert stage["fingerprint"] == result.fingerprint
    assert stage["inputs"]["pages"] == [1]
    assert stage["inputs"]["scale"] == 2.0
    assert sorted(stage["outputs"]) == ["pages/p1.json", "pages/p1.png"]


def test_rerun_reuses_complete_stage_without_touching_page(tmp_path: Path) -> None:
    _pdf_path, data_root = create_registered_pdf(tmp_path)
    first = render_pages(book_id="sample", pages=(1,), scale=2, data_root=data_root)
    png_path = first.output_dir / "pages" / "p1.png"
    first_mtime = png_path.stat().st_mtime_ns

    second = render_pages(book_id="sample", pages=(1,), scale=2, data_root=data_root)

    assert second.reused is True
    assert second.fingerprint == first.fingerprint
    assert png_path.stat().st_mtime_ns == first_mtime


def test_rerun_rebuilds_stage_with_tampered_inputs(tmp_path: Path) -> None:
    _pdf_path, data_root = create_registered_pdf(tmp_path)
    first = render_pages(book_id="sample", pages=(1,), scale=2, data_root=data_root)
    stage_path = first.output_dir / "stage.json"
    stage = json.loads(stage_path.read_text(encoding="utf-8"))
    stage["inputs"]["source_sha256"] = "0" * 64
    stage_path.write_text(json.dumps(stage), encoding="utf-8")

    second = render_pages(book_id="sample", pages=(1,), scale=2, data_root=data_root)

    assert second.reused is False
    repaired = json.loads(stage_path.read_text(encoding="utf-8"))
    assert repaired["inputs"]["source_sha256"] != "0" * 64


def test_scale_and_page_selection_change_fingerprint(tmp_path: Path) -> None:
    _pdf_path, data_root = create_registered_pdf(tmp_path)

    scale_two = render_pages(book_id="sample", pages=(1,), scale=2, data_root=data_root)
    scale_three = render_pages(
        book_id="sample", pages=(1,), scale=3, data_root=data_root
    )
    two_pages = render_pages(
        book_id="sample", pages=(2, 1, 2), scale=2, data_root=data_root
    )

    assert scale_two.fingerprint != scale_three.fingerprint
    assert scale_two.fingerprint != two_pages.fingerprint
    assert (two_pages.output_dir / "pages" / "p2.png").is_file()


@pytest.mark.parametrize("pages", [(0,), (3,), ()])
def test_render_rejects_invalid_page_selection(
    tmp_path: Path, pages: tuple[int, ...]
) -> None:
    _pdf_path, data_root = create_registered_pdf(tmp_path)

    with pytest.raises(ValueError, match="page"):
        render_pages(book_id="sample", pages=pages, scale=2, data_root=data_root)


@pytest.mark.parametrize("scale", [0, -1, float("inf"), float("nan")])
def test_render_rejects_invalid_scale(tmp_path: Path, scale: float) -> None:
    _pdf_path, data_root = create_registered_pdf(tmp_path)

    with pytest.raises(ValueError, match="scale"):
        render_pages(book_id="sample", pages=(1,), scale=scale, data_root=data_root)


def test_render_does_not_publish_partial_stage_on_page_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _pdf_path, data_root = create_registered_pdf(tmp_path)
    import rtr4_learning.stages.render as render_module

    original = render_module._render_page

    def fail_second_page(*args: object, **kwargs: object) -> object:
        if kwargs["page_number"] == 2:
            raise RuntimeError("synthetic render failure")
        return original(*args, **kwargs)

    monkeypatch.setattr(render_module, "_render_page", fail_second_page)

    with pytest.raises(RuntimeError, match="synthetic render failure"):
        render_pages(book_id="sample", pages=(1, 2), scale=2, data_root=data_root)

    render_root = data_root / "books" / "sample" / "renders"
    published = [path for path in render_root.iterdir() if path.is_dir()]
    assert published == []


def test_render_rejects_registered_path_replaced_by_same_page_count_pdf(
    tmp_path: Path,
) -> None:
    pdf_path, data_root = create_registered_pdf(tmp_path)
    replacement = tmp_path / "replacement.pdf"
    create_pdf(replacement, ((612, 792), (612, 792)))
    os.replace(replacement, pdf_path)

    with pytest.raises(ValueError, match="SHA-256|identity"):
        render_pages(book_id="sample", pages=(1,), scale=2, data_root=data_root)

    render_root = data_root / "books" / "sample" / "renders"
    assert not render_root.exists() or not any(
        path.is_dir() for path in render_root.iterdir()
    )


def test_render_rejects_source_modified_during_render(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pdf_path, data_root = create_registered_pdf(tmp_path)
    replacement = tmp_path / "replacement.pdf"
    create_pdf(replacement, ((612, 792), (612, 792)))
    replacement_bytes = replacement.read_bytes()
    import rtr4_learning.stages.render as render_module

    original = render_module._render_page

    def mutate_after_first_page(*args: object, **kwargs: object) -> object:
        result = original(*args, **kwargs)
        with pdf_path.open("r+b") as source:
            source.seek(0)
            source.write(replacement_bytes)
            source.truncate()
            source.flush()
            os.fsync(source.fileno())
        return result

    monkeypatch.setattr(render_module, "_render_page", mutate_after_first_page)

    with pytest.raises(ValueError, match="changed during rendering"):
        render_pages(book_id="sample", pages=(1,), scale=2, data_root=data_root)

    render_root = data_root / "books" / "sample" / "renders"
    assert not any(path.is_dir() for path in render_root.iterdir())


def test_render_removes_published_stage_if_source_changes_at_publish_boundary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pdf_path, data_root = create_registered_pdf(tmp_path)
    replacement = tmp_path / "replacement.pdf"
    create_pdf(replacement, ((612, 792), (612, 792)))
    replacement_bytes = replacement.read_bytes()
    import rtr4_learning.stages.render as render_module

    original_rename = render_module.os.rename

    def rename_then_mutate(source: object, destination: object) -> None:
        original_rename(source, destination)
        with pdf_path.open("r+b") as pdf:
            pdf.seek(0)
            pdf.write(replacement_bytes)
            pdf.truncate()
            pdf.flush()
            os.fsync(pdf.fileno())

    monkeypatch.setattr(render_module.os, "rename", rename_then_mutate)

    with pytest.raises(ValueError, match="changed during rendering"):
        render_pages(book_id="sample", pages=(1,), scale=2, data_root=data_root)

    render_root = data_root / "books" / "sample" / "renders"
    assert not any(path.is_dir() for path in render_root.iterdir())


@pytest.mark.parametrize("artifact", ["pages/p1.png", "pages/p1.json"])
def test_rerun_rebuilds_stage_when_cached_artifact_is_truncated(
    tmp_path: Path, artifact: str
) -> None:
    _pdf_path, data_root = create_registered_pdf(tmp_path)
    first = render_pages(book_id="sample", pages=(1,), scale=2, data_root=data_root)
    artifact_path = first.output_dir / artifact
    artifact_path.write_bytes(b"")

    second = render_pages(book_id="sample", pages=(1,), scale=2, data_root=data_root)

    assert second.reused is False
    assert second.output_dir == first.output_dir
    assert artifact_path.stat().st_size > 0


def test_rerun_rebuilds_stage_when_page_metadata_is_semantically_tampered(
    tmp_path: Path,
) -> None:
    _pdf_path, data_root = create_registered_pdf(tmp_path)
    first = render_pages(book_id="sample", pages=(1,), scale=2, data_root=data_root)
    metadata_path = first.output_dir / "pages" / "p1.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["pixels"]["width"] += 1
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    stage_path = first.output_dir / "stage.json"
    stage = json.loads(stage_path.read_text(encoding="utf-8"))
    for artifact in stage["artifacts"]:
        if artifact["path"] == "pages/p1.json":
            payload = metadata_path.read_bytes()
            artifact["size"] = len(payload)
            artifact["sha256"] = hashlib.sha256(payload).hexdigest()
    stage_path.write_text(json.dumps(stage), encoding="utf-8")

    second = render_pages(book_id="sample", pages=(1,), scale=2, data_root=data_root)

    assert second.reused is False
    repaired = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert repaired["pixels"]["width"] == 400


def test_stage_manifest_records_content_identity_and_dimensions(tmp_path: Path) -> None:
    _pdf_path, data_root = create_registered_pdf(tmp_path)

    result = render_pages(book_id="sample", pages=(1,), scale=2, data_root=data_root)

    stage = json.loads((result.output_dir / "stage.json").read_text(encoding="utf-8"))
    artifacts = {artifact["path"]: artifact for artifact in stage["artifacts"]}
    assert set(artifacts) == {"pages/p1.png", "pages/p1.json"}
    for relative, artifact in artifacts.items():
        payload = (result.output_dir / relative).read_bytes()
        assert artifact["size"] == len(payload)
        assert artifact["sha256"] == hashlib.sha256(payload).hexdigest()
    assert artifacts["pages/p1.png"]["pixel_width"] == 400
    assert artifacts["pages/p1.png"]["pixel_height"] == 600
    metadata = json.loads(
        (result.output_dir / "pages" / "p1.json").read_text(encoding="utf-8")
    )
    assert metadata["stage_fingerprint"] == result.fingerprint


def test_render_wraps_corrupt_pdfium_source_as_value_error(tmp_path: Path) -> None:
    pdf_path, data_root = create_registered_pdf(tmp_path)
    corrupt = b"%PDF-corrupt"
    pdf_path.write_bytes(corrupt)
    manifest_path = book_manifest_path(data_root, "sample")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["source_sha256"] = hashlib.sha256(corrupt).hexdigest()
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match=r"source\.pdf.*corrupt|corrupt.*source\.pdf"):
        render_pages(book_id="sample", pages=(1,), scale=2, data_root=data_root)


def test_render_cli_reports_corrupt_source_without_traceback(tmp_path: Path) -> None:
    pdf_path, data_root = create_registered_pdf(tmp_path)
    corrupt = b"%PDF-corrupt"
    pdf_path.write_bytes(corrupt)
    manifest_path = book_manifest_path(data_root, "sample")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["source_sha256"] = hashlib.sha256(corrupt).hexdigest()
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "rtr4_learning.cli",
            "render",
            "--book-id",
            "sample",
            "--pages",
            "1",
            "--scale",
            "2",
            "--data-root",
            str(data_root),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert str(pdf_path) in result.stderr
    assert "corrupt" in result.stderr
    assert "Traceback" not in result.stderr


def test_parse_page_selection_rejects_huge_range_before_expansion() -> None:
    with pytest.raises(ValueError, match="at most"):
        parse_page_selection("1-999999999")


def test_render_rejects_more_than_page_limit(tmp_path: Path) -> None:
    pdf_path = tmp_path / "many.pdf"
    create_pdf(pdf_path, ((10, 10),) * 257)
    data_root = tmp_path / "data"
    register_book(
        book_id="many", pdf_path=pdf_path, chapter="1:1-257", data_root=data_root
    )

    with pytest.raises(ValueError, match="at most"):
        render_pages(
            book_id="many", pages=tuple(range(1, 258)), scale=1, data_root=data_root
        )


def test_render_rejects_scale_above_limit(tmp_path: Path) -> None:
    _pdf_path, data_root = create_registered_pdf(tmp_path)

    with pytest.raises(ValueError, match="scale.*8"):
        render_pages(book_id="sample", pages=(1,), scale=8.01, data_root=data_root)


def test_render_rejects_page_pixel_budget_before_bitmap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _pdf_path, data_root = create_registered_pdf(tmp_path)
    import rtr4_learning.stages.render as render_module

    monkeypatch.setattr(render_module, "_MAX_PAGE_PIXELS", 100)

    with pytest.raises(ValueError, match="page 1.*pixel budget"):
        render_pages(book_id="sample", pages=(1,), scale=1, data_root=data_root)


def test_render_rejects_total_pixel_budget_before_bitmap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _pdf_path, data_root = create_registered_pdf(tmp_path)
    import rtr4_learning.stages.render as render_module

    monkeypatch.setattr(render_module, "_MAX_PAGE_PIXELS", 1_000_000)
    monkeypatch.setattr(render_module, "_MAX_TOTAL_PIXELS", 100_001)

    with pytest.raises(ValueError, match="total pixel budget"):
        render_pages(book_id="sample", pages=(1, 2), scale=1, data_root=data_root)


@pytest.mark.parametrize(
    ("value", "expected"),
    [("1", (1,)), ("1-2", (1, 2)), ("2,1,2", (1, 2)), ("1,2-2", (1, 2))],
)
def test_parse_page_selection(value: str, expected: tuple[int, ...]) -> None:
    assert parse_page_selection(value) == expected


@pytest.mark.parametrize("value", ["", "0", "2-1", "x", "1-"])
def test_parse_page_selection_rejects_invalid_values(value: str) -> None:
    with pytest.raises(ValueError, match="pages"):
        parse_page_selection(value)


def test_render_cli_uses_current_directory_data_root_by_default(
    tmp_path: Path,
) -> None:
    _pdf_path, data_root = create_registered_pdf(tmp_path)
    assert book_manifest_path(data_root, "sample").is_file()

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "rtr4_learning.cli",
            "render",
            "--book-id",
            "sample",
            "--pages",
            "1-2",
            "--scale",
            "2",
        ],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    stage_files = list(
        (data_root / "books" / "sample" / "renders").glob("*/stage.json")
    )
    assert len(stage_files) == 1
