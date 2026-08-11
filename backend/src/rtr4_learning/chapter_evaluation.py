"""Evaluate chapter retrieval and citation integrity against fixed gates."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path

from rtr4_learning.index import HashEmbeddingProvider
from rtr4_learning.models import Block, BlockType, PageDocument
from rtr4_learning.paths import _is_link_or_reparse_point, book_artifact_dir
from rtr4_learning.qa import answer_question
from rtr4_learning.retrieval import RetrievalResult, retrieve

_BUILD_ID = re.compile(r"^[0-9a-f]{64}$")
_FIXED_QUESTIONS_SHA256 = "ea3840d6ea1c49224693e78cbaf837a36b4b6ad2d77ae58fc12e51d97c5846cd"
_FIXED_RUBRIC_SHA256 = "a0145d8652a989db942f3f9afa7792977e1955e450d4a2ef84768c89c9dbddda"
_REQUIRED_FORMULAS = {
    "p105-formula-5.1": "42da34dd691914d9fdd9f060c5c328148b3bfa86cfaebeafa8e1ec8886b8dd95",
    "p106-formula-5.2": "a602ac4de432f32032e1d5af682bc46afe55dce3af986a495988d557b9d5f12b",
}
_REQUIRED_FIGURES = {
    "p105-figure-5.2",
    "p105-figure-5.3",
    "p116-figure-5.9",
}


def score_retrieval(
    question: Mapping[str, object], results: Sequence[RetrievalResult]
) -> dict[str, object]:
    expected_pages = {int(page) for page in question["expected_pages"]}
    required_types = {
        BlockType(str(block_type))
        for block_type in question["required_block_types"]
    }
    expected_results = [result for result in results if result.page in expected_pages]
    result_types = {result.block_type for result in expected_results}
    return {
        "id": str(question["id"]),
        "page_hit": bool(expected_results),
        "block_type_hit": required_types <= result_types,
        "result_ids": [result.block_id for result in results],
        "result_pages": [result.page for result in results],
    }


def formula_matches(block: Block | None, requirement: Mapping[str, object]) -> bool:
    if block is None or block.type is not BlockType.FORMULA or not block.latex:
        return False
    expected = requirement.get("latex_sha256")
    return isinstance(expected, str) and hashlib.sha256(
        block.latex.encode("utf-8")
    ).hexdigest() == expected


def evaluate_gates(
    *,
    page_hits: int,
    block_type_hits: int,
    citation_validity: float,
    formula_checks: Mapping[str, bool],
    figure_checks: Mapping[str, bool],
    fabricated_ids: set[str],
    abstention_status: str,
    rubric: Mapping[str, object],
) -> dict[str, bool]:
    return {
        "page_hits": page_hits >= int(rubric["minimum_page_hits"]),
        "block_type_hits": block_type_hits
        >= int(rubric["minimum_block_type_hits"]),
        "citation_validity": citation_validity
        >= float(rubric["minimum_citation_validity"]),
        "formula_fidelity": bool(formula_checks) and all(formula_checks.values()),
        "figure_relations": bool(figure_checks) and all(figure_checks.values()),
        "no_fabricated_ids": not fabricated_ids,
        "abstention": abstention_status == "insufficient_evidence",
    }


def validate_rubric(rubric: Mapping[str, object]) -> None:
    if rubric.get("schema_version") != 1:
        raise ValueError("rubric schema_version must be 1")
    if int(rubric["minimum_page_hits"]) < 18:
        raise ValueError("rubric minimum_page_hits must be at least 18")
    if int(rubric["minimum_block_type_hits"]) < 18:
        raise ValueError("rubric minimum_block_type_hits must be at least 18")
    if float(rubric["minimum_citation_validity"]) < 0.95:
        raise ValueError("rubric minimum_citation_validity must be at least 0.95")
    formulas = {
        item.get("block_id"): item.get("latex_sha256")
        for item in rubric.get("required_formulas", [])
        if isinstance(item, dict)
    }
    if formulas != _REQUIRED_FORMULAS:
        raise ValueError("rubric required formulas are fixed for chapter 5")
    figures = {
        item.get("figure_id")
        for item in rubric.get("required_figures", [])
        if isinstance(item, dict)
    }
    if figures != _REQUIRED_FIGURES:
        raise ValueError("rubric required figures are fixed for chapter 5")


def _validate_benchmark_artifacts(questions_bytes: bytes, rubric_bytes: bytes) -> None:
    def canonical_sha256(payload: bytes) -> str:
        canonical = json.dumps(
            json.loads(payload),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()

    if canonical_sha256(questions_bytes) != _FIXED_QUESTIONS_SHA256:
        raise ValueError("chapter 5 questions benchmark does not match fixed policy")
    if canonical_sha256(rubric_bytes) != _FIXED_RUBRIC_SHA256:
        raise ValueError("chapter 5 rubric benchmark does not match fixed policy")


def validate_parser_probe(probe: Mapping[str, object]) -> None:
    if (
        probe.get("status") != "succeeded"
        or probe.get("canonical_pages") != list(range(104, 155))
        or probe.get("backend") != "pipeline"
        or probe.get("cloud_calls") != 0
    ):
        raise ValueError("active build MinerU probe is invalid")
    ram_peak = probe.get("ram_peak_mb")
    if (
        probe.get("ram_memory_metric")
        != "mineru_process_tree_working_set_mb"
        or not isinstance(ram_peak, (int, float))
        or isinstance(ram_peak, bool)
        or ram_peak <= 0
    ):
        raise ValueError("active build MinerU probe RAM peak is invalid")


def _active_artifacts(
    data_root: Path, book_id: str
) -> tuple[str, Path, Path, Path]:
    book_root = book_artifact_dir(data_root, book_id)
    active_path = book_root / "active.json"
    if _is_link_or_reparse_point(active_path):
        raise ValueError("active build pointer is indirect")
    active = json.loads(active_path.read_text(encoding="utf-8"))
    build_id = active.get("build_id")
    if active.get("schema_version") != 1 or not isinstance(build_id, str):
        raise ValueError("active build pointer is invalid")
    if not _BUILD_ID.fullmatch(build_id):
        raise ValueError("active build ID is invalid")
    build_root = book_root / "builds" / build_id
    for component in (book_root / "builds", build_root, build_root / "normalized"):
        if _is_link_or_reparse_point(component):
            raise ValueError("active build path is indirect")
    if not build_root.is_dir() or not build_root.resolve().is_relative_to(
        book_root.resolve()
    ):
        raise ValueError("active build path is invalid")
    return (
        build_id,
        build_root / "normalized/pages.json",
        build_root / "normalized/validation.json",
        build_root / "search.sqlite3",
    )


def evaluate_chapter(
    *,
    data_root: Path,
    book_id: str,
    questions_path: Path,
    rubric_path: Path,
) -> dict[str, object]:
    questions_bytes = questions_path.read_bytes()
    rubric_bytes = rubric_path.read_bytes()
    _validate_benchmark_artifacts(questions_bytes, rubric_bytes)
    questions_payload = json.loads(questions_bytes)
    rubric = json.loads(rubric_bytes)
    validate_rubric(rubric)
    questions = questions_payload.get("questions")
    if not isinstance(questions, list) or len(questions) != 20:
        raise ValueError("chapter evaluation requires exactly 20 questions")

    build_id, pages_path, validation_path, index_path = _active_artifacts(
        data_root, book_id
    )
    pages = tuple(
        PageDocument.model_validate(page)
        for page in json.loads(pages_path.read_text(encoding="utf-8"))
    )
    blocks = {block.id: block for page in pages for block in page.blocks}
    validation_issues = json.loads(validation_path.read_text(encoding="utf-8"))
    raw_artifacts = {
        Path(block.source.raw_artifact)
        for block in blocks.values()
        if block.source.raw_artifact
    }
    if len(raw_artifacts) != 1:
        raise ValueError("active build must reference exactly one raw content list")
    raw_artifact = next(iter(raw_artifacts))
    probe_path = raw_artifact.parents[2] / "probe.json"
    probe_bytes = probe_path.read_bytes()
    probe = json.loads(probe_bytes)
    validate_parser_probe(probe)
    provider = HashEmbeddingProvider(dimensions=int(rubric["embedding_dimensions"]))
    top_k = int(rubric["top_k"])
    scores: list[dict[str, object]] = []
    citation_count = 0
    valid_citation_count = 0
    fabricated_ids: set[str] = set()

    for question in questions:
        query = str(question["query"])
        results = retrieve(
            index_path,
            query,
            chapter=int(questions_payload["chapter"]),
            embedding_provider=provider,
            limit=top_k,
        )
        score = score_retrieval(question, results)
        answer = answer_question(
            query, retrieve_sources=lambda _, sources=results: sources
        )
        citation_ids = [citation.block_id for citation in answer.citations]
        citation_count += len(citation_ids)
        for block_id in citation_ids:
            if block_id in blocks:
                valid_citation_count += 1
            else:
                fabricated_ids.add(block_id)
        score.update(
            {
                "question": question["question"],
                "query": query,
                "answer_status": answer.status,
                "citation_ids": citation_ids,
            }
        )
        scores.append(score)

    formula_checks: dict[str, bool] = {}
    for requirement in rubric["required_formulas"]:
        block = blocks.get(requirement["block_id"])
        formula_checks[requirement["block_id"]] = formula_matches(
            block, requirement
        )

    figure_checks: dict[str, bool] = {}
    for requirement in rubric["required_figures"]:
        figure = blocks.get(requirement["figure_id"])
        caption = blocks.get(requirement["caption_id"])
        figure_checks[requirement["figure_id"]] = bool(
            figure is not None
            and figure.type is BlockType.FIGURE
            and caption is not None
            and caption.type is BlockType.FIGURE_CAPTION
            and any(
                relation.type == "caption_of"
                and relation.target == requirement["figure_id"]
                for relation in caption.relations
            )
        )

    abstention_results = retrieve(
        index_path,
        str(rubric["abstention_query"]),
        chapter=int(questions_payload["chapter"]),
        embedding_provider=provider,
        limit=top_k,
    )
    abstention = answer_question(
        str(rubric["abstention_query"]),
        retrieve_sources=lambda _: abstention_results,
        minimum_score=float(rubric["abstention_minimum_score"]),
    )
    page_hits = sum(bool(score["page_hit"]) for score in scores)
    block_hits = sum(bool(score["block_type_hit"]) for score in scores)
    citation_validity = (
        valid_citation_count / citation_count if citation_count else 0.0
    )
    gates = evaluate_gates(
        page_hits=page_hits,
        block_type_hits=block_hits,
        citation_validity=citation_validity,
        formula_checks=formula_checks,
        figure_checks=figure_checks,
        fabricated_ids=fabricated_ids,
        abstention_status=abstention.status,
        rubric=rubric,
    )
    return {
        "schema_version": 1,
        "book_id": book_id,
        "chapter": questions_payload["chapter"],
        "question_count": len(scores),
        "page_hit_count": page_hits,
        "block_type_hit_count": block_hits,
        "citation_validity": citation_validity,
        "fabricated_ids": sorted(fabricated_ids),
        "formula_checks": formula_checks,
        "figure_checks": figure_checks,
        "abstention_status": abstention.status,
        "validation_issue_count": len(validation_issues),
        "validation_issue_pages": sorted(
            {issue["page"] for issue in validation_issues if issue.get("page")}
        ),
        "validation_issues": validation_issues,
        "content_completeness": (
            "needs_visual_enrichment" if validation_issues else "complete"
        ),
        "active_build_id": build_id,
        "questions_sha256": hashlib.sha256(questions_bytes).hexdigest(),
        "rubric_sha256": hashlib.sha256(rubric_bytes).hexdigest(),
        "probe_sha256": hashlib.sha256(probe_bytes).hexdigest(),
        "parser_run": {
            "probe_dir": probe_path.parent.name,
            "mineru_version": probe["toolchain"]["packages"]["mineru"],
            "backend": probe["backend"],
            "pages": len(probe["canonical_pages"]),
            "elapsed_seconds": probe["elapsed_seconds"],
            "gpu_baseline_mb": probe["gpu_baseline_total_memory_used_mb"],
            "gpu_peak_total_mb": probe["gpu_peak_total_memory_used_mb"],
            "gpu_peak_delta_mb": probe["gpu_peak_delta_from_baseline_mb"],
            "ram_peak_mb": probe.get("ram_peak_mb"),
            "cloud_calls": probe["cloud_calls"],
        },
        "gates": gates,
        "passed": all(gates.values()),
        "questions": scores,
    }


def report_markdown(result: Mapping[str, object]) -> str:
    gates = result["gates"]
    ram_peak = result["parser_run"]["ram_peak_mb"]
    ram_peak_text = (
        "not recorded"
        if not isinstance(ram_peak, (int, float)) or ram_peak <= 0
        else f"{ram_peak} MB"
    )
    lines = [
        "# RTR4 Chapter 5 evaluation",
        "",
        f"- Retrieval acceptance: {'PASS' if result['passed'] else 'FAIL'}",
        f"- Content completeness: {str(result['content_completeness']).replace('_', ' ').upper()}",
        f"- Correct-page hits: {result['page_hit_count']}/{result['question_count']}",
        f"- Required block-type hits: {result['block_type_hit_count']}/{result['question_count']}",
        f"- Citation validity: {float(result['citation_validity']):.2%}",
        f"- Abstention probe: {result['abstention_status']}",
        f"- Validation warnings: {result['validation_issue_count']}",
        f"- Pages needing visual/reference enrichment: {result['validation_issue_pages']}",
        "",
        "## Parser run",
        "",
        f"- Probe directory: {result['parser_run']['probe_dir']}",
        f"- Elapsed: {result['parser_run']['elapsed_seconds']} seconds",
        f"- GPU peak delta: {result['parser_run']['gpu_peak_delta_mb']} MB",
        f"- RAM peak: {ram_peak_text}",
        f"- Cloud calls: {result['parser_run']['cloud_calls']}",
        f"- Active build: `{result['active_build_id']}`",
        f"- Questions SHA-256: `{result['questions_sha256']}`",
        f"- Rubric SHA-256: `{result['rubric_sha256']}`",
        f"- Probe SHA-256: `{result['probe_sha256']}`",
        "",
        "## Gates",
        "",
    ]
    lines.extend(
        f"- {'PASS' if passed else 'FAIL'}: {name}"
        for name, passed in gates.items()
    )
    lines.extend(["", "## Parser warnings", ""])
    for issue in result["validation_issues"]:
        line = (
            f"- {issue['code']} at page {issue['page']} / {issue['block_id']}: "
            f"{issue['message']}"
        )
        if issue.get("disposition"):
            line += f"; disposition={issue['disposition']}"
        if issue.get("disposition_evidence"):
            line += f"; evidence={issue['disposition_evidence']}"
        lines.append(line)
    lines.extend(["", "## Questions", ""])
    for question in result["questions"]:
        lines.append(
            f"- {question['id']}: page={'hit' if question['page_hit'] else 'miss'}, "
            f"types={'hit' if question['block_type_hit'] else 'miss'}, "
            f"pages={question['result_pages']}"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", required=True, type=Path)
    parser.add_argument("--book-id", default="rtr4-cn")
    parser.add_argument("--questions", required=True, type=Path)
    parser.add_argument("--rubric", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    result = evaluate_chapter(
        data_root=args.data_root,
        book_id=args.book_id,
        questions_path=args.questions,
        rubric_path=args.rubric,
    )
    args.report.write_text(report_markdown(result), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
