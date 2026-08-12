# MinerU pipeline probe

Validated on 2026-08-07 against the official MinerU repository, documentation,
and PyPI metadata.

## Pinned toolchain

- Package: `mineru[pipeline]==3.4.4`
- Compatibility dependency: `six==1.17.0` (MinerU pipeline OCR imports it but
  MinerU 3.4.4 does not declare it)
- Python: 3.10 preferred; 3.11 and 3.12 accepted
- Backend: `pipeline`
- Model source: ModelScope, selected explicitly for a mainland China workstation
- CUDA runtime: PyTorch `2.13.0+cu130` and torchvision `0.28.0+cu130` from the
  official PyTorch `cu130` index when NVIDIA hardware is present
- Environment: `<WorkspaceRoot>/.venv-mineru` only
- Caches and temporary files: `<WorkspaceRoot>/.cache/{uv,pip,modelscope,huggingface,tmp}`
  only; environment variables are process-local and never persisted to user or
  system settings

The pipeline extra is intentional. MinerU's official README recommends
`mineru[all]` for broad feature coverage, but this probe does not use VLM,
LMDeploy, Gradio, S3, or router extras. PyPI 3.4.4 publishes a dedicated
`pipeline` extra containing Torch, torchvision, ONNX Runtime, Transformers,
and the layout/formula dependencies needed by this backend.

PyPI's default Windows Torch wheel is CPU-only. MinerU's official Windows CUDA
FAQ directs RTX 20/30/40-series users to replace it with a CUDA-enabled wheel
from PyTorch's official index. This workstation reports an RTX 3050 and driver
CUDA 13.1 support, so setup pins the matching `cu130` builds published by the
official PyTorch index.

Official references:

- <https://pypi.org/project/mineru/3.4.4/>
- <https://github.com/opendatalab/MinerU>
- <https://opendatalab.github.io/MinerU/usage/cli_tools/>
- <https://opendatalab.github.io/MinerU/usage/model_source/>

MinerU 3.4.4 requires Python `>=3.10,<3.14`. Its official platform table limits
Windows to Python 3.10-3.12 because Ray does not support Python 3.13 there.
The CLI documents `--start` and `--end` as inclusive, zero-based page numbers.
Therefore book pages 104-106 are passed as `-s 103 -e 105`.

## Dry run

Dry runs emit JSON and perform no writes:

```powershell
.\scripts\setup-mineru.ps1 -WorkspaceRoot I:\pdf_reaserch -DryRun
.\scripts\probe-mineru.ps1 -WorkspaceRoot I:\pdf_reaserch -DryRun
```

Both real operations refuse to start when less than 25 GB is free. Setup also
refuses any target under `.venv-pdf` or `backend/.venv`.
Both dry-run plans report `UV_CACHE_DIR`, `MODELSCOPE_CACHE`, `HF_HOME`,
`HUGGINGFACE_HUB_CACHE`, `PIP_CACHE_DIR`, `TEMP`, `TMP`, and
`MINERU_TOOLS_CONFIG_JSON` without creating cache directories. The last setting
prevents MinerU from writing `mineru.json` into the user profile; the temp and
pip settings prevent fallback installation from filling the C drive.

## Install

```powershell
.\scripts\setup-mineru.ps1 -WorkspaceRoot I:\pdf_reaserch
```

When `uv` is available the script uses it. Otherwise it uses `py -3.10` (then
3.11 or 3.12) to create a standard-library venv and invokes pip only through
that venv's Python. Rerunning setup is idempotent. Exact package, CLI, Python,
GPU, and model bookkeeping is written to ignored
`data/toolchains/mineru.json` as UTF-8 JSON.
When the pipeline snapshot exists, the record includes model ID, requested
revision, file count, total bytes, and a SHA-256 manifest over every relative
path, file size, and file SHA-256. ModelScope's mutable `master` label is not
treated as an immutable version; the content manifest is the exact local model
fingerprint.

## Three-page probe

```powershell
.\scripts\probe-mineru.ps1 -WorkspaceRoot I:\pdf_reaserch
```

The probe downloads pipeline models with:

```text
mineru-models-download --source modelscope --model_type pipeline
```

It then parses only `RTR4-CN-v1.1.pdf` pages 104-106 using the pipeline
backend. Every run gets a new ignored directory below
`data/books/rtr4-cn/parses/mineru-probe-*`. Native output is retained without
renaming or rewriting. `stdout.log`, `stderr.log`, and `probe.json` record the
command argument array, elapsed time, exit status, artifact inventory, and
sampled NVIDIA device-global memory. `gpu_baseline_total_memory_used_mb` and
`gpu_peak_total_memory_used_mb` include every process using the GPU;
`gpu_peak_delta_from_baseline_mb` is only a workstation-level delta, not exact
per-process attribution. Model download receives separate stdout/stderr logs.
The probe reports success only after finding non-empty Markdown and assets,
exactly one `content_list_v2` file, three non-empty parsed pages, display-equation
and image blocks, and no missing asset references. Validation stdout/stderr are
saved beside the MinerU logs.

On failure, inspect the preserved logs and output before retrying. Do not widen
the page range, switch to a cloud API, or delete native artifacts during
diagnosis.

## Sanitized test fixture

After a successful real probe, fixture sanitization keeps only structural JSON
field names and types, representative block categories and bounding boxes,
formula placeholders, and tiny synthetic text. It excludes page prose, page
images, extracted book figures, and model files. Native probe output remains
ignored under `data/`.
