from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from rtr4_learning.enrichment import (
    EnrichmentQueue,
    EnrichmentResult,
    OpenAICompatibleVisionEnricher,
    UnavailableVisionEnricher,
    enrichment_cache_key,
)


def test_cache_key_is_stable_and_invalidates_model_prompt_or_options() -> None:
    crop = b"representative crop"
    base = enrichment_cache_key(
        crop,
        provider="local",
        model="vision-1",
        prompt_version="formula-v1",
        options={"detail": "high", "temperature": 0},
    )

    assert base == enrichment_cache_key(
        crop,
        provider="local",
        model="vision-1",
        prompt_version="formula-v1",
        options={"temperature": 0, "detail": "high"},
    )
    assert base != enrichment_cache_key(
        b"different crop",
        provider="local",
        model="vision-1",
        prompt_version="formula-v1",
        options={"detail": "high", "temperature": 0},
    )
    assert base != enrichment_cache_key(
        crop,
        provider="remote",
        model="vision-1",
        prompt_version="formula-v1",
        options={"detail": "high", "temperature": 0},
    )
    assert base != enrichment_cache_key(
        crop,
        provider="local",
        model="vision-2",
        prompt_version="formula-v1",
        options={"detail": "high", "temperature": 0},
    )
    assert base != enrichment_cache_key(
        crop,
        provider="local",
        model="vision-1",
        prompt_version="formula-v2",
        options={"detail": "high", "temperature": 0},
    )
    assert base != enrichment_cache_key(
        crop,
        provider="local",
        model="vision-1",
        prompt_version="formula-v1",
        options={"detail": "low", "temperature": 0},
    )


def test_queue_reuses_identical_request_and_persists_result(tmp_path) -> None:
    queue = EnrichmentQueue(tmp_path)
    first, first_created = queue.enqueue(
        b"crop",
        provider="local",
        model="vision-1",
        prompt_version="figure-v1",
        options={"detail": "high"},
    )
    second, second_created = queue.enqueue(
        b"crop",
        provider="local",
        model="vision-1",
        prompt_version="figure-v1",
        options={"detail": "high"},
    )
    changed, changed_created = queue.enqueue(
        b"crop",
        provider="local",
        model="vision-2",
        prompt_version="figure-v1",
        options={"detail": "high"},
    )

    assert first_created is True
    assert second_created is False
    assert changed_created is True
    assert first == second
    assert first.key != changed.key
    with pytest.raises(TypeError):
        first.options["detail"] = "low"  # type: ignore[index]

    result = EnrichmentResult(
        key=first.key,
        status="succeeded",
        latex=r"c_{shaded}",
        description="Gooch shading equation",
    )
    queue.save_result(result)
    assert queue.load_result(first.key) == result


def test_result_loading_rejects_unsafe_or_mismatched_keys(tmp_path) -> None:
    queue = EnrichmentQueue(tmp_path / "queue")
    valid_key = "a" * 64
    wrong_key = "b" * 64
    queue.results_dir.mkdir(parents=True)
    (queue.results_dir / f"{valid_key}.json").write_text(
        json.dumps({"key": wrong_key, "status": "failed", "error": "bad"}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="64 lowercase hex"):
        queue.load_result(r"..\..\outside")
    with pytest.raises(ValueError, match="does not match"):
        queue.load_result(valid_key)


def test_enqueue_rejects_mismatched_cached_identity(tmp_path) -> None:
    queue = EnrichmentQueue(tmp_path)
    request, _ = queue.enqueue(
        b"crop",
        provider="local",
        model="vision-1",
        prompt_version="figure-v1",
        options={"detail": "high"},
    )
    path = queue.requests_dir / f"{request.key}.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["model"] = "wrong-model"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="identity does not match"):
        queue.enqueue(
            b"crop",
            provider="local",
            model="vision-1",
            prompt_version="figure-v1",
            options={"detail": "high"},
        )


def test_concurrent_enqueue_has_exactly_one_creator(tmp_path) -> None:
    queue = EnrichmentQueue(tmp_path)

    def enqueue_once() -> bool:
        return queue.enqueue(
            b"crop",
            provider="local",
            model="vision-1",
            prompt_version="figure-v1",
            options={"detail": "high"},
        )[1]

    with ThreadPoolExecutor(max_workers=8) as executor:
        created = list(executor.map(lambda _: enqueue_once(), range(16)))

    assert created.count(True) == 1


def test_frozen_nested_options_can_be_reused_as_cache_input(tmp_path) -> None:
    queue = EnrichmentQueue(tmp_path)
    first, created = queue.enqueue(
        b"crop",
        provider="local",
        model="vision-1",
        prompt_version="figure-v1",
        options={
            "vision": {"detail": "high"},
            "regions": [1, {"x": 2}],
        },
    )

    second, reused_created = queue.enqueue(
        b"crop",
        provider="local",
        model="vision-1",
        prompt_version="figure-v1",
        options=first.options,
    )

    assert created is True
    assert reused_created is False
    assert second == first
    with pytest.raises(TypeError):
        first.options["vision"]["detail"] = "low"  # type: ignore[index]


def test_provider_shells_never_make_an_implicit_live_call() -> None:
    unavailable = UnavailableVisionEnricher(reason="API key missing")
    configured = OpenAICompatibleVisionEnricher(
        endpoint="http://localhost:1234/v1",
        api_key="test-key",
        model="vision-local",
    )

    assert unavailable.available is False
    assert unavailable.reason == "API key missing"
    assert configured.available is True
    assert configured.model == "vision-local"
    assert configured.live_calls_enabled is False
