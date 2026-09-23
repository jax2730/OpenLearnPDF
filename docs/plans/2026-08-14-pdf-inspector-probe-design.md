# PDF Inspector Probe Design

## Goal

Evaluate `firecrawl/pdf-inspector` against representative RTR4 Chinese pages before allowing it into the production parser pipeline. The probe must measure what it actually preserves—Chinese text, reading order, positioned text, formulas, image placeholders, runtime, and memory—without replacing MinerU or changing active book data.

## Decision

Use `pdf-inspector` only as an isolated backend probe first. Do not add its WASM build to the browser, do not make it the default parser, and do not regenerate the active RTR4 bundle.

If the probe passes, a later change may add a `DocumentParser` adapter for native-text pages while retaining MinerU for formulas, figures, scanned pages, and unreliable CJK text.

## Scope

The first probe processes PDF pages 109, 111, and 113 because they cover:

- Chinese prose and headings;
- formulas 5.9, 5.11, 5.14, 5.17, and 5.18;
- figure references and embedded image objects;
- the exact source blocks already used by the 5.2.2 teaching lesson.

Outputs remain under `I:\pdf_reaserch\data\probes\pdf-inspector`. They are generated evidence and stay outside Git.

## Architecture

The implementation has three small layers:

1. A pure evaluator converts `pdf-inspector` results into a stable JSON report. It knows nothing about installation or subprocess management.
2. A probe runner imports `pdf_inspector`, records elapsed time and peak process memory, extracts selected-page Markdown and positioned text, and writes immutable artifacts.
3. A PowerShell entry point creates or reuses an isolated I-drive virtual environment, redirects pip cache and temporary files to I drive, installs a pinned wheel, and invokes the runner.

The production `DocumentParser` protocol remains unchanged during this phase.

## Artifacts

Each run writes a timestamped directory containing:

- `classification.json`: PDF type, confidence, page count, OCR routing, and package version;
- `pages.json`: per-page Markdown, positioned text items, image placeholders, and quality flags;
- `report.json`: measurements and machine-readable acceptance results;
- `report.md`: compact human comparison checklist;
- `run.json`: source path, source SHA-256, requested pages, tool version, and timestamps.

No PDF copy, rendered PNG, SQLite database, model, virtual environment, or package cache enters Git.

## Acceptance Rules

The probe is evidence gathering, not an automatic production approval. It reports pass/fail for objective checks:

- all requested pages are returned;
- extraction completes without crash;
- each page has positioned items or an explicit OCR reason;
- expected anchor strings or formula-number tokens are found where native extraction claims reliability;
- all coordinates and dimensions are finite and non-negative;
- page numbering is normalized explicitly between zero-based library APIs and one-based book pages;
- source SHA-256 and package version are recorded;
- peak working set and elapsed time are recorded.

Formula semantics and image understanding are always marked unsupported by this parser. Their absence does not make the probe crash, but it prevents `pdf-inspector` from replacing MinerU.

## Error Handling

- Missing package: fail with an installation instruction pointing to the I-drive setup script.
- Missing or invalid PDF: fail before creating a completed run marker.
- Partial page failure: preserve diagnostic output and mark the run failed.
- CJK corruption, empty text, or `needs_ocr`: record the reason and route that page to MinerU in the recommendation.
- Existing output directory: refuse overwrite to preserve evidence.

## Testing

Use TDD around pure report construction and validation. Unit tests use synthetic `pdf-inspector`-shaped objects so normal test runs do not require the native package. A separate opt-in integration command runs against the real RTR4 PDF.

Full repository tests, Ruff, forbidden-artifact audit, and the real three-page probe must pass before publishing the change.

## Non-Goals

- No browser WASM integration.
- No active MinerU bundle mutation.
- No image byte extraction or rasterization.
- No LaTeX reconstruction.
- No automatic full-book conversion.
- No parser-adapter promotion until probe evidence is reviewed.
