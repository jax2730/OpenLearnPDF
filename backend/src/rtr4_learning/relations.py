"""Deterministic relation linking for canonical document blocks."""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Sequence
from itertools import pairwise

from rtr4_learning.models import Block, BlockType, PageDocument, Relation

_REFERENCE = re.compile(
    r"(?<![A-Za-z])(?P<kind>图|方程|Figure|Equation)\s*"
    r"(?P<number>[0-9]+(?:\.[0-9]+)*)",
    re.IGNORECASE,
)


def _append_relation(
    relations: list[Relation], relation_type: str, target: str | None
) -> None:
    if target is None:
        return
    relation = Relation(type=relation_type, target=target)
    if relation not in relations:
        relations.append(relation)


def link_relations(pages: Sequence[PageDocument]) -> tuple[PageDocument, ...]:
    """Return copied pages with structural and explicit-reference relations."""
    ordered_blocks = [block for page in pages for block in page.blocks]
    positions = {block.id: index for index, block in enumerate(ordered_blocks)}
    if len(positions) != len(ordered_blocks):
        raise ValueError("canonical block IDs must be globally unique")

    section_by_id: dict[str, str | None] = {}
    section: str | None = None
    for block in ordered_blocks:
        if block.type is BlockType.HEADING:
            section = block.id
        section_by_id[block.id] = section

    numbered_figures: defaultdict[str, list[Block]] = defaultdict(list)
    numbered_formulas: defaultdict[str, list[Block]] = defaultdict(list)
    for block in ordered_blocks:
        if block.number and block.type is BlockType.FIGURE:
            numbered_figures[block.number].append(block)
        elif block.number and block.type is BlockType.FORMULA:
            numbered_formulas[block.number].append(block)

    def resolve(candidates: Sequence[Block], source: Block) -> str | None:
        if not candidates:
            return None
        narrowed = [candidate for candidate in candidates if candidate.page == source.page]
        if not narrowed:
            narrowed = list(candidates)
        source_section = section_by_id[source.id]
        same_section = [
            candidate
            for candidate in narrowed
            if section_by_id[candidate.id] == source_section
        ]
        if same_section:
            narrowed = same_section
        distances = [
            abs(positions[candidate.id] - positions[source.id])
            for candidate in narrowed
        ]
        minimum = min(distances)
        nearest = [
            candidate
            for candidate, distance in zip(narrowed, distances, strict=True)
            if distance == minimum
        ]
        return nearest[0].id if len(nearest) == 1 else None

    next_by_id = {
        current.id: following.id
        for current, following in pairwise(ordered_blocks)
    }

    linked_pages: list[PageDocument] = []
    current_section: str | None = None
    for page in pages:
        linked_blocks: list[Block] = []
        previous_figure: str | None = None
        for block in page.blocks:
            relations = list(block.relations)
            if block.type is BlockType.HEADING:
                current_section = block.id
            else:
                _append_relation(relations, "belongs_to_section", current_section)

            if block.type is BlockType.FIGURE:
                previous_figure = block.id
            elif block.type is BlockType.FIGURE_CAPTION:
                same_source = [
                    candidate
                    for candidate in ordered_blocks
                    if candidate.type is BlockType.FIGURE
                    and block.source.raw_block_id is not None
                    and block.source.raw_artifact is not None
                    and candidate.source.raw_block_id == block.source.raw_block_id
                    and candidate.source.raw_artifact == block.source.raw_artifact
                ]
                caption_target = resolve(same_source, block)
                if caption_target is None and block.number:
                    caption_target = resolve(numbered_figures[block.number], block)
                _append_relation(
                    relations,
                    "caption_of",
                    caption_target if block.number else caption_target or previous_figure,
                )

            if block.text and block.type is not BlockType.FIGURE_CAPTION:
                for match in _REFERENCE.finditer(block.text):
                    kind = match.group("kind").lower()
                    number = match.group("number")
                    target = (
                        resolve(numbered_figures[number], block)
                        if kind in {"图", "figure"}
                        else resolve(numbered_formulas[number], block)
                    )
                    _append_relation(relations, "refers_to", target)

            _append_relation(relations, "next_block", next_by_id.get(block.id))
            linked_blocks.append(block.model_copy(update={"relations": tuple(relations)}))
        linked_pages.append(page.model_copy(update={"blocks": tuple(linked_blocks)}))
    return tuple(linked_pages)
