# Story Diagrams — Design Spec

## Goal

A graphical view of stories in the Domain Storytelling pictographic notation
([domainstorytelling.org](https://domainstorytelling.org/)), as produced by
[Egon.io](https://egon.io/) — actors and work objects as icons, verbs as
numbered arrows — rendered locally into a **separate self-contained HTML
artifact** so the report itself does not grow.

```bash
pytest --given-diagrams                        # writes given-report/diagrams.html
pytest --given-diagrams=out/diagrams.html      # explicit path
pytest-given report report-data.json --diagrams  # re-render from saved JSON
```

One file per run holds *all* stories, with a story switcher and `#story-id`
deep links (mirroring the report's URL-hash convention). Everything is inlined
(CSS, Alpine.js, SVG); no network access, no new vendored dependency.

## Notation rules

The diagram follows the book's conventions (Hoffmann & Schwentner, *Domain
Storytelling*):

- **Actors appear exactly once per story**, deduplicated by
  `(term_id, instance display)` — `organizer('Carol')` in activities 1–4 and 7
  is one node; `guest('Alice')` is one node even when she is a recipient in
  several activities.
- **Work objects appear once per activity.** Each activity draws its own work
  object icons; within one multi-path activity a work object referenced by
  several paths is drawn once. Repetition across activities is intentional —
  it leaves room for the "different instances involved" reading.
- **Verbs are labeled arrows.** The first edge of each path carries the
  activity's sequence number in a badge; bare-string connectives (`'to'`,
  `'for'`) at later positions are unnumbered edges with the connective as a
  muted label. A bare word sitting at a path's *first* edge position still
  carries the number badge — every activity stays readable by number — with
  the muted styling alone signalling that it is not a glossary verb.
- **Icons (v1):** one glyph for actors (person), one for work objects
  (document). A term that is still kindless after kind inference gets the
  work-object glyph when it sits in a node position.

## Layout engine decision

A spike compared two engines on the hotel-booking example story (7 activities,
4 actors, 8 work objects):

- **elkjs (vendored, ~1.5 MB, EPL-2.0):** flawless orthogonal routing, but the
  wrong genre — a layered algorithm produces a left-to-right dependency
  flowchart in which activity numbers stack out of order and actors stop being
  anchors. The Domain Storytelling reading ("actors are stable anchors, read
  the arrows by number") is not expressible as ELK configuration.
- **Custom heuristic (pure Python, deterministic, ~120 lines in the spike):**
  produced a recognizable domain story; its weaknesses (label collisions near
  busy actors, some crossings) are quality problems fixable with the passes
  specified below.

**Decision: custom heuristic.** No new dependency; layout is data, unit-testable
in Python. Graph extraction is engine-independent, so elkjs remains a possible
fallback if the heuristic hits a wall on much larger stories.

## Architecture

Same shape as the existing renderers: JSON → `report_from_dict` → typed
`Story` / `Activity` / `ActivityPath` model → a new `report/diagram/` package:

- **`graph.py` — graph extraction.** `Story` → `DiagramGraph`: frozen
  dataclasses for nodes (id, label, sublabel, glyph kind, term id) and edges
  (source, target, verb label, activity number or `None`). Encodes all
  notation rules above. Pure and independent of layout.
- **`layout.py` — deterministic force-based layout.** `DiagramGraph` → node
  positions, edge endpoints, label boxes, canvas size. Pure Python, no RNG,
  no I/O.
- **`renderer.py` — HTML emission.** Walks `report.stories`, runs extraction +
  layout per story, renders one Jinja2 template to the diagrams HTML (inline
  SVG per story, Alpine.js for interactivity). Registered in `plugin.py`
  behind `--given-diagrams` and in `report/cli.py` behind `--diagrams`.

### Report ↔ diagram link

When a run generates both `--given-html` and `--given-diagrams`, the report's
Stories view shows a "diagram" link per story: relative href from the report
file to the diagrams file plus the `#story-id` anchor. Generating only one
artifact leaves the other unchanged.

## Layout algorithm

Nodes are placed at **continuous (x, y) positions** by a two-phase force-based
method. Its overriding, **hard invariant is zero overlapping edges**: no drawn
edge may cross another edge or run over an unrelated node, and no two nodes may
sit closer than the minimum node distance. The invariant holds from the very
first placement onward and is *never* traded away for any other goal — every
other objective (short arrows, reading order) only shapes the layout within the
crossing-free region the invariant permits.

1. **Constructive seed in numbered order.** The layout is built by adding
   activities in ascending sequence number, so the reading order 1 → 2 → 3 is
   the *primary* structuring force rather than an afterthought a search tries to
   recover. Activity 1's initiator is placed first; thereafter each activity's
   not-yet-placed nodes are seated to continue the flow from the previously
   placed frontier. A candidate position is accepted only if it is
   **crossing-free** against the edges drawn so far and at least the minimum node
   distance from every placed node — candidates are swept by angle around the
   node's anchor at a preferred edge-length radius, and the radius grows outward
   until a crossing-free one exists (for a node joining through tree edges there
   is always a free direction in open space, so this terminates). Among the
   crossing-free candidates, preference goes first to **continuing the clockwise
   sweep** of the anchor's fan — each actor's spokes advancing clockwise as the
   number rises, so the fan reads 1 → 2 → 3 in order — and then to the shortest
   arrow. Every node therefore *starts* at zero crossings.
2. **Planarity-preserving force refinement.** A deterministic spring embedder
   (no RNG; fixed iteration count and cooling schedule) then relaxes the seed:
   edges pull toward a rest length; every node pair interacts through a
   **preferred-distance potential** — repelling when closer than a comfortable
   spacing but gently *attracting* when farther apart, so nodes settle close
   together without overlapping rather than splaying to the maximum angle (a
   three-spoke fan stays tight, not spread to 120°). The hard minimum node
   distance remains an absolute floor beneath that preferred spacing, and the
   long-range attraction is bounded so it tightens fans without hard-forcing
   overall compactness (zoom still owns fit-to-screen). A gentle **sequence
   spring** also pulls consecutively numbered activities together. Each
   iteration proposes a per-node displacement but **accepts it
   only if the whole layout stays crossing-free, overlap-free, and free of any
   edge running over a foreign node**; an unsafe displacement is binary-searched
   back to the largest safe step. Because the layout starts crossing-free and no
   invariant-breaking move is ever accepted, zero crossings holds throughout —
   the forces only shorten and organic-ise the drawing. This is the "much better
   arrangement a human would find" that the previous grid local-search, trapped
   in local minima, could not reach. There is deliberately **no overall
   compactness term**: total size is owned by the zoom controls (below), so
   readability is never vetoed to keep the whole diagram small.
3. **Non-planar guard.** An activity whose step connects two *already-placed*
   nodes adds an edge with no placement freedom, so it cannot always be kept
   crossing-free by positioning alone — a genuinely non-planar situation for
   that construction order. Rather than silently draw a crossing (violating the
   invariant), the layout detects this and surfaces it. The real example stories
   admit a crossing-free embedding, so this is a guard, not an expected path.
4. **Start reads from the top-left.** The whole diagram is then reflected (an
   axis-aligned isometry — it preserves every crossing and every distance, so
   arrow lengths and sequence spacing are untouched) to seat the story's start
   node, activity 1's initiator, nearest the top-left corner. The reflection is
   chosen clockwise-aware: a single-axis flip reverses handedness, so the flip
   that best seats the start is picked so it cannot silently undo the fans'
   clockwise order.
5. **Label pass.** Each edge label (number badge + verb) starts at the edge
   midpoint, offset perpendicular, and slides along its edge until it overlaps
   neither node icons (including node text) nor previously placed labels.
6. **Canvas sizing.** The canvas is framed to enclose every node with padding
   to spare and grows freely with the diagram; small diagrams re-centre within
   a minimum canvas. Since compactness is not forced, a large story may exceed
   the viewport — the zoom controls handle that.

## Interactivity (Alpine)

- **Story switcher:** slim sidebar listing story titles; selection drives the
  URL hash (`#story-id`) for deep links.
- **Replay:** prev/next buttons plus arrow keys. Step *n* shows activities
  1..*n* at full opacity and fades later ones to ~15%. Initial state shows all
  activities.
- **Hover, node:** tooltip with the term's kind and glossary definition.
- **Hover, activity:** hovering any edge or work object of an activity
  highlights the whole activity (all its paths).
- **Zoom:** the diagram viewport zooms in/out and pans, so a diagram that
  outgrows the viewport (compactness is not forced — see the layout algorithm)
  stays usable. Explicit **zoom-in / zoom-out / fit / reset** buttons, and
  **trackpad and mouse-wheel** support: pinch-to-zoom and ctrl/⌘+wheel zoom
  toward the cursor, two-finger scroll pans. Zoom is per-diagram view state and
  resets to "fit" when switching stories; the app-shell nav stays pinned while
  only the diagram surface transforms.

## Edge cases

- A story with zero activities renders its title and an empty-state note.
- Long labels wrap to two lines under the icon; the wrapped extent feeds the
  label-box sizes used by the collision pass.
- Multi-path activities repeat the number badge once per path.
- Actor → verb → same-actor paths are representable (`path()` validation does
  not reject a repeated node) and are drawn as a loop arc at the actor.

## Testing

Per the project's testing split:

- **Python unit tests** on graph extraction (dedupe rules, numbering,
  connective edges) and on layout **invariants**: determinism (two runs, equal
  output), minimum pairwise node distance, all nodes within canvas, every
  activity's edges present, label boxes non-overlapping, **zero edge crossings
  maintained through both construction and force refinement**, no edge running
  over a foreign node, and the start node seated top-left. Plus the properties
  that make the force method work: construction adds activities in numbered
  order (an earlier activity's new node placed before a later one's), the force
  phase never increases the crossing count, and — for a hub whose numbered
  spokes can be freely placed — each actor's fan reads in **clockwise** number
  order. Positions are data — this is the data-shaped contract.
- **No markup-pinning tests.** The rendered page is Playwright-verified
  (console clean, switcher, replay, hovers, hash deep link, zoom in/out/fit
  buttons and wheel/trackpad zoom) before commit.
- `nox -s examples` regenerates diagrams for the example projects alongside
  the existing artifacts; `nox -s self_report` is unaffected unless the
  self-report opts in.

## Out of scope (v1)

Custom icons; coverage overlay (colouring activities by scenario coverage);
drag-to-adjust with persisted positions; Egon `.egn` export; distinct
person/group/system actor icons. Each is a candidate follow-up; none
constrains the architecture above.
