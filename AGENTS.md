# Agents

## Project overview

See [README.md](README.md) for the user-facing overview, public API, and CLI flags. The rest of this document is contributor-facing.

## Setup

```bash
uv sync --group dev
```

**All Python invocations go through `uv run`** — `uv run pytest …`, `uv run python -m …`, `uv run nox …`. There is no system `python` on PATH; bare `python` / `pytest` calls will fail. This applies to one-off commands (running a single test file, REPL exploration) too, not just nox sessions.

## Quality gates

Run all checks: `uv run nox`. List individual sessions with `uv run nox -l`.

- `uv run nox -s examples` regenerates `examples/report-data.json` and `examples/report.html`. Run after changes to the renderer, templates, plugin output schema, or `examples/test_examples.py` itself, and commit the updated JSON.
- `uv run nox -s coverage` enforces a 100% coverage target.

## Architecture

- `src/pytest_given/__init__.py` — Public API: `scenario`, `given`, `when`, `then`, `attach`, `Template`
- `src/pytest_given/plugin.py` — pytest hooks, parametrized test grouping, structural templatize, scenario-source capture from `item.location`. Top-level orchestrator; allowed to import from all three subpackages.
- `src/pytest_given/capture/decorators.py` — `StepDescriptor` + `ScenarioDecorator`: dual context-manager/decorator, cross-phase nesting detection, thread-local state
- `src/pytest_given/capture/collector.py` — Step stack, collects scenario data during test execution
- `src/pytest_given/capture/template.py` — `Template` (deferred brace substitution for `@scenario(...)`) + `narration_from(...)` (dispatches `str` / `Template` / t-string into a `Narration`) + `parse_tstring(...)`
- `src/pytest_given/model/schema.py` — Frozen / mutable dataclasses for the report tree (`ReportData`, `Metadata`, `Scenario`, `Step`, `Attachment`, `ErrorInfo`, `ParameterTable`, `ParameterCase`, `SourceLocation`); `Narration` + `NarrationLiteral` / `NarrationValue` / `NarrationPlaceholder` / `NarrationPart` union; `NodeId` / `Phase` aliases
- `src/pytest_given/model/serde.py` — `report_to_dict` / `report_from_dict` boundary between JSON and the dataclass model; discriminates the three `NarrationPart` variants by key
- `src/pytest_given/model/errors.py` — `PytestGivenError`
- `src/pytest_given/report/renderer.py` — Reads JSON via `report_from_dict` and walks typed dataclasses; emits self-contained HTML (Jinja2 + Alpine.js); single structural `narration` filter dispatching on `NarrationPart` variants via `match`/`case`
- `src/pytest_given/report/source_link.py` — Preset resolution (`vscode` / `cursor` / `zed` / `pycharm` / `github`), template variable substitution, GitHub org/repo + commit-SHA detection for `--given-source-link`
- `src/pytest_given/report/cli.py` — Standalone `pytest-given report` command (mirrors `--given-source-link` as `--source-link`)
- `src/pytest_given/report/templates/` — Jinja2 template, CSS, bundled Alpine.js

### Step text & placeholders

Three authoring forms (see [README](README.md#step-text--placeholders) for user-facing docs and the [design spec](docs/superpowers/specs/2026-05-23-structured-step-text-design.md)):

| Context | Form |
|---|---|
| Test body, dynamic | `with given(t'a {cup_size} cup')` (eager t-string) |
| Test body, static | `with given('static text')` |
| `@scenario(name)`, dynamic | `@scenario(Template('Brew {cup_size} ml'))` (deferred, parametrize-bound) |
| `@scenario(name)`, static | `@scenario('static name')` |
| Fixture decorator | `@given('static label')` only |
| Helper-function decorator, dynamic | `@when(Template('I insert ${amount}'))` (deferred, helper-arg-bound) |
| Helper-function decorator, static | `@when('static label')` |

Lanes don't overlap: t-strings are rejected in `@scenario` and on any decorator (their values aren't in scope at decoration time); `pytest_given.Template` is rejected in `with given/when/then(...)` (test-body t-strings handle that case) and on fixtures (use a plain string label). `Template` accepts bare identifiers only (no attribute access, no expressions) — t-strings have full expression syntax in test bodies. Helper-function `Template` placeholders must name a positional-or-keyword parameter; `*args` / `**kwargs` placeholders raise at decoration time. Parametrized scenarios use case 1's step structure as the merged-template view; if narration *structure* varies per case, split the test instead.

## Report testing

Any change to `report/templates/` (Jinja, CSS, `app.js`) or the `narration` filter in `renderer.py` **must** be Playwright-verified before commit — Python-side regex tests on rendered HTML do not catch broken Alpine expressions, malformed `:class` bindings, or other runtime browser issues (the substring matches even when the attribute is unparseable). Open `examples/report.html` (regenerate via `uv run nox -s examples`) with the Playwright MCP server, check `browser_console_messages` for errors after init, then drive the changed surface (hover, click, URL hash). Use `browser_snapshot` (not screenshots) to read page content and interact with elements.

- **Don't write Python tests that pin frontend markup** (specific class names, wrapper structure, inline-handler shape, SVG strings). They check implementation details, not behavior, and rot the moment the renderer is refactored. The project has no JS-side UI tests; Playwright is the only verification for frontend concerns. Python tests stay on the renderer's data-shaped contract (what `data-param` value, which scenario IDs, which counts) — not on how the markup is assembled.
- **Don't TDD frontend changes** for the same reason: a failing markup assertion isn't proving the bug exists in the browser, and a passing one isn't proving the fix works. Apply the change, regenerate `examples/`, drive it in Playwright, capture the result.

- The report targets desktop only — assume a minimum viewport width of ~900px. No mobile/responsive layout needed.
- Traceback display and header metadata formatting are known limitations, not current priorities.
- Never save Playwright screenshots into the project directory. Use `/tmp/` or omit the `filename` parameter.
- If the Playwright MCP browser install hangs after the download reaches 100% (microsoft/playwright#40998 in alpha builds), switch `.mcp.json` from `--browser chromium` to `--browser chrome` to use system Chrome.

## Conventions

- Use the project's canonical vocabulary — see [GLOSSARY.md](GLOSSARY.md). Renames touch the glossary in the same commit.
- Avoid `Any` — use precise types, generics, `TYPE_CHECKING` imports, or `ContextVar[T]` over untyped `threading.local`.
- Use `NewType` for domain-specific IDs (e.g., `NodeId`) and PEP 695 `type` statements for aliases. Avoid raw complex types like `dict[str, tuple[list[str], list[Any]]]` — introduce named types instead.
- Only module-level imports — no inline/function-level imports.
- Subpackage boundaries (convention, not lint-enforced): `src/pytest_given/` is split into three subpackages with a strict dependency direction. `model/` is the leaf; `capture/` and `report/` both depend on `model/`; they do not depend on each other. `plugin.py` sits at the top level as the orchestrator and is allowed to import from all three. Inside the package, use relative imports throughout — `from .schema import Scenario` for siblings, `from ..model import Scenario` for cross-subpackage (always through the subpackage root, not into its submodules). The top-level `__init__.py` and `plugin.py` also use relative imports (`from .capture import …`). Tests use absolute imports and may reach into any internal path.
- Prefer `assert` over `# pragma: no cover` for invariant guards. Asserts document the invariant and fail loudly if violated; pragmas hide the line and silently bail. Reserve `# pragma: no cover` for code that genuinely cannot be exercised by a test (e.g. `if __name__ == '__main__':` script entry).
- Step-down rule: callers before callees, public before private. Read each file top-down from high-level API to implementation details.
- TDD: write tests first
- Commit messages: single line, no co-author trailers, no leading file/area labels like `TODO:` or `README:` — just describe the change ("note example cleanup as todo", not "TODO: note example cleanup"). Conventional-commit-style scope prefixes like `docs:` / `examples:` / `renderer:` are fine when they add information.
- Keep commits coherent: each commit should represent one logical change. Don't split "do X", "tests for X", and "review-fixup for X" into separate commits — squash them before pushing. Don't bundle unrelated changes either.
- Plan files under `docs/superpowers/plans/` are scratch artifacts — never commit them. Spec files under `docs/superpowers/specs/` are committed.
- New specs land under `docs/superpowers/specs/proposed/`. When a spec's implementation lands, `git mv` it up one level into `docs/superpowers/specs/` in the same commit. `ls specs/proposed` is the canonical list of outstanding design work.
- Always run `uv run nox` (or at minimum `uv run nox -s format lint mypy test`) before committing
