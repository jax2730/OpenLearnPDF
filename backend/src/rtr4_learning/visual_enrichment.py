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
    BookManifest,
    BoundingBox,
    ContractModel,
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


class VisualEnrichmentPolicy(ContractModel):
    schema_version: int
    render_scale: Annotated[int, Field(ge=1, le=8)]
    figures: tuple[VisualFigure, ...]

    @model_validator(mode="after")
    def fixed_chapter_policy(self) -> VisualEnrichmentPolicy:
        if self.schema_version != 1:
            raise ValueError("visual enrichment schema_version must be 1")
        if tuple((figure.number, figure.page) for figure in self.figures) != _FIXED_FIGURES:
            raise ValueError("visual enrichment figures do not match chapter 5 policy")
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
