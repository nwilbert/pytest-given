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
- **`layout.py` — deterministic layout.** `DiagramGraph` → node positions,
  edge endpoints, label boxes, canvas size. Pure Python, no RNG, no I/O.
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

Nodes are placed on an integer column/row grid whose spacing exceeds the
minimum node distance, so nodes can never overlap by construction. On that
grid a deterministic local search (no RNG) minimizes a single cost made of
**strictly-ranked objectives** — each weight so much larger than the next that
an objective can only ever break ties the one above it leaves, never trade one
away:

1. **No overlapping edges** *(dominant)*. Columns come from a longest-path
   layering of the directed activity flow (sources on the left, each step one
   column further right; back edges are dropped for layering only). Row order
   within a column is seeded by barycentre sweeps, then a local search of
   cell swaps and relocations drives the true straight-line **crossing** count
   — plus edges **grazing** an unrelated node — to their minimum.
2. **Numbered steps read in order** *(secondary)*. Once crossings are minimal,
   a second pass adds two tie-breakers that reorder rows only (never columns,
   so the crossing-free arrangement is preserved):
   - **Proximity.** Pull consecutively numbered activities close together, so
     the eye follows 1 → 2 → 3 without long jumps.
   - **Clockwise fans.** Every numbered step's source is its initiating
     **actor** (path position 0). Grouped by initiating actor, each actor's
     outgoing spokes (actor → target) — taken in ascending number order —
     should advance **clockwise** around that actor. Scored by the
     cross-product sign of consecutive-by-number spokes *sharing an actor*;
     only relative order matters (absolute orientation is set in step 4).
     Ranked just under proximity, so it only settles arrangements proximity
     leaves free — e.g. swapping two work objects in the same column so a
     hub's `1 → 2` reads forward rather than backward. Independent actors form
     independent fans (in the hotel story: Carol owns {1,2,3,4,7}, the Booking
     System owns {5,6}) that never interfere. Never adds a crossing.
3. **Short edges** *(lowest)*. A gentle length term keeps fans from
   flying apart. There is deliberately **no strong height/compactness term**:
   "fit to screen" is owned by the zoom controls (below), not the layout, so
   readability objectives are never vetoed to keep a diagram short.
4. **Start reads from the top-left.** Finally the whole diagram is reflected
   (an axis-aligned isometry — it preserves every crossing, every step
   distance, and every clockwise fan) to seat the story's start node, activity
   1's initiator, nearest the top-left corner.
5. **Label pass.** Each edge label (number badge + verb) starts at the edge
   midpoint, offset perpendicular, and slides along its edge until it overlaps
   neither node icons (including node text) nor previously placed labels.
6. **Canvas sizing.** The canvas is framed to enclose every node with padding
   to spare and grows freely with the diagram; small diagrams re-centre within
   a minimum canvas. Since compactness is no longer forced, a large story may
   exceed the viewport — the zoom controls handle that.

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
  outgrows the viewport (compactness is no longer forced — see step 3 above)
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
  activity's edges present, label boxes non-overlapping, zero edge crossings,
  the start node seated top-left, and — for a hub whose numbered spokes can be
  freely reordered — each actor's fan ending up in **clockwise** number order
  without costing a crossing. Positions are data — this is the data-shaped
  contract.
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
