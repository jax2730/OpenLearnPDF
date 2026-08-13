from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
from pydantic import ValidationError

import rtr4_learning.teaching as teaching_module
from rtr4_learning.teaching import (
    Lesson,
    LessonSection,
    ShaderExample,
    load_lesson_bundle,
    load_shader_sources,
    validate_lesson_bundle,
)

REPO_ROOT = Path(__file__).parents[2]
LESSON_PATH = REPO_ROOT / "content/rtr4-cn/chapter-05/section-5.1.json"
LIGHT_LESSON_PATH = REPO_ROOT / "content/rtr4-cn/chapter-05/section-5.2.json"
PUNCTUAL_LESSON_PATH = (
    REPO_ROOT / "content/rtr4-cn/chapter-05/section-5.2.2.json"
)
KNOWN_BLOCK_IDS = {
    "p105-figure-5.3",
    "p105-formula-5.1",
    "p106-formula-5.2",
    "p106-paragraph-1",
}
LIGHT_BLOCK_IDS = {
    "p106-heading-1",
    "p106-paragraph-5",
    "p107-formula-5.3",
    "p107-formula-5.5",
    "p108-figure-5.4",
    "p108-formula-5.6",
    "p109-paragraph-1",
    "p109-heading-1",
    "p109-paragraph-3",
}
PUNCTUAL_BLOCK_IDS = {
    "p109-heading-2",
    "p109-paragraph-5",
    "p109-formula-5.9",
    "p110-formula-5.10",
    "p110-heading-1",
    "p110-figure-5.5",
    "p111-formula-5.11",
    "p111-formula-5.12",
    "p111-formula-5.13",
    "p111-formula-5.14",
    "p112-figure-5.6",
    "p113-heading-1",
    "p113-formula-5.17",
    "p113-figure-5.7",
    "p113-formula-5.18",
    "p114-figure-5.8",
}


def test_lesson_sections_and_questions_require_citations() -> None:
    with pytest.raises(ValidationError):
        LessonSection(
            level="intuition",
            title="Why cool and warm colors",
            body="Surface orientation becomes visible through hue.",
            citations=(),
        )


def test_unknown_lesson_or_shader_citations_are_rejected() -> None:
    lesson = Lesson(
        id="chapter-05-section-5.1",
        chapter=5,
        section="5.1",
        title="Gooch shading",
        sections=(
            LessonSection(
                level="intuition",
                title="Idea",
                body="Cool and warm interpolation.",
                citations=("p105-formula-5.1",),
            ),
        ),
        questions=(),
        shader_example_id="gooch",
    )
    shader = ShaderExample(
        id="gooch",
        language="glsl",
        stage="fragment",
        source_path="examples/gooch.frag",
        browser_source_path="examples/gooch-shadertoy.frag",
        source_block_ids=("p999-text-1",),
        expected_visual="A cool-to-warm shaded sphere.",
        verification_command="glslangValidator -S frag examples/gooch.frag",
        external_references=("https://www.shadertoy.com/new",),
    )

    with pytest.raises(ValueError, match="unknown block IDs"):
        validate_lesson_bundle(lesson, shader, KNOWN_BLOCK_IDS)


@pytest.mark.parametrize("unsafe", ["/escape.json", "C:escape.json", "../escape.json"])
def test_content_models_reject_unsafe_paths(unsafe: str) -> None:
    with pytest.raises(ValidationError):
        ShaderExample(
            id="gooch",
            language="glsl",
            stage="fragment",
            source_path=unsafe,
            browser_source_path="examples/gooch-shadertoy.frag",
            source_block_ids=("p105-formula-5.1",),
            expected_visual="sphere",
            verification_command="verify",
        )


def test_duplicate_levels_source_ids_and_http_links_are_rejected() -> None:
    section = LessonSection(
        level="intuition",
        title="Idea",
        body="Body",
        citations=("p105-formula-5.1",),
    )
    lesson = Lesson(
        id="chapter-05-section-5.1",
        chapter=5,
        section="5.1",
        title="Gooch",
        sections=(section, section),
        questions=(),
        shader_example_id="gooch",
    )
    shader_data = {
        "id": "gooch",
        "language": "glsl",
        "stage": "fragment",
        "source_path": "examples/gooch.frag",
        "browser_source_path": "examples/gooch-shadertoy.frag",
        "source_block_ids": ("p105-formula-5.1", "p105-formula-5.1"),
        "expected_visual": "sphere",
        "verification_command": "verify",
        "external_references": ("http://example.com",),
    }

    with pytest.raises(ValidationError):
        ShaderExample(**shader_data)
    valid_shader = ShaderExample(
        **{
            **shader_data,
            "source_block_ids": ("p105-formula-5.1",),
            "external_references": ("https://www.shadertoy.com/new",),
        }
    )
    with pytest.raises(ValueError, match="exactly once"):
        validate_lesson_bundle(lesson, valid_shader, KNOWN_BLOCK_IDS)


def test_real_gooch_lesson_has_all_levels_and_valid_citations() -> None:
    lesson, shader = load_lesson_bundle(LESSON_PATH)

    validate_lesson_bundle(lesson, shader, KNOWN_BLOCK_IDS)
    assert {section.level for section in lesson.sections} == {
        "intuition",
        "mathematics",
        "graphics_meaning",
        "implementation",
        "example",
        "pitfalls",
        "exercises",
    }
    assert shader.language == "glsl"
    assert shader.stage == "fragment"
    assert "p105-formula-5.1" in shader.source_block_ids
    assert shader.expected_visual
    assert shader.verification_command
    assert all(str(url).startswith("https://") for url in shader.external_references)
    browser_source = (LESSON_PATH.parent / shader.browser_source_path).read_text(
        encoding="utf-8"
    )
    assert "mainImage" in browser_source
    assert "iResolution" in browser_source


def test_real_directional_light_lesson_has_all_levels_and_valid_citations() -> None:
    lesson, shader = load_lesson_bundle(LIGHT_LESSON_PATH)

    validate_lesson_bundle(lesson, shader, LIGHT_BLOCK_IDS)
    assert lesson.section == "5.2"
    assert {section.level for section in lesson.sections} == {
        "intuition",
        "mathematics",
        "graphics_meaning",
        "implementation",
        "example",
        "pitfalls",
        "exercises",
    }
    assert shader.id == "directional-light"
    assert "p109-paragraph-3" in shader.source_block_ids


def test_real_punctual_light_lesson_has_all_levels_and_valid_citations() -> None:
    lesson, shader = load_lesson_bundle(PUNCTUAL_LESSON_PATH)

    validate_lesson_bundle(lesson, shader, PUNCTUAL_BLOCK_IDS)
    assert lesson.section == "5.2.2"
    assert {section.level for section in lesson.sections} == {
        "intuition",
        "mathematics",
        "graphics_meaning",
        "implementation",
        "example",
        "pitfalls",
        "exercises",
    }
    assert shader.id == "punctual-lights"
    assert {"p111-formula-5.11", "p113-formula-5.18"}.issubset(
        shader.source_block_ids
    )


def test_shader_source_read_rejects_file_swapped_outside_content_root(
    tmp_path, monkeypatch
) -> None:
    lesson_dir = tmp_path / "content"
    examples = lesson_dir / "examples"
    examples.mkdir(parents=True)
    desktop = examples / "gooch.frag"
    browser = examples / "gooch-shadertoy.frag"
    desktop.write_text("safe desktop", encoding="utf-8")
    browser.write_text("safe browser", encoding="utf-8")
    secret = tmp_path / "secret.txt"
    secret.write_text("LOCAL_SECRET", encoding="utf-8")
    shader = ShaderExample(
        id="gooch",
        language="glsl",
        stage="fragment",
        source_path="examples/gooch.frag",
        browser_source_path="examples/gooch-shadertoy.frag",
        source_block_ids=("p105-formula-5.1",),
        expected_visual="sphere",
        verification_command="verify",
    )
    real_resolve = teaching_module._resolve_content_file

    def swapped_resolve(base, relative):
        resolved = real_resolve(base, relative)
        if relative == "examples/gooch.frag":
            return secret
        return resolved

    monkeypatch.setattr(teaching_module, "_resolve_content_file", swapped_resolve)

    with pytest.raises(ValueError, match="outside lesson directory"):
        load_shader_sources(lesson_dir / "section.json", shader)


def test_gooch_fragment_shader_compiles_when_validator_is_available() -> None:
    validator = shutil.which("glslangValidator")
    if validator is None:
        pytest.skip("system validator unavailable; browser demo remains supported")
    _, shader = load_lesson_bundle(LESSON_PATH)
    shader_path = LESSON_PATH.parent / shader.source_path

    completed = subprocess.run(
        [validator, "-S", "frag", str(shader_path)],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
