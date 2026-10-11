# The narration lint

The narration lint enforces the structural part of the rules in [scenarios.md](scenarios.md). Turn it on with `pytest --given-lint` or `given_lint = true` in `[tool.pytest]`; `--no-given-lint` turns an ini-enabled lint off for one run. A *warn* finding prints in the terminal summary. Only an *error* finding fails the run.

| Rule | Default | Catches |
|---|---|---|
| `empty-step` | error | A step whose body does nothing: only constants or `pass`, or, for `when`/`then`, only an `attach(...)` call. |
| `then-without-check` | error | A `then` with no `assert` statement and no checking call. A checking call is one whose name starts with `assert` (`assert_totals(order)`, `result.assert_outcomes(...)`), or `pytest.raises` / `pytest.warns` / `pytest.fail`. Nothing else counts, not even `pytest.approx`. |
| `conditional-check` | warn | A `then` whose checks all sit under an `if`, a loop, a `match` or an `except`, so a run can pass it having checked nothing. An `if` that calls `pytest.fail` counts as a check, and so does a loop over a literal such as `(a, b)`. Assert the condition itself (`assert 'index' not in entry`), or split the cases into rows. |
| `missing-phase` | warn | A passed scenario that doesn't cover all three phases. Fixture `@given`s and `Annotated[..., given(...)]` parameters count. |
| `check-outside-then` | warn | An `assert` inside a `given` or `when`. The `when` half of a `when_then` pair is exempt. |
| `action-in-then` | warn | No `when` performs an action, and a `then` folds the action into its assertion. |
| `unused-interpolation` | warn | A `with` step whose narration interpolates a `{name}` that its body never uses: a t-string interpolation, or a parametrize placeholder in a grouped scenario. |
| `tag-shadows-term` | warn | A scenario tag whose slug duplicates a glossary term. |
| `dead-term` | off | A glossary term that no scenario title, no step and no story sentence references. Off by default, because an unreferenced term is normal. Turn it on where every glossary term is meant to be used. |

You can override each rule's severity with the `given_lint_rules` ini. That and the rest of the setup are in the project documentation at <https://nwilbert.github.io/pytest-given/latest/configuration/narration-lint/>.

**A `then-without-check` finding on a step that does check is usually a naming problem.** The rule only recognizes an assertion helper by its `assert` prefix. So rename `check_totals` to `assert_totals` before you reach for the ignore list. A third-party matcher with another name (`result.stdout.fnmatch_lines(...)`) needs a real `assert` next to it, or an ignore entry.

**Treat a `missing-phase` warning as a prompt to restructure, not to suppress.** It nearly always marks a hidden `when`. Apply the constructor rule under [Phase structure](scenarios.md#phase-structure), or show a parametrized input as `Annotated[..., given(Template('…'))]` so the inline block can narrate the action. A `given_lint_ignore` entry (`missing-phase: <node-id glob>`) is only for an honestly two-phase scenario, and it costs more than it seems. An entry that suppresses nothing is a `stale-ignore` error, which can't be downgraded or ignored. So `pytest tests/one_file.py --given-lint` fails whenever the selection skips the suppressed test.
