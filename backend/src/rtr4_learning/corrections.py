"""Apply explicit source-verified formula corrections."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from rtr4_learning.models import BlockType, PageDocument


def apply_formula_corrections(
    pages: Sequence[PageDocument],
    payload: Mapping[str, object],
    *,
    artifact: str,
    artifact_sha256: str,
) -> tuple[PageDocument, ...]:
    if payload.get("schema_version") != 1:
        raise ValueError("formula corrections schema_version must be 1")
    corrections = payload.get("corrections")
    if not isinstance(corrections, list):
        raise TypeError("formula corrections must be a list")

    blocks = {block.id: block for page in pages for block in page.blocks}
    replacements: dict[str, tuple[str, str]] = {}
    for correction in corrections:
        if not isinstance(correction, dict):
            raise TypeError("formula correction must be an object")
        block_id = correction.get("block_id")
        page = correction.get("page")
        latex = correction.get("latex")
        evidence = correction.get("evidence")
        if not all(
            isinstance(value, str) and value.strip()
            for value in (block_id, latex, evidence)
        ):
            raise ValueError("formula correction requires block_id, latex and evidence")
        block = blocks.get(block_id)
        if block is None or block.type is not BlockType.FORMULA:
            raise ValueError(f"unknown formula block in correction: {block_id}")
        if isinstance(page, bool) or not isinstance(page, int) or page != block.page:
            raise ValueError(f"formula correction page does not match block: {block_id}")
        if block_id in replacements:
            raise ValueError(f"duplicate formula correction: {block_id}")
        replacements[block_id] = (latex, evidence)

    return tuple(
        page.model_copy(
            update={
                "blocks": tuple(
                    block.model_copy(
                        update={
                            "latex": replacements[block.id][0],
                            "source": block.source.model_copy(
                                update={
                                    "correction_artifact": artifact,
                                    "correction_sha256": artifact_sha256,
                                    "correction_evidence": replacements[block.id][1],
                                }
                            ),
                        }
                    )
                    if block.id in replacements
                    else block
                    for block in page.blocks
                )
            }
        )
        for page in pages
    )
