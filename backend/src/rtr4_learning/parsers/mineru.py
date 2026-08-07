"""Minimal subprocess adapter for a fixed MinerU CLI contract."""

from __future__ import annotations

import hashlib
import json
import math
import os
import subprocess
from collections.abc import Iterable
from pathlib import Path, PurePath
from typing import Any

from rtr4_learning.parsers.base import RawParseResult, canonical_pages

MINERU_CLI_PAGE_INDEX_BASE = 0
"""Target MinerU CLI `-s`/`-e` indexes are zero-based and inclusive."""


class ParserOutputError(RuntimeError):
    """MinerU returned success without the adapter's fixed output layout."""


def _mineru_page_index(canonical_page: int) -> int:
    return canonical_page - 1 + MINERU_CLI_PAGE_INDEX_BASE


def _canonical_json_bytes(value: dict[str, Any]) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_link_or_reparse_point(path: Path) -> bool:
    if path.is_symlink():
        return True
    is_junction = getattr(path, "is_junction", None)
    return bool(is_junction is not None and is_junction())


def _canonical_source_path(source_path: Path | str) -> Path:
    try:
        source = Path(source_path).resolve(strict=True)
    except OSError as error:
        raise ValueError("source_path must be an existing ordinary file") from error
    if not source.is_file() or _is_link_or_reparse_point(Path(source_path)):
        raise ValueError("source_path must be an existing ordinary file")
    return source


def _safe_relative_path(value: str) -> Path:
    path = Path(value)
    if (
        not value.strip()
        or value.endswith(("/", "\\"))
        or path in {Path("."), Path("..")}
        or path.is_absolute()
        or ".." in PurePath(value).parts
    ):
        raise ValueError("log paths must be safe relative paths")
    return path


def _contained_path(root: Path, relative: Path) -> Path:
    candidate = (root / relative).resolve()
    try:
        common = os.path.commonpath((str(root), str(candidate)))
    except ValueError as error:
        raise ValueError("log paths must be safe relative paths") from error
    if os.path.normcase(common) != os.path.normcase(str(root)):
        raise ValueError("log paths must be safe relative paths")
    if candidate == root or candidate.is_dir():
        raise ValueError("log paths must target files below output_dir")
    return candidate


def _relative_output_config(source: Path, output: Path) -> str:
    try:
        relative = os.path.relpath(output, start=source.parent)
    except ValueError:
        return output.name
    return Path(relative).as_posix()


def _paths_overlap(left: Path, right: Path) -> bool:
    left_value = os.path.normcase(str(left.resolve(strict=False)))
    right_value = os.path.normcase(str(right.resolve(strict=False)))
    try:
        common = os.path.normcase(os.path.commonpath((left_value, right_value)))
    except ValueError:
        return False
    return common in {left_value, right_value}


def _validate_log_artifact_separation(output: Path, *log_paths: Path) -> None:
    artifacts = (
        output / "raw.json",
        output / "document.md",
        output / "assets",
    )
    if any(
        _paths_overlap(log_path, artifact)
        for log_path in log_paths
        for artifact in artifacts
    ):
        raise ValueError("log path conflicts with parser outputs")


def _validated_output_artifacts(output: Path) -> tuple[Path, Path, Path]:
    raw_json_path = output / "raw.json"
    markdown_path = output / "document.md"
    asset_dir = output / "assets"
    expected = (
        (raw_json_path, "ordinary file"),
        (markdown_path, "ordinary file"),
        (asset_dir, "directory"),
    )
    for path, kind in expected:
        resolved = path.resolve(strict=False)
        try:
            common = os.path.commonpath((str(output), str(resolved)))
        except ValueError as error:
            raise ParserOutputError(
                f"unsafe parser output path: {path.name}"
            ) from error
        if os.path.normcase(common) != os.path.normcase(
            str(output)
        ) or _is_link_or_reparse_point(path):
            raise ParserOutputError(f"unsafe parser output path: {path.name}")
        valid_type = path.is_dir() if kind == "directory" else path.is_file()
        if not valid_type:
            raise ParserOutputError(
                f"expected parser output {path.name} to be an {kind}"
            )
    return raw_json_path, markdown_path, asset_dir


class MinerUParser:
    """Run one range into a new target.

    Failed runs retain their output directory and logs for diagnosis. A retry must use
    a new target, or the caller may inspect and explicitly remove the failed target.
    """

    parser_name = "mineru"
    parser_version = "1"
    backend = "pipeline"

    def __init__(
        self,
        *,
        executable: str = "mineru",
        timeout: float = 300.0,
        stdout_log_path: str = "stdout.log",
        stderr_log_path: str = "stderr.log",
    ) -> None:
        if not executable.strip():
            raise ValueError("executable must not be empty")
        if isinstance(timeout, bool) or not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout must be positive")
        self.executable = executable
        self.timeout = float(timeout)
        self.stdout_log_path = stdout_log_path
        self.stderr_log_path = stderr_log_path

    @staticmethod
    def _canonical_output_dir(output_dir: Path | str) -> Path:
        raw = Path(output_dir)
        raw_value = os.fspath(output_dir)
        if not raw_value.strip() or raw in {Path("."), Path("..")} or ".." in raw.parts:
            raise ValueError("output_dir must be a non-root directory path")
        result = raw.resolve()
        if result == Path(result.anchor):
            raise ValueError("output_dir must not be a filesystem root")
        if raw.exists() or _is_link_or_reparse_point(raw):
            raise ValueError("output_dir already exists; choose a new target")
        return result

    @staticmethod
    def _reserve_output_dir(output: Path) -> None:
        output.parent.mkdir(parents=True, exist_ok=True)
        try:
            output.mkdir(exist_ok=False)
        except FileExistsError as error:
            raise ValueError(
                "output_dir already exists; choose a new target"
            ) from error

    def build_command(
        self,
        *,
        source_path: Path | str,
        pages: Iterable[int],
        output_dir: Path | str,
    ) -> list[str]:
        requested_pages = canonical_pages(pages)
        source = _canonical_source_path(source_path)
        output = self._canonical_output_dir(output_dir)
        return [
            self.executable,
            "-p",
            str(source),
            "-o",
            str(output),
            "-b",
            self.backend,
            "-s",
            str(_mineru_page_index(requested_pages[0])),
            "-e",
            str(_mineru_page_index(requested_pages[-1])),
        ]

    def parse(
        self,
        *,
        source_path: Path | str | None = None,
        pages: Iterable[int],
        output_dir: Path | str | None = None,
    ) -> RawParseResult:
        if source_path is None:
            raise ValueError("source_path is required")
        if output_dir is None:
            raise ValueError("output_dir is required")

        stdout_relative = _safe_relative_path(self.stdout_log_path)
        stderr_relative = _safe_relative_path(self.stderr_log_path)
        output = self._canonical_output_dir(output_dir)
        stdout_path = _contained_path(output, stdout_relative)
        stderr_path = _contained_path(output, stderr_relative)
        if os.path.normcase(str(stdout_path)) == os.path.normcase(str(stderr_path)):
            raise ValueError("stdout and stderr log paths must be distinct")
        _validate_log_artifact_separation(output, stdout_path, stderr_path)
        requested_pages = canonical_pages(pages)
        source = _canonical_source_path(source_path)
        command = self.build_command(
            source_path=source, pages=requested_pages, output_dir=output
        )
        self._reserve_output_dir(output)
        identity = {
            "backend": self.backend,
            "executable": Path(self.executable).name,
            "output_dir": _relative_output_config(source, output),
            "pages": list(requested_pages),
            "parser": self.parser_name,
            "source_sha256": _sha256_file(source),
            "stderr_log_path": stderr_relative.as_posix(),
            "stdout_log_path": stdout_relative.as_posix(),
            "timeout": self.timeout,
            "version": self.parser_version,
        }

        try:
            completed = subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
            try:
                self._write_logs(
                    stdout_path,
                    stderr_path,
                    error.stdout,
                    error.stderr,
                )
            except OSError:
                pass
            raise
        self._write_logs(stdout_path, stderr_path, completed.stdout, completed.stderr)
        raw_json_path, markdown_path, asset_dir = _validated_output_artifacts(output)

        fingerprint = hashlib.sha256(_canonical_json_bytes(identity)).hexdigest()
        return RawParseResult(
            parser_name=self.parser_name,
            parser_version=self.parser_version,
            requested_pages=requested_pages,
            raw_json_path=raw_json_path,
            markdown_path=markdown_path,
            asset_dir=asset_dir,
            fingerprint=fingerprint,
        )

    @staticmethod
    def _write_logs(
        stdout_path: Path,
        stderr_path: Path,
        stdout: str | bytes | None,
        stderr: str | bytes | None,
    ) -> None:
        def text(value: str | bytes | None) -> str:
            if value is None:
                return ""
            if isinstance(value, bytes):
                return value.decode("utf-8", errors="replace")
            return value

        stdout_path.parent.mkdir(parents=True, exist_ok=True)
        stderr_path.parent.mkdir(parents=True, exist_ok=True)
        stdout_path.write_text(text(stdout), encoding="utf-8")
        stderr_path.write_text(text(stderr), encoding="utf-8")
