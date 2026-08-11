"""Retrieval-first question answering with citation allowlisting."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Annotated, Literal, Protocol, runtime_checkable

from pydantic import Field, model_validator

from rtr4_learning.models import ContractModel, StableBlockId
from rtr4_learning.retrieval import RetrievalResult


class ProviderAnswer(ContractModel):
    answer: Annotated[str, Field(min_length=1)]
    citation_ids: Annotated[tuple[StableBlockId, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def validate_unique_citations(self) -> ProviderAnswer:
        if len(self.citation_ids) != len(set(self.citation_ids)):
            raise ValueError("provider citations must be unique")
        return self


class QuestionAnswer(ContractModel):
    status: Literal["answered", "insufficient_evidence"]
    mode: Literal["local_extractive", "configured_provider"]
    answer: str
    citations: tuple[RetrievalResult, ...] = ()

    @model_validator(mode="after")
    def validate_status_payload(self) -> QuestionAnswer:
        if self.status == "answered" and (not self.answer.strip() or not self.citations):
            raise ValueError("answered responses require text and citations")
        if self.status == "insufficient_evidence" and (
            self.answer or self.citations
        ):
            raise ValueError("insufficient evidence responses must abstain")
        return self


@runtime_checkable
class AnswerProvider(Protocol):
    def answer(
        self, question: str, sources: Sequence[RetrievalResult]
    ) -> ProviderAnswer: ...


class ExtractiveAnswerProvider:
    """Deterministic local fallback that only quotes retrieved excerpts."""

    def answer(
        self, question: str, sources: Sequence[RetrievalResult]
    ) -> ProviderAnswer:
        del question
        selected = tuple(sources[:3])
        excerpts = tuple(dict.fromkeys(source.source_excerpt for source in selected))
        return ProviderAnswer(
            answer="根据检索到的来源：" + "；".join(excerpts),
            citation_ids=tuple(source.block_id for source in selected),
        )


class OpenAICompatibleAnswerProvider:
    """Configuration shell; transport must be injected in a future explicit task."""

    def __init__(self, *, base_url: str, api_key: str, model: str) -> None:
        self.base_url = base_url
        self.api_key = api_key
        self.model = model

    def answer(
        self, question: str, sources: Sequence[RetrievalResult]
    ) -> ProviderAnswer:
        del question, sources
        raise RuntimeError(
            "OpenAI-compatible provider requires an explicit transport"
        )


def answer_question(
    question: str,
    *,
    retrieve_sources: Callable[[str], Sequence[RetrievalResult]],
    provider: AnswerProvider | None = None,
    minimum_score: float = 0.15,
) -> QuestionAnswer:
    normalized = question.strip()
    if not normalized:
        raise ValueError("question must not be blank")
    if not 0 <= minimum_score <= 1:
        raise ValueError("minimum_score must be between zero and one")
    sources = tuple(retrieve_sources(normalized))
    eligible_sources = tuple(
        source for source in sources if source.score >= minimum_score
    )
    if not eligible_sources:
        return QuestionAnswer(
            status="insufficient_evidence",
            mode="local_extractive" if provider is None else "configured_provider",
            answer="",
            citations=(),
        )

    active_provider: AnswerProvider = provider or ExtractiveAnswerProvider()
    draft = active_provider.answer(normalized, eligible_sources)
    by_id = {source.block_id: source for source in eligible_sources}
    unknown = tuple(
        citation for citation in draft.citation_ids if citation not in by_id
    )
    if unknown:
        raise ValueError(f"unknown citation from answer provider: {unknown[0]}")
    citations = tuple(by_id[citation] for citation in draft.citation_ids)
    return QuestionAnswer(
        status="answered",
        mode="local_extractive" if provider is None else "configured_provider",
        answer=draft.answer,
        citations=citations,
    )
