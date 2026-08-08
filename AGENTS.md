# Agents

## Project overview

See [README.md](README.md) for the user-facing overview, public API, and CLI flags. The rest of this document is contributor-facing.

## Setup

```bash
uv sync --group dev
```

**All Python invocations go through `uv run`** — `uv run pytest …`, `uv run python -m …`, `uv run nox …`. There is no system `python` on PATH; bare `python` / `pytest` calls will fail. This applies to one-off commands (running a single test file, REPL exploration) too, not just nox sessions.

**Never prepend `cd <path> &&` to commands.** The working directory is already set to the project root; the `cd` is redundant and triggers a permission prompt.

## Quality gates

Run all checks: `uv run nox`. List individual sessions with `uv run nox -l`.

- `uv run nox -s examples` regenerates the JSON, HTML, and Markdown files under `examples/coffeeshop/`, `examples/hotel-booking/`, and `examples/file-glossary-booking/`. Run after changes to the renderer, templates, plugin output schema, or any example test file, and commit the updated outputs.
- `uv run nox -s self_report` regenerates `examples/self-report/` — pytest-given applied to its own backend tests (see [Writing self-report scenarios](#writing-self-report-scenarios)). Run after decorating more tests or changing decorated ones, and commit the updated outputs.
- **Only commit a regenerated report when its *content* actually changed.** Every regeneration rewrites `commit_sha` (to current HEAD, including the SHA-pinned source-link URLs), `timestamp`, and `duration_ms` in the JSON and HTML, so a report whose real content is untouched by your change will still show a diff — `git checkout` those files rather than committing the noise. The Markdown report carries none of these fields: it is deterministic, so **read the `.md` diff first** — it is the behavioural delta of your change in prose. (An unchanged `.md` doesn't by itself prove the JSON/HTML are noise-only: source-line shifts and glossary/story data don't surface in the Markdown.) Regenerate only the reports a change can affect: the `examples` reports narrate the `examples/**` test files, and the `self_report` narrates the backend tests under `tests/**` (so a shifted line number in a decorated backend test — e.g. from adding or removing code above it — is a real self-report change worth committing, even when no example changed).
- Both regeneration sessions run the narration lint (`--given-lint=true`; see [Narration lint](README.md#narration-lint) and the [design spec](docs/specs/2026-07-05-narration-lint-design.md)): in `self_report` the backend suite has no intentional failures, so an error finding **fails report regeneration** — a real gate. The `examples` session's intentional failures already return a tolerated exit 1 (`success_codes=[0, 1]`) that masks the lint exit code; there the printed "narration lint" summary is the signal. Keep the backend suite lint-clean; a step the lint mis-flags belongs on the `given_lint_ignore` list, whose entries must each suppress a finding (stale entries fail the run). The rule catalog and the honest-two-phase ignore convention live in the [authoring skill](.claude/skills/pytest-given-authoring/references/scenarios.md) under "Mechanical counterparts".
- `uv run nox -s coverage` enforces a 100% coverage target.
- `uv run nox -s build` builds the wheel + sdist and verifies them the way a consumer would: it checks the wheel carries `py.typed`, the report templates and the bundled skills, then installs it into a throwaway environment and runs a real scenario through it. The in-repo suite imports from `src/`, so it cannot see a packaging regression — this session is the only thing that can. CI runs it on every push; the release workflow runs the same session.

## Releasing

Releases go to PyPI via a manually dispatched [Release workflow](.github/workflows/release.yml), authenticated with Trusted Publishing (no tokens anywhere) and always rehearsed on TestPyPI first. The step-by-step checklist, the troubleshooting table, and the one-time index/environment setup live in [docs/releasing.md](docs/releasing.md).

The short version: bump `version` in `pyproject.toml` and add a matching `## [x.y.z]` section to `CHANGELOG.md` in a PR, merge to `main`, dispatch with `testpypi`, check the published result, then dispatch with `pypi`.

## Architecture

- `src/pytest_given/__init__.py` — Public API re-exports; the full surface is documented in the skill's [references/api.md](src/pytest_given/skills_data/pytest-given-authoring/references/api.md)
- `src/pytest_given/plugin.py` — pytest hooks, parametrized test grouping, structural templatize, scenario-source capture from `item.location`. Top-level orchestrator.
- `src/pytest_given/cli.py` — Console entry point (`pytest-given`): argparse root, `skills install` subcommand (mirrors `src/pytest_given/skills_data/` into a project's `.claude/skills/`, `--check` for drift). Top-level like `plugin.py`; delegates `report` to `report/cli.py`.
- `src/pytest_given/capture/decorators.py` — `StepDescriptor` + `ScenarioDecorator`: dual context-manager/decorator, cross-phase nesting detection, thread-local state
- `src/pytest_given/capture/collector.py` — Step stack, collects scenario data during test execution
- `src/pytest_given/capture/template.py` — `Template` (deferred brace substitution for `@scenario(...)`) + `narration_from(...)` (dispatches `str` / `Template` / t-string into a `Narration`) + `parse_tstring(...)`
- `src/pytest_given/capture/source.py` — Rootdir-aware `capture_caller_source(skip=...)` helper using `inspect.stack`; used by `story()` and glossary registration to record their construction site as a `SourceLocation`
- `src/pytest_given/model/schema.py` — Frozen / mutable dataclasses for the report tree, the `Narration` part union, and the `NodeId` / `Phase` aliases
- `src/pytest_given/model/serde.py` — `report_to_dict` / `report_from_dict` boundary between JSON and the dataclass model; discriminates the three `NarrationPart` variants by key
- `src/pytest_given/model/errors.py` — `PytestGivenError`
- `src/pytest_given/lint/` — Narration lint: `base.py` (Finding model + rule catalog as data), `config.py` (`given_lint_rules` / `given_lint_ignore` parsing, `apply_config`), `runtime_rules.py` (rules over the recorded model), `ast_rules.py` (rules over step bodies anchored to their `with` / helper `FunctionDef`). Pure — imports only from `model/`; findings surface via the terminal summary and exit code in `plugin.py`, never in report artifacts
- `src/pytest_given/report/html_renderer.py` — Reads JSON via `report_from_dict` and walks typed dataclasses; emits self-contained HTML (Jinja2 + Alpine.js); single structural `narration` filter dispatching on `NarrationPart` variants via `match`/`case`
- `src/pytest_given/report/md_renderer.py` — Plain-text Markdown renderer over the same typed model; `«term»` markers, no browser needed
- `src/pytest_given/report/source_link.py` — Preset resolution (`vscode` / `cursor` / `zed` / `pycharm` / `github`), template variable substitution, GitHub org/repo + commit-SHA detection for `--given-source-link`
- `src/pytest_given/report/cli.py` — The `pytest-given report` subcommand (mirrors `--given-source-link` as `--source-link`); registered on the root parser owned by `cli.py`
- `src/pytest_given/report/templates/` — Jinja2 template, CSS, bundled Alpine.js

### Step text & placeholders

The authoring forms (t-string vs `Template` vs plain string, and where each is rejected) are documented in the skill's [references/api.md](src/pytest_given/skills_data/pytest-given-authoring/references/api.md); design rationale in the [design spec](docs/specs/2026-05-23-structured-step-text-design.md).

## Handling report output

Outputs are opt-in; a bare `uv run pytest` writes nothing. The workflow for reading a run's narration (`--given-md`), querying the JSON report with `jq` by tag/term/status, re-rendering a saved run, and the bare-flag-order trap lives in the [navigating skill](.claude/skills/pytest-given-navigating/SKILL.md).

## Report testing

Any change to `report/templates/` (Jinja, CSS, `app.js`) or the `narration` filter in `html_renderer.py` **must** be Playwright-verified before commit — Python-side regex tests on rendered HTML do not catch broken Alpine expressions, malformed `:class` bindings, or other runtime browser issues (the substring matches even when the attribute is unparseable). Open e.g. `examples/coffeeshop/coffeeshop.html` (regenerate via `uv run nox -s examples`) with the Playwright MCP server, check `browser_console_messages` for errors after init, then drive the changed surface (hover, click, URL hash). Use `browser_snapshot` (not screenshots) to read page content and interact with elements.

- **Don't write Python tests that pin frontend markup** (specific class names, wrapper structure, inline-handler shape, SVG strings). They check implementation details, not behavior, and rot the moment the renderer is refactored. The project has no JS-side UI tests; Playwright is the only verification for frontend concerns. Python tests stay on the renderer's data-shaped contract (what `data-param` value, which scenario IDs, which counts) — not on how the markup is assembled.
- **Don't TDD frontend changes** for the same reason: a failing markup assertion isn't proving the bug exists in the browser, and a passing one isn't proving the fix works. Apply the change, regenerate `examples/`, drive it in Playwright, capture the result.

- The report targets desktop only — assume a minimum viewport width of ~900px. No mobile/responsive layout needed.
- Traceback display and header metadata formatting are known limitations, not current priorities.
- Never save Playwright screenshots into the project directory. Use `/tmp/` or omit the `filename` parameter.
- If the Playwright MCP browser install hangs after the download reaches 100% (microsoft/playwright#40998 in alpha builds), switch `.mcp.json` from `--browser chromium` to `--browser chrome` to use system Chrome.

## Writing self-report scenarios

The narration rules live in the **`pytest-given-authoring` skill** — auto-discovered by contributor agents from [.claude/skills/pytest-given-authoring/](.claude/skills/pytest-given-authoring/SKILL.md) and shipped to downstream projects via `pytest-given skills install`. The canonical source is [src/pytest_given/skills_data/](src/pytest_given/skills_data/pytest-given-authoring/SKILL.md); after editing it, regenerate the committed copy with `uv run pytest-given skills install` and commit both (a sync test fails otherwise). The subsection below covers only what is specific to this repo's self-report.

**The skill is documentation with the same sync duty as the README.** A change to the public API surface or its rules updates the README *and* the skill's [references/api.md](src/pytest_given/skills_data/pytest-given-authoring/references/api.md) (which downstream agents rely on instead of the README — it ships in the wheel, version-matched); a change to narration/lint semantics updates [references/scenarios.md](src/pytest_given/skills_data/pytest-given-authoring/references/scenarios.md) and friends. No mechanical check catches content drift between README and skill — treat "does the skill need this too?" as part of every user-facing change.

### Self-report mechanics (this repo)

- The glossary handle is `pg` — `GLOSSARY.md` loaded as a `FileGlossary` in `tests/conftest.py` via `tests/ubiquitous_language.py`. Term-rename mechanics live under [Conventions](#conventions).
- Regeneration (`uv run nox -s self_report`), narration-lint gating, and the commit-noise / `.md`-diff-review rules live under [Quality gates](#quality-gates).

## Conventions

- Use the project's canonical vocabulary — see [GLOSSARY.md](GLOSSARY.md) — in prose as well as code: docs, skill references, and specs say the official term (`term ref`, not a paraphrase like "narrated term"). Term-naming and rename mechanics live in the skill's [references/glossaries.md](src/pytest_given/skills_data/pytest-given-authoring/references/glossaries.md) — a rename lands everywhere at once: glossary row, `pg\[` references, and the implementation naming. Repo specifics: all of it in the same commit, then `uv run nox -s self_report` and commit the regenerated report (adding a term is safe, but still regenerate).
- Avoid `Any` — use precise types, generics, `TYPE_CHECKING` imports, or `ContextVar[T]` over untyped `threading.local`.
- Use `NewType` for domain-specific IDs (e.g., `NodeId`) and PEP 695 `type` statements for aliases. Avoid raw complex types like `dict[str, tuple[list[str], list[Any]]]` — introduce named types instead.
- Only module-level imports — no inline/function-level imports.
- **pytest config lives in `[tool.pytest]` (native TOML mode).** Since pytest 8.4/9.0, `pyproject.toml`'s `[tool.pytest]` table is parsed with native TOML types — lists are real arrays, not newline-separated strings — and this is the table the project uses (`testpaths = ["tests"]`). `[tool.pytest.ini_options]` is the legacy string-based INI-compat mode; **don't add it alongside `[tool.pytest]`** — pytest raises `UsageError` if both are present. New `addini` options are configured here as native types (a `type='linelist'` ini takes a TOML array).
- Cross-platform: the plugin and its tests must run on native Windows, macOS, Linux, and WSL (Linux interpreter over a `/mnt/<drive>` Windows checkout). Never hardcode a path separator or assume POSIX semantics — go through `pathlib`, normalize with `as_posix()` for stored/serialized paths, and resolve before comparing. The one platform seam is `capture/source.py`, which folds Windows-style and `/mnt/<drive>` path forms into the running platform's native one (mechanics in its docstrings). Tests that assert WSL/`/mnt`-absolute behavior must `skipif(sys.platform == 'win32', …)` — native-Windows pathlib treats `/mnt/<drive>` as drive-relative, not absolute — but every other test must pass on all four targets.
- Subpackage boundaries (convention, not lint-enforced): `src/pytest_given/` is split into four subpackages with a strict dependency direction. `model/` is the leaf; `capture/`, `lint/`, and `report/` all depend on `model/`; they do not depend on each other. `plugin.py` sits at the top level as the orchestrator and is allowed to import from all four. Inside the package, use relative imports throughout — `from .schema import Scenario` for siblings, `from ..model import Scenario` for cross-subpackage (always through the subpackage root, not into its submodules). The top-level `__init__.py` and `plugin.py` also use relative imports (`from .capture import …`). Tests use absolute imports and may reach into any internal path.
- Prefer `assert` over `# pragma: no cover` for invariant guards. Asserts document the invariant and fail loudly if violated; pragmas hide the line and silently bail. Reserve `# pragma: no cover` for code that genuinely cannot be exercised by a test (e.g. `if __name__ == '__main__':` script entry).
- Step-down rule: callers before callees, public before private. Read each file top-down from high-level API to implementation details.
- TDD: write tests first
- Commit messages: single line, no co-author trailers, no leading file/area labels like `TODO:` or `README:` — just describe the change ("note example cleanup as todo", not "TODO: note example cleanup"). Conventional-commit-style scope prefixes like `docs:` / `examples:` / `renderer:` are fine when they add information.
- Keep commits coherent: each commit should represent one logical change. Don't split "do X", "tests for X", and "review-fixup for X" into separate commits — squash them before pushing. Don't bundle unrelated changes either.
- Plan files under `docs/superpowers/plans/` are scratch artifacts — never commit them. Spec files under `docs/specs/` are committed.
- New specs land under `docs/specs/proposed/`. When a spec's implementation lands, `git mv` it up one level into `docs/specs/` in the same commit. `ls docs/specs/proposed` is the canonical list of outstanding design work.
- Always run `uv run nox` (or at minimum `uv run nox -s format lint mypy test`) before committing
