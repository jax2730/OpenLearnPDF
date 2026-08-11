# RTR4 Chapter 5 evaluation

- Retrieval acceptance: PASS
- Content completeness: NEEDS VISUAL ENRICHMENT
- Correct-page hits: 20/20
- Required block-type hits: 20/20
- Citation validity: 100.00%
- Abstention probe: insufficient_evidence
- Validation warnings: 12
- Pages needing visual/reference enrichment: [111, 126, 127, 129, 130, 133, 149, 153]

## Parser run

- Probe directory: mineru-chapter-05-acceptance-ram-20260811T111511Z
- Elapsed: 139.074 seconds
- GPU peak delta: 5183 MB
- RAM peak: 6513.5 MB
- Cloud calls: 0
- Active build: `89b4f1c0cf2c334d734153cf6a1c6f2a1695397a984b2cf2939fcf136bd94e38`
- Questions SHA-256: `44ffe341de5d09b369f3881fedfa18550f654bdeec13b73318c78db153e27bfc`
- Rubric SHA-256: `1d65802f976f215293b97b9fe0320e0f11335f43e5def356abe9e86c01750e90`
- Probe SHA-256: `d8c6e71af4f96145cdf822f24b8f2aba1c4d589297b3850b031215510d4952c3`

## Gates

- PASS: page_hits
- PASS: block_type_hits
- PASS: citation_validity
- PASS: formula_fidelity
- PASS: figure_relations
- PASS: no_fabricated_ids
- PASS: abstention

## Parser warnings

- unknown_explicit_reference at page 111 / p111-paragraph-6: text references an unknown figure or equation; disposition=accepted_pending_visual_enrichment; evidence=Figure 5.6 is referenced in body text but MinerU did not emit its image block; formula 5.14 is present.
- unknown_explicit_reference at page 126 / p126-paragraph-3: text references an unknown figure or equation; disposition=accepted_pending_visual_enrichment; evidence=Figure 5.15 is referenced but its image block was not emitted by MinerU.
- unknown_explicit_reference at page 126 / p126-paragraph-4: text references an unknown figure or equation; disposition=accepted_pending_visual_enrichment; evidence=Figure 5.16 is referenced but its image block was not emitted by MinerU.
- unknown_explicit_reference at page 126 / p126-paragraph-5: text references an unknown figure or equation; disposition=accepted_pending_visual_enrichment; evidence=MinerU merged the Figure 5.16 caption into a paragraph without a figure block.
- unknown_explicit_reference at page 127 / p127-paragraph-2: text references an unknown figure or equation; disposition=accepted_pending_visual_enrichment; evidence=Figure 5.16 is missing; Figure 5.17 resolves correctly.
- unknown_explicit_reference at page 127 / p127-paragraph-4: text references an unknown figure or equation; disposition=accepted_pending_visual_enrichment; evidence=Figure 5.18 is referenced but its image block was not emitted by MinerU.
- unknown_explicit_reference at page 129 / p129-paragraph-1: text references an unknown figure or equation; disposition=accepted_pending_visual_enrichment; evidence=Figure 5.18 is missing; nearby Figure 5.21 resolves correctly.
- unknown_explicit_reference at page 130 / p130-paragraph-5: text references an unknown figure or equation; disposition=accepted_pending_visual_enrichment; evidence=Figure 5.22 is referenced but its image block was not emitted by MinerU.
- unknown_explicit_reference at page 130 / p130-paragraph-6: text references an unknown figure or equation; disposition=accepted_pending_visual_enrichment; evidence=Figure 5.23 is referenced but its image block was not emitted by MinerU.
- unknown_explicit_reference at page 133 / p133-paragraph-1: text references an unknown figure or equation; disposition=accepted_pending_visual_enrichment; evidence=MinerU text ordering produced a malformed figure phrase; retained for visual enrichment.
- unknown_explicit_reference at page 149 / p149-paragraph-2: text references an unknown figure or equation; disposition=accepted_pending_visual_enrichment; evidence=Figure 6.27 is an intentional cross-chapter reference outside the chapter 5 slice.
- unknown_explicit_reference at page 153 / p153-list-1: text references an unknown figure or equation; disposition=accepted_pending_visual_enrichment; evidence=Figure 5.41 is referenced but its image block was not emitted; Figure 5.42 resolves on page 154.

## Questions

- ch5-q01: page=hit, types=hit, pages=[104, 104, 105, 104, 105]
- ch5-q02: page=hit, types=hit, pages=[106, 105, 104, 105, 105]
- ch5-q03: page=hit, types=hit, pages=[104, 105, 104, 104, 127]
- ch5-q04: page=hit, types=hit, pages=[109, 124, 111, 120, 110]
- ch5-q05: page=hit, types=hit, pages=[110, 109, 120, 111, 124]
- ch5-q06: page=hit, types=hit, pages=[111, 124, 120, 114, 110]
- ch5-q07: page=hit, types=hit, pages=[112, 150, 139, 111, 124]
- ch5-q08: page=hit, types=hit, pages=[113, 124, 146, 120, 118]
- ch5-q09: page=hit, types=hit, pages=[129, 115, 143, 128, 139]
- ch5-q10: page=hit, types=hit, pages=[115, 115, 104, 104, 104]
- ch5-q11: page=hit, types=hit, pages=[115, 104, 115, 154, 147]
- ch5-q12: page=hit, types=hit, pages=[122, 125, 122, 124, 127]
- ch5-q13: page=hit, types=hit, pages=[126, 136, 127, 137, 136]
- ch5-q14: page=hit, types=hit, pages=[127, 126, 127, 137, 129]
- ch5-q15: page=hit, types=hit, pages=[129, 129, 129, 126, 135]
- ch5-q16: page=hit, types=hit, pages=[131, 135, 139, 138, 138]
- ch5-q17: page=hit, types=hit, pages=[134, 137, 135, 134, 139]
- ch5-q18: page=hit, types=hit, pages=[149, 140, 146, 149, 144]
- ch5-q19: page=hit, types=hit, pages=[149, 149, 146, 141, 149]
- ch5-q20: page=hit, types=hit, pages=[150, 150, 150, 151, 152]
