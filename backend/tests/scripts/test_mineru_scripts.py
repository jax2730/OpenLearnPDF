from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SETUP_SCRIPT = REPO_ROOT / "scripts" / "setup-mineru.ps1"
PROBE_SCRIPT = REPO_ROOT / "scripts" / "probe-mineru.ps1"
LOCAL_RUNBOOK = REPO_ROOT / "docs" / "runbooks" / "local-development.md"
VALIDATE_OUTPUT_SCRIPT = REPO_ROOT / "scripts" / "validate-mineru-output.py"
SANITIZED_PROBE_FIXTURE = (
    REPO_ROOT
    / "backend"
    / "tests"
    / "fixtures"
    / "mineru"
    / "probe-104-106-content-list-v2.json"
)
POWERSHELL = shutil.which("pwsh") or shutil.which("powershell")


def _dry_run(
    script: Path, workspace_root: Path, *extra_args: str
) -> dict[str, object]:
    assert POWERSHELL is not None
    completed = subprocess.run(
        [
            POWERSHELL,
            "-NoProfile",
            "-NonInteractive",
            "-File",
            str(script),
            "-WorkspaceRoot",
            str(workspace_root),
            "-DryRun",
            *extra_args,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def _expected_cache_environment(workspace: Path) -> dict[str, str]:
    cache_root = workspace / ".cache"
    huggingface_root = cache_root / "huggingface"
    temp_root = cache_root / "tmp"
    return {
        "UV_CACHE_DIR": str(cache_root / "uv"),
        "PIP_CACHE_DIR": str(cache_root / "pip"),
        "MODELSCOPE_CACHE": str(cache_root / "modelscope"),
        "HF_HOME": str(huggingface_root),
        "HUGGINGFACE_HUB_CACHE": str(huggingface_root / "hub"),
        "MINERU_TOOLS_CONFIG_JSON": str(cache_root / "mineru" / "mineru.json"),
        "TEMP": str(temp_root),
        "TMP": str(temp_root),
    }


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell is required")
def test_setup_dry_run_targets_only_isolated_environment(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace with spaces"
    workspace.mkdir()

    result = _dry_run(SETUP_SCRIPT, workspace)

    assert Path(str(result["venv_path"])) == workspace / ".venv-mineru"
    assert result["mineru_requirement"] == "mineru[pipeline]==3.4.4"
    assert result["torch_requirement"] == "torch==2.13.0+cu130"
    assert result["torchvision_requirement"] == "torchvision==0.28.0+cu130"
    assert result["torch_index_url"] == "https://download.pytorch.org/whl/cu130"
    assert result["compatibility_requirements"] == ["six==1.17.0"]
    assert result["model_id"] == "OpenDataLab/PDF-Extract-Kit-1.0"
    assert result["model_revision"] == "master"
    assert result["python_version"] in {"3.10", "3.11", "3.12"}
    assert result["installer"] in {"uv", "venv-pip"}
    assert result["cache_environment"] == _expected_cache_environment(workspace)
    assert result["dry_run"] is True
    assert not (workspace / ".cache").exists()
    assert not (workspace / ".venv-mineru").exists()


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell is required")
def test_setup_rejects_workspace_inside_protected_environment(tmp_path: Path) -> None:
    protected = tmp_path / ".venv-pdf"
    protected.mkdir()

    completed = subprocess.run(
        [
            POWERSHELL,
            "-NoProfile",
            "-NonInteractive",
            "-File",
            str(SETUP_SCRIPT),
            "-WorkspaceRoot",
            str(protected),
            "-DryRun",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode != 0
    assert "protected" in completed.stderr.lower()
    assert not (protected / ".venv-mineru").exists()


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell is required")
def test_probe_dry_run_limits_pipeline_to_canonical_three_pages(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace with spaces"
    workspace.mkdir()

    result = _dry_run(PROBE_SCRIPT, workspace)

    assert result["backend"] == "pipeline"
    assert result["canonical_pages"] == [104, 105, 106]
    assert result["mineru_start_page"] == 103
    assert result["mineru_end_page"] == 105
    command = result["command"]
    assert isinstance(command, list)
    assert command[command.index("-b") + 1] == "pipeline"
    assert command[command.index("-s") + 1] == "103"
    assert command[command.index("-e") + 1] == "105"
    process_arguments = result["process_arguments"]
    assert process_arguments[process_arguments.index("-p") + 1] == f'"{command[2]}"'
    assert process_arguments[process_arguments.index("-o") + 1] == f'"{command[4]}"'
    assert result["cache_environment"] == _expected_cache_environment(workspace)
    assert result["dry_run"] is True
    assert not (workspace / ".cache").exists()
    assert not (workspace / "data").exists()


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell is required")
def test_probe_dry_run_supports_explicit_chapter_page_range(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    result = _dry_run(
        PROBE_SCRIPT,
        workspace,
        "-FirstPage",
        "104",
        "-LastPage",
        "154",
        "-RunLabel",
        "chapter-05",
    )

    assert result["canonical_pages"] == list(range(104, 155))
    assert result["mineru_start_page"] == 103
    assert result["mineru_end_page"] == 153
    assert "mineru-chapter-05-" in str(result["command"][4])


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell is required")
def test_probe_rejects_unbounded_page_span_before_materializing_range(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    completed = subprocess.run(
        [
            POWERSHELL,
            "-NoProfile",
            "-NonInteractive",
            "-File",
            str(PROBE_SCRIPT),
            "-WorkspaceRoot",
            str(workspace),
            "-DryRun",
            "-FirstPage",
            "1",
            "-LastPage",
            "2147483647",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode != 0
    assert "span" in completed.stderr.lower()


def test_mineru_scripts_do_not_use_string_evaluation() -> None:
    for script in (SETUP_SCRIPT, PROBE_SCRIPT):
        source = script.read_text(encoding="utf-8")
        assert "Invoke-Expression" not in source
        assert "cmd /c" not in source.lower()


def test_probe_avoids_deadlock_and_samples_gpu_and_process_tree_ram() -> None:
    source = PROBE_SCRIPT.read_text(encoding="utf-8")

    assert "Start-Process" in source
    assert "RedirectStandardOutput" in source
    assert "RedirectStandardError" in source
    assert "& $mineruExe @commandArgs" not in source
    assert "--query-gpu=memory.used" in source
    assert "gpu_peak_total_memory_used_mb" in source
    assert "gpu_memory_metric = 'device_global_memory_used_mb'" in source
    assert "Get-CimInstance Win32_Process" in source
    assert "WorkingSetSize" in source
    assert "$ramJob = Start-Job" in source
    assert "$ramResult = Receive-Job $ramJob" in source
    assert "PeakWorkingSet64" not in source
    assert "ram_peak_mb" in source


def test_probe_unwraps_background_job_gpu_peak_to_integer() -> None:
    source = PROBE_SCRIPT.read_text(encoding="utf-8")
    lines = {line.strip() for line in source.splitlines()}

    assert "$gpuResult = Receive-Job $gpuJob" in lines
    assert "$gpuPeakTotalMB = [int]$gpuResult" in lines


def test_full_chapter_runbook_uses_snapshot_output_name() -> None:
    source = LOCAL_RUNBOOK.read_text(encoding="utf-8")

    assert "source.snapshot\\auto\\source.snapshot_content_list_v2.json" in source
    assert (
        "mineru-chapter-05-<timestamp>\\RTR4-CN-v1.1\\auto\\"
        "RTR4-CN-v1.1_content_list_v2.json"
    ) not in source


def test_sanitized_probe_fixture_preserves_real_three_page_schema() -> None:
    pages = json.loads(SANITIZED_PROBE_FIXTURE.read_text(encoding="utf-8"))

    assert len(pages) == 3
    assert any(block["type"] == "image" for block in pages[0])
    assert any(block["type"] == "equation_interline" for block in pages[1])
    assert any(block["type"] == "equation_interline" for block in pages[2])
    serialized = json.dumps(pages, ensure_ascii=False)
    assert "Representative" in serialized
    assert len(serialized) < 3000


def test_probe_quotes_process_arguments_and_validates_native_outputs() -> None:
    source = PROBE_SCRIPT.read_text(encoding="utf-8")

    assert "ConvertTo-WindowsProcessArgument" in source
    assert "$processArguments = @($commandArgs | ForEach-Object" in source
    assert "validation.page_count -ne $canonicalPages.Count" in source
    assert "validation.markdown_count -lt 1" in source
    assert "validation.json_count -lt 1" in source
    assert "validation.asset_count -lt 1" in source
    assert "validation.nonempty_page_count -ne $canonicalPages.Count" in source
    assert "validation.markdown_nonempty_count -lt 1" in source
    assert "validation.asset_nonempty_count -lt 1" in source
    assert "validation.equation_block_count -lt 1" in source
    assert "validation.image_block_count -lt 1" in source


def test_probe_always_records_failures_and_cleans_gpu_job() -> None:
    source = PROBE_SCRIPT.read_text(encoding="utf-8")

    assert "model-download.stdout.log" in source
    assert "model-download.stderr.log" in source
    assert "validation.stdout.log" in source
    assert "validation.stderr.log" in source
    assert "finally {" in source
    assert "Remove-Job $gpuJob -Force" in source
    assert "error = $failureMessage" in source


def test_probe_records_source_and_artifact_content_hashes() -> None:
    source = PROBE_SCRIPT.read_text(encoding="utf-8")

    assert "source_sha256 =" in source
    assert "sha256 = (Get-FileHash" in source
    assert "sourceSha256Before" in source
    assert "New-Item -ItemType HardLink" in source


def test_probe_captures_process_handles_and_ids_before_waiting() -> None:
    source = PROBE_SCRIPT.read_text(encoding="utf-8")
    lines = {line.strip() for line in source.splitlines()}

    assert "$modelProcessId = $modelProcess.Id" in lines
    assert "$null = $modelProcess.Handle" in lines
    assert "$processId = $process.Id" in lines
    assert "$null = $process.Handle" in lines
    assert "Stop-ProcessTree -ProcessId $modelProcessId" in source
    assert "Stop-ProcessTree -ProcessId $processId" in source


def test_setup_records_pipeline_model_content_fingerprint() -> None:
    source = SETUP_SCRIPT.read_text(encoding="utf-8")

    assert "requested_revision = $RequestedRevision" in source
    assert "Get-ModelFingerprint $modelRoot $ModelId $ModelRevision" in source
    assert "manifest_sha256" in source
    assert "file_count" in source
    assert "total_bytes" in source


def test_output_validator_reports_required_three_page_artifacts(tmp_path: Path) -> None:
    auto = tmp_path / "book" / "auto"
    images = auto / "images"
    images.mkdir(parents=True)
    (auto / "book.md").write_text("Representative explanation", encoding="utf-8")
    (auto / "book_content_list_v2.json").write_text(
        json.dumps(
            [
                [
                    {
                        "type": "image",
                        "content": {
                            "image_source": {"path": "images/formula.jpg"}
                        },
                    }
                ],
                [
                    {
                        "type": "equation_interline",
                        "content": {
                            "image_source": {"path": "images/formula.jpg"}
                        },
                    }
                ],
                [{"type": "paragraph", "content": {}}],
            ]
        ),
        encoding="utf-8",
    )
    (images / "formula.jpg").write_bytes(b"representative")

    completed = subprocess.run(
        [sys.executable, str(VALIDATE_OUTPUT_SCRIPT), str(tmp_path)],
        check=True,
        capture_output=True,
        text=True,
    )
    report = json.loads(completed.stdout)

    assert report == {
        "asset_count": 1,
        "asset_nonempty_count": 1,
        "block_count": 3,
        "content_v2_count": 1,
        "equation_block_count": 1,
        "image_block_count": 1,
        "json_count": 1,
        "markdown_count": 1,
        "markdown_nonempty_count": 1,
        "missing_referenced_asset_count": 0,
        "nonempty_page_count": 3,
        "page_count": 3,
        "referenced_asset_count": 2,
    }


def test_output_validator_rejects_empty_placeholder_artifacts(tmp_path: Path) -> None:
    (tmp_path / "empty.md").write_text("", encoding="utf-8")
    (tmp_path / "empty_content_list_v2.json").write_text(
        json.dumps([[], [], []]), encoding="utf-8"
    )
    (tmp_path / "empty.jpg").write_bytes(b"")

    completed = subprocess.run(
        [sys.executable, str(VALIDATE_OUTPUT_SCRIPT), str(tmp_path)],
        check=True,
        capture_output=True,
        text=True,
    )
    report = json.loads(completed.stdout)

    assert report["nonempty_page_count"] == 0
    assert report["markdown_nonempty_count"] == 0
    assert report["asset_nonempty_count"] == 0
