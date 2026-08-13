# Knowledge-Synced PDF Reader Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a 5.2.2 knowledge-point reader where selecting a concept synchronizes the original PDF and a focused, stepwise lesson panel.

**Architecture:** Extend the existing lesson contract with optional knowledge points and ordered learning cards, preserving current lessons. Add synchronization state at `App`, keep PDF rendering unchanged, and introduce a focused knowledge panel that falls back to the legacy lesson view when no knowledge points exist.

**Tech Stack:** Pydantic/FastAPI, React 19, TypeScript, Vitest, PDF.js, KaTeX, browser localStorage.

---

### Task 1: Define knowledge-point contracts

**Files:**
- Modify: `backend/src/rtr4_learning/teaching.py`
- Modify: `backend/tests/test_teaching.py`
- Modify: `frontend/src/types.ts`

1. Write backend tests for required point/card citations, unique point IDs, unique card IDs within a point, valid primary source membership, and unknown source rejection.
2. Run focused pytest and confirm RED because models are absent.
3. Add `KnowledgePoint` and `LearningCard` Pydantic models plus optional `Lesson.knowledge_points`.
4. Include point/card citations in `validate_lesson_bundle`.
5. Add matching optional TypeScript interfaces.
6. Run focused backend tests and commit.

### Task 2: Author the 5.2.2 knowledge map

**Files:**
- Modify: `content/rtr4-cn/chapter-05/section-5.2.2.json`
- Modify: `backend/tests/test_teaching.py`

1. Write a failing test requiring five ordered point IDs, source coverage for formulas 5.9/5.11/5.12/5.14/5.18, and all seven card kinds across the lesson.
2. Confirm RED because `knowledge_points` is empty.
3. Add cited points and stepwise cards with compact derivations, a numeric attenuation example, shader-focused code guidance, pitfalls, and exercises.
4. Run focused tests and commit.

### Task 3: Build the focused knowledge panel

**Files:**
- Create: `frontend/src/components/KnowledgeLessonPanel.tsx`
- Create: `frontend/src/components/KnowledgeLessonPanel.test.tsx`
- Modify: `frontend/src/components/LessonPanel.tsx`

1. Write failing tests for point navigation, one active card, previous/next card controls, citation navigation, completion marking, and restored local progress.
2. Confirm RED because the component is absent.
3. Implement the minimum focused panel and storage fallback.
4. Make `LessonPanel` delegate to it when `knowledge_points` exist; retain legacy rendering otherwise.
5. Run component tests and commit.

### Task 4: Synchronize PDF and knowledge points

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/App.test.tsx`
- Modify: `frontend/src/components/LessonPanel.tsx`
- Modify: `frontend/src/components/KnowledgeLessonPanel.tsx`

1. Write failing app tests: selecting a point navigates page/block; selecting a cited PDF block activates the matching point; unmatched blocks preserve the current point.
2. Confirm RED.
3. Lift active point and lesson citation mapping into `App` through small callbacks; avoid global state.
4. Run focused tests and commit.

### Task 5: Add the study-workspace layout

**Files:**
- Create: `frontend/src/app.css`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/main.tsx`
- Modify: `frontend/src/App.test.tsx`

1. Write failing accessibility/structure assertions for two labelled, independently scrollable panes and a compact course selector.
2. Confirm RED.
3. Add a responsive desktop 55/45 split, sticky pane headers, independent scrolling, visible active navigation, readable card typography, and single-column fallback below 900px.
4. Run focused tests and commit.

### Task 6: Verify and publish

1. Run all backend tests and Ruff.
2. Run all frontend tests and production build.
3. Verify the live 5.2.2 API contract and inspect the local Web page at desktop width.
4. Compile all GLSL examples.
5. Audit forbidden tracked artifacts and ensure `.run/` remains untracked/ignored.
6. Push `feature/rtr4-learning` without force and report cumulative commits.
