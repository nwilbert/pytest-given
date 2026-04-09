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
- `src/pytest_given/serializer.py` — Model to JSON
- `src/pytest_given/renderer.py` — JSON to self-contained HTML (Jinja2 + Alpine.js)
- `src/pytest_given/cli.py` — Standalone `pytest-given report` command
- `src/pytest_given/templates/` — Jinja2 template, CSS, bundled Alpine.js

## Conventions

- Python >= 3.12, pytest >= 9.0
- src layout with hatchling build
- Single quotes (ruff format)
- Strict mypy (`disallow_untyped_defs`)
- TDD: write tests first
- Commit messages: single line, no co-author trailers
