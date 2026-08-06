# RTR4 Multimodal Learning System Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a local Web application that parses RTR4 chapter 5 into citation-preserving text, formula, figure, and code blocks, then provides lessons and source-grounded Q&A.

**Architecture:** A Python pipeline produces immutable filesystem artifacts and a SQLite search index. FastAPI exposes normalized book data and retrieval endpoints. A React/Vite frontend uses PDF.js for source pages, KaTeX for formulas, and block coordinates for two-way citation navigation. MinerU runs behind a parser adapter so tests and the UI can use deterministic fixtures before heavyweight model installation.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic, pytest, pypdf, pypdfium2, SQLite FTS5, sentence-transformers, MinerU, React 19, TypeScript, Vite, Vitest, Testing Library, PDF.js, KaTeX.

---

## Execution rules

- Use `@test-driven-development` for every feature task.
- Use `@systematic-debugging` for any failed test or unexpected parser behavior.
- Use `@verification-before-completion` before each completion claim.
- Execute in a dedicated Git worktree created with `@using-git-worktrees`.
- Never add source PDFs, model weights, virtual environments, generated page images, or parsing outputs to Git.
- Keep raw parser output immutable. Normalized output must reference its raw source file.
- Start with PDF pages 104–106. Do not process the full chapter until the vertical slice passes.

### Task 1: Repository hygiene and project skeleton

**Files:**
- Create: `.gitignore`
- Create: `README.md`
- Create: `backend/pyproject.toml`
- Create: `backend/src/rtr4_learning/__init__.py`
- Create: `backend/tests/test_smoke.py`
- Create: `frontend/package.json`
- Create: `frontend/tsconfig.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/App.test.tsx`

**Step 1: Write the backend failing smoke test**

```python
def test_package_imports() -> None:
    import rtr4_learning

    assert rtr4_learning.__version__ == "0.1.0"
```

**Step 2: Run it to verify failure**

Run:

```powershell
cd backend
python -m pytest tests/test_smoke.py -v
```

Expected: FAIL because package or version does not exist.

**Step 3: Create minimal backend package**

`backend/src/rtr4_learning/__init__.py`:

```python
__version__ = "0.1.0"
```

`backend/pyproject.toml` must define:

- package name `rtr4-learning`;
- Python `>=3.11`;
- runtime dependencies: `fastapi`, `pydantic>=2`, `pypdf`, `pypdfium2`, `uvicorn`;
- dev dependencies: `pytest`, `pytest-cov`, `httpx`, `ruff`;
- pytest path configuration for `src`.

**Step 4: Run backend test**

Expected: 1 passed.

**Step 5: Write frontend failing smoke test**

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import App from "./App";

describe("App", () => {
  it("shows the RTR4 reader title", () => {
    render(<App />);
    expect(screen.getByRole("heading", { name: /RTR4 学习系统/ })).toBeInTheDocument();
  });
});
```

**Step 6: Run frontend test to verify failure**

Run:

```powershell
cd frontend
npm install
npm test -- --run
```

Expected: FAIL until `App` and test setup exist.

**Step 7: Implement minimal frontend and Git ignore rules**

`.gitignore` must include:

```gitignore
.venv*/
node_modules/
dist/
target/
data/
models/
*.pdf
*.zip
*.png
*.jpg
*.jpeg
*.sqlite3
*.db
__pycache__/
.pytest_cache/
.ruff_cache/
```

`App.tsx` returns an `<h1>RTR4 学习系统</h1>`.

**Step 8: Run all smoke tests**

Expected: backend and frontend smoke tests pass.

**Step 9: Commit**

```powershell
git add .gitignore README.md backend frontend
git commit -m "chore: scaffold RTR4 learning application"
```

### Task 2: Canonical document contracts

**Files:**
- Create: `backend/src/rtr4_learning/models.py`
- Create: `backend/tests/test_models.py`
- Create: `docs/contracts/document-model.md`

**Step 1: Write failing tests**

Test these behaviors:

```python
from rtr4_learning.models import Block, BlockSource, BlockType, BoundingBox, Relation


def test_formula_block_round_trips() -> None:
    block = Block(
        id="p105-equation-5.1",
        type=BlockType.FORMULA,
        page=105,
        bbox=BoundingBox(x0=0.1, y0=0.5, x1=0.9, y1=0.6),
        latex=r"c_{shaded}=s c_{highlight}",
        number="5.1",
        asset_path="blocks/p105-equation-5.1.png",
        relations=[Relation(type="explained_by", target="p106-paragraph-2")],
        source=BlockSource(parser="fixture", version="1", confidence=0.9),
    )

    assert Block.model_validate_json(block.model_dump_json()) == block


def test_bbox_rejects_out_of_range_coordinates() -> None:
    with pytest.raises(ValueError):
        BoundingBox(x0=-0.1, y0=0, x1=1, y1=1)
```

Also test:

- formula requires `latex` or `asset_path`;
- figure caption relation target is a stable block ID;
- page number is positive;
- confidence is within 0–1.

**Step 2: Run tests and verify failure**

Expected: import failure.

**Step 3: Implement Pydantic models**

Implement enums and models for:

- `BlockType`;
- `BoundingBox`;
- `Relation`;
- `BlockSource`;
- `Block`;
- `PageDocument`;
- `ChapterManifest`;
- `BookManifest`;
- `StageManifest`.

Use normalized top-left coordinates in the inclusive range 0–1.

**Step 4: Run tests**

Expected: all model tests pass.

**Step 5: Document the contract**

Document coordinate system, stable ID format, block types, relation types, confidence meaning, and raw-source traceability.

**Step 6: Commit**

```powershell
git add backend/src/rtr4_learning/models.py backend/tests/test_models.py docs/contracts/document-model.md
git commit -m "feat: define canonical document contracts"
```

### Task 3: Book registration stage

**Files:**
- Create: `backend/src/rtr4_learning/paths.py`
- Create: `backend/src/rtr4_learning/stages/register.py`
- Create: `backend/src/rtr4_learning/cli.py`
- Create: `backend/tests/stages/test_register.py`

**Step 1: Write failing test**

Create a temporary PDF with `pypdf.PdfWriter`, register it, then assert:

- `book.json` exists;
- SHA-256 matches the input file;
- source path is absolute;
- chapter 5 page range is `[104, 154]`;
- rerunning produces byte-identical JSON.

**Step 2: Run test and verify failure**

Expected: `register_book` missing.

**Step 3: Implement minimal registration**

CLI:

```powershell
python -m rtr4_learning.cli register `
  --book-id rtr4-cn `
  --pdf I:\pdf_reaserch\RTR4-CN-v1.1.pdf `
  --chapter 5:104-154 `
  --data-root I:\pdf_reaserch\data
```

Registration must not copy the 203 MB PDF. Save the canonical absolute source path and hash.

**Step 4: Run tests**

Expected: registration tests pass.

**Step 5: Commit**

```powershell
git add backend/src/rtr4_learning/paths.py backend/src/rtr4_learning/stages/register.py backend/src/rtr4_learning/cli.py backend/tests/stages/test_register.py
git commit -m "feat: add idempotent book registration"
```

### Task 4: Page rendering stage

**Files:**
- Create: `backend/src/rtr4_learning/stages/render.py`
- Create: `backend/tests/stages/test_render.py`

**Step 1: Write failing test**

Generate a two-page temporary PDF. Render page 1 at a fixed scale. Assert:

- PNG exists;
- width and height are positive;
- `page.json` records PDF dimensions, pixel dimensions and coordinate transform;
- rerunning skips an unchanged page;
- changing render scale produces a new stage fingerprint.

**Step 2: Run and verify failure**

Expected: renderer missing.

**Step 3: Implement with `pypdfium2`**

The stage writes to a temporary directory and atomically replaces output only after all requested pages succeed.

**Step 4: Run tests**

Expected: all rendering tests pass.

**Step 5: Run the real three-page slice**

```powershell
python -m rtr4_learning.cli render --book-id rtr4-cn --pages 104-106 --scale 2
```

Expected: three PNGs and three page metadata files.

**Step 6: Commit**

```powershell
git add backend/src/rtr4_learning/stages/render.py backend/tests/stages/test_render.py
git commit -m "feat: render cited PDF pages"
```

### Task 5: Parser adapter and deterministic fixture parser

**Files:**
- Create: `backend/src/rtr4_learning/parsers/base.py`
- Create: `backend/src/rtr4_learning/parsers/fixture.py`
- Create: `backend/src/rtr4_learning/parsers/mineru.py`
- Create: `backend/tests/fixtures/mineru/page-105.json`
- Create: `backend/tests/parsers/test_fixture_parser.py`
- Create: `backend/tests/parsers/test_mineru_command.py`

**Step 1: Write adapter tests**

Define a `DocumentParser` protocol returning `RawParseResult` with:

- parser name and version;
- requested pages;
- raw JSON path;
- Markdown path;
- asset directory;
- command/config fingerprint.

Fixture parser test must load a deterministic page-105 fixture.

MinerU command test must assert construction of a pipeline-backend command without executing MinerU.

**Step 2: Run and verify failure**

Expected: parser modules missing.

**Step 3: Implement minimal adapters**

`MinerUParser` uses `subprocess.run([...], check=True, capture_output=True, text=True)` with an argument list, never a shell string.

Support:

- page ranges;
- pipeline backend;
- output directory;
- timeout;
- executable override;
- captured stdout/stderr log paths.

**Step 4: Run tests**

Expected: parser adapter tests pass without MinerU installed.

**Step 5: Commit**

```powershell
git add backend/src/rtr4_learning/parsers backend/tests/parsers backend/tests/fixtures/mineru
git commit -m "feat: add pluggable document parser interface"
```

### Task 6: MinerU isolated environment and real parse probe

**Files:**
- Create: `scripts/setup-mineru.ps1`
- Create: `scripts/probe-mineru.ps1`
- Create: `docs/runbooks/mineru.md`

**Step 1: Write dry-run tests**

Add PowerShell/Python tests that verify scripts:

- target `.venv-mineru` only;
- use Python 3.10–3.12;
- do not modify `.venv-pdf`;
- select `pipeline` backend;
- restrict probe to pages 104–106.

**Step 2: Run and verify failure**

Expected: scripts missing.

**Step 3: Implement setup script**

Use `uv` when available. Install MinerU into `.venv-mineru`. Record exact package and model versions in `data/toolchains/mineru.json`.

**Step 4: Install and probe**

Run only after checking at least 25 GB free disk space.

Expected:

- pages 104–106 parsed;
- raw JSON/Markdown/assets saved;
- no full-book processing;
- GPU peak and elapsed time recorded.

**Step 5: Preserve a sanitized fixture**

Copy only schema-representative, copyright-minimal metadata into tests. Do not commit full page text or page images.

**Step 6: Commit scripts and runbook**

```powershell
git add scripts/setup-mineru.ps1 scripts/probe-mineru.ps1 docs/runbooks/mineru.md backend/tests/fixtures/mineru
git commit -m "chore: add isolated MinerU probe workflow"
```

### Task 7: Normalize raw parser output

**Files:**
- Create: `backend/src/rtr4_learning/normalize.py`
- Create: `backend/src/rtr4_learning/relations.py`
- Create: `backend/tests/test_normalize.py`
- Create: `backend/tests/test_relations.py`

**Step 1: Write failing normalization tests**

Use the sanitized MinerU fixture to assert:

- raw formula becomes `BlockType.FORMULA`;
- absolute parser coordinates become normalized top-left coordinates;
- equation number `5.1` is extracted without deleting it from source data;
- figure and caption become separate blocks;
- page-105 formula and page-106 explanatory paragraph retain stable IDs;
- normalized JSON is deterministic.

**Step 2: Write failing relation tests**

Assert creation of:

- `caption_of`;
- `refers_to` from text such as “图5.3” and “方程5.1”;
- `next_block` in reading order;
- `belongs_to_section`.

**Step 3: Run and verify failure**

Expected: normalization functions missing.

**Step 4: Implement minimal normalization and relation linking**

Keep raw parser payload references in every normalized block.

**Step 5: Run tests**

Expected: normalization and relation tests pass.

**Step 6: Commit**

```powershell
git add backend/src/rtr4_learning/normalize.py backend/src/rtr4_learning/relations.py backend/tests/test_normalize.py backend/tests/test_relations.py
git commit -m "feat: normalize document blocks and relations"
```

### Task 8: Validation and enrichment queue

**Files:**
- Create: `backend/src/rtr4_learning/validate.py`
- Create: `backend/src/rtr4_learning/enrichment.py`
- Create: `backend/tests/test_validate.py`
- Create: `backend/tests/test_enrichment.py`

**Step 1: Write failing validation tests**

Test issues for:

- formula block with neither LaTeX nor image;
- formula containing replacement characters or implausibly short output;
- bbox outside page;
- caption without figure/table target;
- text reference to an unknown figure/equation;
- duplicate stable ID.

**Step 2: Write failing enrichment-cache tests**

Cache key must include:

```text
SHA256(crop bytes + provider + model + prompt version + options JSON)
```

Test that identical input reuses cache and model/prompt changes invalidate it.

**Step 3: Implement provider interface**

Define:

- `VisionEnricher` protocol;
- `UnavailableVisionEnricher` for no API key;
- `OpenAICompatibleVisionEnricher` configuration shell without live calls;
- persisted `EnrichmentRequest` and `EnrichmentResult`.

No live cloud call is required in this task.

**Step 4: Run tests**

Expected: validation and cache tests pass.

**Step 5: Commit**

```powershell
git add backend/src/rtr4_learning/validate.py backend/src/rtr4_learning/enrichment.py backend/tests/test_validate.py backend/tests/test_enrichment.py
git commit -m "feat: validate blocks and queue visual enrichment"
```

### Task 9: Search index and citation retrieval

**Files:**
- Create: `backend/src/rtr4_learning/index.py`
- Create: `backend/src/rtr4_learning/retrieval.py`
- Create: `backend/tests/test_index.py`
- Create: `backend/tests/test_retrieval.py`

**Step 1: Write failing FTS tests**

Index fixture blocks. Assert queries for:

- `Gooch 着色` return pages 104–106;
- `方程 5.1` returns formula block first;
- `逐顶点着色` returns figure 5.9 context;
- chapter filter excludes blocks outside chapter 5.

**Step 2: Write failing citation tests**

Every retrieval result must contain:

- block ID;
- page number;
- bbox;
- block type;
- source excerpt or LaTeX;
- score and score components.

**Step 3: Implement SQLite FTS5**

Use Python standard `sqlite3`. Keep schema migrations in code and store database outside Git.

**Step 4: Add embedding adapter**

Define `EmbeddingProvider`. Initial implementations:

- deterministic hash embedding for tests;
- optional sentence-transformers provider configured for a multilingual model.

Hybrid score combines normalized lexical and cosine scores. Do not add an external vector database in MVP.

**Step 5: Run tests**

Expected: retrieval tests pass deterministically.

**Step 6: Commit**

```powershell
git add backend/src/rtr4_learning/index.py backend/src/rtr4_learning/retrieval.py backend/tests/test_index.py backend/tests/test_retrieval.py
git commit -m "feat: add hybrid citation retrieval"
```

### Task 10: Lesson, question and code-example contracts

**Files:**
- Create: `backend/src/rtr4_learning/teaching.py`
- Create: `backend/tests/test_teaching.py`
- Create: `content/rtr4-cn/chapter-05/section-5.1.json`
- Create: `content/rtr4-cn/chapter-05/examples/gooch.frag`
- Create: `content/rtr4-cn/chapter-05/examples/gooch.json`

**Step 1: Write failing lesson validation tests**

Require every lesson section and factual claim to cite at least one existing block ID. Validate levels:

- intuition;
- mathematics;
- graphics meaning;
- implementation;
- example;
- pitfalls;
- exercises.

**Step 2: Write failing shader metadata test**

Require:

- source block IDs;
- language `glsl`;
- shader stage;
- expected visual result;
- verification command;
- optional external references.

**Step 3: Implement teaching models and citation checks**

Reject lesson JSON containing unknown block IDs or uncited factual sections.

**Step 4: Add the first Gooch lesson and shader**

Cover equations 5.1 and 5.2:

- `t = (dot(n, l) + 1) / 2`;
- cool/warm interpolation;
- reflection vector;
- narrow highlight factor;
- final interpolation.

Use original explanatory wording, not copied book prose.

**Step 5: Compile shader**

Run:

```powershell
glslangValidator -S frag content/rtr4-cn/chapter-05/examples/gooch.frag
```

Expected: exit code 0. If unavailable, install a pinned validator and record it in the runbook before changing the test.

**Step 6: Run teaching tests**

Expected: lesson and shader metadata tests pass.

**Step 7: Commit**

```powershell
git add backend/src/rtr4_learning/teaching.py backend/tests/test_teaching.py content/rtr4-cn/chapter-05
git commit -m "feat: add cited Gooch shading lesson"
```

### Task 11: FastAPI source and retrieval endpoints

**Files:**
- Create: `backend/src/rtr4_learning/api.py`
- Create: `backend/src/rtr4_learning/settings.py`
- Create: `backend/tests/test_api.py`

**Step 1: Write failing API tests**

Using FastAPI `TestClient`, test:

- `GET /api/health`;
- `GET /api/books/rtr4-cn`;
- `GET /api/books/rtr4-cn/chapters/5/pages/105`;
- `GET /api/blocks/p105-equation-5.1`;
- `GET /api/search?q=Gooch&chapter=5`;
- `GET /api/lessons/chapter-05/section-5.1`;
- `GET /api/capabilities` reports cloud vision unavailable when no key exists.

**Step 2: Run and verify failure**

Expected: API module missing.

**Step 3: Implement read-only endpoints**

Prevent arbitrary filesystem access. All asset paths must resolve under configured data/content roots.

**Step 4: Run tests**

Expected: API tests pass.

**Step 5: Commit**

```powershell
git add backend/src/rtr4_learning/api.py backend/src/rtr4_learning/settings.py backend/tests/test_api.py
git commit -m "feat: expose cited learning API"
```

### Task 12: PDF.js reader and block overlay

**Files:**
- Create: `frontend/src/api.ts`
- Create: `frontend/src/types.ts`
- Create: `frontend/src/components/PdfReader.tsx`
- Create: `frontend/src/components/BlockOverlay.tsx`
- Create: `frontend/src/components/PdfReader.test.tsx`
- Modify: `frontend/src/App.tsx`

**Step 1: Write failing component tests**

Mock page data and assert:

- page 105 is requested;
- formula bbox renders as an overlay button;
- clicking block calls `onSelectBlock("p105-equation-5.1")`;
- highlighted bbox uses normalized coordinates converted to percentages;
- page load failure shows a visible error state.

**Step 2: Run and verify failure**

Expected: components missing.

**Step 3: Implement PDF.js viewer**

Use `pdfjs-dist`. Keep the PDF worker path configured through Vite. Overlay must remain aligned during resize.

**Step 4: Run frontend tests**

Expected: reader tests pass.

**Step 5: Commit**

```powershell
git add frontend/src
git commit -m "feat: add PDF reader with cited block overlays"
```

### Task 13: Lesson panel, KaTeX and source navigation

**Files:**
- Create: `frontend/src/components/LessonPanel.tsx`
- Create: `frontend/src/components/Formula.tsx`
- Create: `frontend/src/components/SourceCitation.tsx`
- Create: `frontend/src/components/LessonPanel.test.tsx`
- Modify: `frontend/src/App.tsx`

**Step 1: Write failing tests**

Assert:

- formula 5.1 renders with KaTeX;
- citation button shows page 105;
- clicking citation navigates reader and highlights block;
- shader code and expected result are visible;
- external demo links use `target="_blank"` and safe `rel` attributes.

**Step 2: Run and verify failure**

Expected: components missing.

**Step 3: Implement lesson panel**

Render structured lesson JSON. Do not inject untrusted raw HTML. Use KaTeX strict mode with explicit error display.

**Step 4: Run tests**

Expected: lesson tests pass.

**Step 5: Commit**

```powershell
git add frontend/src
git commit -m "feat: add cited lessons and formula rendering"
```

### Task 14: Grounded Q&A flow

**Files:**
- Create: `backend/src/rtr4_learning/qa.py`
- Create: `backend/tests/test_qa.py`
- Create: `frontend/src/components/QuestionPanel.tsx`
- Create: `frontend/src/components/QuestionPanel.test.tsx`

**Step 1: Write failing backend tests**

Test:

- query retrieves sources before answering;
- answer contains citations only from retrieved block IDs;
- no provider configured returns an extractive source summary, not a hallucinated answer;
- provider response citing an unknown ID is rejected;
- insufficient evidence returns `status="insufficient_evidence"`.

**Step 2: Implement answer-provider abstraction**

Define:

- `AnswerProvider` protocol;
- `ExtractiveAnswerProvider` local fallback;
- `OpenAICompatibleAnswerProvider` configuration shell.

**Step 3: Write and implement frontend tests**

Question panel must show:

- answer status;
- citations;
- page navigation buttons;
- local-degraded capability label;
- insufficient-evidence message.

**Step 4: Run backend and frontend tests**

Expected: all Q&A tests pass.

**Step 5: Commit**

```powershell
git add backend/src/rtr4_learning/qa.py backend/tests/test_qa.py frontend/src
git commit -m "feat: add source-grounded question answering"
```

### Task 15: Real three-page vertical slice

**Files:**
- Create: `backend/tests/e2e/test_chapter5_slice.py`
- Create: `evaluation/chapter-05/questions.json`
- Create: `evaluation/chapter-05/expected-blocks.json`
- Create: `docs/runbooks/local-development.md`

**Step 1: Write failing end-to-end assertions**

For pages 104–106 require:

- page images exist;
- normalized page JSON validates;
- formula 5.1 and 5.2 exist with LaTeX or pending-enrichment status;
- figure 5.2 and 5.3 have captions;
- references resolve;
- search for Gooch returns correct blocks;
- lesson citations resolve;
- API returns the same canonical block data.

**Step 2: Run and verify failure**

Expected: fail until actual MinerU output is normalized and indexed.

**Step 3: Execute stages**

Run register, render, parse, normalize, validate, index and serve for pages 104–106.

**Step 4: Fix only evidence-backed failures**

Use `@systematic-debugging`. Add regression fixtures before changing normalization rules.

**Step 5: Run full verification**

```powershell
cd backend
python -m pytest -v
ruff check .

cd ..\frontend
npm test -- --run
npm run build
```

Expected: all tests pass and frontend production build succeeds.

**Step 6: Commit**

```powershell
git add backend/tests/e2e evaluation docs/runbooks/local-development.md
git commit -m "test: verify RTR4 chapter 5 vertical slice"
```

### Task 16: Expand to all chapter 5 pages and evaluate

**Files:**
- Create: `evaluation/chapter-05/rubric.json`
- Create: `evaluation/chapter-05/report.md`
- Create: `scripts/evaluate-chapter.ps1`
- Modify: `docs/runbooks/local-development.md`

**Step 1: Create the 20-question evaluation set**

Cover:

- Gooch shading;
- directional, point and spot lights;
- inverse-square attenuation;
- evaluation frequency;
- vertex versus pixel shading;
- aliasing and sampling;
- transparency and alpha;
- premultiplied alpha;
- display encoding and gamma correction.

Each question must include expected pages and required source block types.

**Step 2: Add scoring tests**

Score:

- page hit rate;
- block hit rate;
- citation validity;
- formula fidelity;
- figure/caption relation coverage;
- answer abstention when evidence is insufficient.

**Step 3: Process pages 104–154**

Do not proceed if the three-page slice regresses.

**Step 4: Run evaluation**

Pass gates:

- at least 18/20 questions hit a correct page;
- citation validity at least 95%;
- representative formulas 5.1 and 5.2 correct;
- figures 5.2, 5.3 and 5.9 linked correctly;
- no fabricated block IDs.

**Step 5: Write report with gaps**

Document parser failures, pages needing visual enrichment, elapsed time, GPU/RAM peaks and cloud calls avoided or used.

**Step 6: Final verification and commit**

```powershell
git add evaluation scripts/evaluate-chapter.ps1 docs/runbooks/local-development.md
git commit -m "feat: complete RTR4 chapter 5 learning slice"
```

## Final acceptance command set

```powershell
cd backend
python -m pytest -v
ruff check .

cd ..\frontend
npm test -- --run
npm run build

cd ..
powershell -ExecutionPolicy Bypass -File scripts/evaluate-chapter.ps1
git status --short
```

Expected:

- all backend tests pass;
- Ruff reports no errors;
- all frontend tests pass;
- Vite production build succeeds;
- chapter evaluation passes defined gates;
- Git shows no accidentally tracked PDFs, model files, page images, databases or environments.
