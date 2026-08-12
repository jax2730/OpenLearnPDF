"""Citation-preserving lesson, exercise, and shader contracts."""

from __future__ import annotations

import json
import os
from collections import Counter
from collections.abc import Collection
from pathlib import Path
from typing import Annotated, Literal

from pydantic import AnyHttpUrl, Field, field_validator, model_validator

from rtr4_learning.models import ContractModel, StableBlockId

LessonLevel = Literal[
    "intuition",
    "mathematics",
    "graphics_meaning",
    "implementation",
    "example",
    "pitfalls",
    "exercises",
]
_REQUIRED_LEVELS = {
    "intuition",
    "mathematics",
    "graphics_meaning",
    "implementation",
    "example",
    "pitfalls",
    "exercises",
}


class LessonSection(ContractModel):
    level: LessonLevel
    title: Annotated[str, Field(min_length=1)]
    body: Annotated[str, Field(min_length=1)]
    citations: Annotated[tuple[StableBlockId, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def validate_unique_citations(self) -> LessonSection:
        if len(self.citations) != len(set(self.citations)):
            raise ValueError("section citations must be unique")
        return self


class LessonQuestion(ContractModel):
    prompt: Annotated[str, Field(min_length=1)]
    expected_answer: Annotated[str, Field(min_length=1)]
    citations: Annotated[tuple[StableBlockId, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def validate_unique_citations(self) -> LessonQuestion:
        if len(self.citations) != len(set(self.citations)):
            raise ValueError("question citations must be unique")
        return self


class Lesson(ContractModel):
    id: Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9.-]*$")]
    chapter: Annotated[int, Field(gt=0)]
    section: Annotated[str, Field(pattern=r"^[0-9]+(?:\.[0-9]+)*$")]
    title: Annotated[str, Field(min_length=1)]
    sections: Annotated[tuple[LessonSection, ...], Field(min_length=1)]
    questions: tuple[LessonQuestion, ...] = ()
    shader_example_id: Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9_-]*$")]
    shader_metadata_path: str = "examples/gooch.json"

    @field_validator("shader_metadata_path")
    @classmethod
    def validate_shader_metadata_path(cls, value: str) -> str:
        return _safe_relative_path(value)


class ShaderExample(ContractModel):
    id: Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9_-]*$")]
    language: Literal["glsl"]
    stage: Literal["fragment"]
    source_path: str
    browser_source_path: str
    source_block_ids: Annotated[tuple[StableBlockId, ...], Field(min_length=1)]
    expected_visual: Annotated[str, Field(min_length=1)]
    verification_command: Annotated[str, Field(min_length=1)]
    external_references: tuple[AnyHttpUrl, ...] = ()

    @field_validator("source_path")
    @classmethod
    def validate_source_path(cls, value: str) -> str:
        return _safe_relative_path(value)

    @field_validator("browser_source_path")
    @classmethod
    def validate_browser_source_path(cls, value: str) -> str:
        return _safe_relative_path(value)

    @field_validator("external_references")
    @classmethod
    def validate_https_references(
        cls, value: tuple[AnyHttpUrl, ...]
    ) -> tuple[AnyHttpUrl, ...]:
        if any(reference.scheme != "https" for reference in value):
            raise ValueError("external references must use HTTPS")
        return value

    @model_validator(mode="after")
    def validate_unique_source_blocks(self) -> ShaderExample:
        if len(self.source_block_ids) != len(set(self.source_block_ids)):
            raise ValueError("shader source block IDs must be unique")
        return self


def _safe_relative_path(value: str) -> str:
    path = Path(value)
    if (
        path.is_absolute()
        or path.anchor
        or path.drive
        or path.root
        or ".." in path.parts
        or "\\" in value
    ):
        raise ValueError("content path must be a safe POSIX-style relative path")
    return value


def _resolve_content_file(base: Path, relative: str) -> Path:
    root = base.resolve()
    candidate = base / relative
    current = candidate
    while current != base and current.is_relative_to(base):
        is_junction = getattr(current, "is_junction", None)
        if current.is_symlink() or is_junction is not None and is_junction():
            raise ValueError("content path contains a symlink or junction")
        current = current.parent
    resolved = candidate.resolve()
    if not resolved.is_relative_to(root):
        raise ValueError("content path escapes lesson directory")
    return resolved


def load_lesson_bundle(path: str | Path) -> tuple[Lesson, ShaderExample]:
    lesson_path = Path(path)
    lesson = Lesson.model_validate_json(lesson_path.read_text(encoding="utf-8"))
    shader_path = _resolve_content_file(
        lesson_path.parent, lesson.shader_metadata_path
    )
    shader = ShaderExample.model_validate_json(shader_path.read_text(encoding="utf-8"))
    for source_path in (shader.source_path, shader.browser_source_path):
        resolved_source = _resolve_content_file(lesson_path.parent, source_path)
        if not resolved_source.is_file():
            raise FileNotFoundError(resolved_source)
    return lesson, shader


def load_shader_sources(
    lesson_path: str | Path, shader: ShaderExample
) -> tuple[str, str]:
    """Load validated desktop and browser shader sources for API delivery."""
    base = Path(lesson_path).parent
    return (
        _read_content_file(base, shader.source_path),
        _read_content_file(base, shader.browser_source_path),
    )


def _opened_file_path(fd: int, candidate: Path) -> Path:
    if os.name == "nt":
        import ctypes
        import msvcrt

        handle = msvcrt.get_osfhandle(fd)
        buffer = ctypes.create_unicode_buffer(32768)
        length = ctypes.windll.kernel32.GetFinalPathNameByHandleW(
            handle, buffer, len(buffer), 0
        )
        if length == 0 or length >= len(buffer):
            raise OSError(ctypes.get_last_error(), "cannot resolve opened file")
        value = buffer.value
        if value.startswith("\\\\?\\UNC\\"):
            value = "\\\\" + value[8:]
        elif value.startswith("\\\\?\\"):
            value = value[4:]
        return Path(value)

    descriptor = Path(f"/proc/self/fd/{fd}")
    if descriptor.exists():
        return Path(os.readlink(descriptor)).resolve()
    raise OSError(f"cannot securely resolve opened file: {candidate}")


def _read_content_file(base: Path, relative: str) -> str:
    root = base.resolve()
    candidate = _resolve_content_file(base, relative)
    flags = os.O_RDONLY
    flags |= getattr(os, "O_BINARY", 0)
    flags |= getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(candidate, flags)
    try:
        opened_path = _opened_file_path(fd, candidate)
        if not opened_path.is_relative_to(root):
            raise ValueError("opened content file is outside lesson directory")
        with os.fdopen(fd, "r", encoding="utf-8", closefd=True) as source:
            fd = -1
            return source.read()
    finally:
        if fd >= 0:
            os.close(fd)


def validate_lesson_bundle(
    lesson: Lesson,
    shader: ShaderExample,
    known_block_ids: Collection[str],
) -> None:
    cited = {
        citation
        for section in lesson.sections
        for citation in section.citations
    }
    cited.update(
        citation
        for question in lesson.questions
        for citation in question.citations
    )
    cited.update(shader.source_block_ids)
    unknown = sorted(cited.difference(known_block_ids))
    if unknown:
        raise ValueError(f"unknown block IDs: {', '.join(unknown)}")
    if shader.id != lesson.shader_example_id:
        raise ValueError("lesson shader ID does not match shader metadata")
    level_counts = Counter(section.level for section in lesson.sections)
    invalid_levels = sorted(
        level for level in _REQUIRED_LEVELS if level_counts[level] != 1
    )
    if invalid_levels or len(level_counts) != len(_REQUIRED_LEVELS):
        raise ValueError(
            "each required lesson level must appear exactly once"
        )


def lesson_bundle_json(lesson: Lesson, shader: ShaderExample) -> str:
    return json.dumps(
        {
            "lesson": lesson.model_dump(mode="json"),
            "shader": shader.model_dump(mode="json"),
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
