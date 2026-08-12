# RTR4 Chapter 5 visual enrichment design

## Goal

Replace accepted missing-figure dispositions with source-verifiable figure and
caption blocks for figures 5.6, 5.15, 5.16, 5.18, 5.22, 5.23, and 5.41. Keep
the chapter retrieval gates passing and change content completeness to
`complete` when no unresolved in-chapter visual reference remains.

## Approach

Use a reviewed enrichment sidecar layered over immutable MinerU output. Each
entry records the target block IDs, source PDF page, normalized crop box,
caption text, reviewer evidence, and expected crop SHA-256. Ingest renders the
crop from the registered PDF into the fingerprinted build, creates canonical
figure/caption blocks, and links captions and referring paragraphs.

This avoids rerunning or replacing MinerU, preserves raw provenance, and keeps
all generated images under the ignored I-drive data root.

## Data flow

1. Reviewer determines crop boxes from rendered PDF pages.
2. `visual-enrichments.json` stores reviewed metadata but no copyrighted image.
3. Ingest verifies registered PDF SHA, renders each crop, verifies image SHA,
   creates figure/caption blocks, and resolves matching validation issues.
4. Build fingerprint includes enrichment sidecar SHA and rendered asset hashes.
5. Evaluation requires all seven figures, caption relations, and zero unresolved
   in-chapter visual gaps.

Figure 6.27 remains an explicit cross-chapter reference and does not block
chapter 5 completeness. The malformed page 133 phrase receives a reviewed text
correction rather than a fabricated figure.

## Safety and storage

- Read only the registered source PDF.
- Write generated crops only below `I:\pdf_reaserch\data`.
- Never commit PDF pages, crops, MinerU output, models, caches, or databases.
- Reject sidecar paths, page ranges, crop boxes, IDs, and hashes that do not
  satisfy the fixed chapter policy.

## Testing

- Unit tests for sidecar validation, deterministic crop hashing, block creation,
  relation linking, and issue resolution.
- Regression tests proving incorrect crop/page/hash fails ingest.
- Evaluation tests fixing the seven required figure IDs in policy.
- Real chapter ingest/evaluation, backend/frontend suites, Vite build, GLSL
  validation, and forbidden-artifact Git audit before completion.
