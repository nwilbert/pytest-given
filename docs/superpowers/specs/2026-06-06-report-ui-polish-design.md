# Report UI Polish — Design Spec

## Goal

Five small, independent UI changes to the HTML report, bundled into one spec because they all touch the same renderer files (`templates/report.html.j2`, `app.js`, `styles.css`) and share a regression surface:

1. Replace emoji icons (🔍 📎) with inline SVG, and add a clear-search button.
2. Smoothly animate scenario expand/collapse — both directions.
3. Change the URL-hash format for status filters from `passed=0/failed=0/skipped=0` to a single `status=passed,skipped` list.
4. Crosshair hover for parametrization tables that also lights up the matching placeholder in the step narration above.
5. Tag placeholders and parameter-table cells with `data-param` — the small structural change that makes the crosshair possible.

Traceback verbosity (TODO line 19) is **out of scope** — it touches the model and merits its own spec.

## Background

The current report has a few rough edges that the author has flagged as "corny" or unfinished:

- The sidebar search input uses `🔍` as a placeholder prefix and the attachment badge uses `📎`. On Windows these render as colorful cartoon glyphs that clash with the otherwise sober monochrome design.
- Scenarios expand on click with a short fade + translateY, but collapse instantly — the layout snaps because `x-show` toggles `display: none` and there's no height animation.
- The URL-hash `#failed=0` reads as "failed equals zero," not "hide failed." Share-links should be self-documenting.
- The parametrization table has no hover feedback. With multiple parameter columns and several rows it's easy to lose your place, and the report already color-codes parameter columns and narration placeholders by name — that color link is invisible at rest and could be made interactive.

Each change is small. Bundling them keeps the test-regeneration cost (regenerating `examples/report.html` and the snapshot tests) to one round.

## Approach

All five changes live in the renderer subpackage. No schema changes, no plugin changes, no collector changes. The crosshair feature requires adding a `data-param` attribute in three render sites; everything else is template/CSS/JS.

The grid-rows trick for expand/collapse applies to the scenario body, step children, and attachment-content wrappers — the three spots that previously used `x-show` (which snaps `display: none` on collapse). All three follow the same shape: an outer `*-expand` (or `scenario-body`) wrapper with `display: grid; grid-template-rows: 0fr → 1fr`, and an inner content div with `overflow: hidden; min-height: 0`. The `.transition-enter*` classes become dead after this change and are removed. Skip-reason has no toggle and is unaffected.

The URL-hash format is pre-release; no compatibility shim for the old `passed=0`/`failed=0`/`skipped=0` keys.

## Change 1 — Inline SVG icons

Three Lucide-path SVGs go inline in `report.html.j2`, sized 14×14, using `currentColor`:

- **Search** — magnifying glass
- **Search-clear** — X glyph; rendered only when `search !== ''`; clicking it clears the search
- **Paperclip** — replaces the `📎` prefix in `.attachment-badge`

The search input wraps in a `<label class="search-box">` with `position: relative`. The icon and clear-button are positioned absolutely inside it; the `<input>` gets `padding-left` and `padding-right` to make room. Placeholder text drops the emoji prefix.

```html
<label class="search-box">
  <svg class="search-box-icon" …><!-- magnifying glass --></svg>
  <input type="text" placeholder="Search scenarios…" x-model="search">
  <button type="button" class="search-box-clear" @click="search = ''" x-show="search">
    <svg …><!-- X --></svg>
  </button>
</label>
```

The attachment badge inlines the paperclip the same way:

```html
<span class="attachment-badge" @click="…">
  <svg class="attachment-badge-icon" …><!-- paperclip --></svg>
  {{ att.label }}
</span>
```

CSS: search icon and clear-button inherit `--text-muted`; clear-button brightens to `--color-accent` on hover; paperclip inherits the badge color.

## Change 2 — Scenario expand/collapse animation

Replace the current `x-show` + `x-transition` on the scenario body with a CSS-only grid-rows trick.

Today:

```html
<div x-show="expandedScenarios[i]"
     x-transition:enter="transition-enter" …>
  …scenario body…
</div>
```

After:

```html
<div class="scenario-body" :class="{ expanded: expandedScenarios[i] }">
  <div class="scenario-body-inner">
    …scenario body…
  </div>
</div>
```

```css
.scenario-body {
  display: grid;
  grid-template-rows: 0fr;
  transition: grid-template-rows 200ms ease-out;
}
.scenario-body.expanded { grid-template-rows: 1fr; }
.scenario-body-inner { overflow: hidden; min-height: 0; }
```

`display: grid` is always present, so the layout flows correctly when collapsed (height contributes 0). The transition runs both directions identically. Chevron rotation already animates (0.15s ease) and stays untouched.

Step children, attachment expand, and skip-reason keep their existing `x-show` + `x-transition` — they animate within an already-open scenario where the snap is visually invisible.

## Change 3 — URL-hash format

`_writeHash` and `_readHash` in `app.js` change to a single `status` key.

Write logic:

- Compute the set of statuses currently shown — the three `showPassed` / `showFailed` / `showSkipped` booleans mapped back to status names.
- Compute the set of statuses that exist in the report.
- If the shown set equals the existing-in-report set, omit `status` entirely (default view, no hash entry needed).
- Otherwise emit `status=<comma-list>` in stable order: `passed,failed,skipped`.

Read logic:

- If `status=` is present, parse the comma-list and set `showPassed` / `showFailed` / `showSkipped` accordingly. Unknown status names are ignored.
- If `status=` is absent, default all three to `true` (current behavior).

The old `passed=0` / `failed=0` / `skipped=0` keys are removed — neither written nor read. Pre-release, no migration shim.

`tag=` and `q=` are unchanged.

## Change 4 — Crosshair hover for parametrization tables

Hover on a row produces two layered effects:

- **Row** — light blue tint (`var(--color-accent-bg)`), 120ms ease. Failed rows keep their pink background. (An earlier draft of this spec called for an inset left stripe; it was removed during visual review — too heavy alongside the column crosshair.)
- **Column placeholder crosshair** — when a `<td>` is hovered, every element in the same scenario that shares the same `data-param` value lights up: the column header, every placeholder span in the steps above the table, and the `<td>` itself.

Implementation:

- Pure CSS handles the row hover (`:hover` selector). No JS needed for that layer.
- The crosshair uses a tiny Alpine layer. Each `<td>` gets `@mouseenter` / `@mouseleave` handlers that toggle a `param-highlight` class on every element with the matching `data-param` value, scoped to the closest `.scenario` ancestor of the hovered cell. On leave, the same scoped query clears the class.
- Scoping to `.scenario` ensures hovering a row in one parametrized scenario does not light up unrelated scenarios that happen to use the same parameter name.
- `.param-highlight` styles: header and `<td>` get a soft background tint (`var(--color-accent-bg)`); placeholder spans in narration get the same tint with a small border-radius. Using `outline` on inline spans was tried first but rendered asymmetrically across line boxes — a background tint is symmetric and quieter.

## Change 5 — `data-param` plumbing

Three render sites need to emit `data-param="<name>"` so Change 4 has selectors to bind to:

- **`narration` filter in `renderer.py`** — `NarrationPlaceholder` branch emits `<span class="param-color-{n}" data-param="{name}">{token}</span>`.
- **`<th>` in `report.html.j2`** — already has `param-color-N`; add `data-param="{{ name }}"`.
- **`<td>` in `report.html.j2`** — currently `{% for val in case.values %}<td>{{ val }}</td>{% endfor %}`. Replace with a zipped loop that pairs names and values: `{% for name, val in zip(scenario.parameters.names, case.values) %}<td data-param="{{ name }}">{{ val }}</td>{% endfor %}`. The `zip` filter is exposed by adding it to `env.globals` in `render_html`.

`NarrationValue` and `NarrationLiteral` parts are unchanged.

## Files touched

- `src/pytest_given/report/templates/report.html.j2` — SVG icons inline; sidebar search wraps in `<label>`; attachment badge gets paperclip; scenario body wrapper restructured; `<th>` and `<td>` get `data-param`.
- `src/pytest_given/report/templates/app.js` — `_readHash` / `_writeHash` rewritten; `hoverParam(name, event)` method added.
- `src/pytest_given/report/templates/styles.css` — `.search-box`, `.search-box-icon`, `.search-box-clear`; `.attachment-badge-icon`; `.scenario-body` / `.scenario-body-inner` rules; `.param-table tbody tr:hover`; `.param-highlight` rules; remove or simplify `.transition-enter*` if unused after the scenario-body change (audit before deleting).
- `src/pytest_given/report/renderer.py` — `narration` filter emits `data-param` on placeholders; `zip` exposed to Jinja globals.

## Testing

- **Renderer-level Python tests** — assert `data-param="cup_size"` appears on placeholder spans, `<th>`, and `<td>` in the rendered output. Assert the SVG markers are present (e.g., `class="search-box-icon"`) and that no `🔍` / `📎` glyphs remain in the rendered HTML.
- **`_readHash` / `_writeHash` JS coverage** — Python tests already snapshot the JS file as part of the bundled report; the substantive coverage comes from regenerating `examples/report.html` and clicking through it.
- **Visual verification via Playwright MCP** (per AGENTS.md) — open `examples/report.html`, hover a parametrized row to confirm crosshair, expand/collapse a scenario to confirm smooth animation, toggle status pills to confirm the URL hash updates to `#status=…`. Not a CI gate; manual / agent-driven.
- **Examples regeneration** — `uv run nox -s examples` produces a fresh `examples/report-data.json` and `examples/report.html`; both committed.
- **Quality gates** — `uv run nox -s format lint mypy test coverage` before commit.

## Out of scope

- Traceback verbosity (own spec — see TODO line 19).
- Animation of skip-reason (no toggle).
- Any change to the JSON schema. Placeholders already carry `name`; `data-param` is a rendered-HTML concern.
- A general icon library or icon component abstraction. Three inline SVG strings in one template is fine.
