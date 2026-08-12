# Chapter 5 Visual Enrichment Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add seven source-verified missing figures to RTR4 chapter 5 and make chapter content completeness `complete`.

**Architecture:** A committed metadata-only sidecar defines reviewed PDF crops and canonical block identities. Ingest uses existing `pypdfium2` and Pillow support to render verified crops into the ignored fingerprinted build, creates figure/caption blocks and relations, then removes only resolved visual validation issues. Evaluation fixes the seven figures in policy.

**Tech Stack:** Python 3.12, Pydantic, pypdfium2, Pillow, pytest, existing immutable ingest/search pipeline.

---

### Task 1: Locate and review source crops

**Files:**
- Create: `content/rtr4-cn/chapter-05/visual-enrichments.json`
- Create: `scripts/review-visual-enrichments.py`
- Test: `backend/tests/test_visual_enrichment.py`

**Steps:**

1. Write tests requiring schema version 1, exactly figures 5.6/5.15/5.16/5.18/5.22/5.23/5.41, pages 111/126/127/130/153, normalized crop boxes, captions, evidence, and 64-hex crop hashes.
2. Run `backend\.venv\Scripts\python.exe -m pytest -q tests/test_visual_enrichment.py`; expect failure because loader does not exist.
3. Implement sidecar models/loader in `backend/src/rtr4_learning/visual_enrichment.py`.
4. Reuse page renders or render the five source pages at scale 3; inspect them and record reviewed crop boxes/captions/hashes.
5. Add review script that renders crops under `I:\pdf_reaserch\data\review`, prints dimensions/SHA, and never writes inside Git.
6. Run tests; expect pass.
7. Commit `feat: define chapter 5 visual enrichments`.

### Task 2: Render deterministic enrichment assets

**Files:**
- Modify: `backend/src/rtr4_learning/visual_enrichment.py`
- Test: `backend/tests/test_visual_enrichment.py`

**Steps:**

1. Add failing tests for deterministic PNG bytes, exact SHA verification, page mismatch, invalid crop, source replacement, and output containment.
2. Run targeted tests; expect failures.
3. Implement crop rendering with `pypdfium2`, Pillow PNG serialization, registered source SHA verification before/after render, and output path `assets/enriched/<figure-id>.png` below temporary build root.
4. Run targeted tests and Ruff; expect pass.
5. Commit `feat: render verified figure crops`.

### Task 3: Apply blocks and resolve references

**Files:**
- Modify: `backend/src/rtr4_learning/visual_enrichment.py`
- Modify: `backend/src/rtr4_learning/models.py`
- Test: `backend/tests/test_visual_enrichment.py`

**Steps:**

1. Add failing tests for new figure/caption blocks, `caption_of`, `references`, `next_block`, provenance sidecar/SHA/evidence, duplicate rejection, and deterministic ordering.
2. Add reviewed text correction for page 133 malformed phrase and an explicit cross-chapter disposition for Figure 6.27.
3. Implement immutable page transformations and relation linking.
4. Verify all seven figures resolve their in-chapter references; only cross-chapter reference may remain non-blocking.
5. Run tests and Ruff; expect pass.
6. Commit `feat: apply chapter visual enrichment blocks`.

### Task 4: Integrate enrichment into immutable ingest

**Files:**
- Modify: `backend/src/rtr4_learning/cli.py`
- Modify: `backend/src/rtr4_learning/ingest.py`
- Modify: `backend/tests/test_ingest.py`
- Modify: `docs/contracts/document-model.md`

**Steps:**

1. Add failing ingest tests for `--visual-enrichments`, sidecar/crop hashes in build fingerprint, assets inside build, atomic failure behavior, and resolved validation artifact.
2. Run targeted tests; expect failures.
3. Add CLI option and apply enrichment before relation linking/validation.
4. Publish rendered assets with normalized pages/validation/index in one immutable bundle.
5. Ensure repeated ingest reuses identical build; changed sidecar or crop creates new build.
6. Run ingest/concurrency/security tests and Ruff; expect pass.
7. Commit `feat: publish visual enrichments in chapter build`.

### Task 5: Strengthen completeness evaluation

**Files:**
- Modify: `backend/src/rtr4_learning/chapter_evaluation.py`
- Modify: `backend/tests/test_chapter_evaluation.py`
- Modify: `evaluation/chapter-05/rubric.json`
- Modify: `evaluation/chapter-05/report.md`

**Steps:**

1. Add failing tests fixing all seven new figure/caption IDs and rejecting missing/mismatched assets.
2. Add a completeness gate that allows only the intentional Figure 6.27 cross-chapter disposition; in-chapter visual gaps fail.
3. Update canonical rubric policy SHA after reviewed semantic change.
4. Run evaluation tests; expect pass.
5. Commit `test: require complete chapter 5 visuals`.

### Task 6: Real chapter rebuild and acceptance

**Files:**
- Modify: `docs/runbooks/local-development.md`
- Generated outside Git: `I:\pdf_reaserch\data\books\rtr4-cn\builds\...`

**Steps:**

1. Ingest the existing successful 51-page MinerU content list with both correction and visual-enrichment sidecars.
2. Verify active build contains seven new assets and figure/caption blocks with source provenance.
3. Run chapter evaluation; require retrieval 20/20 page/type, citations 100%, all formula/figure gates pass, and content completeness `complete`.
4. Run backend full tests with real E2E, Ruff, frontend tests/build, GLSL compiler, `git diff --check`, and forbidden-artifact audit.
5. Request specification and quality reviews; fix all Important findings.
6. Commit `feat: complete RTR4 chapter 5 visual coverage`.
