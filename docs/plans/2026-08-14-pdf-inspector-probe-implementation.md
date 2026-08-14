# PDF Inspector Probe Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build and run an isolated, reproducible `pdf-inspector` evaluation on RTR4 pages 109, 111, and 113 without changing the active MinerU data or using C-drive caches.

**Architecture:** Add a pure Python report builder plus a thin optional-dependency runner, then wrap it with one PowerShell script that creates an I-drive virtual environment, pins `pdf-inspector==1.14.1`, monitors peak process-tree memory, and writes immutable probe artifacts outside Git. Production parser interfaces remain untouched until the evidence is reviewed.

**Tech Stack:** Python 3.11+, Pydantic-free report helpers, pytest, PowerShell, `pdf-inspector==1.14.1` native wheel.

---

### Task 1: Define stable probe report helpers

**Files:**
- Create: `backend/src/rtr4_learning/pdf_inspector_probe.py`
- Create: `backend/tests/test_pdf_inspector_probe.py`

1. Write failing unit tests for one-based/zero-based page normalization, finite positioned-item validation, expected anchor detection, OCR routing, and deterministic recommendation generation.
2. Run `backend\.venv\Scripts\python.exe -m pytest backend/tests/test_pdf_inspector_probe.py -q` and confirm RED because the module is absent.
3. Implement pure helpers that accept dictionaries or simple objects shaped like the upstream Python API. Do not import `pdf_inspector` at module import time.
4. Make the report distinguish supported native text extraction from unsupported formula semantics and unsupported image understanding.
5. Run focused tests and Ruff.
6. Commit with `feat: define pdf inspector probe reports`.

### Task 2: Add the native-package runner

**Files:**
- Modify: `backend/src/rtr4_learning/pdf_inspector_probe.py`
- Modify: `backend/tests/test_pdf_inspector_probe.py`
- Create: `scripts/run-pdf-inspector-probe.py`

1. Write failing tests for source validation, immutable output refusal, JSON serialization, page artifact construction, source SHA-256, and a clear missing-package error.
2. Confirm RED for missing runner behavior.
3. Implement a small runner that:
   - imports `pdf_inspector` only after argument validation;
   - calls detection once;
   - calls `extract_pages_markdown` with zero-based pages `108,110,112`;
   - calls `extract_text_with_positions` with the upstream page convention verified by an explicit mapping step;
   - writes `classification.json`, `pages.json`, `report.json`, `report.md`, and `run.json` using UTF-8 and atomic file replacement;
   - never copies the source PDF or writes inside the repository.
4. Run focused tests and Ruff.
5. Commit with `feat: add pdf inspector probe runner`.

### Task 3: Add isolated I-drive setup and execution

**Files:**
- Create: `scripts/probe-pdf-inspector.ps1`
- Create: `backend/tests/scripts/test_pdf_inspector_probe_script.py`
- Modify: `.gitignore`

1. Write failing dry-run tests requiring:
   - `.venv-pdf-inspector` below the supplied I-drive workspace;
   - `pdf-inspector==1.14.1` pin;
   - `PIP_CACHE_DIR`, `TEMP`, and `TMP` below `I:\pdf_reaserch\.cache\pdf-inspector`;
   - default pages `109,111,113`;
   - output below `data\probes\pdf-inspector`;
   - no filesystem creation during dry run;
   - no `Invoke-Expression` or `cmd /c`;
   - process-tree working-set monitoring.
2. Confirm RED because the script is absent.
3. Implement the minimum PowerShell workflow:
   - resolve explicit paths;
   - reject a workspace on C drive;
   - verify sufficient I-drive space;
   - create/reuse the isolated venv;
   - redirect pip/temp caches before installing;
   - install the exact wheel only when missing or wrong-versioned;
   - launch the Python runner with `Start-Process` and explicit arguments;
   - sample child-process working sets;
   - add peak memory to `report.json` after successful completion.
4. Add `.probe/` or other local transient control files to `.gitignore` only if the script actually creates them.
5. Run focused script tests.
6. Commit with `feat: isolate pdf inspector probe environment`.

### Task 4: Run the real RTR4 three-page probe

**Files:**
- Create outside Git: `I:\pdf_reaserch\data\probes\pdf-inspector\<timestamp>\...`
- Modify: `docs/runbooks/local-development.md`

1. Run script dry-run and inspect its JSON plan.
2. Run the real probe against `I:\pdf_reaserch\RTR4-CN-v1.1.pdf` for pages 109, 111, and 113.
3. Verify generated artifacts by reading every JSON file and checking the Markdown report.
4. Compare evidence with existing MinerU normalized blocks for the same pages:
   - Chinese heading/prose presence;
   - formulas 5.9, 5.11, 5.14, 5.17, 5.18;
   - image placeholders versus MinerU figures;
   - OCR/encoding flags;
   - elapsed time and peak working set.
5. Add concise runbook commands and explain that generated evidence remains on I drive.
6. Commit with `docs: document pdf inspector probe`.

### Task 5: Verify, decide, and publish

1. Run all backend tests and Ruff.
2. Run all frontend tests and production build because the branch contains the teaching reader.
3. Run all three GLSL compile checks.
4. Audit tracked files for PDF, model, cache, database, PNG, `dist`, and `node_modules` artifacts.
5. Confirm `git status` contains only `.run/` as an allowed untracked directory.
6. Record one of three evidence-backed outcomes in the final report:
   - promote later to a native-text parser adapter;
   - keep only as an OCR-routing preflight;
   - reject for RTR4 CJK quality.
7. Push `feature/rtr4-learning` without force and report the cumulative commit count.
