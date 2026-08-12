# RTR4 local development

This runbook uses the existing I-drive MinerU probe. It does not download models,
rerun MinerU, or install a local shader application. Shader examples run in the
browser or can be pasted into ShaderToy.

## 1. Materialize the real pages 104-106 slice

From `I:\pdf_reaserch\.worktrees\rtr4-learning\backend`:

```powershell
.\.venv\Scripts\python.exe -m rtr4_learning.cli ingest-mineru `
  --book-id rtr4-cn `
  --content-list "I:\pdf_reaserch\data\books\rtr4-cn\parses\mineru-probe-20260811T043121Z\RTR4-CN-v1.1\auto\RTR4-CN-v1.1_content_list_v2.json" `
  --first-page 104 `
  --chapter 5 `
  --parser-version 3.4.4 `
  --data-root I:\pdf_reaserch\data
```

The command builds `pages.json`, `validation.json`, and `search.sqlite3` inside
an immutable fingerprinted bundle, then atomically switches `active.json` only
after all three artifacts validate. Generated data remains under
`I:\pdf_reaserch\data` and is excluded from Git.

## 2. Verify the real vertical slice

```powershell
$env:RTR4_E2E_DATA_ROOT = "I:\pdf_reaserch\data"
$env:RTR4_E2E_PROBE_ROOT = "I:\pdf_reaserch\data\books\rtr4-cn\parses\mineru-probe-20260811T043121Z"
.\.venv\Scripts\python.exe -m pytest tests\e2e\test_chapter5_slice.py -v
```

The test reads the real manifest, renders and probe, but builds normalized data
and the search index under pytest's temporary directory. It never changes the
active production bundle or truncates a future full-chapter index. It checks
formulas 5.1/5.2, figures 5.2/5.3, caption and body-reference relations,
exact Gooch/formula retrieval blocks, lesson citations, and API identity.

## 3. Start the API

From `backend`:

```powershell
$env:RTR4_DATA_ROOT = "I:\pdf_reaserch\data"
$env:RTR4_CONTENT_ROOT = "I:\pdf_reaserch\.worktrees\rtr4-learning\content"
$env:RTR4_SOURCE_ROOTS = "I:\pdf_reaserch"
.\.venv\Scripts\python.exe -m uvicorn `
  rtr4_learning.server:create_environment_app `
  --factory --host 127.0.0.1 --port 8000
```

The first source-PDF request verifies the registered SHA-256 and can take a few
seconds for the large book. Later requests reuse the in-process verification.

## 4. Start the Web UI

In a second terminal, from `frontend`:

```powershell
npm install
npm run dev
```

Open `http://127.0.0.1:5173`. Vite proxies `/api` to
`http://127.0.0.1:8000`. Formula rendering uses KaTeX. PDF rendering and block
overlays use PDF.js. The ShaderToy link opens an external browser demo page;
no local shader runtime is installed.

## 5. Full checks

```powershell
cd I:\pdf_reaserch\.worktrees\rtr4-learning\backend
.\.venv\Scripts\python.exe -m pytest -v
.\.venv\Scripts\ruff.exe check .

cd ..\frontend
npm test
npm run build
```

## 6. Process and evaluate all chapter 5 pages

The default MinerU probe remains pages 104-106. Full chapter processing must be
requested explicitly:

```powershell
cd I:\pdf_reaserch\.worktrees\rtr4-learning
.\scripts\probe-mineru.ps1 `
  -WorkspaceRoot I:\pdf_reaserch `
  -FirstPage 104 -LastPage 154 -RunLabel chapter-05
```

Ingest the resulting content list with the source-verified formula correction:

```powershell
cd backend
.\.venv\Scripts\python.exe -m rtr4_learning.cli ingest-mineru `
  --book-id rtr4-cn `
  --content-list "I:\pdf_reaserch\data\books\rtr4-cn\parses\mineru-chapter-05-<timestamp>\source.snapshot\auto\source.snapshot_content_list_v2.json" `
  --first-page 104 --chapter 5 --parser-version 3.4.4 `
  --formula-corrections "..\content\rtr4-cn\chapter-05\formula-corrections.json" `
  --visual-enrichments "..\content\rtr4-cn\chapter-05\visual-enrichments.json" `
  --data-root I:\pdf_reaserch\data
```

Run the 20-question acceptance evaluation:

```powershell
cd ..
.\scripts\evaluate-chapter.ps1 `
  -WorkspaceRoot I:\pdf_reaserch\.worktrees\rtr4-learning `
  -DataRoot I:\pdf_reaserch\data
```

The report is written to `evaluation/chapter-05/report.md`. The seven reviewed
figure crops are generated inside the immutable build. Only the explicit
Figure 6.27 cross-chapter reference may remain as a non-blocking validation
disposition; any in-chapter missing visual fails completeness.
