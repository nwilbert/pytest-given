# Row-hover value preview for parametrized scenarios

## Problem

A parametrized scenario renders its steps once, as a merged template with
placeholder tokens — `I brew a {cup_size} ml cup` — and lists the per-case
values in a table below. Reading a specific case means mentally substituting a
table row back into the step text. The report already color-codes each
parameter column and lights up the matching column on hover (the "crosshair"),
but it never shows what the steps actually *say* for a given case.

## Goal

When the cursor enters a case row in the parameter table, every placeholder
token in that scenario's steps (and its templated name, if present) swaps from
`{cup_size}` to that row's actual value (`200`), keeping the column color. On
leave, the tokens return.

## Behavior

- **Row hover → substitute.** Entering a value row replaces all placeholder
  tokens in the scenario with that row's values. The token's existing
  `param-color-N` text color is retained, so the value-to-column link stays
  visible.
- **Cell hover → substitute + emphasize one.** Because a cell sits inside a
  row, hovering a cell substitutes the whole row *and* keeps the existing
  per-column crosshair, so the placeholder for that cell's column additionally
  gets the background tint. This is the "highlight that one."
- **Header hover → unchanged.** A header has no single row, so it keeps the
  pure column crosshair (no substitution).
- **Scope.** Substitution is scoped to the row's closest `.scenario` ancestor,
  exactly like the existing crosshair. A templated scenario name in the header
  updates too; other scenarios are untouched.

## Mechanism (frontend only)

The `data-param` attributes this needs are already emitted on both placeholder
spans and table cells. No schema / serde / plugin / renderer changes.

- **`report.html.j2`** — add
  `@mouseenter="setHoverRow($event.currentTarget)"
  @mouseleave="clearHoverRow($event.currentTarget)"` to the value `<tr>` in
  `param-table`. The per-case error `<tr>` (colspan) gets no handlers. The
  per-`<td>` `setHoverParam` handlers stay for the single-column emphasis.
- **`app.js`**
  - `setHoverRow(rowEl)` — build a name→value map from each `<td data-param>`
    in the row; for each `span[data-param]` in the scope, stash its current
    text in `dataset.token` (only if unset, so re-entry is idempotent), set
    `textContent` to the value, and add a `param-substituted` class. A
    placeholder whose `data-param` has no matching cell in the row is skipped.
  - `clearHoverRow(rowEl)` — for each substituted placeholder in scope, restore
    `textContent` from `dataset.token` and drop the `param-substituted` class.
- **`styles.css`** — `.param-substituted` keeps the inherited `param-color-N`
  text color, with a faint tint so a filled-in value reads as resolved rather
  than a `{token}`. Exact treatment tuned during Playwright verification.

## Out of scope

Per-case *formatted* substitution (applying a placeholder's `:03d` format spec,
or `Template.substitute(...)` for scenario names) is the deferred, currently
unreachable substitution machinery noted in `TODO.md`. This feature mirrors the
table cell's displayed text verbatim and does not touch that path.

## Verification

Frontend-only, so no TDD and no markup-pinning Python tests (per AGENTS.md).
Apply the change, run `uv run nox -s examples` to regenerate, then drive
`examples/coffeeshop/coffeeshop.html` in Playwright — it has both templated step
text and a templated scenario name. Confirm: console is clean after init;
hovering a row turns tokens into that row's values in the correct colors and
restores on leave; cell hover still highlights its column; the templated
scenario name updates with the rest.
