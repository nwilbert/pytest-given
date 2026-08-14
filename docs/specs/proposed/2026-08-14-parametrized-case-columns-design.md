# Per-case columns for parametrized scenarios — Design Spec

## Problem

Merging parametrize cases into one scenario (`_group_parametrized`, `plugin.py`) takes the
step tree from `group[0]` and discards every other case's, so the merged view is only honest
about the *first* case. Four kinds of per-case content vary and none survives the merge.

1. **Attachments are dropped.** `_templatize_steps` rewrites narration and recurses into
   children; `dataclasses.replace` carries case 1's `attachments` through untouched. And
   `ParameterCase` holds `values`, `status`, `error` and nothing else, so the other cases'
   payloads have nowhere to go. No warning is emitted.

   ```python
   @pytest.mark.parametrize('flavor', ['vanilla', 'mocha'])
   @scenario(Template('Brew a {flavor} coffee'))
   def test_brew(flavor):
       with when(t"the machine brews {flavor}"):
           attach(f"{flavor} log", f"log-for-{flavor}")
   ```

   ```json
   "steps": [{"text": "the machine brews vanilla",
              "attachments": [{"label": "vanilla log", "content": "log-for-vanilla"}]}]
   ```

   The mocha attachment appears nowhere, and the badge reads case 1's `vanilla log` under a
   step whose own narration correctly shows the `{flavor}` placeholder.

2. **Narrated values freeze to case 1.** `_templatize_narration` promotes a `NarrationValue`
   to a placeholder only when its `expression` matches a parametrize column; otherwise it
   stays verbatim, on the stated assumption that "the rendered value is shared across cases".
   Nothing checks that assumption, and two authoring forms break it:

   ```python
   price = cup_size * 0.01
   with when(t"the drink costs {price} euros"):        # NarrationValue, not a column
   with when(f"the machine brews {cup_size} ml"):      # no parts at all
   ```

   The t-string records `{"rendered": "2.0", "expression": "price"}` and renders "the drink
   costs 2.0 euros" for every row. The f-string is worse: it records
   `{"text": "the machine brews 200 ml", "parts": []}`, so the whole narration is case 1's
   and no structure is left to compare.

3. **A glossary term ref freezes like any narrated value**, recording a per-case
   `(term_id, display)`.

4. **Structure diverges silently.** `divergent-case-structure` (`lint/runtime_rules.py`)
   catches this, but it is lint-only and compares `(phase, children)` signatures alone — the
   rendered report still shows case 1.

A related defect falls out of the same line: the baseline is `group[0]` unconditionally, so
when the first case is skipped the merged scenario renders `"steps": []` even though later
cases ran and recorded a full tree.

## Goal

One rule: **the merged step tree shows only what every case shares; anything that varies
becomes a column in the case table.**

This is the split the table already embodies for parametrize inputs — `{cup_size}` in the
narration, values in the column — extended to varying attachments and varying narrated
values. Kinds 3 and 4 are the exceptions: a varying pill is rejected rather than promoted
(promotion would strip the pill out of the tree), and structure stays lint-only.

## Behavior

### Column kinds

| kind | today | after |
|---|---|---|
| `param` | column | unchanged |
| `derived` — a `NarrationValue` whose rendered text varies across cases | frozen to case 1 | `NarrationPlaceholder` in the tree + column named for the expression |
| `attachment` — an attachment whose content or content type varies (its label may not) | dropped | badge keeps its label on its step + column |

An attachment that is byte-identical across every case is shared structure and stays inline
on its step. Same for a `NarrationValue` whose rendered text is identical everywhere —
today's behaviour, now verified instead of assumed.

Attachments live inside steps, sometimes nested, and the badge keeps that position in the
merged tree; the column is tied back to it by the existing `data-param` hover highlight,
exactly as a `{cup_size}` placeholder is tied to its column. The tree says *where*, the table
says *what*.

### Column identity

A column is identified by its **position in the step tree**, not by its name, and carries
that identity as an `id`; the expression supplies the display `name` only. Two steps can
interpolate the same expression — `{price}` in a `when` and again in a `then` — with
different values, which would collide if the expression string were the key and would
cross-wire the frontend, which matches on `data-param`.

A `param` column uses its parametrize name as both. Generated ids are `d0`, `d1`, … and
`a0`, `a1`, … numbered per kind in emission order; a candidate that collides with a
parametrize name takes a `_` suffix until it is free, since a parameter named `d0` is legal
if unusual.

The split runs through the whole design and is easy to unify by accident: **`data-param`
keys on `id`, the colour palette keys on `name`** — so same-named columns stay separate while
one parameter reads the same colour in every scenario.

### Attachment column headers

**An attachment label is plain text, and `attach` now says so:** the signature narrows to
`attach(label: str, content)`, and anything else raises. `Attachment.label` stays a `str`, so
**no column header ever carries a placeholder** — `data-param` stays confined to the step
tree and to `param`/`derived` headers, and a narrated `th` never has to exist.

This deletes a form that never did anything. A t-string label is flattened at
`decorators.py:438-439` into exactly the string an f-string would produce, so
`attach(t"{flavor} log", …)` and `attach(f"{flavor} log", …)` are indistinguishable in the
report — while for `given/when/then` that same choice decides whether parts are recorded at
all. Allowing it invites the assumption that labels are narrated like step text. The code
shrinks with it: two `isinstance` branches (one raising for `Template`, one flattening
t-strings) collapse into one `not isinstance(label, str)` guard, `collector.attach` already
takes `label: str`, and today's message — "use a t-string (eager) or a plain string" — stops
recommending the form being removed.

> `PytestGivenError: attachment labels are plain text; f-strings are fine — attach(f"{flavor} log", …).`

Labels must also **not vary across cases** ([rule 5](#rejected-authoring-forms)), so a
column's header — and the badge on its step — is always the one label every case shares. A
column exists because the *content* varies; the name of that payload does not. That keeps the
whole surface named: no anonymous column, no nullable `name`, and no renderer needing a
fallback token for a header with no text — a form that would occur in exactly one place in
the design.

The rejected alternative was to make labels narration, so `attach(t"{flavor} log", …)` could
head a column with a live placeholder. It buys one nicer header for a `Narration` in the
schema, placeholders inside `th` elements, a substitution-scope bug with them, and a rule
forcing varying labels into t-strings.

### Term refs bound to a parametrize column

A term ref whose `expression` is a parametrize name is exempt from rule 4: its display varies
by construction, and `_templatize_narration` already tags it with `param_column`
(`plugin.py:951-953`) so `_render_term_ref` colours the pill from that column
(`html_renderer.py:323-324`). This is the `param` split applied to a pill — the tree keeps
the pill, the column already holds the values. It arises when the *parameter itself* is a
term instance:

```python
@pytest.mark.parametrize('guest', [pg['Guest']('Alice'), pg['Guest']('Bob')])
@scenario(Template('{guest} checks in'))
def test_check_in(guest):
    with when(t"{guest} arrives"):
```

The pill in the merged tree reads the baseline display and the column carries the rest;
substituting the pill on row hover is out of scope for v1. Three consumers read `display` and
all three currently see only the baseline — today's bugs, but this design makes the pattern
more likely, so they are fixed here:

- **`_param_value` unwraps a term instance to its display.** Today the instance hits the
  non-scalar branch and the cell stores `str(instance)` — a dataclass repr embedding the
  entire `Glossary` (410 characters for a two-term glossary), in the table and the JSON
  report. The `param` column is now the only place a case's display exists, so it has to hold
  `Alice`.
- **Coverage matches per case, then unions the matches.** `s_for_step`
  (`report/coverage.py:90`) derives an instance identity from `display`, so the merged
  scenario matches on the baseline's `Alice` alone and silently loses coverage of a
  `Bob`-anchored activity. Evaluate each step once per case, substituting that case's cell
  value for every param-linked pill, and union the *matches* — never the identity sets:
  matching is `refs_by_activity[aid].issubset(s_cache)`, so a merged identity set would let a
  step satisfy an activity by combining `Alice` from one case with `latte` from another,
  which no single case satisfies. A scenario with no param-linked pill — every scenario today
  — keeps the single-pass path.
- **Glossary aggregation unions the same way.** `build_glossary_aggregations`
  (`report/aggregations.py`) collects one `TermInstance` per `(term_id, display)`, so without
  this `Bob` never appears under `Guest` in the Glossary view.

Activities anchored on a canonical term are unaffected: `s_for_step`'s canonical fallback
already contributes `(term_id, None)` for every case.

### Baseline case

The baseline becomes the first **passed** case rather than `group[0]`, matching how
`_divergent_case_findings` already picks its baseline. Skipped cases record no steps and
failed ones may abort mid-tree, so neither can define the shared structure. If no case
passed, fall back to `group[0]` — there is nothing to compare.

Baseline selection scopes to the step tree. The merged scenario keeps `group[0]`'s identity
fields (`id`, `source`, tags, story bindings), so deep links and report ordering do not shift
with which case happened to pass.

## Rejected authoring forms

Five forms are rejected. All raise `PytestGivenError` from `_group_parametrized`, naming the
scenario's file and line and the fix. A step-level anchor is not available: `Step.source` is
captured only when lint is enabled (`plugin.py:241`), and these rules must hold with lint off.

Validation runs on **every** session, not only when a sink was requested. These are usage
errors, and the plugin already treats malformed narration as one:
`pytest_collection_modifyitems` raises for a bad `Template` placeholder whether or not a
report was asked for (`plugin.py:289-295`). Gating the merge rules differently would make
whether your suite is well-formed depend on which flags you passed. The existing
unknown-placeholder guard in `_templatize_narration` (`plugin.py:943-949`) therefore stays
where it is, and the merge stays a path that can raise.

Nothing may escape the hook, though: an exception leaving `pytest_sessionfinish` is neither a
test failure nor an INTERNALERROR — on pytest 9.0.3 it propagates out of `console_main` as a
bare traceback after the progress line, no summary at all and exit 1, indistinguishable from
an ordinary failing run. So `pytest_sessionfinish` catches the raise, records the message for
`pytest_terminal_summary`, writes **no** sink, and sets
`session.exitstatus = pytest.ExitCode.TESTS_FAILED` — the path `_run_lint` already uses. A
report the plugin knows to be false is never emitted, and the run fails loudly enough to stop
CI.

1. **A `str` narration whose value varies across cases.** A `str` records `parts == []`
   however it was built, so there is nothing to promote and nothing to compare — the whole
   narration is case 1's. An f-string is the common cause, but `when(label_for(cup_size))`,
   `when("brews " + str(cup_size))` and `when(LABELS[cup_size])` look identical from the
   recorder's side. The fix is a t-string, which records the varying part as a part instead
   of baking it into the text.

   > `PytestGivenError: step narration in 'test_brew' varies across parametrize cases but records no parts — a plain str bakes case 1's values (an f-string is the usual cause). Use a t-string: when(t"…").`

2. **A promoted expression that is not a bare name.** `NarrationValue.expression` is the
   interpolation's *source text*, so `t"{cup_size * 0.01}"` records
   `expression: "cup_size * 0.01"` and `t"{m.balance}"` records `"m.balance"` — attribute
   access is compound too, despite reading name-ish. The test is `str.isidentifier()` on the
   recorded expression: naming a column and a placeholder after arbitrary source text reads
   as noise in prose. The fix is to bind a local and narrate that.

   > `PytestGivenError: 'cup_size * 0.01' in 'test_brew' varies across parametrize cases — bind it to a local and narrate that: price = cup_size * 0.01; when(t"… {price} …").`

3. **An expression that matches a parametrize name but not its value.** Today
   `_templatize_narration` converts any `NarrationValue` whose `expression` is a parametrize
   column into a `NarrationPlaceholder` and **discards `rendered`** (`plugin.py:933`); the
   renderer then substitutes from the parameter table. Rebinding the name breaks that
   identity silently:

   ```python
   cup_size = cup_size * 2
   with when(t"the machine brews {cup_size} ml"):     # records rendered "400"
   ```

   The report reads "brews 200 ml" and "brews 350 ml" while the code brewed 400 and 700 —
   wrong for *every* case, not just the first. This match short-circuits before any
   cross-case comparison, so no other rule sees it.

   The check has one source of truth, and it is the **cell**: for a param match `rendered` is
   discarded, `_placeholder_token` renders the merged slot as a schematic `{cup_size}` with
   conversion and spec deliberately dropped, and row hover substitutes the cell's own text —
   so `rendered` is never displayed for a param placeholder, only ever used as evidence. Per
   case, then: apply the interpolation's own `conversion` and `format_spec` to that case's
   parameter value and compare with `rendered`. Agreement keeps today's placeholder path;
   disagreement raises.

   > `PytestGivenError: 'cup_size' in 'test_brew' matches a parametrize column but narrates a different value (case [200] narrates '400') — rebinding a parameter name makes the narration ambiguous. Rename the local.`

   That re-format runs on the **raw** parameter object, never on the cell, because
   `_param_value` (`plugin.py:358-361`) has already coerced anything non-scalar to `str`: a
   `datetime` under `t"{when:%Y}"` would compare the recorded `'2026'` against
   `format('2026-01-01 00:00:00', '%Y')`, which raises `ValueError: Invalid format specifier`,
   and under `t"{when!r}"` it would compare the datetime's repr against the *string's* and
   accuse a faithful interpolation of rebinding. `ParamSpec` therefore carries the raw values
   alongside the coerced ones — `param_info` is in-memory, cleared right after the merge and
   never serialized, so this is one field and no JSON change. Re-formatting the raw object is
   exactly what the t-string did at capture time, so a faithful interpolation agrees for every
   type, `t"{cup_size!r:>8}"` included.

   A pre-existing defect, fixed here because the merged view has to tell the truth about every
   part kind it renders.

4. **A glossary term ref whose pill varies across cases**, other than one bound to a
   parametrize column (see
   [Term refs bound to a parametrize column](#term-refs-bound-to-a-parametrize-column)). Both
   `term_id` and `display` are compared, and either one varying raises.

   A varying pill is rejected rather than promoted, whatever the shape of its expression.
   Promotion would strip the pill out of the merged tree, and `compute_coverage`
   (`report/coverage.py:115`) matches story activities on term-ref identities — so a promoted
   pill silently drops that scenario's coverage of an activity and can trip `dead-term`. The
   fix splits the pill from the value, leaving a constant pill and an ordinary `param`
   placeholder.

   > `PytestGivenError: glossary term ref {pg['Customer'](name)} in 'test_order' varies across parametrize cases — a term pill must name the same term and read the same in every case. Split the pill from the value: given(t"{pg['Customer']} {name} places an order").`

   The exemption is what keeps `param_column` alive: without it this rule would reject the
   only pattern that field exists for, and `param_column` would have to be retired from
   schema, serde, renderer and `report-json.md`.

5. **An attachment label that varies across cases.** A label names its payload; the payload is
   what varies, and the row already says which case it belongs to. `attach(f"{flavor} log", …)`
   puts the parameter in the name instead of leaving it in the `flavor` column that is already
   there, and leaves the merged tree with a badge that can only be one case's. The fix is a
   constant label with the varying part in the content — which also yields a *named* column
   instead of an anonymous one. Content and content type are exempt by design: varying those
   is exactly what the `attachment` column is for.

   > `PytestGivenError: attachment label in 'test_brew' varies across parametrize cases ('vanilla log' vs 'mocha log') — a label names the payload and must read the same in every case. Use a constant label and let the content vary: attach("brew log", …).`

An error means the author can do better: every rule above carries a one-line fix that yields
a strictly better report. Where no such fix exists the merge copes instead of raising — a
pill bound to a parametrize column, and divergent structure (see
[Out of scope](#out-of-scope)). Together the rules also make promotion **total**: every
column is named by an identifier or a shared label by construction, so no renderer ever has
to display raw source text or invent a header.

### When each fires

The trigger is variance, not syntax. The merge sees recorded parts, never source: an f-string
is indistinguishable from any other `str`, so rule 1's real condition is `parts == []`
**and** the rendered text differs across cases. The table covers step narration only — an
attachment label is plain text with one rule of its own (rule 5) and carries no parts to
classify.

| narrated text | varies? | result |
|---|---|---|
| any expression producing a `str` (literal, f-string, helper call, lookup) | no | inline, unchanged |
| any expression producing a `str` | yes | **error 1** |
| t-string, expression is a parametrize name, value agrees | — | placeholder + existing `param` column |
| t-string, expression is a parametrize name, value disagrees | — | **error 3** |
| t-string, expression is a bare name | no | inline verbatim, unchanged |
| t-string, expression is a bare name | yes | promoted to a `derived` column |
| t-string, expression is compound | no | inline verbatim, unchanged |
| t-string, expression is compound | yes | **error 2** |
| t-string, glossary term ref | no | inline pill, unchanged |
| t-string, glossary term ref whose expression is a parametrize name | yes | pill stays, values already in that `param` column |
| t-string, glossary term ref | yes | **error 4** |

No rule bans a form outright — a constant compound interpolation still renders inline, and a
varying bare-name t-string is the supported path. Variance is measured across **passed** cases
only, so a group with fewer than two passed cases cannot raise.

**Why not lint.** `given_lint` defaults to `False` (`plugin.py:172-177`), so an error-severity
rule would enforce nothing for a default user and the report would go on lying quietly. The
check belongs where the merge already holds every case's tree.

### Compatibility

Rules 1 and 2 upgrade a documented caveat
(`docs/specs/2026-05-23-structured-step-text-design.md:302`, "renders the first case's value
across all cases. **Fix:** use a t-string") into a hard error. They fire only when the
narration genuinely varies, so the affected suites are exactly those already getting a wrong
report. Rules 3, 4 and 5 have the same character: a rebound parameter name, a per-case term
pill and a per-case attachment label all render wrong today — the last worst of all, since
every non-baseline attachment is dropped outright. No rule here breaks code that produces a
correct report.

## Schema

`ParameterTable.names: list[str]` becomes `columns: list[ParameterColumn]`, and a case's
`values` stays positionally aligned with it. Each column carries an `id` (what the DOM keys
on) as well as a display `name`; the two coincide for a `param` column (see
[Column identity](#column-identity)).

The widening is also the moment to stop `ParameterCase.values` being `list[Any]`
(`schema.py:284`) — gratuitous even today, since `ParamSpec.values` is already typed. A named
cell type states the heterogeneity instead of hiding it, per AGENTS.md's avoid-`Any`
convention:

```python
type CellValue = ParamValue | Attachment   # ParamValue = str | int | float | bool | None
```

Cells are heterogeneous **by column kind**, deliberately: a `param` cell keeps the parametrize
value as captured, a `derived` cell carries the *rendered* string — already through the
interpolation's conversion and format spec, and no renderer re-formats it — and an
`attachment` cell is an object, which is also how serde discriminates the two on read. `null`
marks a case with no value for that column (see [Edge cases](#edge-cases)).

`Attachment` itself is unchanged, so an attachment cell keeps the existing shape and `name`
stays a plain `str` for every column kind: an attachment column's `name` is the label every
case shares, never null.

```json
"parameters": {
  "columns": [
    {"id": "cup_size", "name": "cup_size", "kind": "param"},
    {"id": "d0", "name": "price", "kind": "derived"},
    {"id": "a0", "name": "machine state", "kind": "attachment"}
  ],
  "cases": [
    {"values": [200, "2.0",
                {"label": "machine state", "content": "…", "content_type": "json"}],
     "status": "passed", "error": null}
  ]
}
```

One shape for all three kinds, so both renderers and downstream `jq` recipes loop a single
list instead of branching per kind. This is a breaking change to the JSON report, riding along
with the JSON-format polish already on the TODO; report versioning is that item's job, not
this one's.

## Merge algorithm

1. Group cases as today. Pick the baseline: first passed case, else `group[0]`.
2. Validate the rejected authoring forms across the group — including verifying that every
   param-name-matching interpolation really renders its parameter's value — and raise on any.
3. Walk the baseline step tree. At each position, compare against the same position in every
   other passed case:
   - each `NarrationValue` whose `expression` is not a parametrize name — compare `rendered`;
   - each `NarrationTermRef` whose `expression` is not a parametrize name — compare
     `(term_id, display)`; any difference raises (rule 4) rather than promoting;
   - each attachment — compare `(content, content_type)`; a differing label raises (rule 5).
4. Identical everywhere → leave inline. Otherwise → emit a column; for a `derived` value,
   replace the inline occurrence in the step narration with a placeholder. An attachment badge
   stays where it is and keeps its label, which rule 5 guarantees every case shares.
5. Fill each case's cells by reading the same positions out of that case's own tree.

Parametrize columns are emitted first, in their existing order, then `derived` and
`attachment` columns in tree order — so the table still reads inputs-first.

## Edge cases

- **No case passed.** Nothing to compare; fall back to today's `group[0]` rendering.
- **A skipped or failed case.** It records no tree, or an aborted one, so step 5 finds nothing
  at those positions: its `derived` and `attachment` cells are `null` and render blank. Its
  `param` cells are unaffected.
- **Structure diverges.** Positional matching is undefined for that case, so its cells are
  `null` and render blank. `divergent-case-structure` already fires, so this introduces no new
  lint rule.
- **Attachment count differs at the same step** (a loop-driven `attach`). Positional matching
  fails for that step, so all of its attachments become columns, blank where a case has none.
- **Single-value parametrize.** Everything is trivially shared; no new columns.
- **Module/session-scoped fixture that attaches.** Only the first consumer records the fixture
  subtree, so later cases read as structure divergence: blank cells plus the existing lint
  finding. Surfaced, not fixed — that belongs to the fixture-scope design.

## Attachment icon

Independent of the merge work, and touching the same surfaces. The HTML report's paperclip SVG
and the Markdown renderer's `📎` are replaced by an icon chosen from `content_type`: a document
glyph for `text`, braces for `json` — a branch in the macro plus a second inline SVG, no new
data. The badge then says what it will expand into before it is clicked.

## Markdown rendering

Columns render as table columns like any other. Attachment cells follow the split
`_attachment_lines` already uses: short single-line content sits inline in the cell in
backticks; multiline or backtick-bearing content shows the label in the cell and renders fenced
below the table, keyed by the case's parametrize values.

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

The case row gains a cell per new column. Attachment cells render the badge with that case's
label and expand their content in place, reusing the `expandedAttachments` Alpine state and the
`grid-rows` expand already used by step attachments. `derived` columns are not visually
distinguished from `param` columns in v1.

The [row-hover value preview](../2026-06-28-row-hover-value-preview-design.md) is live, and this
design silently extends it to two new column kinds. Three things need care:

- **`data-param` carries the column `id`, not its name** (see
  [Column identity](#column-identity)). `setHoverParam` (`app.js:258-266`) and `setHoverRow`
  (`app.js:267-282`) both match on the attribute value, so keying on `id` fixes the cross-wiring
  with no JS change — only the three emission sites (`report.html.j2:258` and `:271`,
  `html_renderer.py:263`) change.
- **Row-hover substitution needs its own attribute at both ends.** `setHoverRow` reads every
  `td[data-param]` in the row and writes into every `span[data-param]` in the `.scenario` scope
  — the attribute the highlight also keys on, so neither end can be filtered by dropping it.
  Both over-reach as written: an attachment cell's `textContent` is its badge label plus any
  expanded content, and the badge is itself a `span[data-param]` whose `textContent` assignment
  would destroy the inline SVG irrecoverably (`clearHoverRow` restores text only). Give
  substitution a dedicated pair — a value attribute on `param`/`derived` cells only, a slot
  attribute on narration placeholders only — leaving `data-param` purely for the highlight. No
  attachment cell then feeds a substitution and the badge is never a target, so its SVG is never
  touched. (Headers stay out of it: labels are flat and shared, so no header is narrated.)
- **Palette scope.** `_build_param_color_map` (`html_renderer.py:167-177`) assigns a colour per
  name across the report. `derived` columns join it; `attachment` columns do not — a badge needs
  no value colour.

## Implementation touch points

| file | change |
|---|---|
| `src/pytest_given/model/schema.py` | `ParameterColumn` (`id`, `name`, `kind`); `ParameterTable.columns` replaces `names`; `CellValue = ParamValue \| Attachment` replaces `ParameterCase.values: list[Any]` |
| `src/pytest_given/model/serde.py` | round-trip for the new shape, with object-vs-scalar cell discrimination |
| `src/pytest_given/capture/decorators.py` | `attach(label: str, content)`; the `Template` rejection and the t-string flattening at `438-439` collapse into one non-`str` guard |
| `src/pytest_given/plugin.py` | passed-case baseline; rejected-form validation on every session, caught in `pytest_sessionfinish` so a violation suppresses every sink and fails the run; cross-case comparison; column construction; `_templatize_narration` promotes varying `rendered` to placeholders; `ParamSpec` carries raw values for rule 3; `_param_value` unwraps a term instance to its display |
| `src/pytest_given/report/coverage.py`, `report/aggregations.py` | a param-linked pill resolves per case from its column: match coverage once per case and union the matches; collect one `TermInstance` per case display |
| `src/pytest_given/report/html_renderer.py`, `templates/report.html.j2`, `templates/styles.css`, `templates/app.js` | column loop, attachment cells, `content_type` icons, `data-param` keyed on column `id`, dedicated substitution attributes for cells and narration slots, palette excludes attachment columns |
| `src/pytest_given/report/md_renderer.py` | column loop, attachment cells and below-table blocks, icon |
| `examples/coffeeshop/test_coffeeshop.py` | a parametrized scenario that both attaches and narrates a derived local |
| `src/pytest_given/skills_data/pytest-given-navigating/references/report-json.md` | new `parameters` shape and `jq` recipes |
| `src/pytest_given/skills_data/pytest-given-authoring/references/scenarios.md`, `references/api.md` | in a parametrized scenario, a varying `str` narration (f-strings included), a varying compound interpolation and a varying `attach` label are now errors, not caveats; `attach` takes a `str` label |
| `README.md` | `attach(label, content)` — the label is a plain `str`; t-strings are rejected |
| `CHANGELOG.md` | seven `## [Unreleased]` entries (see below) |

No lint changes. The rules this design displaces move into the merge rather than into the
catalog; what that implies for `divergent-case-structure` is settled under
[Out of scope](#out-of-scope).

This lands as seven user-facing changes, each needing its own `## [Unreleased]` entry in the
commit that makes it (per AGENTS.md), four of them breaking:

- **Changed (breaking).** `parameters.names` becomes `parameters.columns` (each column an
  `id`/`name`/`kind`) and cells widen to scalar-or-attachment. Affects anything reading the JSON
  report, including the `jq` recipes in the navigating skill.
- **Added.** Attachments and derived values that vary across parametrize cases now render as
  columns instead of being dropped or frozen to the first case.
- **Changed (breaking).** In a parametrized scenario, a `str` narration whose value varies
  across cases (typically an f-string), a t-string interpolating anything but a bare name
  (`t"{cup_size * 0.01}"`, `t"{m.balance}"`) whose value varies, a glossary term ref whose pill
  differs between cases (unless the pill is a parametrize value itself), and an `attach` label
  that differs between cases now raise `PytestGivenError`; the run fails and writes no report.
  Suites hitting any of them were already getting a wrong one.
- **Fixed (breaking).** A t-string interpolating a rebound parametrize name rendered the
  *parameter's* value rather than the narrated one, wrong for every case. It now raises rather
  than rendering a false value.
- **Changed (breaking).** `attach` takes a plain `str` label; a t-string label now raises
  instead of being silently flattened to the same text. Use an f-string —
  `attach(f"{flavor} log", …)`.
- **Changed.** Attachment badges show an icon derived from the attachment's content type instead
  of a paperclip, in both the HTML and Markdown reports.
- **Fixed.** Parametrizing over a glossary term instance
  (`@pytest.mark.parametrize('guest', [pg['Guest']('Alice'), …])`) stored a dataclass repr of the
  whole glossary in the parameter table; the column now holds the display, and activity coverage
  and the Glossary view see every case's instance rather than the first case's.

The project is pre-1.0, so these ride a minor bump rather than a major one.

## Verification

- Unit: merge comparison (shared stays inline; varying promotes; identical-content attachments
  do not promote), passed-case baseline, divergent-structure blanks, schema round-trip, Markdown
  short/long split.
- Unit: all five rejected forms raise, with the file/line and fix in the message; none fires
  when the text happens to be constant across cases — including a term ref whose
  `(term_id, display)` is identical in every case, which stays an inline pill.
- Unit: rule 3 does *not* fire for a faithful interpolation carrying a conversion or format spec
  (`t"{cup_size!r:>8}"`), including over a non-scalar parameter (`t"{when:%Y}"` on a `datetime`)
  — the case that needs the raw value rather than the coerced cell.
- Unit: a term ref bound to a parametrize column does not raise; its cell holds the display
  rather than a repr; coverage of an activity anchored on a *non-baseline* case's instance is
  found; the Glossary view lists every case's instance; and an activity whose refs are satisfied
  only by mixing two cases' displays is **not** matched.
- Unit: an attachment whose content varies but whose label is shared becomes a column headed by
  that label, with the badge keeping it; a byte-identical attachment stays inline and makes no
  column; `attach` rejects t-string and `Template` labels through the one guard (replacing
  today's eager-render test).
- Unit: two same-named `derived` columns in one scenario get distinct `id`s, and a generated id
  never collides with a parametrize name.
- Integration: a parametrized scenario with an attachment and a derived local, asserted through
  `--given-json`; and a violating suite that writes no JSON, HTML or Markdown sink, exits
  non-zero with the message in the terminal summary and no escaped traceback, and fails the same
  way with no sink flag at all.
- `uv run nox -s examples` and `-s self_report`, reading the `.md` diff first. Only parametrized
  scenarios that attach or narrate a varying value should move.
- Playwright for the template work: console clean after init, then drive cell expand, the
  tree-badge → column hover highlight, and row hover — confirming that `param`/`derived` slots
  fill from the hovered case and that attachment badges, icons included, are left alone. Per
  AGENTS.md this is not TDD'd and gets no markup-pinning Python tests.

## Out of scope

- `@scenario(group_parametrized=False)` (TODO). This shrinks its remit but does not retire it:
  varying *structure* still has no honest merged rendering, and the opt-out remains the answer
  there.
- **`divergent-case-structure` stays a lint rule**, deferred to that same TODO — now the last
  member of the family behind an opt-in check, so with `given_lint` off a scenario whose cases
  branch differently still renders the baseline's tree and says nothing. Unlike the five rejected
  forms it has no one-line fix: the cases genuinely differ and no merged view can represent them.
  The graceful answer is to decline the merge and emit one scenario per case — the same opt-out,
  applied automatically — and that decision belongs with the opt-out.
- Substituting a param-linked term pill on row hover.
- Distinguishing `derived` from `param` columns visually.
- Fixing session/module-scoped fixture attachment recording.
