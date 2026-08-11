from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from rtr4_learning import chapter_evaluation
from rtr4_learning.chapter_evaluation import (
    evaluate_gates,
    formula_matches,
    report_markdown,
    score_retrieval,
    validate_rubric,
)
from rtr4_learning.models import (
    Block,
    BlockSource,
    BlockType,
    BoundingBox,
)
from rtr4_learning.retrieval import RetrievalResult, ScoreComponents


def _result(block_id: str, page: int, block_type: BlockType) -> RetrievalResult:
    return RetrievalResult(
        block_id=block_id,
        page=page,
        bbox=BoundingBox(x0=0.1, y0=0.1, x1=0.9, y1=0.2),
        block_type=block_type,
        source_excerpt="evidence",
        score=0.8,
        score_components=ScoreComponents(
            lexical=1.0, embedding=0.5, type_bonus=0.0
        ),
    )


def test_scores_page_and_required_block_type_hits() -> None:
    score = score_retrieval(
        {
            "id": "q01",
            "expected_pages": [105],
            "required_block_types": ["formula"],
        },
        (
            _result("p104-paragraph-1", 104, BlockType.TEXT),
            _result("p105-formula-5.1", 105, BlockType.FORMULA),
        ),
    )

    assert score["page_hit"] is True
    assert score["block_type_hit"] is True


def test_requires_every_declared_block_type() -> None:
    score = score_retrieval(
        {
            "id": "q02",
            "expected_pages": [105],
            "required_block_types": ["figure", "figure_caption"],
        },
        (_result("p105-figure-5.2", 105, BlockType.FIGURE),),
    )

    assert score["page_hit"] is True
    assert score["block_type_hit"] is False


def test_required_type_must_come_from_an_expected_page() -> None:
    score = score_retrieval(
        {
            "id": "q03",
            "expected_pages": [105],
            "required_block_types": ["formula"],
        },
        (
            _result("p105-paragraph-1", 105, BlockType.TEXT),
            _result("p127-formula-5.9", 127, BlockType.FORMULA),
        ),
    )

    assert score["page_hit"] is True
    assert score["block_type_hit"] is False


def test_report_includes_parser_gaps_and_resource_provenance() -> None:
    report = report_markdown(
        {
            "passed": True,
            "page_hit_count": 20,
            "question_count": 20,
            "block_type_hit_count": 20,
            "citation_validity": 1.0,
            "abstention_status": "insufficient_evidence",
            "validation_issue_count": 2,
            "validation_issue_pages": [126, 149],
            "validation_issues": [
                {
                    "code": "unknown_explicit_reference",
                    "block_id": "p126-paragraph-3",
                    "page": 126,
                    "message": "text references an unknown figure or equation",
                    "disposition": "accepted_pending_visual_enrichment",
                    "disposition_evidence": "Figure 5.15 was not emitted.",
                }
            ],
            "content_completeness": "needs_visual_enrichment",
            "active_build_id": "a" * 64,
            "questions_sha256": "b" * 64,
            "rubric_sha256": "c" * 64,
            "probe_sha256": "d" * 64,
            "parser_run": {
                "probe_dir": "mineru-chapter-05-acceptance",
                "elapsed_seconds": 85.9,
                "gpu_peak_delta_mb": 3182,
                "ram_peak_mb": None,
                "cloud_calls": 0,
            },
            "gates": {"page_hits": True},
            "questions": [],
        }
    )

    assert "Retrieval acceptance: PASS" in report
    assert "Overall: PASS" not in report
    assert "Content completeness: NEEDS VISUAL ENRICHMENT" in report
    assert "Validation warnings: 2" in report
    assert "GPU peak delta: 3182 MB" in report
    assert "Cloud calls: 0" in report
    assert "p126-paragraph-3" in report
    assert "Questions SHA-256" in report
    assert "Probe directory: mineru-chapter-05-acceptance" in report
    assert "Figure 5.15 was not emitted." in report


def test_report_marks_zero_ram_measurement_as_unrecorded() -> None:
    result = {
        "passed": True,
        "page_hit_count": 20,
        "question_count": 20,
        "block_type_hit_count": 20,
        "citation_validity": 1.0,
        "abstention_status": "insufficient_evidence",
        "validation_issue_count": 0,
        "validation_issue_pages": [],
        "validation_issues": [],
        "content_completeness": "complete",
        "active_build_id": "a" * 64,
        "questions_sha256": "b" * 64,
        "rubric_sha256": "c" * 64,
        "probe_sha256": "d" * 64,
        "parser_run": {
            "probe_dir": "probe",
            "elapsed_seconds": 1,
            "gpu_peak_delta_mb": 0,
            "ram_peak_mb": 0,
            "cloud_calls": 0,
        },
        "gates": {},
        "questions": [],
    }

    assert "RAM peak: not recorded" in report_markdown(result)


def test_parser_probe_requires_positive_process_tree_ram_peak() -> None:
    probe = {
        "status": "succeeded",
        "canonical_pages": list(range(104, 155)),
        "backend": "pipeline",
        "cloud_calls": 0,
        "ram_memory_metric": "mineru_process_tree_working_set_mb",
        "ram_peak_mb": 2048.5,
    }

    assert hasattr(chapter_evaluation, "validate_parser_probe")
    validate = chapter_evaluation.validate_parser_probe
    validate(probe)
    probe["ram_peak_mb"] = 0
    with pytest.raises(ValueError, match="RAM peak"):
        validate(probe)


def test_fixed_benchmark_rejects_synchronized_golden_rewrite() -> None:
    root = Path(__file__).parents[2]
    questions = (root / "evaluation/chapter-05/questions.json").read_bytes()
    rubric = (root / "evaluation/chapter-05/rubric.json").read_bytes()

    assert hasattr(chapter_evaluation, "_validate_benchmark_artifacts")
    validate = chapter_evaluation._validate_benchmark_artifacts
    validate(questions, rubric)
    validate(questions + b" \r\n", rubric + b" \r\n")
    changed_questions = questions.replace(b'"query":"Gooch shading model"', b'"query":"wrong"')
    changed_rubric = rubric.replace(b'"top_k": 5', b'"top_k": 6')
    with pytest.raises(ValueError, match="questions benchmark"):
        validate(changed_questions, rubric)
    with pytest.raises(ValueError, match="rubric benchmark"):
        validate(questions, changed_rubric)


@pytest.mark.parametrize(
    ("change", "gate"),
    [
        ({"page_hits": 17}, "page_hits"),
        ({"block_type_hits": 17}, "block_type_hits"),
        ({"citation_validity": 0.949}, "citation_validity"),
        ({"formula_checks": {"f": False}}, "formula_fidelity"),
        ({"figure_checks": {"g": False}}, "figure_relations"),
        ({"fabricated_ids": {"p999-fake-1"}}, "no_fabricated_ids"),
        ({"abstention_status": "answered"}, "abstention"),
    ],
)
def test_each_acceptance_gate_detects_failure(change, gate) -> None:
    values = {
        "page_hits": 18,
        "block_type_hits": 18,
        "citation_validity": 0.95,
        "formula_checks": {"f": True},
        "figure_checks": {"g": True},
        "fabricated_ids": set(),
        "abstention_status": "insufficient_evidence",
    }
    values.update(change)

    gates = evaluate_gates(
        **values,
        rubric={
            "minimum_page_hits": 18,
            "minimum_block_type_hits": 18,
            "minimum_citation_validity": 0.95,
        },
    )

    assert gates[gate] is False


def test_formula_fidelity_uses_complete_latex_hash() -> None:
    latex = r"c=a+b\tag{5.1}"
    block = Block(
        id="p105-formula-5.1",
        type=BlockType.FORMULA,
        page=105,
        bbox=BoundingBox(x0=0.1, y0=0.1, x1=0.9, y1=0.2),
        latex=latex,
        number="5.1",
        source=BlockSource(parser="mineru", version="3.4.4", confidence=0.9),
    )
    requirement = {
        "block_id": block.id,
        "latex_sha256": hashlib.sha256(latex.encode()).hexdigest(),
    }

    assert formula_matches(block, requirement) is True
    assert formula_matches(
        block.model_copy(update={"latex": latex + "x"}), requirement
    ) is False


def test_rubric_cannot_remove_required_formula_or_figure_gates() -> None:
    with pytest.raises(ValueError, match="required formulas"):
        validate_rubric(
            {
                "schema_version": 1,
                "top_k": 5,
                "embedding_dimensions": 64,
                "minimum_page_hits": 18,
                "minimum_block_type_hits": 18,
                "minimum_citation_validity": 0.95,
                "required_formulas": [],
                "required_figures": [],
            }
        )
