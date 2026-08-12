"""Quality checks for canonical document blocks."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Sequence
from typing import Annotated

from pydantic import Field

from rtr4_learning.models import Block, BlockType, ContractModel, PageDocument

_REFERENCE = re.compile(
    r"(?<![A-Za-z])(?P<kind>图|方程|Figure|Equation)\s*"
    r"(?P<number>[0-9]+(?:\.[0-9]+)*)",
    re.IGNORECASE,
)


class ValidationIssue(ContractModel):
    code: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]*$")]
    message: Annotated[str, Field(min_length=1)]
    block_id: str | None = None
    page: int | None = None


def _issue(code: str, message: str, block: Block) -> ValidationIssue:
    return ValidationIssue(
        code=code,
        message=message,
        block_id=block.id,
        page=block.page,
    )


def _bbox_is_valid(block: Block) -> bool:
    bbox = block.bbox
    return (
        0 <= bbox.x0 < bbox.x1 <= 1
        and 0 <= bbox.y0 < bbox.y1 <= 1
    )


def validate_pages(pages: Sequence[PageDocument]) -> tuple[ValidationIssue, ...]:
    """Return deterministic validation issues without changing input pages."""
    blocks = [block for page in pages for block in page.blocks]
    id_counts = Counter(block.id for block in blocks)
    figures = {
        block.number
        for block in blocks
        if block.type is BlockType.FIGURE and block.number
    }
    formulas = {
        block.number
        for block in blocks
        if block.type is BlockType.FORMULA and block.number
    }
    block_by_id = {block.id: block for block in blocks}
    issues: list[ValidationIssue] = []

    for block in blocks:
        if id_counts[block.id] > 1:
            issues.append(
                _issue("duplicate_block_id", "block ID is not globally unique", block)
            )

        if not _bbox_is_valid(block):
            issues.append(
                _issue("bbox_out_of_range", "bbox is outside normalized page bounds", block)
            )

        if block.type is BlockType.FORMULA:
            latex = block.latex.strip() if block.latex else ""
            asset_path = block.asset_path.strip() if block.asset_path else ""
            if not latex and not asset_path:
                issues.append(
                    _issue(
                        "formula_missing_representation",
                        "formula has neither LaTeX nor image asset",
                        block,
                    )
                )
            if "\ufffd" in latex:
                issues.append(
                    _issue(
                        "formula_replacement_character",
                        "formula LaTeX contains a replacement character",
                        block,
                    )
                )
            if latex and len(latex) < 2:
                issues.append(
                    _issue(
                        "formula_implausibly_short",
                        "formula LaTeX is implausibly short",
                        block,
                    )
                )

        if block.type is BlockType.FIGURE_CAPTION:
            caption_targets = [
                relation.target
                for relation in block.relations
                if relation.type == "caption_of"
            ]
            valid_targets = [
                target
                for target in caption_targets
                if target in block_by_id
                and block_by_id[target].type in {BlockType.FIGURE, BlockType.TABLE}
            ]
            if not valid_targets:
                issues.append(
                    _issue(
                        "caption_without_target",
                        "caption has no valid figure or table target",
                        block,
                    )
                )

        if block.text and block.type is not BlockType.FIGURE_CAPTION:
            unknown = False
            for match in _REFERENCE.finditer(block.text):
                kind = match.group("kind").lower()
                number = match.group("number")
                known = number in figures if kind in {"图", "figure"} else number in formulas
                if not known:
                    unknown = True
                    break
            if unknown:
                issues.append(
                    _issue(
                        "unknown_explicit_reference",
                        "text references an unknown figure or equation",
                        block,
                    )
                )

    unique: dict[tuple[str, str | None], ValidationIssue] = {}
    for issue in issues:
        unique.setdefault((issue.code, issue.block_id), issue)
    return tuple(unique.values())
