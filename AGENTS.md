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

## Architecture

- `src/pytest_given/__init__.py` — Public API: `scenario`, `given`, `when`, `then`, `attach`
- `src/pytest_given/step_descriptor.py` — `StepDescriptor`: dual context-manager/decorator, cross-phase nesting detection
- `src/pytest_given/collector.py` — Step stack, collects scenario data during test execution
- `src/pytest_given/plugin.py` — pytest hooks, parametrized test grouping
- `src/pytest_given/renderer.py` — JSON to self-contained HTML (Jinja2 + Alpine.js)
- `src/pytest_given/cli.py` — Standalone `pytest-given report` command
- `src/pytest_given/templates/` — Jinja2 template, CSS, bundled Alpine.js

## Conventions

- Python >= 3.12, pytest >= 9.0
- src layout with hatchling build
- Single quotes (ruff format)
- Strict mypy (`disallow_untyped_defs`)
- Use `NewType` for domain-specific IDs (e.g., `NodeId`) and PEP 695 `type` statements for aliases. Avoid raw complex types like `dict[str, tuple[list[str], list[Any]]]` — introduce named types instead.
- Step-down rule: callers before callees, public before private. Read each file top-down from high-level API to implementation details.
- TDD: write tests first
- Commit messages: single line, no co-author trailers
- Always run `nox` (or at minimum `nox -s format lint mypy test`) before committing
