from __future__ import annotations

import pytest

from rtr4_learning.corrections import apply_formula_corrections
from rtr4_learning.models import (
    Block,
    BlockSource,
    BlockType,
    BoundingBox,
    PageDocument,
)


def _pages() -> tuple[PageDocument, ...]:
    return (
        PageDocument(
            page=106,
            blocks=(
                Block(
                    id="p106-formula-5.2",
                    type=BlockType.FORMULA,
                    page=106,
                    bbox=BoundingBox(x0=0.1, y0=0.1, x1=0.9, y1=0.2),
                    latex=r"r=2(n\cdot l)n-1",
                    number="5.2",
                    source=BlockSource(
                        parser="mineru", version="3.4.4", confidence=0.9
                    ),
                ),
            ),
        ),
    )


def test_applies_evidence_backed_formula_correction() -> None:
    corrected = apply_formula_corrections(
        _pages(),
        {
            "schema_version": 1,
            "corrections": [
                {
                    "block_id": "p106-formula-5.2",
                    "page": 106,
                    "latex": r"r=2(n\cdot l)n-l",
                    "evidence": "Verified against rendered source page 106.",
                }
            ],
        },
        artifact="content/formula-corrections.json",
        artifact_sha256="a" * 64,
    )

    assert corrected[0].blocks[0].latex == r"r=2(n\cdot l)n-l"
    source = corrected[0].blocks[0].source
    assert source.correction_artifact == "content/formula-corrections.json"
    assert source.correction_sha256 == "a" * 64
    assert source.correction_evidence == "Verified against rendered source page 106."


def test_rejects_correction_for_unknown_block() -> None:
    with pytest.raises(ValueError, match="unknown formula block"):
        apply_formula_corrections(
            _pages(),
            {
                "schema_version": 1,
                "corrections": [
                    {
                        "block_id": "p106-formula-9.9",
                        "page": 106,
                        "latex": "x=y",
                        "evidence": "Verified against source.",
                    }
                ],
            },
            artifact="corrections.json",
            artifact_sha256="b" * 64,
        )
