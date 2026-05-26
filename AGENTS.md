# Agents

## Project overview

See [README.md](README.md) for the user-facing overview, public API, and CLI flags. The rest of this document is contributor-facing.

## Setup

```bash
uv sync --group dev
```

## Quality gates

Run all checks: `uv run nox`

Individual sessions:
- `uv run nox -s format` — ruff format
- `uv run nox -s lint` — ruff check
- `uv run nox -s mypy` — type checking (strict)
- `uv run nox -s test` — pytest
- `uv run nox -s coverage` — 100% coverage target
- `uv run nox -s audit` — pip-audit
- `uv run nox -s examples` — regenerate `examples/report-data.json` and `examples/report.html`. Run after changes to the renderer, templates, plugin output schema, or `examples/test_examples.py` itself, and commit the updated JSON.

## Architecture

- `src/pytest_given/__init__.py` — Public API: `scenario`, `given`, `when`, `then`, `attach`, `Template`
- `src/pytest_given/decorators.py` — `StepDescriptor` + `ScenarioDecorator`: dual context-manager/decorator, cross-phase nesting detection, thread-local state
- `src/pytest_given/template.py` — `Template` (deferred brace substitution for `@scenario(...)`) + `Narration` dataclass (`text` + `parts`) with structured part dataclasses (`NarrationLiteral` / `NarrationValue` / `NarrationPlaceholder` / `NarrationPart` union); `narration_from(...)` dispatches `str` / `Template` / t-string into a `Narration`
- `src/pytest_given/collector.py` — Step stack, collects scenario data during test execution
- `src/pytest_given/plugin.py` — pytest hooks, parametrized test grouping, structural templatize
- `src/pytest_given/renderer.py` — JSON to self-contained HTML (Jinja2 + Alpine.js); single structural `narration` filter dispatching on serialized `Narration` parts
- `src/pytest_given/cli.py` — Standalone `pytest-given report` command
- `src/pytest_given/templates/` — Jinja2 template, CSS, bundled Alpine.js

### Step text & placeholders

Three authoring forms (see [README](README.md#step-text--placeholders) for user-facing docs and the [design spec](docs/superpowers/specs/2026-05-23-structured-step-text-design.md)):

| Context | Form |
|---|---|
| Test body, dynamic | `with given(t'a {cup_size} cup')` (eager t-string) |
| Test body, static | `with given('static text')` |
| `@scenario(name)`, dynamic | `@scenario(Template('Brew {cup_size} ml'))` (deferred, parametrize-bound) |
| `@scenario(name)`, static | `@scenario('static name')` |
| Fixture decorator | `@given('static label')` only |

Lanes don't overlap: `pytest_given.Template` is rejected in `given/when/then/attach`; t-strings are rejected in `@scenario`. `Template` accepts bare identifiers only (no attribute access, no expressions) — t-strings have full expression syntax in test bodies. Parametrized scenarios use case 1's step structure as the merged-template view; if narration *structure* varies per case, split the test instead.

## Report testing

A Playwright MCP server is available for visually inspecting the HTML report. Open it with `file:///` URLs pointing to `examples/report.html` (regenerate via `uv run nox -s examples`). Use `browser_snapshot` (not screenshots) to read page content and interact with elements.

- The report targets desktop only — assume a minimum viewport width of ~900px. No mobile/responsive layout needed.
- Traceback display and header metadata formatting are known limitations, not current priorities.
- Never save Playwright screenshots into the project directory. Use `/tmp/` or omit the `filename` parameter.

## Conventions

- Use the project's canonical vocabulary — see [GLOSSARY.md](GLOSSARY.md). Renames touch the glossary in the same commit.
- src layout with hatchling build
- Single quotes (ruff format)
- Strict mypy (`disallow_untyped_defs`). Avoid `Any` — use precise types, generics, `TYPE_CHECKING` imports, or `ContextVar[T]` over untyped `threading.local`.
- Use `NewType` for domain-specific IDs (e.g., `NodeId`) and PEP 695 `type` statements for aliases. Avoid raw complex types like `dict[str, tuple[list[str], list[Any]]]` — introduce named types instead.
- Only module-level imports — no inline/function-level imports.
- Prefer `assert` over `# pragma: no cover` for invariant guards. Asserts document the invariant and fail loudly if violated; pragmas hide the line and silently bail. Reserve `# pragma: no cover` for code that genuinely cannot be exercised by a test (e.g. `if __name__ == '__main__':` script entry).
- Step-down rule: callers before callees, public before private. Read each file top-down from high-level API to implementation details.
- TDD: write tests first
- Commit messages: single line, no co-author trailers, no leading file/area labels like `TODO:` or `README:` — just describe the change ("note example cleanup as todo", not "TODO: note example cleanup"). Conventional-commit-style scope prefixes like `docs:` / `examples:` / `renderer:` are fine when they add information.
- Keep commits coherent: each commit should represent one logical change. Don't split "do X", "tests for X", and "review-fixup for X" into separate commits — squash them before pushing. Don't bundle unrelated changes either.
- Plan files under `docs/superpowers/plans/` are scratch artifacts — never commit them. Spec files under `docs/superpowers/specs/` are committed.
- Always run `uv run nox` (or at minimum `uv run nox -s format lint mypy test`) before committing
