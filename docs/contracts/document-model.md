# Canonical document model

Pipeline stages exchange Pydantic models from `rtr4_learning.models`. These
normalized records are derived data. A parser's raw output is an immutable
stage artifact and must never be rewritten during normalization.

Canonical records are immutable after validation, including their structural
collections. To make a change, construct and validate a new record rather than
mutating an existing object in place.

## Coordinates

`BoundingBox` uses normalized, top-left coordinates `(x0, y0, x1, y1)`.
The page's top-left is `(0, 0)` and bottom-right is `(1, 1)`. Coordinates are
inclusive, so zero and one are valid. Rectangles must have positive area and
satisfy `x0 < x1` and `y0 < y1`. Parser-specific pixel or PDF coordinates
remain in the raw artifact; normalization is the only place that converts
them.

## Stable block IDs

Every block uses `p{page}-{kind}-{local-key}`, for example
`p105-equation-5.1`, `p105-figure-caption-1`, or `p106-paragraph-2`. IDs must
be deterministic for the same source and normalization version. Relations
store these IDs rather than array indexes, text snippets, or transient object
identities.

## Block types

Canonical types are `text`, `heading`, `formula`, `figure`,
`figure_caption`, `table`, `code`, `list`, `page_header`, and `page_footer`.
A formula retains LaTeX when available and/or an image crop in `asset_path`;
at least one representation is required.

## Relations

Relation names are lower snake case. Initial pipeline relation types include:

- `caption_of`: caption to its figure or table;
- `explained_by`: formula or figure to explanatory prose;
- `refers_to`: prose to an explicitly cited block;
- `next_block`: reading-order successor;
- `belongs_to_section`: content to its section heading;
- `uses_figure`: content to a supporting figure.

All relation targets must be stable block IDs. Unknown relation names may be
preserved when they follow the same naming rule, allowing parser adapters to
add evidence without changing the contract.

## Confidence and provenance

`BlockSource.confidence` is a parser- or model-reported score in the inclusive
range `[0, 1]`; higher means stronger confidence. It is evidence for quality
routing, not a calibrated probability unless the producing parser documents
that guarantee. Parser name, parser version, and optional model identify the
producer.

Real parser-derived blocks must set `raw_artifact` to the immutable raw output
path and retain `raw_block_id` when the producer provides a record identifier.
Normalization may create corrected text, LaTeX, assets, and relations, but it
must never edit the referenced raw payload. Fixtures and manually authored
blocks may explicitly omit both fields because no raw parser artifact exists.

## Container manifests

`PageDocument` groups canonical blocks by positive PDF page number.
`ChapterManifest` records an inclusive page range. `BookManifest` binds
chapters to the canonical source path and SHA-256 identity. `StageManifest`
records a stage version, deterministic fingerprint, inputs, and output
artifacts so cached derived data can be reproduced and invalidated safely.
