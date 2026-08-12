from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pypdfium2 as pdfium
import pytest
from PIL import Image
from pypdf import PdfWriter

from rtr4_learning.models import (
    Block,
    BlockSource,
    BlockType,
    BookManifest,
    BoundingBox,
    PageDocument,
)

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
    return {
        "schema_version": 1,
        "render_scale": 3,
        "figures": figures,
        "text_corrections": [],
        "validation_dispositions": [],
    }


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
    assert policy.text_corrections[0].block_id == "p133-paragraph-1"
    assert policy.validation_dispositions[0].block_id == "p149-paragraph-2"


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


def _block(
    block_id: str,
    page: int,
    text: str | None = None,
    *,
    block_type: BlockType = BlockType.TEXT,
    number: str | None = None,
) -> Block:
    return Block(
        id=block_id,
        type=block_type,
        page=page,
        bbox=BoundingBox(x0=0.1, y0=0.8, x1=0.9, y1=0.9),
        text=text,
        number=number,
        asset_path="images/existing.png" if block_type is BlockType.FIGURE else None,
        source=BlockSource(parser="mineru", version="3.4.4", confidence=0.5),
    )


def test_applies_blocks_replaces_misclassified_content_and_links_relations() -> None:
    from rtr4_learning.relations import link_relations
    from rtr4_learning.visual_enrichment import (
        apply_visual_enrichments,
        load_visual_enrichments,
    )

    policy = load_visual_enrichments(
        REPO_ROOT / "content/rtr4-cn/chapter-05/visual-enrichments.json"
    )
    pages = (
        PageDocument(
            page=111,
            blocks=(_block("p111-paragraph-6", 111, "如图5.6所示。"),),
        ),
        PageDocument(
            page=112,
            blocks=(_block("p112-paragraph-1", 112, "后续正文"),),
        ),
        PageDocument(
            page=126,
            blocks=(
                _block("p126-paragraph-3", 126, "图5.15展示采样。"),
                _block("p126-paragraph-4", 126, "如图5.16所示。"),
                _block("p126-paragraph-5", 126, policy.figures[2].caption),
            ),
        ),
        PageDocument(page=128),
        PageDocument(page=130),
        PageDocument(page=131),
        PageDocument(
            page=153,
            blocks=(
                _block(
                    "p153-figure-1",
                    153,
                    block_type=BlockType.FIGURE,
                ),
                _block("p153-list-1", 153, "图5.41展示边缘。"),
            ),
        ),
    )

    enriched = apply_visual_enrichments(
        pages,
        policy,
        artifact="visual-enrichments.json",
        artifact_sha256="a" * 64,
    )
    linked = link_relations(enriched)
    blocks = {block.id: block for page in linked for block in page.blocks}

    assert "p126-paragraph-5" not in blocks
    assert "p153-figure-1" not in blocks
    for figure in policy.figures:
        figure_id = f"p{figure.page}-figure-{figure.number}"
        caption_id = f"p{figure.page}-figure_caption-{figure.number}"
        assert blocks[figure_id].asset_path == f"assets/enriched/figure-{figure.number}.png"
        assert blocks[caption_id].text == figure.caption
        assert any(
            relation.type == "caption_of" and relation.target == figure_id
            for relation in blocks[caption_id].relations
        )
        assert blocks[figure_id].source.enrichment_sha256 == "a" * 64
        assert blocks[figure_id].source.enrichment_evidence == figure.evidence
    assert any(
        relation.type == "refers_to" and relation.target == "p112-figure-5.6"
        for relation in blocks["p111-paragraph-6"].relations
    )


def test_visual_application_is_deterministic_and_rejects_duplicates() -> None:
    from rtr4_learning.visual_enrichment import (
        apply_visual_enrichments,
        load_visual_enrichments,
    )

    policy = load_visual_enrichments(
        REPO_ROOT / "content/rtr4-cn/chapter-05/visual-enrichments.json"
    )
    pages = tuple(PageDocument(page=page) for page in (112, 126, 128, 130, 131, 153))
    first = apply_visual_enrichments(
        pages, policy, artifact="sidecar.json", artifact_sha256="b" * 64
    )
    second = apply_visual_enrichments(
        pages, policy, artifact="sidecar.json", artifact_sha256="b" * 64
    )
    assert first == second
    with pytest.raises(ValueError, match="duplicate visual enrichment"):
        apply_visual_enrichments(
            first, policy, artifact="sidecar.json", artifact_sha256="b" * 64
        )


def test_applies_reviewed_text_correction_and_rejects_stale_source() -> None:
    from rtr4_learning.visual_enrichment import (
        apply_visual_enrichments,
        load_visual_enrichments,
    )

    policy = load_visual_enrichments(
        REPO_ROOT / "content/rtr4-cn/chapter-05/visual-enrichments.json"
    )
    correction = policy.text_corrections[0]
    pages = tuple(
        PageDocument(
            page=page,
            blocks=(
                _block(correction.block_id, page, correction.source_text)
                if page == 133
                else _block(f"p{page}-paragraph-1", page, "text")
            ,),
        )
        for page in (112, 126, 128, 130, 131, 133, 153)
    )

    enriched = apply_visual_enrichments(
        pages, policy, artifact="sidecar.json", artifact_sha256="c" * 64
    )
    corrected = next(
        block
        for page in enriched
        for block in page.blocks
        if block.id == correction.block_id
    )
    assert corrected.text == correction.replacement_text
    assert corrected.source.enrichment_sha256 == "c" * 64

    stale_pages = tuple(
        page.model_copy(
            update={
                "blocks": tuple(
                    block.model_copy(update={"text": "changed"})
                    if block.id == correction.block_id
                    else block
                    for block in page.blocks
                )
            }
        )
        for page in pages
    )
    with pytest.raises(ValueError, match="text correction source mismatch"):
        apply_visual_enrichments(
            stale_pages,
            policy,
            artifact="sidecar.json",
            artifact_sha256="c" * 64,
        )


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
