# Narration Lint — Design Spec

## Goal

Extend the [phase check](2026-07-05-scenario-phase-check-design.md) into a general **narration linter**: a set of rules that mechanically catch steps whose narration lies about their body. This spec focuses on the rule catalog — what each rule flags, why the flagged pattern is a lie, and its default severity. Implementation (AST walker design, hook wiring, flag surface) is deliberately sketched only where it constrains the rules.

## Background

pytest-given's narration is **auditable, not verified**: the same author (increasingly, the same agent) writes both the code and the claim about the code, and nothing compares a step's text to its body. The report's proximity argument — narration in the same `with` block, same diff hunk, same review pane as the code — makes drift *visible*; this linter makes the structural subset of drift *detectable*.

The existing `--given-phase-check` is the first rule of this family (a scenario missing a Given/When/Then phase), with a proven config shape: `off | warn | error`, an ini default, and a node-id-glob ignore list for scenarios that are honestly exempt. The linter generalizes that shape to a rule catalog.

Rules operate on two surfaces:

- **Static (AST)** — analysis of `@scenario`-decorated test functions at collection time. Sees step bodies, assert statements, and t-string expressions; runs without executing tests.
- **Runtime (collected data)** — checks over the recorded scenario tree at session finish, where per-case step structure and glossary usage are known. The phase check already lives here.

## What the linter cannot catch (non-goal)

Semantic mismatch — `with when('I insert $2')` over a body that inserts $3 — is out of scope for mechanical rules. The intended path there is separate: capture each step's body source range into the report JSON, so a `pytest-given audit` command can emit (step text, body source) pairs for a human or LLM judge to grade. That is a future spec; this one covers only what static/runtime analysis can decide reliably.

## Rule catalog

| # | Rule id | Surface | Default | One-line statement |
|---|---------|---------|---------|--------------------|
| 0 | `missing-phase` | runtime | off (existing) | A passed scenario lacks a Given, When, or Then phase. |
| 1 | `empty-step` | AST | error | A step body contains no executable code. |
| 2 | `then-without-check` | AST | error | A `then` step body contains no assertion. |
| 3 | `check-outside-then` | AST | warn | An `assert` is the substantive content of a `given` or `when`. |
| 4 | `action-in-then` | AST | warn | The system-under-test call is folded into a `then` assertion. |
| 5 | `unused-interpolation` | AST | warn | A t-string step interpolates a name its body never uses. |
| 6 | `divergent-case-structure` | runtime | warn | A parametrize case records a different step structure than case 1. |
| 7 | `tag-shadows-term` | runtime | warn | A scenario tag duplicates a glossary term. |
| 8 | `dead-term` | runtime | off | A glossary term is referenced by no step and no story. |

### 0. `missing-phase` (existing)

The current phase check, folded in as a rule so all narration diagnostics share one summary, one severity mechanism, and one ignore-list shape. `--given-phase-check` / `given_phase_check` stay as aliases for this rule's level.

### 1. `empty-step`

**Flags:** a `with given/when/then(...)` (or `when_then`) block whose body is only `pass`, `...`, a docstring/string expression, or comments.

**Why it's a lie:** a step with no code claims behaviour that nothing performs — the purest false statement a report can contain. The AGENTS.md rule "never write a placeholder step" made mechanical.

**Notes:** zero expected false positives; safe at `error`. Also fires on a step whose only content is `attach(...)` **when the phase is `when` or `then`** — attaching is not acting or checking (a `given` that only attaches its arranged artifact is legitimate and must not fire).

### 2. `then-without-check`

**Flags:** a `then` step containing no `assert`, no `pytest.raises` / `pytest.warns` context, and no nested `then` child that has one. A `when_then` counts as checked — the recorded `then` *is* the caught raise.

**Why it's a lie:** the report claims a verified outcome that nothing verifies. This is the most damaging drift class for a reader who trusts the report: a green scenario whose "then" checked nothing.

**Notes:** a `then` that delegates its assertion to a called helper (e.g. a shared `assert_valid(x)` function) is a real pattern; detecting it needs either a naming heuristic (`assert*` call counts as a check) or the ignore list. Start with the naming heuristic plus per-rule ignores; keep at `error` only if the false-positive rate in this repo's own suite proves negligible, else `warn`.

### 3. `check-outside-then`

**Flags:** an `assert` statement directly inside a `given` or plain `when` body (not inside a nested `then`).

**Why it's a lie:** the narration files the check under arrangement or action, so the report hides what was actually verified. Enforces "action in `when`, check in `then`" mechanically.

**Notes:** guard-style asserts on arranged state (`assert machine['coffees'] > 0` before acting) are honest and common — hence `warn`, and the rule should ignore asserts that precede the step's substantive statements (a leading-guard tolerance) if the noise proves real.

### 4. `action-in-then`

**Flags:** a `then` whose assert expression contains a call (`assert sut(x) == …`) in a scenario where **no** `when` body performs any call.

**Why it's a lie:** the action under test is invisible in the report — the scenario reads as if an outcome materialized without an act. This is the "most common missed `when`" from AGENTS.md.

**Notes:** deliberately heuristic and narrow: it only fires when the whole scenario has no acting `when`, which keeps comparison-helper calls (`math.isclose(...)`, `str(x)`) in scenarios that *do* act from triggering it. Stays `warn` permanently.

### 5. `unused-interpolation`

**Flags:** a t-string step text interpolating `{name}` where `name` is never read in that step's body (nor, for a `given`, bound by it).

**Why it's a lie:** the narration parades a value the code ignores — the reader assumes the step depends on it. This is the strongest purely mechanical text↔body consistency check available: it ties a *specific token of the claim* to the code.

**Notes:** glossary term refs (`{pg["Term"]}`, handle calls) are vocabulary, not data flow — exempt. Values used only by an enclosing/child step need scoping care; start with "referenced anywhere within the step subtree".

### 6. `divergent-case-structure`

**Flags:** at session finish, a parametrize case whose recorded step sequence differs structurally (phase/nesting/count, not values) from case 1's.

**Why it's a lie:** the merged parameter-table view renders **every** row against case 1's step structure, so divergent cases are silently misdescribed today — a documented footgun this rule converts from silent to loud.

**Notes:** runtime rule over data the collector already records. The fix it points to is "split the scenario" (or, once implemented, `@scenario(group_parametrized=False)` — see TODO). Skipped cases record no steps and are exempt.

### 7. `tag-shadows-term`

**Flags:** a scenario tag whose slug (`id_derive`) collides with a glossary term's.

**Why it matters:** tags and terms are two filter axes; a duplicated one splits the same concept across both and rots independently. The AGENTS.md "tag orthogonally to the glossary" rule made mechanical. Only active when a glossary is registered.

### 8. `dead-term`

**Flags:** a glossary term referenced by no step and no story activity.

**Why it matters:** dead vocabulary in a *code-defined* glossary is unused code. For a `FileGlossary` it is often intentional — the file is the team's full glossary, and unreferenced terms still belong in the Glossary tab (current documented behaviour). Hence default `off`; teams that want their glossary fully exercised opt in.

## Configuration shape (sketch)

Generalize the phase-check surface rather than inventing a new one:

- `--given-lint=off|warn|error` — master level; `error` makes any error-level finding fail the run (CI gate).
- `given_lint_ignore` — node-id globs, optionally rule-scoped (`"empty-step: tests/unit/test_x.py::test_y"`), following the `given_phase_check_ignore` pattern.
- Per-rule level overrides in `pyproject.toml` for tuning individual rules up/down.
- One combined "narration lint" summary block at session end, one line per finding: rule id, node id, and what to do about it.

Exact flag/ini naming, AST-walker structure, and how static findings attach to collected items are implementation-phase decisions.

## Rollout sketch

1. **Rules 1–2** (`empty-step`, `then-without-check`): highest confidence, error-capable, and the two purest lies. Validate against the self-report suite (the `self_report` nox session should run them at `error`, as it does the phase check today).
2. **Rules 3–5**: the warn-level heuristics; tune tolerances on this repo's suite before documenting.
3. **Rules 6–8** + folding in `missing-phase`: runtime rules and config unification.
