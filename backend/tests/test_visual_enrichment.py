from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pypdfium2 as pdfium
import pytest
from PIL import Image
from pypdf import PdfWriter

from rtr4_learning.models import BookManifest

REPO_ROOT = Path(__file__).resolve().parents[2]


def _payload() -> dict[str, object]:
    figures = []
    for number, page in (
        ("5.6", 112),
        ("5.15", 126),
        ("5.16", 126),
        ("5.18", 128),
        ("5.22", 130),
        ("5.23", 131),
        ("5.41", 153),
    ):
        figures.append(
            {
                "number": number,
                "page": page,
                "bbox": [0.1, 0.1, 0.9, 0.5],
                "caption": f"Figure {number} reviewed caption.",
                "crop_sha256": "a" * 64,
                "evidence": f"Visually verified on PDF page {page}.",
            }
        )
    return {"schema_version": 1, "render_scale": 3, "figures": figures}


def _source_and_policy(tmp_path: Path) -> tuple[BookManifest, object]:
    from rtr4_learning.visual_enrichment import VisualEnrichmentPolicy

    source = tmp_path / "source.pdf"
    writer = PdfWriter()
    for _ in range(153):
        writer.add_blank_page(width=20, height=20)
    with source.open("wb") as output:
        writer.write(output)
    payload = _payload()
    payload["render_scale"] = 1
    document = pdfium.PdfDocument(source)
    try:
        page = document[111]
        try:
            bitmap = page.render(scale=1)
            try:
                image = bitmap.to_pil().crop((2, 2, 18, 10))
                output = tmp_path / "expected.png"
                image.save(output, format="PNG")
            finally:
                bitmap.close()
        finally:
            page.close()
    finally:
        document.close()
    expected_hash = hashlib.sha256(output.read_bytes()).hexdigest()
    for figure in payload["figures"]:
        figure["bbox"] = [0.1, 0.1, 0.9, 0.5]
        figure["crop_sha256"] = expected_hash
    manifest = BookManifest(
        id="sample",
        title="Sample",
        source_path=str(source.resolve()),
        source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        page_count=153,
    )
    return manifest, VisualEnrichmentPolicy.model_validate(payload)


def test_loads_fixed_chapter_5_visual_policy(tmp_path: Path) -> None:
    from rtr4_learning.visual_enrichment import load_visual_enrichments

    path = tmp_path / "visual-enrichments.json"
    path.write_text(json.dumps(_payload()), encoding="utf-8")

    policy = load_visual_enrichments(path)

    assert [figure.number for figure in policy.figures] == [
        "5.6",
        "5.15",
        "5.16",
        "5.18",
        "5.22",
        "5.23",
        "5.41",
    ]
    assert [figure.page for figure in policy.figures] == [112, 126, 126, 128, 130, 131, 153]
    assert policy.render_scale == 3


def test_committed_chapter_5_visual_policy_is_source_reviewed() -> None:
    from rtr4_learning.visual_enrichment import load_visual_enrichments

    policy = load_visual_enrichments(
        REPO_ROOT / "content/rtr4-cn/chapter-05/visual-enrichments.json"
    )

    assert len(policy.figures) == 7
    assert all(figure.caption.startswith(f"图 {figure.number}：") for figure in policy.figures)
    assert all("RTR4-CN-v1.1.pdf" in figure.evidence for figure in policy.figures)


def test_renders_deterministic_verified_png_assets(tmp_path: Path) -> None:
    from rtr4_learning.visual_enrichment import render_visual_enrichments

    manifest, policy = _source_and_policy(tmp_path)
    first_root = tmp_path / "build-1"
    second_root = tmp_path / "build-2"

    first = render_visual_enrichments(manifest, policy, first_root)
    second = render_visual_enrichments(manifest, policy, second_root)

    assert first == second
    assert [asset.path for asset in first] == [
        f"assets/enriched/figure-{number}.png"
        for number in ("5.6", "5.15", "5.16", "5.18", "5.22", "5.23", "5.41")
    ]
    for asset in first:
        first_bytes = (first_root / asset.path).read_bytes()
        second_bytes = (second_root / asset.path).read_bytes()
        assert first_bytes == second_bytes
        assert hashlib.sha256(first_bytes).hexdigest() == asset.sha256
        with Image.open(first_root / asset.path) as image:
            assert image.size == (16, 8)


def test_rejects_crop_hash_mismatch_without_publishing_assets(tmp_path: Path) -> None:
    from rtr4_learning.visual_enrichment import render_visual_enrichments

    manifest, policy = _source_and_policy(tmp_path)
    payload = policy.model_dump(mode="json")
    payload["figures"][0]["crop_sha256"] = "0" * 64
    bad_policy = type(policy).model_validate(payload)
    build_root = tmp_path / "build"

    with pytest.raises(ValueError, match="crop SHA-256 mismatch.*5.6"):
        render_visual_enrichments(manifest, bad_policy, build_root)

    assert not (build_root / "assets").exists()


def test_rejects_manifest_page_mismatch_and_replaced_source(tmp_path: Path) -> None:
    from rtr4_learning.visual_enrichment import render_visual_enrichments

    manifest, policy = _source_and_policy(tmp_path)
    short_manifest = manifest.model_copy(update={"page_count": 120})
    with pytest.raises(ValueError, match="page.*page count"):
        render_visual_enrichments(short_manifest, policy, tmp_path / "short")

    replacement = tmp_path / "replacement.pdf"
    replacement.write_bytes(Path(manifest.source_path).read_bytes() + b"changed")
    os.replace(replacement, manifest.source_path)
    with pytest.raises(ValueError, match="SHA-256"):
        render_visual_enrichments(manifest, policy, tmp_path / "replaced")


def test_rejects_output_root_that_is_not_a_directory(tmp_path: Path) -> None:
    from rtr4_learning.visual_enrichment import render_visual_enrichments

    manifest, policy = _source_and_policy(tmp_path)
    output = tmp_path / "build"
    output.write_text("not a directory", encoding="utf-8")

    with pytest.raises(ValueError, match="build root"):
        render_visual_enrichments(manifest, policy, output)


@pytest.mark.parametrize(
    "change",
    [
        lambda payload: payload.update(schema_version=2),
        lambda payload: payload["figures"].pop(),
        lambda payload: payload["figures"][0].update(page=111),
        lambda payload: payload["figures"][0].update(bbox=[0, 0, 1.1, 1]),
        lambda payload: payload["figures"][0].update(crop_sha256="bad"),
        lambda payload: payload["figures"][0].update(evidence=""),
    ],
)
def test_rejects_visual_policy_outside_fixed_contract(tmp_path: Path, change) -> None:
    from rtr4_learning.visual_enrichment import load_visual_enrichments

    payload = _payload()
    change(payload)
    path = tmp_path / "visual-enrichments.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises((ValueError, TypeError)):
        load_visual_enrichments(path)
