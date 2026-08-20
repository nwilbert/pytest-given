# Opting out of parametrize merging — Design Spec

## Problem

Grouping collapses the N scenario records of a parametrized test into one narrated tree plus
a case table (`grouping/`). The tree is one case's — the baseline's — and every column the
[per-case columns work](2026-08-14-parametrized-case-columns-design.md) added exists to carry
what *varies between* cases: a parameter value, a narrated derived value, an attachment
payload. What no column can carry is a case that narrates a **different sentence**, or a
different tree of them. There the grouped view stops being a summary and becomes a false
statement about every case but one.

Four authoring shapes reach that state, and today none of them fails the run:

1. **Cases branch into different step trees.** `divergent-case-structure` reports it, but only
   at `warn` severity and only when `given_lint` is on, which it is not by default. The case
   drops out of `_comparable`, its generated cells go blank, and the report renders the
   baseline's tree with a `≠` beside the row.
2. **Same structure, differently-shaped narration.** `structure_signature` compares
   `(phase, children)`, so `when(t"{n} items load" if n else "nothing loads")` leaves both
   cases comparable while their part lists are laid out differently. The baseline walk then
   indexes part-by-part into a sentence that is not shaped the same way, and either raises
   rule 1 with the wrong diagnosis or promotes a `derived` column standing in for a sentence
   the other case never narrated.
3. **Same shape, different literal text.** `t"{n} items load"` against `t"{n} things break"`:
   identical part kinds, so nothing compares the literals and the baseline's words are shown
   for every row. Rule 1 does not see it — that rule fires only on a `str` narration, whose
   `parts` are empty.
4. **Same index, different expression.** Two cases interpolating different locals at the same
   slot promote a `derived` column named for the baseline's expression, pointing the reader at
   a local the other case never narrated.

Shapes 2–4 were deferred from the per-case columns spec with the note that all of them want
the same treatment — *refuse to merge and emit one scenario per case* — which only exists once
the opt-out does.

The opt-out is also the missing consumer for machinery that is already built. A `Template`
scenario name records its placeholders and is rendered in the grouped title as `{cup_size}`
tokens; nothing in the product ever substitutes a case's values into them. The same holds for
the `Annotated[..., given(Template('a {cup_size} ml cup'))]` step label, which reaches
grouping as a `NarrationPlaceholder` for the case table to fill on hover.

## Goal

`@scenario(..., group_parametrized=False)` declines the merge: each case becomes its own
scenario, named for its own values and narrating its own tree.

With that answer available, the merge stops lying. All four shapes above become a rejected
form — a single rule with a single fix — and `divergent-case-structure` retires along with
the `divergent` machinery that existed to render its aftermath.

## Behavior

### The flag

```python
@scenario('Brew coffee', group_parametrized=False)
@pytest.mark.parametrize('cup_size', [200, 300])
def test_brew(cup_size): ...
```

Keyword-only, `bool`, default `True`. It is a property of the scenario, not of a case, so it
is read once per item in `pytest_runtest_setup` and travels to the grouping pass on the
`ParamSpec` that pass already reads (`ParamSpec.group: bool = True`) — `param_info` is
runtime-only and never serialized, so this adds nothing to the report schema and leaves
`group_parametrized(scenarios, param_info)` a two-argument function.

**On a non-parametrized test it raises at collection**, in the `pytest_collection_modifyitems`
hook that already rejects a `Template` name on a non-parametrized test:

> `@scenario(group_parametrized=False) on '<nodeid>' has nothing to opt out of; the test is
> not parametrized. Drop the argument, or add @pytest.mark.parametrize.`

Same hook, same reason as its neighbour: a flag that quietly does nothing hides a
misunderstanding, and collection time is the only point where marker order is settled.

### What a case scenario is

An ordinary `Scenario`. It keeps the node id it was recorded under (`test_brew[200]`; a
grouped scenario already keeps `group[0]`'s id, parametrize tail included, so a per-case id is
nothing new downstream), its own `status`, `duration_ms`, `steps`, `source`, `story_id` and
`activity_ids`, and it carries **no `ParameterTable`**. Parameter values reach the reader through the substituted
name, the substituted step narrations, and the parametrize id in the title — not through a
one-row table, which would be a comparison of a single thing against nothing.

None of the five rejected-form checks run on an opted-out group. Each exists to protect a
merged tree from misrepresenting its cases; with no merge there is nothing to misrepresent,
including rule 3, whose per-case comparison is against a cell that is never built.

### Substitution

One function, applied to the scenario narration and recursively to every step narration:
each `NarrationPlaceholder` becomes the `NarrationValue` that case's parameters render, via
the shared `render_interpolation` (so `{n:03d}` and `{obj!r}` behave exactly as they do in a
t-string), and `text` is rebuilt from the resulting parts. A placeholder naming no parameter
raises the existing `placeholder_mismatch` — the same error the grouped path raises, though
`pytest_collection_modifyitems` has already caught the `@scenario` case before any test runs.

Note that this works on the **recorded** `Narration`, not on the `Template` object:
`narration_from` already turned a `Template` name into `text='Brew {cup_size} ml'` plus
placeholder parts at `start_scenario`. So the scenario name and the `Annotated` step label go
through the identical code path, and `Template.substitute` stays what it is today — the
helper-decorator's call-time renderer.

### Naming

| name form | per-case name |
|---|---|
| `Template('Brew {cup_size} ml')` | `Brew 200 ml` — substituted as above |
| `'Brew coffee'` | `Brew coffee [200-oat]` — `case_suffix(scenario.id)` appended |
| `t'{pg["Barista"]} brews'` | `Barista brews [200-oat]` — suffix appended as a trailing `NarrationLiteral`, so the pill survives |

A `Template` naming only some columns can render the same name twice — `Brew {cup_size} ml`
over `(cup_size, milk)` gives `Brew 200 ml` for both `200-oat` and `200-soy`. When any two
substituted names in a group collide, **every** case in that group takes the id suffix. Two
scenarios that look identical in the browse list are the failure worth avoiding; a title
suffixed on some rows and not others reads as a bug, so the group is treated uniformly.

## Rule 6: every passed case must narrate the same template

The invariant the merge needs, stated once:

> A grouped scenario's passed cases must narrate the *same template*, differing only in what
> a column can carry.

Concretely, the signature compared across cases is `structure_signature(steps)` — unchanged —
plus, per step, the shape of its narration parts:

| part | contributes |
|---|---|
| `NarrationLiteral` | `('lit', value)` — the literal text, which is what shape 3 varies |
| `NarrationValue` | `('val', expression, conversion, format_spec)` — never `rendered`, which is exactly what grouping promotes |
| `NarrationPlaceholder` | `('ph', name, conversion, format_spec)` |
| `NarrationTermRef` | `('term', expression)` — not `display`, which rule 4 governs and which a param-bound pill varies by design |

A `str` narration contributes an empty part list in every case, so rule 6 stays silent on it
and **rule 1 keeps its own better diagnosis** ("a plain str bakes case 1's values"). The two
rules do not overlap.

**When it fires.** Over the passed cases only — a skipped case records no steps and a failed
one may abort mid-tree, so neither can be held to the baseline's shape. Fewer than two passed
cases means nothing to compare, exactly as the retiring lint rule had it. It runs **first** in
`_grouped_scenario`, before the other checks and before the baseline walk: shape 2's whole
problem is that a later rule reaches it first and misdiagnoses it.

**Message.** Through `grouping_error`, so it is located like every other rejected form,
naming the diverging case and the fix:

> `case [300-soy] of 'test_brew' narrates a different step structure than case [200-oat] — a
> grouped scenario renders one tree for every row, so the cases cannot be merged honestly. Use
> @scenario(..., group_parametrized=False) to emit one scenario per case.`

with the first clause varying by what actually differs (step structure / a differently-shaped
narration / different wording / a different interpolated expression), since that is what tells
the author where to look.

### What this retires

- **`_comparable` collapses.** Every passed case is comparable by construction once rule 6
  holds, so the filter becomes "the passed cases" and `structure_signature`'s use there goes
  with it (rule 6 still uses it).
- **`ParameterCase.divergent`** can no longer be `True`. The field leaves the schema, the `≠`
  marker leaves `report.html.j2` and `.case-divergent` leaves `styles.css`,
  `_case_divergence_note` leaves the Markdown renderer, and `coverage.py`'s
  `passed and not divergent` collapses to `passed`. `serde.py` keeps reading the key through
  its existing `d.get('divergent', False)` default, so a saved report still loads; a JSON
  consumer reading the field does not, which makes it a breaking entry.
- **`divergent-case-structure`** leaves the lint catalog (`lint/base.py`),
  `_divergent_case_findings` leaves `runtime_rules.py`, and with it the last reason
  `run_runtime_rules` takes the pre-grouping per-case list. **This breaks configs**: an
  existing `given_lint_rules` or `given_lint_ignore` entry naming the rule raises `ValueError`
  from `lint/config.py` ("unknown rule"). That is the right loudness — the rule's subject now
  fails the run outright — but it needs its own migration line in the changelog.

## Edge cases

- **A group where no case passed.** Rule 6 never fires; the existing `_baseline` fallback
  (first case with steps) still renders. Unchanged.
- **A single-case parametrize with the flag set.** One scenario out, named by substitution or
  suffixed with its id. No collision possible, no rule 6.
- **`indirect=True`.** Substitution reads `ParamSpec.values`, which `_capture_param_spec`
  already snapshots from `item.funcargs` — the value the test actually saw, which is what the
  narration rendered.
- **A failed or skipped opted-out case.** Emitted like any other scenario, carrying its error
  or skip reason. Where the grouped view showed one row of a table, the report now shows one
  failing scenario — strictly more legible.
- **Nested pytester sessions.** `param_info` is cleared in `pytest_sessionfinish`'s `finally`
  either way; the new `ParamSpec` field rides along and needs nothing added.

## Implementation touch points

| file | change |
|---|---|
| `src/pytest_given/capture/decorators.py` | `scenario(..., group_parametrized: bool = True)`; the flag stored on `ScenarioDecorator` |
| `src/pytest_given/model/schema.py` | `ParamSpec.group: bool = True`; `ParameterCase.divergent` removed |
| `src/pytest_given/model/serde.py` | stop writing `divergent`; keep tolerating it on read |
| `src/pytest_given/plugin.py` | collection-time rejection of the flag on a non-parametrized test; `_capture_param_spec` reads the marker and sets `ParamSpec.group`; `_run_lint` and `run_runtime_rules` drop their `per_case` parameter, and `pytest_sessionfinish` stops passing `collector.scenarios` alongside the grouped list |
| `src/pytest_given/grouping/group.py` | route opted-out groups to the per-case path; `_comparable` collapses to the passed cases; `divergent=` drops out of `ParameterCase` construction |
| `src/pytest_given/grouping/percase.py` (new) | placeholder substitution over a scenario's narration and step tree, per-case naming, group-wide collision suffixing |
| `src/pytest_given/grouping/templatize.py` | `_text_from_parts` shared out as `text_from_parts` for the new module |
| `src/pytest_given/grouping/checks.py` | rule 6: `check_same_template`, plus the narration-shape signature |
| `src/pytest_given/lint/base.py`, `lint/runtime_rules.py` | `divergent-case-structure` and `_divergent_case_findings` removed |
| `src/pytest_given/report/coverage.py`, `md_renderer.py`, `templates/report.html.j2`, `templates/styles.css` | the `divergent` exclusion, note, marker and its CSS removed |
| `GLOSSARY.md` | *Group* gains the opt-out; *Templatize* says "every comparable case" where cases can no longer diverge; *Case* is unchanged. Per AGENTS.md a glossary edit pulls in `uv run nox -s self_report` |
| `README.md` | the parametrize section documents the flag and per-case naming; the `divergent-case-structure` row leaves the lint table |
| `src/pytest_given/skills_data/pytest-given-authoring/references/api.md`, `references/scenarios.md` | the flag; divergence as a rejected form rather than a lint rule; the rule list in "Mechanical counterparts". Resync with `uv run pytest-given skills install` |
| `src/pytest_given/skills_data/pytest-given-navigating/references/report-json.md` | `divergent` gone from the case shape |
| `examples/` | a parametrized scenario that opts out, so the behaviour is visible in a rendered report |
| `tests/**` | a self-report scenario stating the rule (AGENTS.md: new user-facing behaviour needs a scenario, not just a test) |
| `CHANGELOG.md` | see below |

Four `## [Unreleased]` entries, three of them breaking:

- **Added.** `@scenario(group_parametrized=False)` emits one scenario per parametrize case,
  named by `Template` substitution or by its parametrize id.
- **Changed (breaking).** A parametrized scenario whose passed cases narrate different step
  structures or differently-shaped narration now fails the run; add
  `@scenario(group_parametrized=False)` to the scenario.
- **Removed (breaking).** The `divergent-case-structure` lint rule; delete any
  `given_lint_rules` or `given_lint_ignore` entry naming it, which would otherwise fail
  config parsing.
- **Removed (breaking).** `divergent` on a parameter-table case in the JSON report.

## Verification

TDD throughout, except the template edits (per AGENTS.md, frontend changes are applied and
then driven, not test-driven).

- Unit, per-case path: `Template` name substituted per case; `str` and glossary-t-string names
  suffixed; colliding `Template` names suffix the whole group; `Annotated` placeholder step
  labels substituted; no `ParameterTable` on the result; format specs and conversions survive
  substitution; a failed and a skipped case emit normally.
- Unit, rule 6: each of the four shapes raises, with its own first clause; a plain `str` that
  varies still raises rule 1's message, not rule 6's; a group with one passed case does not
  raise; non-passed cases are exempt; a group that differs only in *rendered* values still
  merges exactly as it does today.
- Unit, retirements: `_comparable` no longer filters; coverage counts a passed case with no
  `divergent` field; serde round-trips a case, and still loads one carrying a stale
  `divergent` key.
- Integration, through `pytester`: the flag on a non-parametrized test fails at
  `--collect-only`; an opted-out parametrized test yields N scenarios in `--given-json`; a
  divergent test fails the run and writes no sink.
- `uv run nox -s examples self_report`, reading the `.md` diff first.
- Playwright on the regenerated `examples/coffeeshop/coffeeshop.html` for the `≠` removal:
  console clean after init, then a parametrized scenario's case table still expands, hovers
  and highlights.

## Out of scope

- **A global or ini-level opt-out.** The flag is per scenario, which is where the knowledge
  lives; a suite-wide switch would turn every parametrized scenario into N, which is a
  different product, not a convenience.
- **Automatic opting out on divergence.** Considered and rejected: the report shape would
  change under the author's feet, one scenario silently becoming N, and an accidental
  divergence — a stray `if` in a step body — would never be pointed out. The error names the
  one-line fix instead.
- **Rendering an opted-out group as a set in the report** (a shared header, collapsed cases).
  They are ordinary scenarios; if their volume becomes a browsing problem, that is a report
  concern with its own design.
- **Combining a glossary t-string and a per-case value in one scenario name.** Still not
  expressible; unchanged by this work.
