# Report linking & deep links — design

Date: 2026-06-20
Status: accepted
Branch target: `domain-storytelling`

Implementation notes (deviations from this spec, both intentional):

- The top-level tab anchors in §5 were dropped during implementation (commit
  `b0fff3d`); the tabs already write `view=` to the hash, so the section stays
  shareable without a per-tab copy icon.
- The `scenario=` deep-link target (§2) now uses a short readable slug rather
  than the raw node id, refined in
  [2026-06-20-scenario-deep-link-slug-design.md](2026-06-20-scenario-deep-link-slug-design.md).

## Goal

Improve navigation in the self-contained HTML report along three axes:

1. **Cross-linking** between scenarios, glossary terms, and stories — so the
   relationships already present in the data are clickable.
2. **Deep links** via the URL fragment — every major element is addressable, so
   a person can share a link that points at a specific scenario, glossary term,
   story, or section.
3. **Anchor affordances on headings** — the familiar website pattern where a
   link icon appears behind a heading on hover, and clicking it copies a
   shareable URL.

Plus two interaction additions surfaced during design:

- A **scenario term-filter** reachable from a glossary entry.
- A **multi-select activity highlight** in the Stories view.

## Background — current state

- The URL hash is **already** used, but as a *query-string-style state
  serializer*: `#view=stories&story=X&tag=Y&status=passed,failed&q=search`.
  `app.js` reads it in `_readHash`, writes it in `_writeHash`, and uses
  `history.replaceState` (no browser history entries).
- Existing cross-links: stories → scenarios (switch tab + expand + scroll),
  stories "Covers:" strip → activity (scroll within stories), glossary
  "Stories:" → story (switch tab + select).
- Term pills are emitted everywhere (step text, scenario names, activity prose)
  by `_term_pill` in `renderer.py`, carry `data-term-id` and a `title`
  tooltip, but have **no click behavior**.
- Scenarios anchor on positional index (`scenario-0`), not a stable id.

## Chosen approach — extend the existing param-hash

Rejected alternatives:

- **Native `id=` fragments + `:target` CSS.** Targets live inside hidden tabs
  (`x-show`) and collapsed bodies (`:class="expanded"`); the browser would jump
  to zero-height/hidden nodes, and it collides with the existing param-hash.
- **Hybrid (param-hash for state + a second convention for anchors).** Two
  conventions in one hash → ordering bugs, two code paths.

Selected: **one consistent param-hash mechanism** for both filter state and
deep-link targets. Scrolling is JS-driven (it must be — targets are inside
hidden/collapsed regions the browser cannot reach natively), and a single
shareable URL carries both filter state and target.

## Section 1 — Data layer

Responsibilities stay where they already live: computation in
`aggregations.py`, wiring/serialization in `renderer.py`, markup hooks in the
template.

### `aggregations.py` (Python)

Add:

```python
def build_term_scenario_index(report: ReportData) -> dict[TermId, list[NodeId]]:
    ...
```

Walks each scenario's narration and its steps (reusing the existing
`walk_steps` helper), collecting `NarrationTermRef.term_id`, and maps
term → the scenarios that reference it. Dedup per scenario; preserve render
order. Empty/no-glossary report → `{}`.

### `renderer.py` (Python)

- Call `build_term_scenario_index(report)` and pass the result into
  `template.render(...)`.
- Serialize it to JSON Markup (same pattern as `story_ids_json` /
  `term_ids_json`) for a `window.__termScenarios` global of shape
  `{termId: [nodeId, …]}`.
- No new HTML-string assembly in `renderer.py` — it remains the orchestrator.

### `report.html.j2` (template)

- Add `data-scenario-id="{{ scenario.id }}"` to each scenario element. The
  pytest node id is the **stable, addressable** key (survives re-runs);
  positional index is retained only for internal expand-state.
- Emit `window.__termScenarios = {{ term_scenarios_json }};` in the existing
  `<script>` block alongside `__storyIds` / `__termIds`.

### `app.js`

- Read `window.__termScenarios`.
- Resolve a `scenario=<node-id>` hash to the current positional index for
  scroll/expand (internal expand-state continues to key on index).

## Section 2 — Hash schema & navigation (`app.js`)

All targets live in the single param-hash, written via `_writeHash`, read via
`_readHash` / `hashchange`.

| Param         | Meaning                                            | Example                          |
|---------------|----------------------------------------------------|----------------------------------|
| `view`        | active tab (existing)                               | `view=glossary`                  |
| `tag`         | scenario tag filter (existing)                     | `tag=checkout`                   |
| `status`      | status filter (existing)                            | `status=passed,failed`           |
| `q`           | search query (existing)                             | `q=refund`                       |
| `story`       | selected story (existing)                           | `story=booking`                  |
| `term-filter` | **new** — filter scenarios to those using a term    | `term-filter=guest`              |
| `scenario`    | **new** — target scenario (node id)                 | `scenario=test_x.py::test_y`     |
| `term`        | **new** — target glossary term entry                | `term=room`                      |

(No `activity` deep-link target — dropped during design. Activity highlighting
in §4 is client-only.)

Two param categories with deliberately different lifetimes:

- **Persistent state** (`view`, `tag`, `status`, `q`, `term-filter`, `story`):
  written continuously as the user interacts, exactly as today.
- **One-shot targets** (`scenario`, `term`): consumed on read — switch view,
  expand, scroll, then **clear that param** from the hash (`replaceState`) so
  the URL settles and later manual scrolling doesn't re-trigger. (Anchor
  "copy link" in §5 still produces a full URL containing the target.)

Navigation actions in the Alpine component:

- `goToTerm(id)` → `mainView='glossary'`, expand entry, `$nextTick` scroll.
- `goToScenario(nodeId)` → resolve index, `mainView='scenarios'`, expand,
  scroll. (Generalizes today's `scrollToAndExpand`, which already takes a node
  id.)
- `filterScenariosByTerm(id)` → `mainView='scenarios'`, set `termFilter=id`.
- (No `goToStoryActivity` — dropped with the `activity` target.)

`_matchesFilters` gains a term-filter clause:

```js
if (this.termFilter &&
    !(window.__termScenarios[this.termFilter] || []).includes(s.id)) return false;
```

The active term filter surfaces in `filterSummary` as a removable chip
(`Term: Guest ✕`), matching how `tag` already appears.

## Section 3 — Cross-links: clickable term pills + term filter

### Term pills become clickable

Pills are emitted by `_term_pill` in `renderer.py` (used by both
`_render_term_ref` and the `activity_part` filter). They already carry
`data-term-id`.

- Add **one delegated `click` listener** in `app.js` `init()`: clicks on any
  `[data-term-id]` call `goToTerm(el.dataset.termId)`. (Delegation avoids
  emitting inline Alpine handlers on every pill across three render contexts.)
- Pills get a `term-ref--link` class for cursor/hover affordance.
- Pills inside their **own** glossary entry are not made clickable (no
  self-jump).

### Glossary entry → "Show N scenarios using this term"

In each glossary entry's expanded `refs-content`, add an action — only when
`term_scenario_index[term.id]` is non-empty — calling
`filterScenariosByTerm(term.id)`. The label includes the count:

- "Show 7 scenarios using this term" / "Show 1 scenario using this term".

This replaces the rejected "list every scenario" idea (too many scenarios to
enumerate). It switches to the Scenarios tab with the term filter applied and
shown as a removable chip in the header.

## Section 4 — Stories-view activity highlighting (client-only, multi-select)

In the Stories view, each scenario card's "Covers:" strip lists activity-id
chips (`use-chip`), and the activity timeline has numbered rows
(`activity-num`).

- **State:** `highlightedActivities: {}` (a set keyed by activity id) in the
  Alpine component. Cleared on `selectedStory` change to avoid stale highlights
  (activity ids are only meaningful within the shown story).
- **Toggle sources:** clicking an activity chip in a Covers strip **or** an
  activity number/row in the timeline calls `toggleActivityHighlight(id)`
  (adds/removes from the set). No auto-scroll.
- **Wiring:** a delegated `[data-activity-id]` click listener in `init()`
  (mirrors the term-pill delegation), covering both the timeline numbers and
  the Covers-strip chips.
- **Highlight rendering:** when an id is in the set, **both** (a) the timeline
  `activity-row` for that id and (b) every chip/number with that id (across all
  scenario cards + the timeline) get a highlight class via `:class` bindings on
  `highlightedActivities[id]`.
- **Reset:** a "Clear highlights ✕" control appears in the Stories view when
  the set is non-empty, calling `clearActivityHighlights()`.

Client-only — **not** serialized to the hash (transient exploration state,
consistent with step/attachment expansion).

## Section 5 — Anchor links on headings

The standard website pattern. A small link icon (`#` / 🔗) sits at the end of a
heading, revealed on hover; clicking it writes the target hash **and** copies
the full shareable URL to the clipboard.

Anchors appear on:

- **Scenario headers** → `#scenario=<node-id>` (plus current filter state).
- **Glossary term entry heads** → `#view=glossary&term=<id>`.
- **Glossary kind headers** (Actors / Work Objects / Verbs) and the three
  **top-level tabs** → `#view=<tab>` (section-level).
- **Story title header** → `#view=stories&story=<id>`.

One reusable mechanism in `app.js`: `copyAnchor(hashString, evt)` — sets the
hash via `replaceState`, calls `navigator.clipboard.writeText(location.href)`,
and briefly flips the icon to a "copied ✓" state. Handlers use `@click.stop`
so clicking an anchor does not toggle the scenario/term it sits in.

Template: a small Jinja macro `anchor_link(hash)` emitting the icon button,
dropped into each heading. CSS: hidden by default, opacity up on heading-row
`:hover`, reusing existing icon styling conventions.

## Section 6 — Testing

Per AGENTS.md: **no Python tests pinning frontend markup, no frontend TDD.**

- **Python (TDD, data contract):** unit-test `build_term_scenario_index`
  (term → expected scenario node ids; dedup; terms with no refs; no-glossary
  report). Renderer test asserts the new JS global / `data-scenario-id`
  presence at the data-shaped level only.
- **Playwright (the real verification):** regenerate `examples/` via
  `uv run nox -s examples`, open `examples/report.html`, confirm
  `browser_console_messages` is clean after init, then drive each surface:
  - term pill → glossary jump;
  - glossary "Show N scenarios" → filtered list + removable header chip;
  - anchor icons copy + scroll;
  - deep-link hashes on a **fresh load** (`scenario=`, `term=`, `term-filter=`)
    then verify the one-shot target params clear;
  - activity highlight toggle from both a Covers chip and a timeline number,
    plus "Clear highlights".
- **Full gate:** `uv run nox` before commit. Regenerated `examples/` JSON +
  HTML committed.

## Out of scope

- Browser history entries / back-button navigation between targets (stays on
  `replaceState`).
- Mobile/responsive layout (desktop-only per AGENTS.md).
- Listing individual scenarios inside a glossary entry (replaced by the
  term-filter action).
- Deep-linking individual activities.
