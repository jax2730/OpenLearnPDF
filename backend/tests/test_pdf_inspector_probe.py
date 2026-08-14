from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from rtr4_learning.pdf_inspector_probe import (
    build_probe_report,
    load_pdf_inspector,
    run_probe,
    sha256_file,
    to_zero_based_pages,
)


def _page(page: int, markdown: str, *, needs_ocr: bool = False):
    return SimpleNamespace(
        page=page - 1,
        markdown=markdown,
        needs_ocr=needs_ocr,
        ocr_reason="scanned" if needs_ocr else None,
    )


def _item(page: int, text: str, **overrides: object):
    values: dict[str, object] = {
        "page": page,
        "text": text,
        "x": 10.0,
        "y": 20.0,
        "width": 30.0,
        "height": 12.0,
        "item_type": "text",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _classification(**overrides: object):
    values: dict[str, object] = {
        "pdf_type": "text_based",
        "confidence": 0.98,
        "page_count": 500,
        "pages_needing_ocr": [],
        "has_encoding_issues": False,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_to_zero_based_pages_validates_and_normalizes_one_based_pages() -> None:
    assert to_zero_based_pages([113, 109, 111, 109]) == (108, 110, 112)

    with pytest.raises(ValueError, match="positive"):
        to_zero_based_pages([0])


def test_report_accepts_complete_native_text_evidence() -> None:
    report = build_probe_report(
        requested_pages=(109, 111, 113),
        classification=_classification(),
        page_markdown=[
            _page(109, "精确光源 公式 5.9"),
            _page(111, "平方反比衰减 5.11 5.14"),
            _page(113, "聚光灯 5.17 5.18"),
        ],
        positioned_items=[
            _item(109, "精确光源"),
            _item(111, "平方反比衰减"),
            _item(113, "聚光灯"),
        ],
        expected_anchors={
            109: ("精确光源", "5.9"),
            111: ("平方反比衰减", "5.11", "5.14"),
            113: ("聚光灯", "5.17", "5.18"),
        },
    )

    assert report["recommendation"] == "native_text_candidate"
    assert report["capabilities"] == {
        "native_text": "supported",
        "formula_semantics": "unsupported",
        "image_understanding": "unsupported",
    }
    assert all(page["route"] == "native_text" for page in report["pages"])
    assert all(page["missing_anchors"] == [] for page in report["pages"])


def test_report_routes_ocr_page_to_mineru_and_counts_image_placeholders() -> None:
    report = build_probe_report(
        requested_pages=(109, 111),
        classification=_classification(pdf_type="mixed", pages_needing_ocr=[111]),
        page_markdown=[
            _page(109, "精确光源 5.9"),
            _page(111, "", needs_ocr=True),
        ],
        positioned_items=[
            _item(109, "精确光源"),
            _item(109, "[Image: Im0]", item_type="image"),
        ],
        expected_anchors={109: ("精确光源", "5.9"), 111: ("5.11",)},
    )

    assert report["recommendation"] == "routing_preflight_only"
    assert report["pages"][0]["image_placeholder_count"] == 1
    assert report["pages"][1]["route"] == "mineru"
    assert report["pages"][1]["ocr_reason"] == "scanned"


def test_report_rejects_corrupt_cjk_or_invalid_geometry() -> None:
    report = build_probe_report(
        requested_pages=(109,),
        classification=_classification(has_encoding_issues=True),
        page_markdown=[_page(109, "���")],
        positioned_items=[_item(109, "���", width=float("nan"))],
        expected_anchors={109: ("精确光源", "5.9")},
    )

    assert report["recommendation"] == "reject_cjk_quality"
    assert report["pages"][0]["invalid_geometry_count"] == 1
    assert report["pages"][0]["missing_anchors"] == ["精确光源", "5.9"]


def test_report_requires_every_requested_page() -> None:
    with pytest.raises(ValueError, match="requested pages"):
        build_probe_report(
            requested_pages=(109, 111),
            classification=_classification(),
            page_markdown=[_page(109, "精确光源 5.9")],
            positioned_items=[_item(109, "精确光源")],
            expected_anchors={109: ("精确光源",), 111: ("5.11",)},
        )


class _FakePdfInspector:
    __version__ = "1.14.1"

    @staticmethod
    def detect_pdf(path: str):
        assert Path(path).is_file()
        return _classification()

    @staticmethod
    def extract_pages_markdown(path: str, pages: list[int]):
        assert pages == [108, 110, 112]
        return SimpleNamespace(
            pages=[
                _page(109, "精确光源 5.9"),
                _page(111, "平方反比衰减 5.11 5.14"),
                _page(113, "聚光灯 5.17 5.18"),
            ]
        )

    @staticmethod
    def extract_text_with_positions(path: str, pages: list[int]):
        assert pages == [109, 111, 113]
        return [
            _item(109, "精确光源"),
            _item(111, "平方反比衰减"),
            _item(113, "聚光灯"),
        ]


def test_sha256_file_reads_source_without_copying_it(tmp_path: Path) -> None:
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-test")

    assert sha256_file(source) == (
        "3c87d37f1dbea6909f917ce437c390fb8e655a774387d9e69301c0b2283d5b63"
    )


def test_run_probe_writes_immutable_utf8_artifacts(tmp_path: Path) -> None:
    source = tmp_path / "RTR4-CN-v1.1.pdf"
    source.write_bytes(b"%PDF-test")
    output = tmp_path / "data" / "probe-run"

    result = run_probe(
        source_path=source,
        output_dir=output,
        requested_pages=(109, 111, 113),
        expected_anchors={
            109: ("精确光源", "5.9"),
            111: ("平方反比衰减", "5.11", "5.14"),
            113: ("聚光灯", "5.17", "5.18"),
        },
        pdf_inspector=_FakePdfInspector(),
    )

    assert result["recommendation"] == "native_text_candidate"
    assert sorted(path.name for path in output.iterdir()) == [
        "classification.json",
        "pages.json",
        "report.json",
        "report.md",
        "run.json",
    ]
    assert "精确光源" in (output / "pages.json").read_text(encoding="utf-8")
    assert "native_text_candidate" in (output / "report.md").read_text(
        encoding="utf-8"
    )

    with pytest.raises(FileExistsError, match="already exists"):
        run_probe(
            source_path=source,
            output_dir=output,
            requested_pages=(109, 111, 113),
            expected_anchors={},
            pdf_inspector=_FakePdfInspector(),
        )


def test_run_probe_rejects_non_pdf_before_creating_output(tmp_path: Path) -> None:
    source = tmp_path / "not-a-pdf.pdf"
    source.write_bytes(b"plain text")
    output = tmp_path / "probe"

    with pytest.raises(ValueError, match="PDF header"):
        run_probe(
            source_path=source,
            output_dir=output,
            requested_pages=(109,),
            expected_anchors={},
            pdf_inspector=_FakePdfInspector(),
        )

    assert not output.exists()


def test_missing_native_package_has_actionable_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def missing(_name: str):
        raise ModuleNotFoundError("missing")

    monkeypatch.setattr("importlib.import_module", missing)

    with pytest.raises(RuntimeError, match="probe-pdf-inspector.ps1"):
        load_pdf_inspector()
