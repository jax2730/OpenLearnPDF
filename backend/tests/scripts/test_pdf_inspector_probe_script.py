from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
PROBE_SCRIPT = REPO_ROOT / "scripts" / "probe-pdf-inspector.ps1"
POWERSHELL = shutil.which("pwsh") or shutil.which("powershell")


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell is required")
def test_dry_run_keeps_environment_and_caches_on_i_drive() -> None:
    workspace = Path("I:/pdf-inspector-probe-dry-run")
    assert POWERSHELL is not None

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
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    result = json.loads(completed.stdout)

    assert Path(result["venv_path"]) == workspace / ".venv-pdf-inspector"
    assert result["requirement"] == "pdf-inspector==1.14.1"
    assert result["pages"] == [109, 111, 113]
    assert Path(result["output_parent"]) == (
        workspace / "data" / "probes" / "pdf-inspector"
    )
    cache = result["cache_environment"]
    assert Path(cache["PIP_CACHE_DIR"]) == (
        workspace / ".cache" / "pdf-inspector" / "pip"
    )
    assert Path(cache["TEMP"]) == workspace / ".cache" / "pdf-inspector" / "tmp"
    assert cache["TMP"] == cache["TEMP"]
    assert result["dry_run"] is True
    assert not workspace.exists()


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell is required")
def test_dry_run_rejects_c_drive_workspace(tmp_path: Path) -> None:
    assert POWERSHELL is not None

    completed = subprocess.run(
        [
            POWERSHELL,
            "-NoProfile",
            "-NonInteractive",
            "-File",
            str(PROBE_SCRIPT),
            "-WorkspaceRoot",
            str(tmp_path),
            "-DryRun",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode != 0
    assert "c drive" in completed.stderr.lower()


def test_script_uses_safe_process_launch_and_process_tree_memory_sampling() -> None:
    source = PROBE_SCRIPT.read_text(encoding="utf-8")

    assert "Invoke-Expression" not in source
    assert "cmd /c" not in source.lower()
    assert "Start-Process" in source
    assert "RedirectStandardOutput" in source
    assert "RedirectStandardError" in source
    assert "Get-CimInstance Win32_Process" in source
    assert "WorkingSetSize" in source
    assert "peak_working_set_mb" in source
