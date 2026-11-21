# Story Diagrams — Design Spec

## Goal

A graphical view of stories in the Domain Storytelling pictographic notation
([domainstorytelling.org](https://domainstorytelling.org/)), as produced by
[Egon.io](https://egon.io/) — actors and work objects as icons, activities as
numbered arrows labelled with their verbs — rendered locally into a **separate
self-contained HTML page** so the report itself does not grow.

```bash
pytest --given-diagrams                        # writes given-report/diagrams.html
pytest --given-diagrams=out/diagrams.html      # explicit path
pytest-given report report-data.json --diagrams  # re-render from saved JSON
```

One file per run holds *all* stories, with a story switcher and `#story-id`
deep links (mirroring the report's URL-hash convention). Everything is inlined
(CSS, fonts, Alpine.js, SVG); no network access, no new vendored dependency.
The page wears the report's shell — topbar, story sidebar, theme switch and
colour tokens — so it reads as part of the same report in either theme.

## Notation rules

The diagram follows the book's conventions (Hoffmann & Schwentner, *Domain
Storytelling*):

- **Actors appear exactly once per story**, deduplicated by
  `(term_id, instance display)` — `organizer('Carol')` in sentences 1–4 and 7
  is one node; `guest('Alice')` is one node even when she is a recipient in
  several sentences.
- **Work objects appear once per sentence.** Each sentence draws its own work
  object icons; within one multi-clause sentence a work object referenced by
  several clauses is drawn once. Repetition across sentences is intentional —
  it leaves room for the "different instances involved" reading.
- **Activities are labeled arrows.** The first edge of each clause carries the
  sentence's number in a badge; bare connective words (`'to'`, `'for'`) at
  later positions are unnumbered edges. Connectives are drawn exactly like
  activity terms — same arrow, same label — so every arrow in a sentence
  matches; only the number badge (present on each clause's first edge) and the
  glossary tooltip (terms only) tell them apart. A bare word sitting at a
  clause's *first* edge position still carries the number badge, so every
  sentence stays readable by number.
- **Icons (v1):** one glyph for actors (person), one for work objects
  (document). A term that is still kindless after kind inference gets the
  work-object glyph when it sits in a node position.

## Layout engine decision

A spike compared two engines on the hotel-booking example story (7 sentences,
4 actors, 8 work objects):

- **elkjs (vendored, ~1.5 MB, EPL-2.0):** flawless orthogonal routing, but the
  wrong genre — a layered algorithm produces a left-to-right dependency
  flowchart in which sentence numbers stack out of order and actors stop being
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
`Story` / `Sentence` / `Clause` model → a `report/diagram/` package:

- **`graph.py` — graph extraction.** `Story` → `DiagramGraph`: frozen
  dataclasses for nodes (id, label, sublabel, glyph kind, term id) and edges
  (source, target, label, sentence number or `None`). Encodes all
  notation rules above. Pure and independent of layout.
- **`layout.py` — deterministic force-based layout.** `DiagramGraph` → node
  positions, edge endpoints, label boxes, canvas size. Pure Python, no RNG,
  no I/O.
- **`renderer.py` — HTML emission.** Walks `report.stories`, runs extraction +
  layout per story, renders one Jinja2 template to the diagrams page (inline
  SVG per story, Alpine.js for interactivity) and returns its text.

The page is one more sink: `SinkConfig.diagrams_path`, set by
`--given-diagrams` in the plugin and `--diagrams` on `pytest-given report`, so
`emit_sinks` renders and writes it together with the other sinks, and a failed
render discards it with them. `sinks` loads the package lazily, since most runs
draw no diagram.

### Report ↔ diagram link

When a run generates both `--given-html` and `--given-diagrams`, the report's
Stories view shows a *Diagram* link per story: relative href from the report
file to the diagrams file plus the `#story-id` anchor. Without the diagrams
page the report shows no link. On Windows, two files on different drives get
none either, since no relative href joins them.

## Layout algorithm

Nodes are placed at **continuous (x, y) positions** by a two-phase force-based
method. Its overriding, **hard invariant is zero overlapping edges**: no drawn
edge may cross another edge or run over an unrelated node, and no two nodes may
sit closer than the minimum node distance. The invariant holds from the very
first placement onward and is *never* traded away for any other goal — every
other objective (short arrows, reading order) only shapes the layout within the
crossing-free region the invariant permits.

1. **Constructive seed in numbered order.** The layout is built by adding
   sentences in ascending number, so the reading order 1 → 2 → 3 is
   the *primary* structuring force rather than an afterthought a search tries to
   recover. Sentence 1's initiator is placed first; thereafter each sentence's
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
   arrow. A node that closes back onto *several* already-placed partners — a
   work object shared by a multi-clause sentence — is instead seated nearest
   their centroid, so it sits between them rather than out along one fan.
   Every node therefore *starts* at zero crossings.

   A purely forward, greedy walk cannot always reach a crossing-free seed even
   when one exists: a later multi-clause step (a work object fanning back to
   several already-seated actors) can be boxed in by the earlier greedy
   placements, so no single seat reaches all of its partners. The seed therefore
   runs as a **bounded, deterministic backtracking search** rather than a
   one-shot greedy pass. Each node placement yields its crossing-free candidate
   positions best-first (clockwise, then shortest arrow); taking the first
   candidate at every step reproduces the plain greedy layout, so ordinary
   stories are unchanged. When a node has *no* candidate that keeps every one of
   its (current and closing) edges crossing-free, the search backtracks and
   re-seats an earlier node, trying its next candidate — so an over-constrained
   fan is resolved by moving the anchors that boxed it in. The search is bounded
   (a capped number of placements tried) and deterministic. If the bound is
   exhausted, the search runs once more over a second order: each edge
   between two unplaced nodes is held back until a later edge ties them to the
   drawing. A second actor whose work object goes back to guests seated
   earlier then has that work object seated between the guests first, and
   itself beside it, instead of on a ring around the drawing from which no
   seat reaches both guests. The second order also seats each node as soon as
   all its neighbours are placed, so of several work objects two guests share,
   one that needs nothing else (the suite both check in to) takes the gap
   between them before one whose sender still has to sit beside it (the
   confirmation), which goes outside with its sender. Reading order stays the first try, since it lays
   out the stories it can solve more tidily. If that bound is exhausted too,
   the seed falls back to the best-effort greedy placement and the non-planar
   guard (below) surfaces any residual crossing.
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
   spring** also pulls consecutively numbered sentences together, and an
   **alignment force** eases each edge toward the nearest multiple of 45°, so
   arrows run horizontal, vertical or diagonal where they can. Each
   iteration proposes a per-node displacement but **accepts it
   only if the whole layout stays crossing-free, overlap-free, and free of any
   edge running over a foreign node**; an unsafe displacement is binary-searched
   back to the largest safe step. Because the layout starts crossing-free and no
   invariant-breaking move is ever accepted, zero crossings holds throughout —
   the forces only shorten and organic-ise the drawing. This is the "much better
   arrangement a human would find" that the previous grid local-search, trapped
   in local minima, could not reach. There is deliberately **no overall
   compactness term**: total size is owned by the zoom controls (below), so
   readability is never vetoed to keep the whole diagram small. A final
   **snap pass** then moves nodes whose x or y nearly agree onto a shared
   column or row, each move again accepted only if the invariant holds, so a
   chain-shaped story reads as clean rows.
3. **Non-planar guard.** A sentence whose step connects two *already-placed*
   nodes adds an edge with no placement freedom, so it cannot always be kept
   crossing-free by positioning alone — a genuinely non-planar situation for
   that construction order. Rather than silently draw a crossing (violating the
   invariant), the layout detects this and surfaces it as a
   `PytestGivenWarning`. The real example stories
   admit a crossing-free embedding, so this is a guard, not an expected path.
4. **Start reads from the top-left.** The whole diagram is then reflected (an
   axis-aligned isometry — it preserves every crossing and every distance, so
   arrow lengths and sequence spacing are untouched) to seat the story's start
   node, sentence 1's initiator, nearest the top-left corner. The reflection is
   chosen clockwise-aware: a single-axis flip reverses handedness, so the flip
   that best seats the start is picked so it cannot silently undo the fans'
   clockwise order.
5. **Label pass.** Each edge label (number badge + label) starts at the edge
   midpoint, offset perpendicular, and slides along its edge until it overlaps
   neither node icons (including node text) nor previously placed labels.
6. **Canvas sizing.** The canvas is framed to enclose every node with padding
   to spare and grows freely with the diagram; small diagrams re-centre within
   a minimum canvas. Since compactness is not forced, a large story may exceed
   the viewport — the zoom controls handle that.

## Interactivity (Alpine)

- **Story switcher:** slim sidebar listing story titles; selection drives the
  URL hash (`#story-id`) for deep links.
- **Replay:** prev/next buttons plus arrow keys. Step *n* shows sentences
  1..*n* at full opacity and fades later ones to ~15%. Initial state shows all
  sentences.
- **Hover, term:** a node or an activity term shows a tooltip with the term's
  glossary definition.
- **Hover, sentence:** hovering any edge or work object of a sentence
  highlights the whole sentence (all its clauses): its arrows thicken and glow.
- **Zoom:** the diagram viewport zooms in/out and pans, so a diagram that
  outgrows the viewport (compactness is not forced — see the layout algorithm)
  stays usable. Explicit **zoom-in / zoom-out / fit / reset** buttons. The
  mouse wheel, a trackpad pinch and ctrl/⌘+wheel zoom toward the cursor, and
  dragging pans. Zoom resets to "fit" when switching stories. The topbar,
  sidebar and replay controls stay pinned while only the diagram surface
  transforms.
- **Theme:** the report's Light / Dark / System switch, sharing its stored
  choice, so both pages open in the same theme.

## Edge cases

- A story with zero sentences renders its title and an empty-state note.
- A run with no stories renders a page that says so.
- Long labels wrap to two lines under the icon; the wrapped extent feeds the
  label-box sizes used by the collision pass.
- Multi-clause sentences repeat the number badge once per clause. Clauses
  sharing an identical first step draw that edge once.
- Actor → verb → same-actor clauses are representable (`clause()` validation
  does not reject a repeated node) and are drawn as a loop arc at the actor.

## Testing

Per the project's testing split:

- **Python unit tests** on graph extraction (dedupe rules, numbering,
  connective edges) and on layout **invariants**: determinism (two runs, equal
  output), minimum pairwise node distance, all nodes within canvas, every
  sentence's edges present, label boxes non-overlapping, **zero edge crossings
  maintained through both construction and force refinement**, no edge running
  over a foreign node, and the start node seated top-left. Plus the properties
  that make the force method work: construction adds sentences in numbered
  order (an earlier sentence's new node placed before a later one's), the force
  phase never increases the crossing count, and — for a hub whose numbered
  spokes can be freely placed — each actor's fan reads in **clockwise** number
  order. Positions are data — this is the data-shaped contract.
- **No markup-pinning tests.** The rendered page is Playwright-verified
  (console clean, switcher, replay, hovers, hash deep link, zoom in/out/fit
  buttons and wheel/trackpad zoom) before commit.
- `nox -s examples` and `nox -s self_report` write a diagrams page beside each
  report that has stories, and the documentation site publishes them with the
  example reports.

## Out of scope (v1)

Custom icons; coverage overlay (colouring sentences by scenario coverage);
drag-to-adjust with persisted positions; Egon `.egn` export; distinct
person/group/system actor icons. Each is a candidate follow-up; none
constrains the architecture above.
