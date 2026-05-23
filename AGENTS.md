# Agents

## Project overview

pytest-given is a pytest plugin that generates interactive HTML reports from Given/When/Then annotated Python tests. Inspired by JGiven (Java). The code is the single source of truth — no Gherkin DSL.

## Setup

```bash
uv sync --group dev
```

## Quality gates

Run all checks: `nox`

Individual sessions:
- `nox -s format` — ruff format
- `nox -s lint` — ruff check
- `nox -s mypy` — type checking (strict)
- `nox -s test` — pytest
- `nox -s coverage` — 100% coverage target
- `nox -s audit` — pip-audit
- `nox -s examples` — regenerate `examples/report-data.json` and `examples/report.html`. Run after changes to the renderer, templates, plugin output schema, or `examples/test_examples.py` itself, and commit the updated JSON.

## Architecture

- `src/pytest_given/__init__.py` — Public API: `scenario`, `given`, `when`, `then`, `attach`
- `src/pytest_given/decorators.py` — `StepDescriptor` + `ScenarioDecorator`: dual context-manager/decorator, cross-phase nesting detection, thread-local state
- `src/pytest_given/collector.py` — Step stack, collects scenario data during test execution
- `src/pytest_given/plugin.py` — pytest hooks, parametrized test grouping
- `src/pytest_given/renderer.py` — JSON to self-contained HTML (Jinja2 + Alpine.js)
- `src/pytest_given/cli.py` — Standalone `pytest-given report` command
- `src/pytest_given/templates/` — Jinja2 template, CSS, bundled Alpine.js

## Report testing

A Playwright MCP server is available for visually inspecting the HTML report. Open it with `file:///` URLs pointing to `examples/report.html` (regenerate via `nox -s examples`). Use `browser_snapshot` (not screenshots) to read page content and interact with elements.

- The report targets desktop only — assume a minimum viewport width of ~900px. No mobile/responsive layout needed.
- Traceback display and header metadata formatting are known limitations, not current priorities.
- Never save Playwright screenshots into the project directory. Use `/tmp/` or omit the `filename` parameter.

## Conventions

- Python >= 3.12, pytest >= 9.0
- src layout with hatchling build
- Single quotes (ruff format)
- Strict mypy (`disallow_untyped_defs`). Avoid `Any` — use precise types, generics, `TYPE_CHECKING` imports, or `ContextVar[T]` over untyped `threading.local`.
- Use `NewType` for domain-specific IDs (e.g., `NodeId`) and PEP 695 `type` statements for aliases. Avoid raw complex types like `dict[str, tuple[list[str], list[Any]]]` — introduce named types instead.
- Only module-level imports — no inline/function-level imports.
- Prefer `assert` over `# pragma: no cover` for invariant guards. Asserts document the invariant and fail loudly if violated; pragmas hide the line and silently bail. Reserve `# pragma: no cover` for code that genuinely cannot be exercised by a test (e.g. `if __name__ == '__main__':` script entry).
- Step-down rule: callers before callees, public before private. Read each file top-down from high-level API to implementation details.
- TDD: write tests first
- Commit messages: single line, no co-author trailers
- Keep commits coherent: each commit should represent one logical change. Don't split "do X", "tests for X", and "review-fixup for X" into separate commits — squash them before pushing. Don't bundle unrelated changes either.
- Plan files under `docs/superpowers/plans/` are scratch artifacts — never commit them. Spec files under `docs/superpowers/specs/` are committed.
- Always run `nox` (or at minimum `nox -s format lint mypy test`) before committing
