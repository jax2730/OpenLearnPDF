from __future__ import annotations

import pytest

from rtr4_learning.models import BlockType, BoundingBox
from rtr4_learning.qa import (
    OpenAICompatibleAnswerProvider,
    ProviderAnswer,
    answer_question,
)
from rtr4_learning.retrieval import RetrievalResult, ScoreComponents


def _source(block_id: str = "p105-formula-5.1", score: float = 0.9):
    return RetrievalResult(
        block_id=block_id,
        page=105,
        bbox=BoundingBox(x0=0.1, y0=0.5, x1=0.9, y1=0.6),
        block_type=BlockType.FORMULA,
        source_excerpt="Gooch 使用冷暖色表达表面方向。",
        latex=r"c_{shaded}=s c_{highlight}+(1-s)c_{cool}",
        score=score,
        score_components=ScoreComponents(
            lexical=score,
            embedding=0.0,
            type_bonus=0.0,
        ),
    )


class RecordingProvider:
    def __init__(self, events, citation_id="p105-formula-5.1") -> None:
        self.events = events
        self.citation_id = citation_id

    def answer(self, question, sources):
        self.events.append(("answer", tuple(source.block_id for source in sources)))
        return ProviderAnswer(
            answer="Gooch 使用冷暖色插值。",
            citation_ids=(self.citation_id,),
        )


def test_retrieves_before_provider_and_returns_only_retrieved_citations() -> None:
    events = []

    def retrieve_sources(question):
        events.append(("retrieve", question))
        return (_source(),)

    result = answer_question(
        "Gooch 如何表达方向？",
        retrieve_sources=retrieve_sources,
        provider=RecordingProvider(events),
    )

    assert events[0][0] == "retrieve"
    assert events[1] == ("answer", ("p105-formula-5.1",))
    assert result.status == "answered"
    assert [citation.block_id for citation in result.citations] == [
        "p105-formula-5.1"
    ]


def test_unknown_provider_citation_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown citation"):
        answer_question(
            "Gooch?",
            retrieve_sources=lambda _question: (_source(),),
            provider=RecordingProvider([], citation_id="p999-text-1"),
        )


def test_no_provider_uses_local_extractive_answer() -> None:
    result = answer_question(
        "Gooch?",
        retrieve_sources=lambda _question: (_source(),),
    )

    assert result.status == "answered"
    assert result.mode == "local_extractive"
    assert "Gooch 使用冷暖色" in result.answer
    assert result.citations[0].block_id == "p105-formula-5.1"


def test_insufficient_evidence_abstains_without_calling_provider() -> None:
    events = []
    result = answer_question(
        "书中没有的问题",
        retrieve_sources=lambda _question: (_source(score=0.01),),
        provider=RecordingProvider(events),
    )

    assert result.status == "insufficient_evidence"
    assert result.citations == ()
    assert events == []


def test_low_score_sources_are_excluded_from_provider_and_citation_allowlist() -> None:
    events = []
    result = answer_question(
        "Gooch?",
        retrieve_sources=lambda _question: (
            _source(),
            _source("p105-formula-weak", score=0.01),
        ),
        provider=RecordingProvider(events),
    )

    assert events == [("answer", ("p105-formula-5.1",))]
    assert [citation.block_id for citation in result.citations] == [
        "p105-formula-5.1"
    ]


def test_openai_compatible_shell_never_calls_network_implicitly() -> None:
    provider = OpenAICompatibleAnswerProvider(
        base_url="https://example.com/v1",
        api_key="secret",
        model="example-model",
    )

    with pytest.raises(RuntimeError, match="explicit transport"):
        provider.answer("question", (_source(),))
