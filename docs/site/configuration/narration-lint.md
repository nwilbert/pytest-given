# Narration lint

`--given-lint` checks the scenarios of a test run for steps whose text doesn't match their code. It checks the steps that actually ran, so steps from decorated helpers, fixtures, and `when_then` are all handled correctly.

When the lint is off, it costs nothing: pytest-given records nothing extra, and the reports are exactly the same as with the lint on.

## Rules

Each rule has a default severity. A `warn` finding is printed in the terminal summary. An `error` finding is printed too, and also fails the run.

| Rule | Default | Catches |
|------|---------|---------|
| `empty-step` | `error` | A step whose body does nothing: it only contains constants or `pass`, or, for `when` and `then`, only an `attach(...)` call. |
| `then-without-check` | `error` | A `then` without an `assert` or a checking call. Checking calls are calls whose name starts with `assert`, and `pytest.raises`, `pytest.warns` and `pytest.fail`. Nothing else counts, not even `pytest.approx`. |
| `conditional-check` | `warn` | A `then` whose checks all sit under an `if`, a loop, a `match` or an `except`, so a run can pass it without checking anything. An `if` that calls `pytest.fail` counts as a check, and so does a loop over a literal such as `(a, b)`. |
| `missing-phase` | `warn` | A passed scenario that is missing one of the phases Given, When or Then. `@given` fixtures and `Annotated[..., given(...)]` parameters count as `given` steps. A parametrized scenario is checked once, not once per case. |
| `check-outside-then` | `warn` | An `assert` inside a `given` or `when`. The `when` part of a `when_then` is allowed to contain one. |
| `action-in-then` | `warn` | A scenario where no `when` performs an action, and a `then` performs it inside its assertion instead. |
| `unused-interpolation` | `warn` | A `with` step whose text contains a `{name}` (a t-string value or a parameter-table placeholder) that the step's body doesn't use. |
| `tag-shadows-term` | `warn` | A scenario tag that matches a glossary term, so the same concept has two names. |
| `dead-term` | `off` | A glossary term that no step, scenario name, or story sentence uses. Turn this on if every glossary term should be used. |

## Configuration

Change a rule's severity with `given_lint_rules`. Skip findings for specific tests with `given_lint_ignore`: each entry is a node-id pattern (with `*` wildcards), optionally limited to one rule with a `rule-id:` prefix.

```toml
[tool.pytest]
given_lint = true
given_lint_rules = [
    "missing-phase=error",
    "dead-term=warn",
]
given_lint_ignore = [
    "missing-phase: *::test_*_raises",
    "tests/unit/test_math.py::test_constant_is_stable",
]
```

An ignore entry that no longer matches any finding causes a `stale-ignore` error. This keeps the list from growing out of date.

To turn the lint on or off for a single run, pass `--given-lint` or `--no-given-lint`. Both override the `given_lint` setting.

## Output

Each finding is printed on one line, with its severity, rule, test, message, and source location:

```
============= pytest-given: narration lint (2 findings, 1 error) ==============
ERROR empty-step     tests/test_shop.py::test_buy   given 'a coin' has no code (test_shop.py:12)
WARN  missing-phase  tests/test_shop.py::test_idle  missing: when (test_shop.py:31)
```
