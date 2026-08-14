# Per-case columns for parametrized scenarios — Design Spec

## Problem

Merging parametrize cases into one scenario (`_group_parametrized`, `plugin.py`) takes
the step tree from `group[0]` and discards every other case's. The merged view is
therefore only honest about what the *first* case recorded. Three things vary per case;
none of them survive:

1. **Attachments are dropped.** `_templatize_steps` rewrites narration and recurses into
   children, and `dataclasses.replace` carries case 1's `attachments` list through
   untouched. `ParameterCase` holds `values`, `status`, `error` and nothing else, so
   there is nowhere for the other cases' payloads to go. No warning is emitted.

   ```python
   @pytest.mark.parametrize('flavor', ['vanilla', 'mocha'])
   @scenario(Template('Brew a {flavor} coffee'))
   def test_brew(flavor):
       with when(t"the machine brews {flavor}"):
           attach(t"{flavor} log", f"log-for-{flavor}")
   ```

   ```json
   "steps": [{"text": "the machine brews vanilla",
              "attachments": [{"label": "vanilla log", "content": "log-for-vanilla"}]}]
   ```

   The mocha attachment appears nowhere in the report. The badge also reads
   `vanilla log` — an eagerly-rendered case-1 label — sitting under a step whose own
   narration correctly shows the `{flavor}` placeholder.

2. **Narrated values freeze to case 1.** `_templatize_narration` turns a
   `NarrationValue` into a placeholder only when its `expression` matches a parametrize
   column; otherwise it stays verbatim, on the stated assumption that "the rendered
   value is shared across cases". Nothing checks that assumption. Two authoring forms
   break it:

   ```python
   price = cup_size * 0.01
   with when(t"the drink costs {price} euros"):        # NarrationValue, not a column
   with when(f"the machine brews {cup_size} ml"):      # no parts at all
   ```

   The t-string records `{"rendered": "2.0", "expression": "price"}` and renders "the
   drink costs 2.0 euros" for every row. The f-string is worse — it records
   `{"text": "the machine brews 200 ml", "parts": []}`, so the whole narration is case
   1's and there is no structure left to compare.

3. **Structure diverges silently in the report.** `divergent-case-structure`
   (`lint/runtime_rules.py`) catches this, but it is lint-only and compares
   `(phase, children)` signatures alone — the rendered report still shows case 1.

A related defect falls out of the same line: the baseline is `group[0]` unconditionally,
so when the first case is skipped the merged scenario renders `"steps": []` even though
later cases ran and recorded a full tree.

## Goal

One rule, applied to all three: **the merged step tree shows only what every case
shares; anything that varies becomes a column in the case table.**

This is the split the table already embodies for parametrize inputs — `{cup_size}` in
the narration, values in the column — extended to the other two kinds of varying leaf.

## Behavior

### Column kinds

| kind | today | after |
|---|---|---|
| `param` | column | unchanged |
| `derived` — a `NarrationValue` whose rendered text varies across cases | frozen to case 1 | `NarrationPlaceholder` in the tree + column named for the expression |
| `attachment` — an attachment whose label, content, or content type varies | dropped | badge stays on its step + column |

An attachment that is byte-identical across every case is shared structure and stays
inline on its step, where its step context is visible. Same for a `NarrationValue` whose
rendered text is identical everywhere — that is today's behaviour, now verified instead
of assumed.

### Column identity

A column is identified by its **position in the step tree**, not by its name, and carries
that identity as an `id`. Two steps can interpolate the same expression — `{price}` in a
`when` and again in a `then` — with different values, which would collide if the
expression string were the key; it would also cross-wire the frontend, which matches on
`data-param` (see [HTML rendering](#html-rendering)). The expression supplies the
column's display name only; a `param` column uses its parametrize name as both.

### Where the step context comes from

Attachments live inside steps, sometimes nested, so flattening them into a case row
would lose that. It does not need carrying: the badge stays in the merged tree at its
original position, and the column is tied back to it by the existing `data-param` hover
highlight, exactly as a `{cup_size}` placeholder is tied to its column. The tree says
*where*, the table says *what*.

### Attachment labels

`Attachment.label` becomes a `Narration`, the same type as `Step.narration`, and `attach`
records a t-string label structurally instead of rendering it eagerly at
`decorators.py:436-437`. Labels then follow the narration rules exactly: templatized on
merge, varying parts promoted, and the same rejected forms apply (see rule 3 below).

`attach(t"{flavor} log", …)` therefore yields a column headed `{flavor} log` with a live
placeholder. That placeholder resolves against the **existing** `flavor` column, so the
label creates no column of its own and needs no palette colour — its highlight comes from
whichever column it references.

Because every label either templatizes or raises, an attachment column always has a real
header and the tree badge always has real text. There is no icon-only fallback anywhere in
the design.

The cell still carries that case's rendered label, so the table reads without hovering.
`attach`'s signature is unchanged, as is the existing rejection of `attach(Template(...))`.

**Consequence outside parametrized scenarios.** Dropping eager rendering means t-string
labels record parts everywhere, so a non-parametrized scenario's labels gain the neutral
value highlight that step text already has. Rendered text is unchanged; the HTML is not.
Existing example and self-report outputs will show this diff.

### Baseline case

The baseline becomes the first **passed** case rather than `group[0]`, matching how
`_divergent_case_findings` already picks its baseline. Skipped cases record no steps and
failed ones may abort mid-tree, so neither can define the shared structure. If no case
passed, fall back to `group[0]` — there is nothing to compare.

## Rejected authoring forms

Four forms are rejected. All raise `PytestGivenError` from `_group_parametrized`, naming
the file, line and fix.

1. **A `str` narration whose value varies across cases.** `given/when/then` accept
   `str | Template`; a `str` records `parts == []` however it was built, so there is
   nothing to promote and nothing to compare — the whole narration is case 1's. An
   f-string is the common cause, but `when(label_for(cup_size))`,
   `when("brews " + str(cup_size))` and `when(LABELS[cup_size])` are identical from the
   recorder's side. The fix is a t-string, so the varying part is recorded as a part
   rather than baked into the text.

   > `PytestGivenError: step narration in 'test_brew' varies across parametrize cases but records no parts — a plain str bakes case 1's values (an f-string is the usual cause). Use a t-string: when(t"…").`

2. **A promoted expression that is not a bare name.** `NarrationValue.expression` is
   the interpolation's *source text*, so `t"{cup_size * 0.01}"` records
   `expression: "cup_size * 0.01"` and `t"{m.balance}"` records `"m.balance"` —
   attribute access is compound too, despite reading name-ish. The test is
   `str.isidentifier()` on the recorded expression. Naming a column and a placeholder
   after arbitrary source text reads as noise in prose. The fix is to bind a local and
   narrate that.

   > `PytestGivenError: 'cup_size * 0.01' in 'test_brew' varies across parametrize cases — bind it to a local and narrate that: price = cup_size * 0.01; when(t"… {price} …").`

3. **An attachment label that varies and cannot be templatized.** Rules 1 and 2 applied
   to `Attachment.label`, which is now a `Narration`. Strictly this is stricter than
   correctness requires — a varying label never makes the report *wrong*, since the cell
   shows each case's real label — but one rule across every narrated surface beats two,
   and it is what guarantees every attachment column a real header.

   > `PytestGivenError: attachment label in 'test_brew' varies across parametrize cases but records no parts — use a t-string: attach(t"{flavor} log", …).`

   This breaks `attach(f"…")` calls that are legal today and produce a truthful report.
   See [Compatibility](#compatibility).

4. **An expression that matches a parametrize name but not its value.** Today
   `_templatize_narration` converts any `NarrationValue` whose `expression` is a
   parametrize column into a `NarrationPlaceholder` and **discards `rendered`**
   (`plugin.py:933`); the renderer then substitutes from the parameter table. Rebinding
   the name breaks that identity silently:

   ```python
   cup_size = cup_size * 2
   with when(t"the machine brews {cup_size} ml"):     # records rendered "400"
   ```

   The report reads "brews 200 ml" and "brews 350 ml" while the code brewed 400 and 700 —
   wrong for *every* case, not just the first. This match short-circuits before any
   cross-case comparison, so none of the other rules sees it.

   The check is the same verify-don't-assume move used everywhere else here: for each
   case, compare `rendered` against that case's parameter value **formatted through the
   interpolation's own `conversion` and `format_spec`** — `t"{cup_size!r:>8}"` renders
   differently from `str(cup_size)` and must not be flagged for it. Agreement keeps
   today's placeholder path; disagreement raises.

   > `PytestGivenError: 'cup_size' in 'test_brew' matches a parametrize column but narrates a different value (case [200] narrates '400') — rebinding a parameter name makes the narration ambiguous. Rename the local.`

   This is a pre-existing defect, not one this design introduces. It is fixed here because
   the spec's central claim is that the merged view tells the truth, and this is the last
   member of the family.

This makes promotion **total**: every promoted column is named by an identifier by
construction, so no renderer ever has to display raw source text, and the elide/tooltip
question does not arise.

### When each fires

The trigger is variance, not syntax. The merge sees recorded parts, never source: an
f-string is indistinguishable from any other `str`, so rule 1's real condition is
`parts == []` **and** the rendered text differs across cases.

The table applies to step narration and to attachment labels alike — both are
`Narration`, and rules 1, 2 and 4 read the same parts either way (rule 3 is just their
application to labels).

| narrated text | varies? | result |
|---|---|---|
| any expression producing a `str` (literal, f-string, helper call, lookup) | no | inline, unchanged |
| any expression producing a `str` | yes | **error** (1 for narration, 3 for a label) |
| t-string, expression is a parametrize name, value agrees | — | placeholder + existing `param` column |
| t-string, expression is a parametrize name, value disagrees | — | **error 4** |
| t-string, expression is a bare name | no | inline verbatim, unchanged |
| t-string, expression is a bare name | yes | promoted to a `derived` column |
| t-string, expression is compound | no | inline verbatim, unchanged |
| t-string, expression is compound | yes | **error** (2 for narration, 3 for a label) |

No rule bans a form outright: a compound interpolation whose value is constant across
cases renders inline exactly as it does today, and a varying bare-name t-string is the
supported path rather than a violation. Variance is measured across **passed** cases only,
so a group with fewer than two passed cases cannot raise.

Attachment **content** never triggers anything — varying content is exactly what the
`attachment` column is for, and it is compared byte-wise, not narrated.

**Why not lint.** `given_lint` defaults to `False` (`plugin.py:172-177`) — the linter is
opt-in, so an error-severity rule would enforce nothing for a default user and the report
would go on lying quietly. The check belongs where the merge already holds every case's
tree. It fires only on runs that request a report; a bare `pytest` writes nothing and
stays silent.

### Compatibility

Rules 1 and 2 upgrade a documented caveat
(`docs/specs/2026-05-23-structured-step-text-design.md:302`, "renders the first case's
value across all cases. **Fix:** use a t-string") into a hard error. They fire only when
the text genuinely varies, so the affected suites are exactly those already getting a
wrong report.

Rule 3 is different and worth calling out on rollout: `attach(f"{flavor} log", …)` in a
parametrized scenario is legal today *and* produces a truthful report, so this rule breaks
working code for consistency rather than correctness. It was chosen deliberately over an
icon-only-header fallback.

Both need CHANGELOG entries plus updates to the authoring skill's
`references/scenarios.md` and `references/api.md`.

## Schema

`ParameterTable.names: list[str]` becomes `columns: list[ParameterColumn]`, and a case's
`values` stays positionally aligned with it. A cell is a scalar for `param`/`derived`
columns and an attachment object for `attachment` columns.

A column carries an `id` as well as a `name`. `id` is stable within the scenario and is
what the DOM keys on; `name` is display text only. They differ because two columns in one
scenario can share a name — `{price}` narrated in a `when` and again in a `then` with
different values — and `data-param` matching by name would cross-wire them (see
[HTML rendering](#html-rendering)). For a `param` column the two coincide.

`Attachment.label` also changes: `str` becomes `Narration`, so a templatized label
round-trips like step narration.

```json
"parameters": {
  "columns": [
    {"id": "cup_size", "name": "cup_size", "kind": "param"},
    {"id": "d0", "name": "price", "kind": "derived"},
    {"id": "a0", "name": "{flavor} log", "kind": "attachment"}
  ],
  "cases": [
    {"values": [200, "2.0",
                {"label": "vanilla log", "content": "…", "content_type": "json"}],
     "status": "passed", "error": null}
  ]
}
```

The attachment column's `name` is the merged label with its placeholder; each cell's
`label` is that case's rendered text.

One shape for all three kinds, so both renderers and downstream `jq` recipes loop a
single list instead of branching per kind. This is a breaking change to the JSON report;
it rides along with the JSON-format polish already on the TODO. A cell is `null` where a
case has no value for that column (see Edge cases).

## Merge algorithm

1. Group cases as today. Pick the baseline: first passed case, else `group[0]`.
2. Validate the rejected authoring forms across the group — including verifying that
   every param-name-matching interpolation really renders its parameter's value — and
   raise on any.
3. Walk the baseline step tree. At each position, compare against the same position in
   every other passed case:
   - each `NarrationValue` whose `expression` is not a parametrize name — compare
     `rendered`;
   - each attachment — compare `(label, content, content_type)`.
4. Identical everywhere → leave inline. Otherwise → emit a column and replace the
   inline occurrence with a placeholder — in the step narration, or in the badge's
   templatized label.
5. Fill each case's cells by reading the same positions out of that case's own tree.

Parametrize columns are emitted first, in their existing order, then `derived` and
`attachment` columns in tree order — so the table still reads inputs-first.

## Edge cases

- **No case passed.** Nothing to compare; fall back to today's `group[0]` rendering.
- **Structure diverges.** Positional matching is undefined for that case, so its cells
  are `null` and render blank. `divergent-case-structure` already fires, so this
  introduces no new lint rule.
- **Attachment count differs at the same step** (a loop-driven `attach`). Positional
  matching fails for that step, so all of its attachments become columns, blank where a
  case has none.
- **Single-value parametrize.** Everything is trivially shared; no new columns.
- **Module/session-scoped fixture that attaches.** Only the first consumer records the
  fixture subtree, so later cases read as structure divergence: blank cells plus the
  existing lint finding. Surfaced, not fixed — that belongs to the fixture-scope design.

## Attachment icon

Independent of the merge work, and touching the same surfaces. The HTML report's
paperclip SVG and the Markdown renderer's `📎` are replaced by an icon chosen from
`content_type`: a document glyph for `text`, braces for `json`. `Attachment` is already
typed, so this is a branch in the macro plus a second inline SVG — no new data. The badge
then says what it will expand into before it is clicked.

## Markdown rendering

Columns render as table columns like any other. Attachment cells follow the split
`_attachment_lines` already uses: short single-line content sits inline in the cell in
backticks; multiline or backtick-bearing content shows the label in the cell and renders
fenced below the table, grouped by case.

````markdown
| cup_size | price | state | |
|---|---|---|---|
| 200 | 2.0 | `ok` | ✓ |
| 350 | 3.5 | state | ✓ |

- **350** — state:
  ```
  {"ml": 350, "full": true}
  ```
````

## HTML rendering

The case row gains a cell per new column. Attachment cells render the badge with that
case's label and expand their content in place, reusing the `expandedAttachments` Alpine
state and the `grid-rows` expand already used by step attachments. `derived` columns are
not visually distinguished from `param` columns in v1.

Three existing frontend behaviours need care — the
[row-hover value preview](2026-06-28-row-hover-value-preview-design.md) is live and this
design silently extends it to two new column kinds.

- **`data-param` carries the column `id`, not its name.** `setHoverParam`
  (`app.js:258-266`) and `setHoverRow` (`app.js:267-282`) both match on the attribute
  value, so two same-named columns in one scenario would cross-highlight and
  cross-substitute. Keying on `id` fixes both with no JS change.
- **Attachment columns are excluded from the row-hover substitution.** `setHoverRow`
  copies `td.textContent` into the matching narration `span` (`app.js:271-280`); for an
  attachment cell that text is the badge label, so hovering a row would replace a step's
  placeholder with `vanilla log`. The highlight is fine and stays; the substitution pass
  must skip `kind == 'attachment'`. Cheapest form: emit the substitution attribute only
  for `param`/`derived` cells, leaving the JS untouched.
- **Palette scope.** `_build_param_color_map` (`html_renderer.py:167-177`) assigns a
  colour per name across the report. `derived` columns join it; `attachment` columns do
  not — a badge needs no value colour, including them would shift every existing param's
  colour, and an attachment header's placeholder already draws its colour from the column
  it references.

  Note the deliberate split: **colour is keyed by `name`, highlighting by `id`.** Colour
  stays name-keyed so the same parameter reads the same colour in every scenario, while
  `data-param` must be id-keyed so same-named columns don't cross-wire. Easy to
  accidentally unify during implementation; they are not the same key.

## Implementation touch points

| file | change |
|---|---|
| `src/pytest_given/model/schema.py` | `ParameterColumn` (`id`, `name`, `kind`); `ParameterTable.columns` replaces `names`; cell type widens to scalar-or-`Attachment`; `Attachment.label` becomes `Narration` |
| `src/pytest_given/model/serde.py` | round-trip for the new shape, including narrated labels |
| `src/pytest_given/capture/decorators.py`, `capture/collector.py` | `attach` records a t-string label structurally instead of rendering it eagerly |
| `src/pytest_given/plugin.py` | passed-case baseline; rejected-form validation; cross-case comparison; column construction; `_templatize_narration` promotes varying `rendered` to placeholders and runs over attachment labels |
| `src/pytest_given/report/html_renderer.py`, `templates/report.html.j2`, `templates/styles.css` | column loop, attachment cells, `content_type` icons, `data-param` keyed on column `id`, substitution skipped for attachment cells, palette excludes attachment columns |
| `src/pytest_given/report/md_renderer.py` | column loop, attachment cells and below-table blocks, icon |
| `examples/coffeeshop/test_coffeeshop.py` | a parametrized scenario that both attaches and narrates a derived local |
| `src/pytest_given/skills_data/pytest-given-navigating/references/report-json.md` | new `parameters` shape and `jq` recipes |
| `src/pytest_given/skills_data/pytest-given-authoring/references/scenarios.md`, `references/api.md` | in a parametrized scenario, a varying `str` narration (f-strings included) and a varying compound interpolation are now errors, not caveats; the same rules now apply to `attach` labels |
| `CHANGELOG.md` | three `## [Unreleased]` entries (see below) |

No lint changes. The rules this design displaces move into the merge rather than into
the catalog, for the reason given under [Rejected authoring forms](#rejected-authoring-forms)
— see [Open questions](#open-questions) for what that implies for
`divergent-case-structure`.

This lands as five user-facing changes, each needing its own `## [Unreleased]` entry in
the commit that makes it (per AGENTS.md), four of them breaking:

- **Changed (breaking).** `parameters.names` becomes `parameters.columns` (each column an
  `id`/`name`/`kind`); cells widen to scalar-or-attachment; `Attachment.label` becomes a
  narration object. Affects anything reading the JSON report, including the `jq` recipes
  in the navigating skill.
- **Added.** Attachments and derived values that vary across parametrize cases now render
  as columns instead of being dropped or frozen to the first case.
- **Changed (breaking).** In a parametrized scenario, a `str` narration whose value
  varies across cases (typically an f-string), and a t-string interpolating anything but
  a bare name (`t"{cup_size * 0.01}"`, `t"{m.balance}"`) whose value varies, now raise
  `PytestGivenError`. Suites hitting either were already getting a wrong report. The same
  two rules now apply to `attach` labels — see the rollout note below.
- **Fixed (breaking).** A t-string interpolating a rebound parametrize name rendered the
  *parameter's* value rather than the narrated one, wrong for every case. It now raises
  rather than rendering a false value.
- **Changed.** `attach` records t-string labels structurally instead of rendering them
  eagerly, so labels carry value highlighting in the HTML report the way step text does.
  Rendered text is unchanged.

The project is pre-1.0, so these ride a minor bump rather than a major one.

**Rollout note.** The label rule (rejected form 3) is the only one that breaks code
producing a *correct* report today. Worth calling out explicitly in the release notes
rather than folding into the general breaking-change entry.

## Verification

- Unit: merge comparison (shared stays inline; varying promotes; identical-content
  attachments do not promote), passed-case baseline, divergent-structure blanks,
  schema round-trip, Markdown short/long split.
- Unit: all four rejected forms raise, with the file/line and fix in the message; none
  fires when the text happens to be constant across cases; none fires on a run that
  requests no report.
- Unit: rule 4 does *not* fire for a faithful interpolation carrying a conversion or
  format spec (`t"{cup_size!r:>8}"`), which renders differently from `str(cup_size)`
  without being a rebind.
- Unit: a templatized attachment label round-trips, merges to a placeholder header, and
  renders its per-case label in the cell; a label whose placeholder names a parametrize
  column creates no new column.
- Unit: two same-named `derived` columns in one scenario get distinct `id`s.
- Integration: a parametrized scenario with an attachment and a derived local, asserted
  through `--given-json`.
- `uv run nox -s examples` and `-s self_report`, reading the `.md` diff first. Expect a
  non-empty HTML diff for *non-parametrized* attachment labels too — that is the eager-
  rendering change, not noise.
- Playwright for the template work: console clean after init, then drive cell expand, the
  tree-badge → column hover highlight, and row hover — confirming a narration placeholder
  substitutes from `param`/`derived` cells and is left alone by attachment cells. Per
  AGENTS.md this is not TDD'd and gets no markup-pinning Python tests.

## Out of scope

- `@scenario(group_parametrized=False)` (TODO). This shrinks its remit but does not
  retire it: varying *structure* still has no honest merged rendering, and the opt-out
  remains the answer there.
- Distinguishing `derived` from `param` columns visually.
- Fixing session/module-scoped fixture attachment recording.

## Open questions

**Does `divergent-case-structure` still belong in the linter?** After this design it is
the last member of the family still handled by an opt-in check. The argument that moved
the other two into the merge applies to it unchanged: with `given_lint` off — the
default — a scenario whose cases take different branches still renders the baseline's
structure, showing steps that some cases never ran, and says nothing about it.

It does not follow that it should raise. Unlike the four rejected forms, structure
divergence has no one-line fix: the cases genuinely differ, and the merged view cannot
represent them. The graceful answer is to decline the merge and emit one scenario per
case — which is `group_parametrized=False` from TODO line 25, applied automatically
rather than by opt-in.

That is a larger change than this spec, and it would make the merge fall back rather
than fail in a third situation. Left open deliberately: this design neither fixes nor
worsens it, but it does make the inconsistency visible.
