# Glossary-ref t-strings in `@scenario` names

**Status:** proposed
**Date:** 2026-07-12

## Problem

Glossary handles surface as kind-coloured *term pills* wherever narration is
structured — step text, activity slots, story labels. Scenario **titles** are
the one narration surface that cannot carry a pill: `@scenario(...)` rejects
every t-string outright (`decorators.py`, `scenario()`), so an author writing
`@scenario(t"{pg['Guest']} checks in")` gets a hard error even though a glossary
handle is perfectly resolvable at import time.

The rest of the pipeline is already wired for pilled titles:

- `Scenario.narration.parts` flows through the term-scenario index.
- The HTML renderer pipes titles through the pill `narration` filter
  (`report.html.j2:195`); the Markdown heading goes through `_narration_md`.
- Story-view scenario cards already render titles through the `narration`
  filter as plain headings, ready to show pills.

Only the blanket t-string rejection blocks authoring.

## Why the rejection exists (and why it over-blocks)

`scenario()` runs at **module-import time**, before pytest has substituted
parametrize values, so a t-string interpolating a parametrize column cannot be
resolved — that is the correct thing to reject. But glossary handles are *not*
per-case data: they identify a concept and are in scope at import. The blanket
rule throws them out with the parametrize values. The step-decorator path
(`_check_tstring_decorator_safety`) already draws the right line: accept a
t-string whose interpolations are **all glossary handles**, reject any
value/expression interpolation with guidance toward `Template`. We mirror it.

## Three-way authoring model (result)

The three name forms cover **different axes**; none subsumes another.

| Form | Resolves | Can emit term pills? | Can use parametrize values? |
|---|---|---|---|
| Plain string | — (static) | no | no |
| `Template('… {col} …')` | deferred, at collection | **no** (`{col}` → value/placeholder) | **yes** |
| t-string `t"… {pg['Guest']} …"` | **eager, at import** | **yes** (`NarrationTermRef`) | **no** (values not in scope) |

Consequence, stated explicitly so it is not mistaken for a bug: a title needing
**both** a term pill **and** a per-case parametrize value in one name is not
expressible today (`t"{pg['Guest']} books {room_type}"` — the `{room_type}`
value interpolation is rejected; `Template` cannot pill). If that need arises it
is a separate future item, out of scope here.

## Design

### 1. `scenario()` — relax the t-string gate (`capture/decorators.py`)

Replace the blanket `templatelib.Template` rejection with the step-fixture rule:

1. Render the t-string eagerly via `parse_tstring` (through `narration_from`).
2. If any resulting part is a `NarrationValue` (a non-glossary interpolation),
   raise `PytestGivenError` with a message steering to `Template` (for a
   parametrize value) or a plain string (for a static label) — the same line the
   step decorator draws, worded for the scenario-name context.
3. Otherwise store the rendered `Narration` on the decorator.

`ScenarioDecorator.name` widens from `str | Template` to
`str | Template | Narration`. Validation and rendering happen once, at import,
matching how `StepDescriptor` stores `self.narration` eagerly. (Approach
rejected: keep the raw t-string on `name` and re-parse in `start_scenario` —
double-parses and splits the validation site from the stored value.)

The `NarrationValue`-detection is shared in spirit with
`_check_tstring_decorator_safety`; the two keep distinct messages (step vs.
scenario-name), so factor only the "does this narration contain a
`NarrationValue`" predicate if it reads cleanly, otherwise leave inline.

### 2. `narration_from()` — `Narration` pass-through (`capture/template.py`)

Add a leading `isinstance(value, Narration)` branch returning the value
unchanged, so a pre-rendered scenario-name `Narration` flows through
`start_scenario` (`collector.py`) without a second parse.

### 3. Downstream — already correct, no code change

- **Grouping** (`plugin.py` `_group_parameterized`) keys off
  `scenario.narration.text`. Glossary handles render deterministically, so every
  parametrize case of a term-titled scenario produces identical text → one
  group.
- **Templatize** (`plugin.py` `_templatize_narration`) already has a
  `NarrationTermRef` case: a term whose `expression` is not a parametrize column
  passes through unchanged (a glossary handle's expression, e.g. `pg['Guest']`,
  never matches a column).
- **`_validate_all_scenarios`** (`plugin.py`) gates on
  `isinstance(marker.name, Template)`; a `Narration` name correctly skips the
  "Template name must be parametrized" constraint.

### Edge cases

- **Import-time lookup.** `pg['Unknown']` raises the existing did-you-mean error
  at import — acceptable; the glossary is loaded (via `conftest.py`) before test
  modules import.
- **Display override preserves surface text.** `pg['Guest']('guests')` yields a
  `DeferredTermInstance` with custom display, so a converted title can read
  byte-identically to its former plain-string wording (case, plurals).
- **Parametrized + term-in-title** groups to a single scenario, with the term
  pill in the merged title and the parameter table below.

## Testing

TDD, in the capture/decorator suite (data-shaped assertions, not markup):

1. A glossary-handle t-string name is accepted; assert `Narration.text` and the
   `parts` shape (`NarrationTermRef` with the expected `term_id`/`display`).
2. A value interpolation (`t"{x} does thing"`) is rejected with the guidance
   message.
3. Display override (`pg['Term']('surface')`) renders the exact surface text.
4. A parametrized test with a term-titled name groups into one scenario whose
   merged narration keeps the `NarrationTermRef`.

No frontend markup tests (per AGENTS.md); the rendered title pill is verified
via Playwright during the dogfood phase.

## Documentation & skill sync

User-facing surface change — update in the **same** work, following AGENTS.md
§"Writing self-report scenarios":

- README: the `@scenario(...)` name forms.
- Canonical skill source under
  `src/pytest_given/skills_data/pytest-given-authoring/references/`:
  - `api.md` — line ~16 (`name` is a plain string, `Template`, **or a
    glossary-handle t-string**); the *Step text forms* table (add the
    `@scenario` t-string row, glossary-only); hard rule 2 (a t-string in
    `@scenario(...)` is rejected only for value/expression interpolations —
    glossary-handle t-strings are accepted).
  - `scenarios.md` / `glossaries.md` — mention pilled titles where term-pill
    surfaces are listed.
- Regenerate the committed `.claude/skills/` copy with
  `uv run pytest-given skills install` and commit both (the sync test enforces
  this).

## Dogfood phase (all self-report titles)

A distinct phase after the feature + docs land: audit every `@scenario(...)`
title under `tests/**`, and for each word mapping to a `GLOSSARY.md` term,
convert the title to a term-pill t-string, using the display-override form to
keep rendered wording byte-identical. Then:

- `uv run nox -s self_report`; review the `.md` diff (should be pill markup
  only, not reworded titles).
- Playwright-verify title pills render and their tooltips/links work.

The self-report glossary handle is `pg` (loaded in `tests/conftest.py` via
`tests/ubiquitous_language.py`); files gaining a pilled title import it.

## Out of scope

- Combining a term pill and a parametrize value in one scenario name.
- Any renderer/template change — titles already pipe through the pill filter.
