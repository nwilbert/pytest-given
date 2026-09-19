# Narration lint

`--given-lint` runs a rule catalog over the scenarios the run just recorded, catching steps whose narration lies about their body. The AST rules analyze exactly the steps the run identified (there is no parallel static discovery), so decorated helpers, fixtures, and `when_then` pairs are all attributed correctly.

Each rule has a fixed default severity; there is no master level. A `warn` finding prints in the terminal summary; an `error` finding also fails the run.

| Rule | Default | Catches |
|------|---------|---------|
| `empty-step` | `error` | A step whose body does nothing (only constants/`pass`, or — for `when`/`then` — only an `attach(...)` call). |
| `then-without-check` | `error` | A `then` whose body contains no `assert` and no checking call — a call whose name starts with `assert`, or `pytest.raises` / `pytest.warns` / `pytest.fail`. Nothing else counts, `pytest.approx` included. |
| `missing-phase` | `warn` | A passed scenario that doesn't cover all three Given/When/Then phases. Fixture `@given`s and `Annotated[..., given(...)]` parameters count; each logical scenario is evaluated once regardless of parametrization. |
| `check-outside-then` | `warn` | An `assert` inside a `given` or `when` (the `when` half of a `when_then` pair is exempt). |
| `action-in-then` | `warn` | A scenario where no `when` performs an action and a `then` folds the action into its assertion. |
| `unused-interpolation` | `warn` | A `with`-anchored step whose narration interpolates `{name}` — a t-string value or a parameter-table placeholder — that the step body never uses. |
| `tag-shadows-term` | `warn` | A scenario tag whose slug duplicates a glossary term — one concept named through two mechanisms. |
| `dead-term` | `off` | A glossary term referenced by no scenario or step narration and no story activity. Opt in on suites whose glossary is meant to be fully exercised. |

Override severities per rule with `given_lint_rules`, and exempt individual subjects with `given_lint_ignore` — bare node-id globs, or scoped to one rule with a `rule-id:` prefix:

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

An ignore entry that suppresses no finding is itself an error-level `stale-ignore` finding — the list can only shrink, never rot. `--given-lint` and `--no-given-lint` each override the `given_lint` ini for a single run.

Findings print one aligned row each — severity, rule, subject, message, and the source location the rule fired at:

```
============= pytest-given: narration lint (2 findings, 1 error) ==============
ERROR empty-step     tests/test_shop.py::test_buy   given 'a coin' has no code (test_shop.py:12)
WARN  missing-phase  tests/test_shop.py::test_idle  missing: when (test_shop.py:31)
```

The lint is zero-cost when off: nothing extra is captured, and report artifacts are byte-identical with the lint on or off.

