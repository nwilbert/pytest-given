# Scenario deep-link slug — design

## Goal

The report's URL fragment addresses a scenario by its raw pytest node id:

```
#scenario=examples/hotel-booking/test_hotel_booking.py::test_complete_booking
```

This is the only humongous fragment in the hash. The other params are already
compact: `story`, `term`, `term-filter` are short slugs; `tag`, `status`, `q`
are short user text. Shorten the scenario fragment to a readable slug while
keeping it **stable across re-runs** (a shared link must keep resolving).

## Slug format

`<file>/<func>`, where both parts drop the `test_` prefix and the file drops
its `.py` extension:

```
examples/hotel-booking/test_hotel_booking.py::test_complete_booking
  →  hotel_booking/complete_booking
```

Derivation from the node id (a pure function of that single string):

1. Split on `::` → left is the file path (with `.py`), right is the function.
2. File part → basename after the last `/`, drop `.py`, drop a leading `test_`.
3. Function part → drop a leading `test_`. A parametrization tail is kept, so
   `test_pour[water]` → `pour[water]` (needed to keep cases distinct).
4. Join with `/`: `hotel_booking/complete_booking`.

The `/` separator stays literal and readable in the URL because the heading
anchor writes the hash as a raw string (`history.replaceState('#' + hash)`),
not through `URLSearchParams` (which would percent-encode `/`). On read,
`URLSearchParams.get('scenario')` parses the literal `/` back unchanged.

## Stability and uniqueness

Because the slug is a pure function of the node id, it never depends on what
else is in the report — re-runs with the same test produce the same slug, so
shared links survive. (Chosen over conditional/“minimal” disambiguation
precisely to avoid set-dependence.)

The only way two scenarios collide is **two test files with the same basename
in different directories** — already a pytest anti-pattern (the default import
mode rejects duplicate basenames without packaging). `build_scenario_slug_index`
**asserts global slug uniqueness and raises a clear error** listing the
offending node ids if it ever happens, rather than silently building
set-dependent disambiguation.

## Where it lives

Responsibilities stay where they already live: computation in
`aggregations.py`, wiring/serialization in `renderer.py`, markup hook in the
template, hash translation in `app.js`.

### `aggregations.py`

Add:

```python
def build_scenario_slug_index(report: ReportData) -> dict[NodeId, str]:
    ...
```

Maps each scenario's node id → its slug (per the derivation above). Raises on a
duplicate slug, naming the colliding node ids.

### `renderer.py`

- Call `build_scenario_slug_index(report)`.
- Pass the `NodeId → slug` map into `template.render(...)` as `scenario_slugs`.
- Emit the **reverse** map as a JS global for resolution on read:
  `window.__scenarioSlugs = {{ scenario_slugs_json }};` of shape
  `{slug: nodeId}` (JSON Markup, same pattern as `story_ids_json` /
  `term_ids_json`).

### `report.html.j2`

- Scenario heading anchor (currently line 199):
  `{{ anchor_link('scenario=' ~ scenario_slugs[scenario.id]) }}`.
- `data-scenario-id` and the nav `scrollToAndExpand(s.id)` are unchanged — all
  internal logic continues to key on the full node id.

### `app.js`

- In `_readHash`, resolve the scenario param through the reverse map before
  navigating:

  ```js
  const targetSlug = params.get('scenario');
  const targetScenario = targetSlug
    ? (window.__scenarioSlugs || {})[targetSlug]
    : null;
  ```

  then `goToScenario(targetScenario)` as today. No raw-value fallback — alpha,
  old/hand-typed full-node-id links need not resolve.

- `_writeHash` is untouched: it never emitted `scenario` (the param is a
  one-shot target written only by the heading anchor and cleared on read).

## Other fragments

No change. `story` / `term` / `term-filter` are already short slugs;
`tag` / `status` / `q` are short user text. Scenario was the only offender.

## Testing

Per AGENTS.md: no Python tests pinning frontend markup, no frontend TDD.

- **Python (TDD, data contract):** unit-test `build_scenario_slug_index` —
  basic case, `test_`-stripping on both parts, `.py` drop, a parametrized
  `[...]` case, and that a duplicate basename raises with a clear message. A
  renderer test asserts the `__scenarioSlugs` global / `scenario_slugs` wiring
  at the data-shaped level only.
- **Playwright (the real verification):** regenerate `examples/` via
  `uv run nox -s examples`; open a report; confirm console is clean; click a
  scenario heading anchor and verify the copied hash is
  `#scenario=hotel_booking/complete_booking`; load that hash on a fresh page
  and verify it switches to Scenarios, expands, and scrolls the right scenario,
  then clears the one-shot param.
- **Full gate:** `uv run nox` before commit. Regenerated `examples/` JSON +
  HTML committed.

## Out of scope

- Shortening any other hash param (all already compact).
- Backward-compatible resolution of old full-node-id `scenario=` links (alpha;
  dropped deliberately).
