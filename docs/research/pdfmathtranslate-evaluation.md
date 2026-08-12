# PDFMathTranslate reuse evaluation

Date: 2026-08-11

## Decision

Do not replace the RTR4 extraction pipeline with PDFMathTranslate.

Keep the authoritative flow:

```text
MinerU raw output -> canonical blocks -> relations -> validation -> retrieval -> teaching
```

PDFMathTranslate may later run as an optional, isolated sidecar that produces a
monolingual or bilingual PDF for comparison reading. Its output must not be the
authoritative source for formula, figure, or citation relations.

BabelDOC exposes a structured intermediate layer and parse-only functions. It is
a separate future extractor candidate, not a reason to embed PDFMathTranslate in
the current backend. Evaluate it against the same three-page fixture before any
integration decision.

## Evidence

Sources inspected at fixed revisions:

- PDFMathTranslate `44c4d5b332705797c1df17fadde2022e7c49f5de`
- PDFMathTranslate-next `61a6b68ccecf277bb02eb783c5f0ae4e4ce72b9f`
- BabelDOC `38d3896dcde9b5a940c62cf5563cadea673a64d3`

PDFMathTranslate describes its goal as scientific PDF translation with layout
preservation. Its unified result contract contains only `mono_pdf`, `dual_pdf`,
and timing data. The experimental precise worker also serializes only mono/dual
PDF paths back to the parent process. The documented v1 API is temporarily
deprecated and directs programmatic users to BabelDOC.

Its legacy converter protects formula characters with placeholders such as
`{vN}`, translates surrounding text, then restores the protected content during
PDF layout reconstruction. This preserves visible formulas but does not produce
our canonical formula semantics, stable block IDs, or teaching relations.

BabelDOC internally creates an IL containing text, character styles, formulas,
layout, graphics, and XObjects. `parse_only.py` returns that representation, and
debug mode can write `create_il.debug.json`. Public translation results still
focus on translated PDF paths. Using the IL would therefore require a new
adapter, schema mapping, fidelity tests, and AGPL review.

## Fit matrix

| Need | MinerU + canonical pipeline | PDFMathTranslate | BabelDOC IL |
|---|---|---|---|
| Text and reading blocks | Direct | Internal translation input | Available, adapter required |
| Formula LaTeX | Direct MinerU field | Protected/restored visually | Formula structure exists; fidelity must be measured |
| Figures and assets | Direct paths and blocks | Preserved in output PDF | Graphics/layout available; export mapping required |
| Stable block IDs | Implemented locally | Not exposed | Not compatible without mapping |
| Relations and citations | Implemented locally | Not exposed | Must be derived locally |
| Bilingual comparison PDF | Not a goal | Strong fit | Strong fit through translation flow |
| Drop-in backend dependency | Already isolated | No | No |

## Integration constraints

- PDFMathTranslate 1.9.11 requires Python `>=3.11,<3.13`; the existing MinerU
  environment uses Python 3.10. Never merge these environments.
- PDFMathTranslate and BabelDOC use AGPL-3.0. Do not copy their source into the
  core service without accepting and reviewing AGPL obligations.
- Both dependency sets are heavy and include ONNX, OpenCV, PDF libraries, UI or
  translation clients. Keep any experiment in an I-drive isolated environment.
- No PDFMathTranslate or BabelDOC package, model, or environment is installed by
  this decision.

## Recommended future experiment

If bilingual reading becomes a priority:

1. Add a disabled-by-default subprocess adapter.
2. Use an isolated I-drive environment and explicit output/working directories.
3. Run only PDF pages 104-106 first.
4. Consume only mono/dual PDF outputs.
5. Keep MinerU canonical blocks authoritative.

If extraction quality becomes a priority, evaluate BabelDOC parse-only IL as a
separate parser adapter. Compare formula fidelity, figure coverage, reading
order, time, memory, and missing assets against the same MinerU fixture.

## Official source links

- [PDFMathTranslate README](https://github.com/PDFMathTranslate/PDFMathTranslate/blob/44c4d5b332705797c1df17fadde2022e7c49f5de/README.md)
- [PDFMathTranslate dependency and license metadata](https://github.com/PDFMathTranslate/PDFMathTranslate/blob/44c4d5b332705797c1df17fadde2022e7c49f5de/pyproject.toml)
- [Unified result protocol](https://github.com/PDFMathTranslate/PDFMathTranslate/blob/44c4d5b332705797c1df17fadde2022e7c49f5de/pdf2zh/kernel/protocol.py)
- [Precise subprocess worker](https://github.com/PDFMathTranslate/PDFMathTranslate/blob/44c4d5b332705797c1df17fadde2022e7c49f5de/pdf2zh/kernel/v2_worker.py)
- [Chinese API deprecation notice](https://github.com/PDFMathTranslate/PDFMathTranslate/blob/44c4d5b332705797c1df17fadde2022e7c49f5de/docs/README_zh-CN.md)
- [PDFMathTranslate-next Python API](https://github.com/PDFMathTranslate/PDFMathTranslate-next/blob/61a6b68ccecf277bb02eb783c5f0ae4e4ce72b9f/docs/zh/advanced/API/python.md)
- [BabelDOC parse-only API](https://github.com/funstory-ai/BabelDOC/blob/38d3896dcde9b5a940c62cf5563cadea673a64d3/babeldoc/format/pdf/parse_only.py)
- [BabelDOC parsing and IL design](https://github.com/funstory-ai/BabelDOC/blob/38d3896dcde9b5a940c62cf5563cadea673a64d3/docs/ImplementationDetails/PDFParsing/PDFParsing.md)
