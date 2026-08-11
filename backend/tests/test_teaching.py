from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
from pydantic import ValidationError

from rtr4_learning.teaching import (
    Lesson,
    LessonSection,
    ShaderExample,
    load_lesson_bundle,
    validate_lesson_bundle,
)

REPO_ROOT = Path(__file__).parents[2]
LESSON_PATH = REPO_ROOT / "content/rtr4-cn/chapter-05/section-5.1.json"
KNOWN_BLOCK_IDS = {
    "p104-figure-5.3",
    "p105-formula-5.1",
    "p106-formula-5.2",
    "p106-paragraph-1",
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
