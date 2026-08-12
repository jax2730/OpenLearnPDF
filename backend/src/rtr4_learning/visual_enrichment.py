"""Source-reviewed visual enrichment policy."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from io import BytesIO
from pathlib import Path
from typing import Annotated

import pypdfium2 as pdfium
from PIL import Image
from pydantic import Field, field_validator, model_validator

from rtr4_learning.models import (
    Block,
    BlockSource,
    BlockType,
    BookManifest,
    BoundingBox,
    ContractModel,
    PageDocument,
    StageArtifact,
)
from rtr4_learning.stages.render import _verified_source

_FIXED_FIGURES = (
    ("5.6", 112),
    ("5.15", 126),
    ("5.16", 126),
    ("5.18", 128),
    ("5.22", 130),
    ("5.23", 131),
    ("5.41", 153),
)


class VisualFigure(ContractModel):
    number: Annotated[str, Field(pattern=r"^5\.[0-9]+$")]
    page: Annotated[int, Field(ge=104, le=154)]
    bbox: BoundingBox
    caption: Annotated[str, Field(min_length=1)]
    crop_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    evidence: Annotated[str, Field(min_length=1)]

    @field_validator("bbox", mode="before")
    @classmethod
    def parse_bbox(cls, value: object) -> object:
        if isinstance(value, list) and len(value) == 4:
            return dict(zip(("x0", "y0", "x1", "y1"), value, strict=True))
        return value


class VisualTextCorrection(ContractModel):
    block_id: Annotated[str, Field(pattern=r"^p133-paragraph-1$")]
    page: Annotated[int, Field(ge=133, le=133)]
    source_text: Annotated[str, Field(min_length=1)]
    replacement_text: Annotated[str, Field(min_length=1)]
    evidence: Annotated[str, Field(min_length=1)]


class VisualValidationDisposition(ContractModel):
    code: Annotated[str, Field(pattern=r"^unknown_explicit_reference$")]
    block_id: Annotated[str, Field(pattern=r"^p149-paragraph-2$")]
    evidence: Annotated[str, Field(min_length=1)]


class VisualEnrichmentPolicy(ContractModel):
    schema_version: int
    render_scale: Annotated[int, Field(ge=1, le=8)]
    figures: tuple[VisualFigure, ...]
    text_corrections: tuple[VisualTextCorrection, ...] = ()
    validation_dispositions: tuple[VisualValidationDisposition, ...] = ()

    @model_validator(mode="after")
    def fixed_chapter_policy(self) -> VisualEnrichmentPolicy:
        if self.schema_version != 1:
            raise ValueError("visual enrichment schema_version must be 1")
        if tuple((figure.number, figure.page) for figure in self.figures) != _FIXED_FIGURES:
            raise ValueError("visual enrichment figures do not match chapter 5 policy")
        if len(self.text_corrections) > 1 or len(self.validation_dispositions) > 1:
            raise ValueError("visual enrichment auxiliary policy is not fixed")
        return self


def load_visual_enrichments(path: str | Path) -> VisualEnrichmentPolicy:
    payload = json.loads(Path(path).read_bytes())
    return VisualEnrichmentPolicy.model_validate(payload)


def _png_bytes(image: Image.Image) -> bytes:
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def render_visual_enrichments(
    manifest: BookManifest,
    policy: VisualEnrichmentPolicy,
    build_root: str | Path,
) -> tuple[StageArtifact, ...]:
    """Render verified figure crops and atomically publish them below a build."""
    root = Path(build_root).resolve()
    if root.exists() and not root.is_dir():
        raise ValueError(f"build root is not a directory: {root}")
    if any(figure.page > manifest.page_count for figure in policy.figures):
        raise ValueError("visual enrichment page exceeds registered PDF page count")
    root.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".visual-enrichment-", dir=root.parent))
    temporary_assets = temporary / "assets" / "enriched"
    temporary_assets.mkdir(parents=True)
    artifacts: list[StageArtifact] = []
    try:
        with _verified_source(manifest) as source:
            try:
                document = pdfium.PdfDocument(source.stream)
            except (pdfium.PdfiumError, OSError) as error:
                raise ValueError(f"registered PDF is corrupt: {source.path}") from error
            try:
                if len(document) != manifest.page_count:
                    raise ValueError("registered PDF page count changed")
                for figure in policy.figures:
                    page = document[figure.page - 1]
                    bitmap = None
                    try:
                        bitmap = page.render(scale=policy.render_scale)
                        image = bitmap.to_pil()
                        width, height = image.size
                        crop = image.crop(
                            (
                                round(figure.bbox.x0 * width),
                                round(figure.bbox.y0 * height),
                                round(figure.bbox.x1 * width),
                                round(figure.bbox.y1 * height),
                            )
                        )
                        payload = _png_bytes(crop)
                    finally:
                        if bitmap is not None:
                            bitmap.close()
                        page.close()
                    digest = hashlib.sha256(payload).hexdigest()
                    if digest != figure.crop_sha256:
                        raise ValueError(
                            f"crop SHA-256 mismatch for figure {figure.number}"
                        )
                    relative = f"assets/enriched/figure-{figure.number}.png"
                    output = temporary / relative
                    output.write_bytes(payload)
                    artifacts.append(
                        StageArtifact(
                            path=relative,
                            size=len(payload),
                            sha256=digest,
                            pixel_width=crop.width,
                            pixel_height=crop.height,
                        )
                    )
            finally:
                document.close()
            source.verify_unchanged()

        published_assets = root / "assets" / "enriched"
        if published_assets.exists():
            raise ValueError(f"visual enrichment assets already exist: {published_assets}")
        published_assets.parent.mkdir(parents=True, exist_ok=True)
        os.rename(temporary_assets, published_assets)
        return tuple(artifacts)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


_REPLACED_BLOCKS = {
    "5.16": "p126-paragraph-5",
    "5.41": "p153-figure-1",
}


def apply_visual_enrichments(
    pages: tuple[PageDocument, ...],
    policy: VisualEnrichmentPolicy,
    *,
    artifact: str,
    artifact_sha256: str,
) -> tuple[PageDocument, ...]:
    """Add reviewed figure/caption blocks without mutating source pages."""
    existing_ids = {block.id for page in pages for block in page.blocks}
    generated_ids = {
        block_id
        for figure in policy.figures
        for block_id in (
            f"p{figure.page}-figure-{figure.number}",
            f"p{figure.page}-figure_caption-{figure.number}",
        )
    }
    if existing_ids & generated_ids:
        raise ValueError("duplicate visual enrichment block")

    by_page: dict[int, list[tuple[VisualFigure, Block, Block]]] = {}
    for figure in policy.figures:
        source = BlockSource(
            parser="visual_enrichment",
            version="1",
            confidence=1.0,
            raw_artifact=artifact,
            raw_block_id=figure.number,
            enrichment_artifact=artifact,
            enrichment_sha256=artifact_sha256,
            enrichment_evidence=figure.evidence,
        )
        figure_block = Block(
            id=f"p{figure.page}-figure-{figure.number}",
            type=BlockType.FIGURE,
            page=figure.page,
            bbox=figure.bbox,
            number=figure.number,
            asset_path=f"assets/enriched/figure-{figure.number}.png",
            source=source,
        )
        caption_block = Block(
            id=f"p{figure.page}-figure_caption-{figure.number}",
            type=BlockType.FIGURE_CAPTION,
            page=figure.page,
            bbox=figure.bbox,
            text=figure.caption,
            number=figure.number,
            source=source,
        )
        by_page.setdefault(figure.page, []).append(
            (figure, figure_block, caption_block)
        )

    available_pages = {page.page for page in pages}
    missing_pages = set(by_page) - available_pages
    if missing_pages:
        raise ValueError(
            f"visual enrichment pages are absent: {sorted(missing_pages)}"
        )

    corrections = {item.block_id: item for item in policy.text_corrections}
    present_pages = {page.page for page in pages}
    present_ids = {block.id for page in pages for block in page.blocks}
    for correction in policy.text_corrections:
        if correction.page in present_pages and correction.block_id not in present_ids:
            raise ValueError(f"unknown text correction block: {correction.block_id}")

    enriched_pages: list[PageDocument] = []
    for page in pages:
        replacements = {
            _REPLACED_BLOCKS[figure.number]
            for figure, _, _ in by_page.get(page.page, ())
            if figure.number in _REPLACED_BLOCKS
        }
        blocks = []
        for block in page.blocks:
            if block.id in replacements:
                continue
            correction = corrections.get(block.id)
            if correction is not None:
                if block.text != correction.source_text:
                    raise ValueError(
                        f"text correction source mismatch: {block.id}"
                    )
                block = block.model_copy(
                    update={
                        "text": correction.replacement_text,
                        "source": block.source.model_copy(
                            update={
                                "enrichment_artifact": artifact,
                                "enrichment_sha256": artifact_sha256,
                                "enrichment_evidence": correction.evidence,
                            }
                        ),
                    }
                )
            blocks.append(block)
        for figure, figure_block, caption_block in by_page.get(page.page, ()):
            insertion = next(
                (
                    index
                    for index, block in enumerate(blocks)
                    if block.bbox.y0 >= figure.bbox.y0
                ),
                len(blocks),
            )
            blocks[insertion:insertion] = [figure_block, caption_block]
        enriched_pages.append(page.model_copy(update={"blocks": tuple(blocks)}))
    return tuple(enriched_pages)
