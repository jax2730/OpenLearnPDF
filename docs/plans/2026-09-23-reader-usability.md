# Reader usability iteration

Keep the approved side-by-side PDF and cited lesson layout. Reuse the current React/API/data pipeline without installing models or a shader runtime.

## Findings and changes

- Page navigation was citation-only. Add bounded chapter navigation (104–154) and a draft field committed on submit; invalid input must not navigate. Label PDF versus printed page numbers.
- Course switching left an unrelated PDF page/citation selected. Navigate to existing lesson entry pages (105, 106, 109), clear stale selection. Manual browsing preserves the course.
- Dense source boxes obscure reading. Add a toggle without reloading the document.
- Knowledge-point courses returned before rendering shader examples. Share the practice section across both lesson layouts; describe the external link accurately as an editor. Keep code folded initially.
- Real browser startup produced a transient PDF 409. Source verification compared complete stat records, including access time that can change during reading. Compare identity, size, mtime and ctime while retaining SHA-256 validation. Regression covers access-time changes and content-metadata changes.

## Validation and remaining scope

Frontend component tests cover navigation, bounds, citation clearing, overlay toggle and shader visibility. Backend tests cover source integrity. Real chapter evaluation remains 20/20 with valid citations and the accepted chapter-6 cross-reference warning.

Manual browser verification uses the existing local PDF. Port 5173 is denied by the host; use 15173. Detailed authored teaching currently covers only 5.1, 5.2 and 5.2.2. Full-book teaching, full-chapter authored lessons, layout resizing, automatic cross-course citation routing and persistent reading position remain future work.
