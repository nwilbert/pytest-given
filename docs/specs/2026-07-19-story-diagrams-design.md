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
  `'for'`) are unnumbered edges with the connective as a muted label.
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

1. **Actor banding.** Actors initiating ≥ 1 activity (source of a numbered
   edge) are pinned on the left band; pure recipients on the right band; both
   ordered by first activity number and spread vertically. Initiating wins for
   actors that both initiate and receive.
2. **Work-object seeding.** In activity order: one placed neighbour → fan
   around that anchor at ideal edge length, evenly spaced angles biased toward
   the canvas centre; 2+ placed neighbours → centroid; chained work objects
   (`payment → for → booking`) continue outward from the chain.
3. **Relaxation.** Fixed iteration count; actors stay pinned; work objects
   move under springs (rest length = ideal edge length) plus pairwise
   repulsion below a minimum node distance; positions clamped to margins.
   Deterministic by construction.
4. **Label pass.** After positions settle: each edge label (number badge +
   verb) starts at the edge midpoint, offset perpendicular; a collision pass
   nudges overlapping label boxes along their edge until labels overlap
   neither node icons (including node text) nor other labels. This is a
   first-class layout step — it was the spike's visible weakness.
5. **Canvas sizing.** Width and height grow with band occupancy and node
   count, so large stories gain room instead of density.

## Interactivity (Alpine)

- **Story switcher:** slim sidebar listing story titles; selection drives the
  URL hash (`#story-id`) for deep links.
- **Replay:** prev/next buttons plus arrow keys. Step *n* shows activities
  1..*n* at full opacity and fades later ones to ~15%. Initial state shows all
  activities.
- **Hover, node:** tooltip with the term's kind and glossary definition.
- **Hover, activity:** hovering any edge or work object of an activity
  highlights the whole activity (all its paths).

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
  activity's edges present, label boxes non-overlapping. Positions are data —
  this is the data-shaped contract.
- **No markup-pinning tests.** The rendered page is Playwright-verified
  (console clean, switcher, replay, hovers, hash deep link) before commit.
- `nox -s examples` regenerates diagrams for the example projects alongside
  the existing artifacts; `nox -s self_report` is unaffected unless the
  self-report opts in.

## Out of scope (v1)

Custom icons; coverage overlay (colouring activities by scenario coverage);
drag-to-adjust with persisted positions; Egon `.egn` export; distinct
person/group/system actor icons. Each is a candidate follow-up; none
constrains the architecture above.
