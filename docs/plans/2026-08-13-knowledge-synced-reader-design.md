# Knowledge-Synced PDF Reader Design

Date: 2026-08-13

## Goal

Turn the existing side-by-side PDF and lesson page into a knowledge-point study
workspace. The PDF remains the authoritative source on the left. The right side
reduces reading effort by explaining one selected concept at a time and keeping
the source page and highlighted block synchronized.

## First Vertical Slice

Only section 5.2.2 is migrated initially. Its knowledge points are:

1. Light vector and distance
2. Inverse-square attenuation
3. Near-distance stabilization
4. Finite light range
5. Spotlight cone

The existing 5.1 and 5.2 lessons keep their current rendering. This limits the
change surface while establishing a reusable contract.

## Data Contract

`Lesson` gains an optional ordered `knowledge_points` collection. Each point
has a stable ID, title, short summary, primary source block, related citations,
and ordered learning cards. Cards use a small fixed set of kinds:

- intuition
- derivation
- visual
- numeric_example
- code
- pitfall
- exercise

Every point and every card retains source citations. The primary source drives
the initial PDF location. The existing seven lesson sections remain required so
older clients and lessons continue to work.

## Interaction

The workspace uses a fixed two-column desktop layout: PDF on the left and study
content on the right. Both columns scroll independently.

Selecting a knowledge point:

1. updates the active point;
2. navigates the PDF to the primary source page;
3. highlights the primary source block;
4. shows only that point's learning cards;
5. stores the active point ID locally.

Selecting a PDF overlay searches the current lesson for a knowledge point that
cites that block. When found, it selects the point. When no point cites the
block, the PDF highlight still changes and the lesson remains unchanged.

Each card citation remains clickable and can move the PDF to a related formula,
figure, or paragraph without changing the active point.

## Presentation

The right column contains:

- compact horizontal/vertical knowledge-point navigation;
- progress indicator;
- point title and one-sentence learning objective;
- one expanded card at a time, with previous/next card controls;
- rendered formulas and concise source buttons;
- focused shader excerpt only for the code card;
- full shader and ShaderToy link in a collapsed reference area.

Visual cards use the original PDF page and highlighted figure rather than a
duplicated image. This keeps provenance clear and avoids committing generated
assets.

## Persistence and Error Handling

The browser stores only the active knowledge-point ID and completed point IDs,
namespaced by lesson ID. Invalid or removed IDs fall back to the first point.
Storage failures do not block reading. Missing cited blocks show a visible
source-unavailable message while other cards remain usable.

## Testing

- Backend contract tests reject missing point/card citations and unknown block
  IDs.
- Component tests verify point selection, PDF navigation, reverse synchronization,
  card navigation, and local progress restoration.
- Existing lesson rendering stays covered for lessons without knowledge points.
- Full backend, frontend, production build, GLSL, and forbidden-file audits remain
  release gates.

