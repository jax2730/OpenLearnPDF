from __future__ import annotations

import hashlib
import json
import math
import subprocess
from pathlib import Path

import pytest

from rtr4_learning.parsers.mineru import MinerUParser


def test_build_command_converts_one_based_pages_to_mineru_zero_based_range(
    tmp_path: Path,
) -> None:
    source = tmp_path / "book.pdf"
    source.write_bytes(b"pdf identity")
    output_dir = tmp_path / "output"
    parser = MinerUParser(executable="custom-mineru", timeout=90)

    command = parser.build_command(
        source_path=source, pages=[106, 104, 105], output_dir=output_dir
    )

    assert command == [
        "custom-mineru",
        "-p",
        str(source.resolve()),
        "-o",
        str(output_dir.resolve()),
        "-b",
        "pipeline",
        "-s",
        "103",
        "-e",
        "105",
    ]


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"pages": []}, "pages"),
        ({"pages": [1, 3]}, "contiguous"),
        ({"pages": [0]}, "positive"),
        ({"timeout": 0}, "timeout"),
        ({"timeout": -1}, "timeout"),
        ({"timeout": math.nan}, "timeout"),
        ({"timeout": math.inf}, "timeout"),
        ({"executable": ""}, "executable"),
        ({"executable": "   "}, "executable"),
    ],
)
def test_mineru_rejects_invalid_configuration_or_pages(
    tmp_path: Path, kwargs: dict[str, object], message: str
) -> None:
    source = tmp_path / "book.pdf"
    source.write_bytes(b"pdf")
    parser_kwargs = {
        key: value for key, value in kwargs.items() if key in {"timeout", "executable"}
    }
    pages = kwargs.get("pages", [1])

    with pytest.raises(ValueError, match=message):
        parser = MinerUParser(**parser_kwargs)  # type: ignore[arg-type]
        parser.build_command(
            source_path=source,
            pages=pages,  # type: ignore[arg-type]
            output_dir=tmp_path / "output",
        )


@pytest.mark.parametrize("log_name", ["../escape.log", "nested/../../escape.log"])
def test_mineru_rejects_log_path_escape(tmp_path: Path, log_name: str) -> None:
    with pytest.raises(ValueError, match="safe relative"):
        MinerUParser(stdout_log_path=log_name).parse(
            source_path=tmp_path / "book.pdf",
            pages=[1],
            output_dir=tmp_path / "output",
        )


def test_parse_runs_argument_list_and_writes_captured_logs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    source = tmp_path / "book.pdf"
    source.write_bytes(b"pdf")
    output_dir = tmp_path / "output"
    calls: list[tuple[list[str], dict[str, object]]] = []

    def fake_run(
        command: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, "stdout text", "stderr text")

    monkeypatch.setattr(subprocess, "run", fake_run)
    parser = MinerUParser(
        executable="mineru-test",
        timeout=42,
        stdout_log_path="logs/stdout.log",
        stderr_log_path="logs/stderr.log",
    )

    result = parser.parse(source_path=source, pages=[2, 1, 2], output_dir=output_dir)

    assert len(calls) == 1
    command, kwargs = calls[0]
    assert isinstance(command, list)
    assert kwargs == {
        "check": True,
        "capture_output": True,
        "text": True,
        "timeout": 42.0,
    }
    assert (output_dir / "logs" / "stdout.log").read_text(encoding="utf-8") == (
        "stdout text"
    )
    assert (output_dir / "logs" / "stderr.log").read_text(encoding="utf-8") == (
        "stderr text"
    )
    assert result.raw_json_path == (output_dir / "raw.json").resolve()
    assert result.markdown_path == (output_dir / "document.md").resolve()
    assert result.asset_dir == (output_dir / "assets").resolve()
    assert result.requested_pages == (1, 2)


def test_parse_preserves_called_process_error_and_writes_logs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    source = tmp_path / "book.pdf"
    source.write_bytes(b"pdf")
    output_dir = tmp_path / "output"
    error = subprocess.CalledProcessError(
        2, ["mineru"], output="failed stdout", stderr="failed stderr"
    )

    def fail_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise error

    monkeypatch.setattr(subprocess, "run", fail_run)

    with pytest.raises(subprocess.CalledProcessError) as raised:
        MinerUParser().parse(source_path=source, pages=[1], output_dir=output_dir)

    assert raised.value is error
    assert (output_dir / "stdout.log").read_text(encoding="utf-8") == "failed stdout"
    assert (output_dir / "stderr.log").read_text(encoding="utf-8") == "failed stderr"


def test_log_write_failure_does_not_mask_called_process_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    source = tmp_path / "book.pdf"
    source.write_bytes(b"pdf")
    process_error = subprocess.CalledProcessError(2, ["mineru"])
    parser = MinerUParser()

    monkeypatch.setattr(
        subprocess, "run", lambda *args, **kwargs: (_ for _ in ()).throw(process_error)
    )
    monkeypatch.setattr(
        parser,
        "_write_logs",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("disk full")),
    )

    with pytest.raises(subprocess.CalledProcessError) as raised:
        parser.parse(source_path=source, pages=[1], output_dir=tmp_path / "output")

    assert raised.value is process_error


def test_fingerprint_is_stable_and_changes_with_key_configuration(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    source = tmp_path / "book.pdf"
    source.write_bytes(b"same source")
    output_dir = tmp_path / "output"

    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, "", ""),
    )
    first = MinerUParser(executable="mineru-a", timeout=30).parse(
        source_path=source, pages=[2, 1], output_dir=output_dir
    )
    repeated = MinerUParser(executable="mineru-a", timeout=30).parse(
        source_path=source, pages=[1, 2], output_dir=output_dir
    )
    changed = MinerUParser(executable="mineru-b", timeout=30).parse(
        source_path=source, pages=[1, 2], output_dir=output_dir
    )
    changed_output = MinerUParser(executable="mineru-a", timeout=30).parse(
        source_path=source, pages=[1, 2], output_dir=tmp_path / "other-output"
    )

    assert first.fingerprint == repeated.fingerprint
    assert first.fingerprint != changed.fingerprint
    assert first.fingerprint != changed_output.fingerprint
    assert (
        first.fingerprint
        == hashlib.sha256(
            json.dumps(
                {
                    "backend": "pipeline",
                    "executable": "mineru-a",
                    "output_dir": str(output_dir.resolve()),
                    "pages": [1, 2],
                    "parser": "mineru",
                    "source_path": str(source.resolve()),
                    "source_sha256": hashlib.sha256(b"same source").hexdigest(),
                    "timeout": 30.0,
                    "version": "1",
                },
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
    )


def test_fingerprint_uses_source_identity_captured_before_process_runs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    source = tmp_path / "book.pdf"
    source.write_bytes(b"before")

    def mutate_source(
        *args: object, **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        source.write_bytes(b"after")
        return subprocess.CompletedProcess(args[0], 0, "", "")

    monkeypatch.setattr(subprocess, "run", mutate_source)
    result = MinerUParser().parse(
        source_path=source, pages=[1], output_dir=tmp_path / "output"
    )
    expected = hashlib.sha256(
        json.dumps(
            {
                "backend": "pipeline",
                "executable": "mineru",
                "output_dir": str((tmp_path / "output").resolve()),
                "pages": [1],
                "parser": "mineru",
                "source_path": str(source.resolve()),
                "source_sha256": hashlib.sha256(b"before").hexdigest(),
                "timeout": 300.0,
                "version": "1",
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()

    assert result.fingerprint == expected


def test_output_directory_must_not_be_source_file_parent_escape(tmp_path: Path) -> None:
    source = tmp_path / "book.pdf"
    source.write_bytes(b"pdf")
    output_dir = tmp_path / "output"
    parser = MinerUParser()

    with pytest.raises(ValueError, match="output_dir"):
        parser.build_command(
            source_path=source,
            pages=[1],
            output_dir=output_dir / ".." / "escaped",
        )
