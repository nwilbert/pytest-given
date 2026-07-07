# Narration Lint — Design Spec

## Goal

Extend the [phase check](2026-07-05-scenario-phase-check-design.md) into a general **narration linter**: a rule catalog that mechanically catches steps whose narration lies about their body, sharing one config surface, one summary section, and one severity/ignore mechanism.

```toml
# pyproject.toml — pytest native TOML mode (this project's [tool.pytest] table)
[tool.pytest]
given_lint = true                    # default: false
given_lint_rules = [
    # per-rule severity overrides: rule-id=level (off | warn | error)
    "then-without-check=warn",
    "dead-term=warn",
]
given_lint_ignore = [
    # subject globs, optionally rule-scoped with a "rule-id:" prefix
    "missing-phase: tests/unit/capture/test_collector.py::test_pop_step_*",
    "*::test_*_raises",
    "dead-term: legacy-*",
]
```

```bash
pytest --given-lint=true             # CLI overrides the ini value for one run (true | false)
```

The linter **replaces** the standalone phase check: `--given-phase-check`, `given_phase_check`, and `given_phase_check_ignore` are removed in the same release, without aliases (the phase check shipped one day before this spec; there is no adoption to preserve). The phase check becomes the `missing-phase` rule.

**Hard requirement:** when `given_lint` is `false` (the default), the feature costs practically nothing — one boolean check per recorded step, no frame walking, no AST parsing, no findings pass, byte-identical report artifacts.

## Background

pytest-given's narration is **auditable, not verified**: the same author (increasingly, the same agent) writes both the code and the claim about the code, and nothing compares a step's text to its body. The report's proximity argument — narration in the same `with` block, same diff hunk, same review pane as the code — makes drift *visible*; this linter makes the structural subset of drift *detectable*.

Most rules are the mechanical faces of narration rules already written down in [AGENTS.md](../../AGENTS.md#narration-rules-portable): "never write a placeholder step" (`empty-step`), "put the system-under-test call in `when`, not folded into the `then` assertion" (`action-in-then`, `check-outside-then`), "step structure must not depend on parameter values" (`divergent-case-structure`), "tag orthogonally to the glossary" (`tag-shadows-term`).

## What the linter cannot catch (non-goal)

Semantic mismatch — `with when('I insert $2')` over a body that inserts $3 — is out of scope for mechanical rules. The intended path there is separate: capture each step's body source range into the report JSON, so a `pytest-given audit` command can emit (step text, body source) pairs for a human or LLM judge to grade. That is a future spec; this one covers only what static/runtime analysis can decide reliably. (The per-step source capture introduced below is the first half of that machinery.)

## Architecture

### Everything runs at session finish

The phase-check spec established that a scenario's true structure is only knowable at runtime (fixture grafting, `Annotated` givens, `when_then`). The same reasoning extends to the "static" rules: a purely static walker would have to re-derive *what is a step* — recognizing `@scenario` functions and `given`/`when`/`then` imports including aliases, and missing step-emitting helper functions entirely — maintaining a parallel definition that can drift from the real one. Instead, **the run itself identifies the steps, and the linter analyzes the AST of exactly those**.

All rules therefore run in the existing `pytest_sessionfinish` path, like the phase check today. The cost of this choice: lint feedback requires running the tests (which CI and the nox sessions do anyway), and code inside a step that never executes on the linted run is not seen. Both are accepted; a lint-without-running mode was considered and rejected.

### Per-step source anchoring (gated capture)

A new model field carries the anchor:

```python
@dataclass
class Step:
    ...
    source: SourceLocation | None = None   # NOT serialized in v1
```

Capture is **gated on the lint switch**: `plugin.py` resolves the enabled flag at configure time and hands the collector a `capture_step_source` flag. When off, every `Step.source` stays `None` and no capture code runs beyond the flag check. When on:

- **Inline `with` steps** — `StepDescriptor.__enter__` captures the caller frame's file+line (the `with` statement line), via the existing `capture/source.py` helpers. `WhenThen.__enter__` captures once; its `when` and `then` steps share the location.
- **Decorated helper steps** (`@given('…')` on a helper function) — the wrapped function's `__code__.co_filename` / `co_firstlineno`, no frame walk. The helper's `FunctionDef` body *is* the step body.
- **Fixture-root steps and `Annotated` givens** — stay `None`. They have no lintable body (a fixture body's inline steps capture normally as their own steps), and every AST rule skips source-less steps by construction.

`Step.source` is deliberately **not serialized** in v1 so report artifacts stay byte-identical whether or not lint ran. Serializing it later is the natural first step of the `audit` command spec.

### AST pass

At session finish, when lint is enabled:

1. **Runtime rules** run over the recorded data: `missing-phase`, `tag-shadows-term`, and `dead-term` on the grouped scenario list (one evaluation per logical scenario); `divergent-case-structure` on the **pre-grouping per-case list** — the only place per-case step structure exists, since `_group_parameterized` collapses cases onto case 1's tree.
2. **AST rules** (1–5) collect all steps that carry a `source`, group them by file, `ast.parse` each file **once**, and index its `With` and `FunctionDef` nodes by line. Each step looks up its node by its recorded line (for `With` nodes, a line matching any with-item's context-expression range counts, so multi-line parenthesized `with` headers anchor correctly). Rules then evaluate against the node body; `action-in-then` evaluates per scenario over all its anchored nodes. A **`when_then` pair** is recognized as sibling `when`+`then` steps sharing one source anchor — unambiguous, because cross-phase nesting is rejected at record time, so no other construct produces that shape. Rules 1–4 all treat the pair specially (see the catalog); they key off this recognition.
3. Findings from both passes are merged, filtered through the ignore globs, mapped to their effective severities, stashed, and printed by `pytest_terminal_summary`; at least one error-level finding sets the exit code.

**Failure tolerance:** an unreadable or unparseable source file, or a line with no matching node, silently skips that step's AST rules. Lint must never crash the run or affect the report. (A `-v`-gated debug note is fine; a hard error is not.)

### Module layout

`src/pytest_given/report/lint.py` (new) absorbs `report/phase_check.py`. Pure functions, no pytest imports — same testability contract as `phase_check.py` today:

- `Finding` — frozen dataclass: `rule: RuleId`, `severity: Level`, `subject: str`, `node_id: NodeId | None`, `location: SourceLocation | None`, `message: str`.
- The rule catalog as data: rule id → default severity + surface, so config validation and docs stay in sync with one table.
- One entry point per surface, e.g. `run_runtime_rules(grouped, per_case, glossary, stories) -> list[Finding]` and `run_ast_rules(scenarios) -> list[Finding]`, plus `apply_config(findings, levels, ignores) -> list[Finding]`.

`plugin.py` keeps only: the option/ini declarations, enable-flag resolution and rule-config validation at configure, the `capture_step_source` flag, the sessionfinish invocation, the terminal summary, and the exit-code logic — mirroring the phase-check wiring it replaces.

## Configuration

| Setting | Kind | Values | Default |
|---|---|---|---|
| `--given-lint` | `addoption`, `choices=['true','false']` | `true` \| `false` | `None` (fall back to ini) |
| `given_lint` | `addini`, `type='bool'` | `true` \| `false` | `false` |
| `given_lint_rules` | `addini`, `type='linelist'` | `rule-id=level` entries | `[]` |
| `given_lint_ignore` | `addini`, `type='linelist'` | subject globs, optional `rule-id:` prefix | `[]` |

`given_lint` is a plain **enable switch** — `false` is the zero-cost path (see hard requirement). The CLI value, when given, overrides the ini value for one run; it takes an explicit `true`/`false` (not a bare flag) so an ini-enabled lint can also be *disabled* for one run, and it deliberately uses the same words as the TOML ini value.

Everything else is decided by each rule's **effective severity** — its catalog default unless overridden in `given_lint_rules`:

- **`off`** — the rule doesn't run.
- **`warn`** — its findings print in the summary; the exit code is untouched.
- **`error`** — its findings print, and at least one of them sets `session.exitstatus = pytest.ExitCode.TESTS_FAILED` (when the run would otherwise pass).

There is deliberately **no master severity**: one severity vocabulary with one meaning. The "show everything, fail nothing" adoption mode is expressed explicitly by demoting the two error-default rules: `given_lint_rules = ["empty-step=warn", "then-without-check=warn"]`.

Validation at `pytest_configure` (fail fast, `pytest.UsageError`): unknown rule id or level in `given_lint_rules`, unknown rule prefix in `given_lint_ignore`.

### Ignore-list matching: subjects

Each finding has a **subject** that the ignore globs (`fnmatch`) match against:

- scenario/step rules (`missing-phase`, rules 1–6) — the scenario's **node id**, as in the phase check;
- `tag-shadows-term` — the **tag slug**;
- `dead-term` — the **term id**.

So "this tag is fine" and "this term is intentionally unreferenced" are expressible directly (`"dead-term: legacy-*"`) instead of abusing node-id globs. A bare pattern applies to all rules; a `rule-id:` prefix scopes it.

**Stale entries are errors.** Every entry must earn its keep: an entry that suppressed no finding in the session is reported as an error-level `stale-ignore` line in the summary and fails the run. There is deliberately no off-switch — the list stays honest by construction; delete dead entries. An entry scoped to a disabled rule is stale by this definition. Caveat: under a partial selection (`-k`, node ids, `--lf`), entries for unselected scenarios suppress nothing and are flagged — lint is meant for full runs (the nox sessions, CI), not ad-hoc selections. (This replaces the phase check's silent tolerance and resolves that spec's open question 3 the strict way.)

## Rule catalog

| # | Rule id | Surface | Default | One-line statement |
|---|---------|---------|---------|--------------------|
| 0 | `missing-phase` | runtime | warn | A passed scenario lacks a Given, When, or Then phase. |
| 1 | `empty-step` | AST | error | A step body contains no executable code. |
| 2 | `then-without-check` | AST | error | A `then` step body contains no assertion. |
| 3 | `check-outside-then` | AST | warn | An `assert` sits in a `given` or `when` body. |
| 4 | `action-in-then` | AST | warn | The system-under-test call is folded into a `then` assertion. |
| 5 | `unused-interpolation` | AST | warn | A t-string step interpolates a name its body never uses. |
| 6 | `divergent-case-structure` | runtime | warn | A parametrize case records a different step structure than case 1. |
| 7 | `tag-shadows-term` | runtime | warn | A scenario tag duplicates a glossary term. |
| 8 | `dead-term` | runtime | off | A glossary term is referenced by no step and no story. |

### 0. `missing-phase`

The phase check as implemented, folded in: passed scenarios only, grouped list, phase set over the whole step tree. Default moves from the standalone `off` to **`warn`**: the standalone check defaulted off because it *was* the whole opt-in; inside an already-opt-in linter, an off-by-default flagship rule is invisible. Its honest-two-phase exceptions are exactly what the ignore list is for.

### 1. `empty-step`

**Flags:** a step whose anchored body (the `With` block, or a decorated helper's `FunctionDef` body) is *empty*: after dropping `pass`, `...` and other constant-expression statements, and docstrings, no statement remains. Additionally fires when the only remaining content is `attach(...)` calls (bare name or attribute call named `attach`) **and** the phase is `when` or `then` — attaching is not acting or checking, while a `given` that only attaches its arranged artifact is legitimate.

**Why it's a lie:** a step with no code claims behaviour that nothing performs — the purest false statement a report can contain. The AGENTS.md rule "never write a placeholder step" made mechanical.

**Decisions:** a nested step's `with` block counts as content for its parent — only leaves fire. A `when_then` is analyzed once via its shared `With`; its `pytest.raises` with-item does not count as body content (the acting call must still be there). Zero expected false positives; safe at `error`.

### 2. `then-without-check`

**Flags:** a `then` step whose anchored body contains none of:

- an `assert` statement;
- a `pytest.raises` / `pytest.warns` with-item or call;
- a call to a name starting with `assert` — bare (`assert_valid(x)`) or attribute (`helpers.assert_valid(x)`) — the naming heuristic for shared assertion helpers;
- a `pytest.fail(...)` call (a body that conditionally fails *is* checking).

A parent `then` whose nested `then` child contains a check passes. `when_then`-produced `then` steps pass naturally: the `pytest.raises` with-item sits on their anchored `With`.

**Why it's a lie:** the report claims a verified outcome that nothing verifies — the most damaging drift class for a reader who trusts a green scenario.

**Decisions:** ships at `error`. The naming heuristic plus rule-scoped ignores are the escape hatches; if this repo's suite shows a real false-positive rate during rollout step 1, the default drops to `warn` before release.

### 3. `check-outside-then`

**Flags:** an `assert` statement directly inside a `given` or plain `when` body — not inside a nested `then`'s `With` block. `when_then` bodies are exempt: the shared body belongs to the pair's `then` half, so an `assert` there is a check in `then` territory, not a check hidden in a `when`.

**Why it's a lie:** the narration files the check under arrangement or action, so the report hides what was actually verified. Enforces "action in `when`, check in `then`" mechanically.

**Decisions:** v1 flags *all* such asserts, including guard-style asserts on arranged state (`assert machine['coffees'] > 0` before acting). The leading-guard tolerance from the original sketch is explicitly deferred until this repo's suite shows real noise — the ignore list covers stragglers meanwhile. Stays `warn`.

### 4. `action-in-then`

**Flags** (per scenario): some `then` step's `assert` expression contains a `Call`, **and** no `when` step acts. If any `when` in the scenario lacks a source anchor, the rule skips the scenario — unknowable beats wrong.

`when_then` needs care on both sides of the rule:

- A `when_then`'s `when` counts as acting **unconditionally** — not via the body-contains-a-`Call` test. The construct wraps the act by definition, and the acting expression need not be a call (`with when_then(…), pytest.raises(KeyError): mapping[key]` acts via a subscript). A plain `when` acts iff its body contains a `Call` **or a `Subscript`** — the subscript half is the same reasoning applied to plain `when`s, added in rollout step 2 when a call-only test false-positived on this suite's `glossary['Guest']` lookup-as-action.
- A `when_then`'s `then` is **excluded from the then-side scan**: it anchors to the shared `With` node, so its "body" is the acting body — any call there *is* the act, not an action folded into a check.

**Why it's a lie:** the action under test is invisible in the report — the scenario reads as if an outcome materialized without an act. The "most common missed `when`" from AGENTS.md.

**Decisions:** deliberately narrow — comparison-helper calls (`math.isclose(...)`) in scenarios that *do* act never trigger it. Overlaps `missing-phase` when the scenario has no `when` at all; both fire, and that's fine — they give different advice (add the phase vs. move the call). Stays `warn` permanently.

### 5. `unused-interpolation`

**Flags:** a `NarrationValue` part whose `expression` is a **bare identifier** (parses to a single `Name`) that is never loaded anywhere in the step's anchored body, including nested step blocks; for a `given`, a store (the step *binding* the name) also counts as use.

**Why it's a lie:** the narration parades a value the code ignores — the reader assumes the step depends on it. The strongest purely mechanical text↔body consistency check available: it ties a specific token of the claim to the code.

**Decisions:** glossary term refs are exempt by type (`NarrationTermRef`, not `NarrationValue`). Complex expressions (`machine["coffees"]`, `str(x)`) are skipped entirely — conservative, near-zero false positives. `Template` placeholders on decorated helpers are out of scope in v1: decoration-time signature validation already ties each placeholder to a parameter; extending this rule to *unused parameters* is a possible follow-up.

### 6. `divergent-case-structure`

**Flags:** on the pre-grouping per-case list, a parametrize case whose **structural signature** — the step tree reduced to nested phase tuples, ignoring narration text and values — differs from case 1's. One finding per scenario, naming the diverging case ids.

**Why it's a lie:** the merged parameter-table view renders every row against case 1's step structure, so divergent cases are silently misdescribed today — a documented footgun this rule converts from silent to loud.

**Decisions:** non-`passed` cases are exempt (skipped cases record no steps; failed cases abort mid-tree). The fix it points to is "split the scenario" (or, once implemented, `@scenario(group_parametrized=False)` — see TODO).

### 7. `tag-shadows-term`

**Flags:** a scenario tag whose slug (`id_derive`) equals a glossary term's id. One finding **per unique tag** (subject = tag slug; message counts affected scenarios and names one), not per scenario — the fix is renaming the tag once, and per-scenario findings would be pure repetition. Only runs when a glossary is registered.

**Why it matters:** tags and terms are two filter axes; a duplicated one splits the same concept across both and rots independently. The AGENTS.md "tag orthogonally to the glossary" rule made mechanical.

### 8. `dead-term`

**Flags:** a glossary term with no `NarrationTermRef` in any scenario or step narration and no story-activity reference. Subject = term id.

**Why it matters:** dead vocabulary in a *code-defined* glossary is unused code. For a `FileGlossary` it is often intentional — the file is the team's full glossary, and unreferenced terms still belong in the Glossary tab (current documented behaviour). Hence default **`off`**; teams that want their glossary fully exercised opt in via `given_lint_rules`.

## Reporting

One terminal-summary section whenever lint is enabled and findings exist, one line per finding — errors first, then file/line order:

```
=== pytest-given: narration lint (4 findings, 2 errors) ===
ERROR empty-step            tests/unit/test_x.py::test_a   then 'the total updates' has no code (test_x.py:42)
ERROR then-without-check    tests/unit/test_x.py::test_b   then 'the receipt prints' contains no assertion (test_x.py:57)
WARN  check-outside-then    tests/unit/test_y.py::test_c   assert inside given 'a stocked machine' (test_y.py:17)
WARN  tag-shadows-term      tag 'glossary'                 duplicates glossary term 'Glossary' (3 scenarios, e.g. tests/unit/test_y.py::test_d)
```

Stale ignore entries append their own lines to the same section (`ERROR stale-ignore  'dead-term: legacy-*'  suppressed no finding`).

Each line carries severity, rule id, subject, and a message including the step text and source location where available. As with the phase check: no per-item failure injection — the gate is a session-level outcome (`--cov-fail-under` precedent), and the per-item question stays open.

## Implementation Touch Points

| File | Change |
|---|---|
| `src/pytest_given/model/schema.py` | `Step.source: SourceLocation \| None = None`. Not emitted by `serde`. |
| `src/pytest_given/capture/decorators.py` | Gated capture in `StepDescriptor.__enter__` / `WhenThen.__enter__` (frame line) and `StepDescriptor.__call__` (helper code object). |
| `src/pytest_given/capture/collector.py` | `capture_step_source` flag; `push_step(..., source=...)` threading. |
| `src/pytest_given/report/lint.py` | New. `Finding`, rule catalog, runtime rules, AST pass, config application. Absorbs `phase_check.py` (which is deleted). |
| `src/pytest_given/plugin.py` | Swap the three phase-check declarations for the three lint ones; enable-flag resolution and rule-config validation; set the capture flag; invoke lint at sessionfinish; terminal summary; exit code. |
| `noxfile.py` | `--given-phase-check=…` → `--given-lint=true` in both the `examples` and `self_report` sessions. |
| `README.md` | Replace the phase-check section with the lint surface: flags, rule table, per-rule overrides, subject-based ignores. |
| `AGENTS.md` | Update the quality-gates cross-reference; note that the portable narration rules now have mechanical counterparts. |

## Test Coverage

Unit tests (`tests/unit/report/test_lint.py`) — rules are pure functions over hand-built `Scenario`/`Step` models and nodes from `ast.parse` of inline source strings; each rule gets fire / no-fire / edge cases, and every exemption named in the catalog above becomes a test:

- `empty-step`: `pass`/`...`/docstring-only fires; nested-step-only parent doesn't; `attach`-only fires for `when`/`then` but not `given`; helper `FunctionDef` body.
- `then-without-check`: bare `assert`, `pytest.raises` item, `assert_*` bare and attribute calls, `pytest.fail`, checked nested child; `when_then` `then` passes.
- `check-outside-then`: assert in `given`/`when` fires; assert inside nested `then` doesn't; assert in a `when_then` body doesn't.
- `action-in-then`: fires only with call-in-then-assert AND no acting `when`; anchor-less `when` skips; a `when_then` acts even when its body's raising expression is not a `Call` (subscript/attribute); a `when_then`'s `then` never contributes to the then-side scan.
- `when_then` pair recognition: sibling `when`+`then` sharing one anchor is a pair; a plain sibling `when` and `then` on separate lines is not.
- `unused-interpolation`: bare-identifier unused fires; used (load) doesn't; `given` store counts; complex expression and term ref skipped.
- `divergent-case-structure`: signature equality/difference; non-passed cases exempt.
- `tag-shadows-term` / `dead-term`: slug collision; unreferenced term; subject values.
- Config application: severity overrides, subject globs bare and rule-scoped.
- Migrated phase-check unit tests (`missing-phase`).

Integration tests (`tests/integration/test_plugin.py`, pytester):

- Disabled (default): no lint output, exit 0, and **every recorded `Step.source` is `None`** (the zero-overhead contract).
- Enabled: an error-level finding fails the run; warn-level findings alone print but don't fail it; a clean suite exits 0.
- `given_lint_rules` override changes a rule's effect (`error`→`warn` stops failing the run); `rule=off` disables it.
- Ignore list: bare and rule-scoped subject globs suppress findings; an entry that suppresses nothing fails the run with a `stale-ignore` line, while a suppressing entry doesn't.
- CLI overrides ini in both directions (`--given-lint=false` silences an ini-enabled lint); unknown rule id / level → usage error.
- The removed `given_phase_check` keys are gone (using them warns/errors as pytest does for unknown ini keys).
- A lint-enabled run's JSON/MD output is byte-identical to a lint-off run's.

## Rollout

1. **Engine + config + rules 1–2** (`empty-step`, `then-without-check`): the capture gating, AST pass, and the two purest, error-capable lies. Validate against the self-report suite; wire `--given-lint=true` into the `self_report` and `examples` sessions in this step (replacing the phase-check flags there). `self_report`'s clean suite makes the two error-default rules a real regeneration gate; the `examples` session's `success_codes=[0, 1]` masks the exit code regardless, so findings there are informational.
2. **Rules 3–5**: the warn-level heuristics; tune on this repo's suite before documenting (this is where the rule-2 severity decision and any rule-3 guard tolerance get their data).
3. **Rules 6–8 + `missing-phase` fold-in**: runtime rules, deletion of `phase_check.py` and the old config keys, README/AGENTS updates. The spec then moves out of `proposed/`.

## Out of Scope

- **Lint without running tests** (pre-commit / `--collect-only` mode). Considered and rejected: it requires a parallel static definition of "what is a step" (decorator/import/alias recognition) that can drift from the real one. Session-integrated linting matches how the suite is actually exercised (nox, CI).
- **Report integration.** Findings do not appear in the JSON/HTML/Markdown outputs in v1; artifacts stay byte-identical. A per-scenario badge/filter is a natural later spec once the rules have proven their signal.
- **Serializing `Step.source`.** Captured but not emitted; turning it on is the first step of the future `audit` command spec.
- **Semantic text↔body comparison** (the LLM-judge `audit` path) — see the non-goal section.
- **Per-scenario opt-out kwarg/tag**, **auto-fixing**, **phase order/count checks**, **non-scenario tests** — unchanged from the phase-check spec's exclusions.

## Open Questions

1. **Per-item failure vs. session-level gate** — inherited from the phase check, unchanged: start session-level, revisit if users want per-item attribution.
2. **Rule-2 severity** — `error` by default, demoted to `warn` before release if rollout step 1 shows real false positives on this suite.

(A third question — stale ignore entries — was resolved the strict way: see [Ignore-list matching](#ignore-list-matching-subjects).)
