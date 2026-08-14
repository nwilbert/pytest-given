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
| `attachment` — an attachment whose content or content type varies (its label may not) | dropped | `AttachmentRef` badge keeps its label on its step + column |

An attachment that is byte-identical across every case is shared structure and stays inline
on its step. Same for a `NarrationValue` whose rendered text is identical everywhere —
today's behaviour, now verified instead of assumed.

Attachments live inside steps, sometimes nested; the badge keeps that position in the merged
tree, tied to its column by the existing `data-param` hover highlight, exactly as a
`{cup_size}` placeholder is. The tree says *where*, the table says *what* — and it says it
only once, since a promoted badge carries no content of its own (see [Schema](#schema)).

### Column identity

A column is identified by its **position in the step tree**, not by its name, and carries
that identity as an `id`; the expression supplies the display `name` only. Two steps can
interpolate the same expression — `{price}` in a `when` and again in a `then` — with
different values, which would collide if the expression were the key, cross-wiring a frontend
that matches on `data-param`.

A `param` column uses its parametrize name as both. Generated ids are `derived:0`,
`derived:1`, … and `attachment:0`, `attachment:1`, … numbered per kind in emission order. The
colon makes them **unable** to collide with a parametrize name rather than merely unlikely to:
parametrize names are `callspec.params` keys, so they are always Python identifiers, and no
identifier contains a colon. That is the whole collision story — no suffixing, no retry, no
rule to test. The value only ever reaches JSON, an HTML attribute and `CSS.escape`
(`app.js:263`), all of which take a colon; it is never compiled as an expression, since
`setHoverParam` reads `$el.dataset.param` rather than being handed an interpolated string.

The tree carries the id at both promotion sites: `NarrationPlaceholder.column_id` for a
`derived` value, `AttachmentRef.column_id` for an attachment. Both are always populated —
for a `param` column the id is the parametrize name, so the field restates it rather than
going null and making every reader write `column_id or name`.

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
column exists because the *content* varies; the name of that payload does not.

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
  it `Bob` never appears under `Guest` in the Glossary view.

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

**Which cases a rule sees.** Rules 1, 2, 4 and 5 compare cases against each other, and do so
only across passed cases whose step structure matches the baseline's (see
[Merge algorithm](#merge-algorithm)). A case that branched differently is positionally
incomparable, so comparing it would report structural divergence as a narration defect —
`[given, when, then]` against `[given, given, when, then]` lines a `when` up with a `given`
and raises rule 1 about two unrelated steps. Divergence stays lint's business, and such a
case is excluded from validation exactly as it is excluded from cell-filling. Rule 3 is the
exception: it compares a case against its own parameter values rather than against another
case, so structure is irrelevant and it applies to every passed case.

Validation runs on **every** session, not only when a sink was requested: these are usage
errors, and the plugin already treats malformed narration as one —
`pytest_collection_modifyitems` raises for a bad `Template` placeholder whether or not a
report was asked for (`plugin.py:289-295`). Gating the merge rules on flags would make
whether your suite is well-formed depend on which ones you passed. The existing
unknown-placeholder guard in `_templatize_narration` (`plugin.py:943-949`) therefore stays
put, and the merge stays a path that can raise.

Nothing may escape the hook, though: an exception leaving `pytest_sessionfinish` is neither a
test failure nor an INTERNALERROR — on pytest 9.0.3 it propagates out of `console_main` as a
bare traceback after the progress line, no summary and exit 1, indistinguishable from an
ordinary failing run. So `pytest_sessionfinish` catches the raise, records the message for
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

   The displayed value has one source of truth, the **cell**: `rendered` is discarded on a
   param match, `_placeholder_token` renders the merged slot as a schematic `{cup_size}` with
   conversion and spec deliberately dropped, and row hover substitutes the cell's own text —
   so `rendered` is never displayed for a param placeholder, only used as evidence. Per case,
   then: apply the interpolation's own `conversion` and `format_spec` to that case's
   parameter value and compare with `rendered`. Agreement keeps today's placeholder path;
   disagreement raises.

   > `PytestGivenError: 'cup_size' in 'test_brew' matches a parametrize column but narrates a different value (case [200] narrates '400') — rebinding a parameter name makes the narration ambiguous. Rename the local.`

   That re-format runs on the **raw** parameter object, never on a coerced one:
   `t"{when:%Y}"` on a `datetime` compared against the string `'2026-01-01 00:00:00'` would
   evaluate `format('2026-01-01 00:00:00', '%Y')` — `ValueError: Invalid format specifier` —
   and `t"{when!r}"` would compare the datetime's repr against the *string's*, accusing a
   faithful interpolation of rebinding. Re-formatting the raw object is exactly what the
   t-string did at capture time, so a faithful interpolation agrees for every type,
   `t"{cup_size!r:>8}"` included.

   So **`_param_value` moves to where cells are built**, and `ParamSpec.values` holds what
   `callspec.params` gave. Today the coercion runs at setup (`plugin.py:350`) and the raw
   object is dropped on the spot, which would force `ParamSpec` to carry both forms; coercing
   in `_group_parametrized` instead keeps one representation and puts the conversion at the
   boundary that needs it — the serializable cell — beside the term-instance unwrap, which
   has to happen there anyway. No new field, and nothing changes for the two sites that
   unpack the `NamedTuple`. `ParamSpec.values` does weaken from `list[ParamValue]` to a
   `RawParamValue` alias over `object`, which is the honest type for an arbitrary parametrize
   argument. Nothing is retained that was not already: pytest holds `item.callspec.params` on
   `session.items` until the session ends regardless.

   Being a per-case check rather than a comparison, this rule fires where no other can: a
   single passed case is enough, so `@pytest.mark.parametrize('cup_size', [200])` still
   catches the rebinding. It runs on passed cases only, like every other rule — a failed
   case's tree may be truncated mid-step, and the merge trusts nothing else from it either.

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

5. **A step whose set of attachment labels differs across cases.** A label names its payload;
   the payload is what varies, and the row already says which case it belongs to.
   `attach(f"{flavor} log", …)` puts the parameter in the name instead of leaving it in the
   `flavor` column that is already there, and leaves the merged tree with a badge that can
   only be one case's. The fix is a constant label with the varying part in the content.
   Content and content type are exempt by design: varying those is exactly what the
   `attachment` column is for.

   The comparison is over the **distinct labels** at a step, because that is the key
   attachments merge on (see [Merge algorithm](#merge-algorithm)). A label attached a
   different *number* of times — a loop whose iteration count depends on the parameter —
   therefore does not raise: the occurrences become columns and the short case's trailing
   cells are blank. Matching by label rather than by position also means reordered `attach`
   calls are merged, not rejected.

   > `PytestGivenError: attachment label 'vanilla log' in 'test_brew' is attached in some parametrize cases but not others — a label names the payload and must read the same in every case. Use a constant label and let the content vary: attach("brew log", …).`

An error means the author can do better: every rule above carries a one-line fix that yields
a strictly better report. Where no such fix exists the merge copes instead of raising — a
pill bound to a parametrize column, and divergent structure (see
[Out of scope](#out-of-scope)). Together the rules also make promotion **total**: every
column is named by an identifier or a shared label by construction, so no `name` is nullable
and no renderer ever has to display raw source text or invent a header.

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
of matching structure only, so a group with fewer than two such cases cannot raise rules 1, 2,
4 or 5. Rule 3 is not a variance rule and is not bounded that way: it checks each passed case
against its own parameter values and fires on a single case.

**Why not lint.** `given_lint` defaults to `False` (`plugin.py:172-177`), so an error-severity
rule would enforce nothing for a default user and the report would go on lying quietly. The
check belongs where the merge already holds every case's tree.

### Compatibility

Rules 1 and 2 upgrade a documented caveat
(`docs/specs/2026-05-23-structured-step-text-design.md:302`, "renders the first case's value
across all cases. **Fix:** use a t-string") into a hard error, and fire only when the
narration genuinely varies — so the affected suites are exactly those already getting a wrong
report. Rules 3, 4 and 5 have the same character: a rebound parameter name, a per-case term
pill and a per-case attachment label all render wrong today, the last worst of all since
every non-baseline attachment is dropped outright. No rule here breaks code that produces a
correct report.

## Schema

`ParameterTable.names: list[str]` becomes `columns: list[ParameterColumn]`, and a case's
`values` stays positionally aligned with it. Each column carries an `id` (what the DOM keys
on) as well as a display `name`; the two coincide for a `param` column (see
[Column identity](#column-identity)).

The widening is also the moment to stop `ParameterCase.values` being `list[Any]`
(`schema.py:284`). A cell's range is small and knowable — that is the point of the column
kinds — so a named type states the heterogeneity instead of hiding it, per AGENTS.md's
avoid-`Any` convention:

```python
type CellValue = ParamValue | Attachment   # ParamValue = str | int | float | bool | None
```

Cells are heterogeneous **by column kind**, deliberately: a `param` cell keeps the parametrize
value as captured, a `derived` cell carries the *rendered* string — already through the
interpolation's conversion and format spec, and no renderer re-formats it — and an
`attachment` cell is an object, which is also how serde discriminates the two on read. `null`
marks a case with no value for that column (see [Edge cases](#edge-cases)).

`Attachment` itself is unchanged, so an attachment cell keeps the existing shape, and `name`
stays a plain `str` for every column kind.

```json
"parameters": {
  "columns": [
    {"id": "cup_size", "name": "cup_size", "kind": "param"},
    {"id": "derived:0", "name": "price", "kind": "derived"},
    {"id": "attachment:0", "name": "machine state", "kind": "attachment"}
  ],
  "cases": [
    {"values": [200, "2.0",
                {"label": "machine state", "content": "…", "content_type": "json"}],
     "status": "passed", "error": null}
  ]
}
```

One shape for all three kinds, so both renderers and downstream `jq` recipes loop a single
list instead of branching per kind.

The tree side gets three changes, all so a merged step stops speaking for a single case.

**`NarrationPlaceholder` gains `column_id: str`**, always populated (see
[Column identity](#column-identity)). `name` keeps supplying the `{price}` token and the
palette entry; `column_id` is what `_render_part` puts in `data-param`.

**A promoted attachment becomes an `AttachmentRef`**, and `Step.attachments` widens to
`list[Attachment | AttachmentRef]`:

```python
@dataclass(frozen=True)
class AttachmentRef:
    label: str
    content_type: ContentType   # describes the payload the badge points at
    column_id: str
```

The ref has no `content` field, so the merged tree cannot carry the baseline's payload —
without this the badge would still expand to case 1's blob, which is the defect this design
opens with, and the column would duplicate the payload rather than replace it. Payloads live
in cells; the tree holds pointers. Serde discriminates the two on the presence of `content`,
and the union gives the renderers an exhaustive `match` the way `NarrationPart` already does.
Only two sites read `step.attachments` (`md_renderer.py:110`, `report.html.j2:84`).

**A merged step's `narration.text` is rebuilt from its merged parts**, so it reads `the drink
costs {price} euros` rather than the baseline's `the drink costs 2.0 euros`. Today a merged
step's `text` is case 1's rendering even for `param` placeholders — coffeeshop ships
`"text": "I insert $1"` under parts that say `{euros}` — while a *scenario*'s `text` is
already documented as "the merged template for parametrized scenarios" (`report-json.md:16`).
Steps join scenarios. Both renderers prefer `parts` wherever they exist, so no HTML or
Markdown output moves; what changes is the JSON field and the wording of the three
`ast_rules` findings that interpolate it (`ast_rules.py:194,272,282`) — ignore entries match
on `finding.subject`, not the message, so no `given_lint_ignore` list breaks.

The step matching the table above reads:

```json
"steps": [{"narration": {"text": "the drink costs {price} euros",
                         "parts": [{"value": "the drink costs "},
                                   {"name": "price", "column_id": "derived:0"},
                                   {"value": " euros"}]},
           "attachments": [{"label": "machine state",
                            "content_type": "json", "column_id": "attachment:0"}]}]
```

This is a breaking change to the JSON report, riding along with the JSON-format polish already
on the TODO; report versioning is that item's job, not this one's.

## Merge algorithm

1. Group cases as today. Pick the baseline: first passed case, else `group[0]`.
2. Take the **comparable** cases: the passed ones whose structure signature equals the
   baseline's. Everything from here on compares only those; the rest are carried for their
   `param` cells alone.
3. Validate the rejected authoring forms — rules 1, 2, 4 and 5 across the comparable cases,
   rule 3 on each passed case against its own parameter values — and raise on any.
4. Walk the baseline step tree. At each position, compare against the same position in every
   other comparable case:
   - each `NarrationValue` whose `expression` is not a parametrize name — compare `rendered`;
   - each `NarrationTermRef` whose `expression` is not a parametrize name — compare
     `(term_id, display)`; any difference raises (rule 4) rather than promoting;
   - each attachment — paired **by label**, and by occurrence order among same-label ones —
     compare `(content, content_type)`.
5. Identical everywhere → leave inline. Otherwise → emit a column; a `derived` value's inline
   occurrence becomes a `NarrationPlaceholder`, and an attachment badge becomes an
   `AttachmentRef` in place, keeping the label that rule 5 guarantees every case shares. Any
   step whose parts now hold a placeholder — `param` ones included — has its `narration.text`
   rebuilt from those parts.
6. Fill each case's cells by reading the same positions — and, for attachments, the same
   labels — out of that case's own tree.

"The same position" is an index path, and the walk that produces one already exists twice:
`walk_steps` (`report/coverage.py:168`) yields `(index_path, step)`, `iter_steps`
(`lint/base.py:65`) yields the steps alone, and `report/` and `lint/` cannot import from each
other, so neither copy can go. The merge would be the third. A new **`model/steps.py`** owns
the walk instead — `model/` is the leaf all three already depend on, and `ids.py` is the
precedent for small pure helpers over the schema living there:

```python
type StepPath = tuple[int, ...]                              # a position in a step tree
def walk_steps(steps: list[Step]) -> Iterable[tuple[StepPath, Step]]: ...
def iter_steps(steps: list[Step]) -> Iterator[Step]: ...     # walk_steps, paths discarded
def structure_signature(steps: list[Step]) -> StepSignature: ...
```

`coverage.py` drops its copy, `lint/base.py` drops `iter_steps` and `runtime_rules.py` drops
`_structure_signature` (`:122-123`), the two lint rule modules import both from `..model`
instead of `.base`, and the merge indexes each case's tree into a `dict[StepPath, Step]` so
"compare against the same position" is a lookup rather than a parallel descent. `StepPath`
also gives the spec's positional language a name in the code.

Attachments key on label rather than position because rule 5 already guarantees the label set
is shared, which makes the key total, and because position does not survive a case attaching
the same labels in a different order or a different number of times. Parametrize columns are
emitted first, in their existing order, then `derived` and `attachment` columns in baseline
tree order — so the table still reads inputs-first.

## Edge cases

- **No case passed.** Nothing to compare; fall back to today's `group[0]` rendering.
- **A skipped or failed case.** It records no tree, or an aborted one, so step 6 finds nothing
  at those positions: its `derived` and `attachment` cells are `null` and render blank. Its
  `param` cells are unaffected.
- **Structure diverges.** The case is not comparable (step 2), so it is excluded from
  validation as well as from cell-filling: its `derived` and `attachment` cells are `null` and
  render blank, and it cannot raise a rule about a step the baseline lines up differently.
  `divergent-case-structure` already fires, so this introduces no new lint rule.
- **The same label attached a different number of times** (a loop whose iteration count
  depends on the parameter). Label sets still match, so rule 5 stays quiet; the occurrences
  become columns and the short case's trailing cells are blank.
- **Single-value parametrize.** Nothing to compare, so rules 1, 2, 4 and 5 cannot fire and no
  `derived` or `attachment` column is emitted — but rule 3 still checks that case's
  interpolations against its own parameter values.
- **Module/session-scoped fixture that attaches.** Only the first consumer records the fixture
  subtree, so later cases read as structure divergence: blank cells plus the existing lint
  finding. Surfaced, not fixed — that belongs to the fixture-scope design.

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

In the step tree, `_attachment_lines` gains a third branch: an `AttachmentRef` has no content
to inline or fence, so it renders as badge and label alone, pointing at the table.

```markdown
- **when** the machine brews {flavor}
  - 📎 machine state — *see case table*
```

## HTML rendering

The case row gains a cell per new column. Attachment cells render the badge with that case's
label and expand their content in place, reusing the `expandedAttachments` Alpine state and the
`grid-rows` expand already used by step attachments. `derived` columns are not visually
distinguished from `param` columns in v1.

In the step tree an `AttachmentRef` renders as badge, label and `data-param`, with **no
expander and no `expandedAttachments` key** — there is nothing to expand, and the highlight it
lights up is the column holding every case's payload. `expandedAttachments` stays the state of
real `Attachment`s: the ones inline on a step because they were byte-identical everywhere, and
the ones in case cells.

The [row-hover value preview](../2026-06-28-row-hover-value-preview-design.md) is live, and this
design silently extends it to two new column kinds. Three things need care:

- **`data-param` carries the column `id`, not its name** (see
  [Column identity](#column-identity)). `setHoverParam` (`app.js:258-266`) and `setHoverRow`
  (`app.js:267-282`) both match on the attribute value, so keying on `id` fixes the cross-wiring
  with no JS change — only the three emission sites (`report.html.j2:258` and `:271`,
  `html_renderer.py:263`) change.
- **Row-hover substitution needs its own attribute.** `setHoverRow` reads every
  `td[data-param]` in the row and writes into every `span[data-param]` in the `.scenario` scope
  — the attribute the highlight also keys on, so neither end can be filtered by dropping it.
  Both over-reach as written: an attachment cell's `textContent` is its badge label plus any
  expanded content, and the badge is itself a `span[data-param]` whose `textContent` assignment
  would destroy the inline SVG irrecoverably (`clearHoverRow` restores text only). Give
  substitution one attribute of its own — `data-subst`, carrying the column id — on
  `param`/`derived` cells and on narration placeholders, and nowhere else; `data-param` is then
  purely the highlight's. One name suffices for both ends because `setHoverRow` already tells
  source from target by element type, reading `td[…]` and writing `span[…]` (`app.js:271-274`):
  the selectors change, the function's shape does not. No attachment cell feeds a substitution
  and the badge is never a target, so its SVG is never in reach.
- **Palette scope.** `_build_param_color_map` (`html_renderer.py:167-177`) assigns a colour per
  name across the report. `derived` columns join it; `attachment` columns do not — a badge needs
  no value colour.

## Implementation touch points

| file | change |
|---|---|
| `src/pytest_given/model/schema.py` | `ParameterColumn` (`id`, `name`, `kind`); `ParameterTable.columns` replaces `names`; `CellValue = ParamValue \| Attachment` replaces `ParameterCase.values: list[Any]`; `NarrationPlaceholder.column_id`; `AttachmentRef` and the `Step.attachments` widening |
| `src/pytest_given/model/steps.py` (new) | `StepPath`, `walk_steps`, `iter_steps`, `structure_signature` — one depth-first walk for the three packages that each need one |
| `src/pytest_given/model/serde.py` | round-trip for the new shapes: object-vs-scalar cell discrimination, `AttachmentRef` vs `Attachment` on the presence of `content`, `column_id` on placeholders |
| `src/pytest_given/capture/decorators.py` | `attach(label: str, content)`; the `Template` rejection and the t-string flattening at `438-439` collapse into one non-`str` guard |
| `src/pytest_given/plugin.py` | passed-case baseline; comparable-case filter on the structure signature; rejected-form validation on every session, caught in `pytest_sessionfinish` so a violation suppresses every sink and fails the run; cross-case comparison, label-keyed for attachments; column construction; `_templatize_narration` promotes varying `rendered` to placeholders and rebuilds `narration.text`; `_param_value` moves here from setup so `ParamSpec` keeps the raw parameter objects rule 3 needs, and unwraps a term instance to its display on the way into a cell |
| `src/pytest_given/lint/base.py`, `lint/runtime_rules.py`, `lint/ast_rules.py` | `iter_steps` and `_structure_signature` deleted in favour of `model/steps.py`; the two rule modules import from `..model` instead of `.base` — no rule change |
| `src/pytest_given/report/coverage.py`, `report/aggregations.py` | `walk_steps` deleted in favour of `model/steps.py`; a param-linked pill resolves per case from its column: match coverage once per case and union the matches; collect one `TermInstance` per case display |
| `src/pytest_given/report/html_renderer.py`, `templates/report.html.j2`, `templates/styles.css`, `templates/app.js` | column loop, attachment cells, `data-param` keyed on column `id` (from `column_id` in the tree), `AttachmentRef` badges with no expander, `data-subst` on cells and narration slots, palette excludes attachment columns |
| `src/pytest_given/report/md_renderer.py` | column loop, attachment cells and below-table blocks, `AttachmentRef` branch in `_attachment_lines` |
| `examples/coffeeshop/test_coffeeshop.py` | a parametrized scenario that both attaches and narrates a derived local |
| `GLOSSARY.md` | *Parameter table* is defined as "column names + cases" and needs the column kinds; *Value highlight* is defined around interpolations that don't match a parametrize column, now true only when they are constant across cases. Per AGENTS.md a glossary edit pulls in `uv run nox -s self_report` |
| `src/pytest_given/skills_data/pytest-given-navigating/references/report-json.md` | new `parameters` shape, placeholder and attachment part shapes, merged step `text`, and `jq` recipes |
| `src/pytest_given/skills_data/pytest-given-authoring/references/scenarios.md`, `references/api.md` | in a parametrized scenario, a varying `str` narration (f-strings included), a varying compound interpolation and a varying `attach` label are now errors, not caveats; `attach` takes a `str` label |
| `README.md` | `attach(label, content)` — the label is a plain `str`; t-strings are rejected |
| `CHANGELOG.md` | seven `## [Unreleased]` entries (see below) |

No lint rule changes: every rule keeps its behaviour and the catalog is untouched — the lint
package only stops owning two tree helpers it was never the sole user of. The rules this
design displaces move into the merge rather than into the catalog; what that implies for
`divergent-case-structure` is settled under [Out of scope](#out-of-scope).

This lands as seven user-facing changes, each needing its own `## [Unreleased]` entry in the
commit that makes it (per AGENTS.md), five of them breaking:

- **Changed (breaking).** `parameters.names` becomes `parameters.columns` (each column an
  `id`/`name`/`kind`) and cells widen to scalar-or-attachment. Placeholder parts gain
  `column_id`, and a promoted attachment appears in the step tree as a content-less reference
  to its column. Affects anything reading the JSON report, including the `jq` recipes in the
  navigating skill.
- **Changed (breaking).** A merged parametrized scenario's step `narration.text` is now the
  template (`the drink costs {price} euros`) rather than the first case's rendering (`the
  drink costs 2.0 euros`), matching what the scenario's own `narration.text` has always done.
  HTML and Markdown output is unchanged; this is visible to JSON readers only.
- **Added.** Attachments and derived values that vary across parametrize cases now render as
  columns instead of being dropped or frozen to the first case.
- **Changed (breaking).** In a parametrized scenario, a `str` narration whose value varies
  across cases (typically an f-string), a t-string interpolating anything but a bare name
  (`t"{cup_size * 0.01}"`, `t"{m.balance}"`) whose value varies, a glossary term ref whose pill
  differs between cases (unless the pill is a parametrize value itself), and a step whose set of
  `attach` labels differs between cases now raise `PytestGivenError`; the run fails and writes
  no report. Suites hitting any of them were already getting a wrong one.
- **Fixed (breaking).** A t-string interpolating a rebound parametrize name rendered the
  *parameter's* value rather than the narrated one, wrong for every case. It now raises rather
  than rendering a false value.
- **Changed (breaking).** `attach` takes a plain `str` label; a t-string label now raises
  instead of being silently flattened to the same text. Use an f-string —
  `attach(f"{flavor} log", …)`.
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
  that label; the badge left on the step is an `AttachmentRef` carrying **no content** — the
  guard against re-introducing the defect this design opens with — and a byte-identical
  attachment stays an inline `Attachment` and makes no column; `attach` rejects t-string and
  `Template` labels through the one guard (replacing today's eager-render test).
- Unit: label-keyed attachment merging — a step attaching the same labels in a different order
  merges rather than raising; the same label attached a different number of times yields
  columns with blank trailing cells and no error; a label present in one case only raises rule
  5 naming that label.
- Unit: a structurally divergent case raises nothing — in particular a shifted tree that lines
  a `when` up against a `given` gets blank cells and the existing lint finding, not rule 1.
- Unit: rule 3 fires on a single-case parametrize, where no comparison rule can.
- Unit: a merged step's `narration.text` is the template, and matches what the parts render.
- Unit: two same-named `derived` columns in one scenario get distinct `id`s and each
  placeholder carries its own `column_id`, so hovering one row substitutes both independently.
  (Nothing tests id collision — the colon makes it unreachable.)
- Integration: a parametrized scenario with an attachment and a derived local, asserted through
  `--given-json`; and a violating suite that writes no JSON, HTML or Markdown sink, exits
  non-zero with the message in the terminal summary and no escaped traceback, and fails the same
  way with no sink flag at all.
- `uv run nox -s examples` and `-s self_report`, reading the `.md` diff first. Only parametrized
  scenarios that attach or narrate a varying value should move.
- Playwright for the template work: console clean after init, then drive cell expand, the
  tree-badge → column hover highlight, and row hover — confirming that `param`/`derived` slots
  fill from the hovered case, that attachment badges are left alone, and that a promoted tree
  badge highlights its column without offering an expander. Per AGENTS.md this is not TDD'd
  and gets no markup-pinning Python tests.

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
