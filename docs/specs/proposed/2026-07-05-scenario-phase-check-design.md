# Scenario Phase Check — Design Spec

## Goal

An opt-in check that flags `@scenario`-decorated tests which don't cover all three Given/When/Then phases, so a suite can catch *accidentally* two-phase scenarios in CI.

```toml
# pyproject.toml — pytest native TOML mode (this project's [tool.pytest] table)
[tool.pytest]
given_phase_check = "error"          # off | warn | error   (default: off)
given_phase_check_ignore = [
    # scenarios that are honestly two-phase — exempt by node-id glob
    "tests/unit/capture/test_collector.py::test_pop_step_*",
    "*::test_*_raises",
]
```

```bash
pytest --given-phase-check=warn      # CLI overrides the ini value for one run
```

When enabled, a scenario is a **violation** if it ran to a `passed` result but its recorded steps don't include all of `given`, `when`, and `then`. `warn` prints a summary and leaves the exit code alone; `error` prints the same summary and fails the run.

## Background

pytest-given scenarios narrate in Given/When/Then phases, but nothing enforces that all three appear. Two legitimate situations produce a two-phase scenario:

- **Honest two-phase** (per [AGENTS.md](../../AGENTS.md)): an assertion on a *static property of arranged state* (`given` + `then`), or a pure "constructing X raises" check (`when_then` with no `given`). These are correct and should not be forced to three phases.
- **Accidental two-phase**: the action under test is folded into the `given` (e.g. `FileGlossary(path)` built inside a `given` whose `then` asserts a property of it) or into the `then` assertion. The missing `when` hides the action from the report.

Only the author can tell these apart, but the *accidental* kind is a recurring, mechanical smell — a manual audit of this suite found seven such scenarios. A check turns "remember to look" into a gate. Because the honest kind is real, the check is **opt-in** and carries an **ignore list**, not a blanket default-on error.

### Why this can't be a static/lint check

A scenario's phase set is only known at runtime:

- `given` steps arrive via **fixture grafting** — a `@given`-decorated fixture (`guest`, `search`, `room`, …) contributes a `given` step to every consuming scenario, with nothing written in the test body.
- `given` also arrives via **`Annotated[..., given(Template(...))]`** parameter metadata.
- `when`/`then` can come from a single **`when_then(...)`** call, which emits two sibling steps.

A source-level scan sees none of these reliably (the manual audit's first pass produced 26 false positives that collapsed to 7 once fixture-grafted and annotation givens were accounted for). The authoritative phase set exists only after the scenario's steps are recorded. So the check runs **at report-build time**, over the finished scenario tree.

## Approach

Hook the existing `pytest_sessionfinish` path. It already calls `_group_parameterized(...)` to produce the final, grouped scenario list (one record per logical scenario, parametrize cases merged) before writing JSON. The check iterates that list, so each logical scenario is evaluated **once** regardless of parametrization.

For each scenario:

1. Skip unless `scenario.status == 'passed'`. A `skipped` scenario records no steps; a `failed`/errored one may be missing a phase *because* it aborted mid-body — flagging it would pile a spurious authoring complaint on top of the real failure.
2. Skip if the scenario's node id matches any `given_phase_check_ignore` glob.
3. Collect the set of `phase` values across the scenario's whole step tree. `{given, when, then} ⊆ phases` → complete; otherwise it's a violation carrying the sorted list of missing phases.

Violations are accumulated, then surfaced by a `pytest_terminal_summary` section. In `error` mode the session exit code is set to failed.

The check is pure inspection of already-built data — no change to recording, grouping, or the JSON/HTML output. A report is produced exactly as today; the check only reads it and may affect the process exit code and terminal output.

## Configuration

Mirrors the `--given-source-link` / `given_source_link` precedent (CLI option overrides ini value).

| Setting | Kind | Values | Default |
|---|---|---|---|
| `--given-phase-check` | `addoption`, `choices=['off','warn','error']` | `off` \| `warn` \| `error` | `None` (fall back to ini) |
| `given_phase_check` | `addini`, `type='string'` | `off` \| `warn` \| `error` | `off` |
| `given_phase_check_ignore` | `addini`, `type='linelist'` | list of node-id globs | `[]` |

Resolution: `level = cli_value or ini_value`; an unrecognised value raises `pytest.UsageError` at `pytest_configure` (fail fast, like a bad preset). When `level == 'off'` the check is skipped entirely (zero cost).

In pytest's native TOML mode (the `[tool.pytest]` table this project uses since pytest 8.4/9.0), `given_phase_check_ignore` is a real TOML array of strings and the `addini(type='linelist')` declaration accepts that array directly. Under the legacy `[tool.pytest.ini_options]` table or a `pytest.ini` / `tox.ini`, the same key is a newline-separated list. Either way this is the ignore mechanism the feature ships with.

### Ignore-list matching

Each pattern is matched with `fnmatch.fnmatch` against the scenario's **node id** (e.g. `tests/unit/capture/test_x.py::test_y`). Node id is chosen over the display name because it's unique, stable, and already the collector's key. Globs (`*`, `?`, `[...]`) cover the common cases: a whole file (`tests/foo.py::*`), a naming convention (`*::test_*_raises`), or one scenario (exact string). A pattern that matches nothing is left as-is (no error) — a suite may legitimately keep an entry for a scenario it hasn't written yet or has removed; failing on stale entries is noise. (Reconsider if it proves error-prone.)

## What counts as a phase

The phase set is the distinct `Step.phase` values over the scenario's entire step tree (`given` / `when` / `then`). This naturally includes:

- **Grafted fixture givens** — the `@given` fixture's root step is grafted into the scenario tree.
- **Annotated givens** — `Annotated[..., given(Template(...))]` produces a `given` step.
- **`when_then` steps** — the paired `when` and `then` steps each carry their phase.

Walking the whole tree (not just top-level steps) is belt-and-suspenders: cross-phase nesting is already rejected at record time, so phases are effectively top-level, but a tree walk is robust to future nesting rules and cheap (scenarios have few steps).

## Reporting

A single terminal-summary section, emitted for both `warn` and `error`:

```
=== pytest-given: incomplete scenarios (3) ===
tests/unit/capture/test_x.py::test_a          missing: when
tests/unit/capture/test_y.py::test_b          missing: given
tests/unit/capture/test_z.py::test_c[case1]   missing: when, then
```

- **`warn`**: printed as a warning-styled section; process exit code unchanged. Intended for adoption / local feedback.
- **`error`**: same section, and `session.exitstatus` is set to `pytest.ExitCode.TESTS_FAILED` when at least one violation exists and the run would otherwise have passed. Intended for CI gating.

The section lists the node id and the sorted missing phases. It does not fail individual test items (they already reported their real pass/fail); the gate is a session-level outcome, consistent with how `--cov-fail-under` reports. (Per-item failure attribution is discussed under Open Questions.)

## Implementation Touch Points

| File | Change |
|---|---|
| `src/pytest_given/plugin.py` | Add the two `addoption`/`addini` declarations. In `pytest_configure`, validate the resolved level. In `pytest_sessionfinish`, after `_group_parameterized(...)`, run the check over the grouped scenarios when `level != 'off'`; store violations on the session/config stash. Add `pytest_terminal_summary` to print them; set `session.exitstatus` in `error` mode. |
| `src/pytest_given/report/phase_check.py` (new) | Pure helpers: `scenario_phases(scenario) -> set[Phase]`, `missing_phases(scenario) -> list[Phase]`, `is_ignored(node_id, patterns) -> bool`, and `find_violations(scenarios, patterns) -> list[PhaseViolation]`. No pytest imports — unit-testable in isolation. Lives under `report/` because it consumes the built model (leaf `model/` dependency only). |
| `src/pytest_given/model/schema.py` | (Optional) a small frozen `PhaseViolation(node_id: str, missing: tuple[Phase, ...])` dataclass, or keep it local to `phase_check.py`. |
| `README.md` | Document the flag, the ini keys, the ignore list, and the "two phases is fine when honest → use the ignore list" guidance. |
| `AGENTS.md` | Cross-reference: the existing GWT-phase conventions plus how to run the check locally (`--given-phase-check=warn`). |

## Test Coverage

Unit tests for `report/phase_check.py` (`tests/unit/report/test_phase_check.py`) — build `Scenario` models directly:

- `scenario_phases` returns exactly the phases present across the step tree, deduped.
- A scenario with `given`+`when`+`then` → no missing; `given`+`then` → missing `when`; `when`+`then` → missing `given`.
- A scenario whose only `then` sits inside a `when_then`-produced pair still counts `when` and `then`.
- A scenario whose `given` is a grafted fixture root (a top-level `given` step it didn't author inline) counts as having `given`.
- `is_ignored` matches file-glob, name-convention-glob, and exact node id; non-matching patterns don't.
- `find_violations` skips non-`passed` scenarios (skipped, failed) and ignored node ids; dedupes nothing extra (input is already grouped).

Integration tests (`tests/integration/test_plugin.py`) — run a tiny inner pytest suite via `pytester`:

- `off` (default): a two-phase scenario produces no phase-check output and exit 0.
- `warn`: a two-phase scenario prints the summary section naming it and the missing phase; exit code still reflects the underlying tests (0 when they pass).
- `error`: a two-phase scenario makes the run exit non-zero with the summary; a fully three-phase suite exits 0.
- Ignore list: a two-phase scenario listed in `given_phase_check_ignore` is not reported under `error`, and the run passes.
- CLI overrides ini: `given_phase_check = "off"` in ini + `--given-phase-check=error` on the CLI → the check runs.
- A **failing** two-phase scenario is not additionally flagged (its failure is the only reported problem).
- A parametrized two-phase scenario is reported once, not once per case.

## Out of Scope

- **Per-scenario opt-out** (a `two-phase` tag or `@scenario(..., phases='partial')` kwarg). Deferred by decision; the ignore list in `pyproject.toml` covers the same need for v1. A tag/kwarg could be added later as a more local alternative without changing the check core.
- **Auto-fixing** or suggesting where the missing phase should go. The check reports; the author decides.
- **Static / collection-time checking.** Phase completeness isn't reliably knowable before the body runs (fixture grafting, annotations, `when_then`); a lint-style pre-run check would be wrong. The check is intentionally post-run.
- **Checking phase *order* or *count*** (e.g. "a `when` before its `then`", "no more than one `when`"). Only presence of each phase is checked.
- **Non-scenario tests.** Undecorated tests are never scenarios and are never checked.

## Open Questions

1. **Per-item failure vs. session-level gate.** `error` mode currently sets the session exit code and prints a summary, rather than marking each offending item as failed. Session-level is simpler and matches `--cov-fail-under`, but per-item failures integrate better with test-result dashboards. Per-item would require injecting a failure in a `pytest_runtest_makereport` wrapper for the `call` phase, evaluating phases there (they're finalized by `finish_scenario` in `pytest_runtest_logreport`) — feasible but more invasive. Start session-level; revisit if users want per-item attribution.
2. **Default level.** Ships as `off` (pure opt-in, no surprise for existing users). Alternative: default `warn` so the feature is discoverable. `off` is the conservative choice; the project's own `pyproject.toml` can set `error` to guard this suite.
3. **Stale ignore entries.** v1 ignores non-matching patterns silently. A future `--given-phase-check-strict-ignore` could flag ignore entries that matched nothing, to keep the list honest. Not worth it until the list is large.
