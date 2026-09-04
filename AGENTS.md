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

`uv run nox` runs the default gate — `format`, `lint`, `mypy`, `test`, `coverage` (a 100% target), `audit` (a `pip-audit` of the locked dependencies). The sessions below are on-demand; list them all with `uv run nox -l`.

- `uv run nox -s examples` regenerates the JSON, HTML, and Markdown files under `examples/coffeeshop/`, `examples/hotel-booking/`, and `examples/file-glossary-booking/`. Run after changes to the renderer, templates, plugin output schema, or any example test file, and commit the updated outputs.
- `uv run nox -s self_report` regenerates `examples/self-report/` — pytest-given applied to its own backend tests (see [Writing self-report scenarios](#writing-self-report-scenarios)). Run after decorating more tests or changing decorated ones, and commit the updated outputs.
- **Only commit a regenerated report when its *content* actually changed.**
  - Every regeneration rewrites `commit_sha` (to current HEAD, including the SHA-pinned source-link URLs), `timestamp`, and `duration_ms` in the JSON and HTML, so a report your change didn't really touch still shows a diff — `git checkout` those files rather than committing the noise.
  - **Read the `.md` diff first**: the Markdown carries none of those fields, so it is the behavioral delta of your change in prose. An unchanged `.md` doesn't by itself prove the JSON/HTML are noise-only (glossary and story data never surface in the Markdown); a shifted source line does show up, in the `relpath:line::test_name` anchor under every heading.
  - Regenerate only the reports a change can affect — `examples` narrates `examples/**`, `self_report` narrates `tests/**`. A shifted line number in a decorated backend test is therefore a real self-report change worth committing, even when no example changed.
- Both regeneration sessions run the narration lint (`--given-lint`; see [Narration lint](README.md#narration-lint) and the [design spec](docs/specs/2026-07-05-narration-lint-design.md)): in `self_report` the backend suite has no intentional failures, so an error finding **fails report regeneration** — a real gate. The `examples` session's intentional failures already return a tolerated exit 1 (`success_codes=[0, 1]`) that masks the lint exit code; there the printed "narration lint" summary is the signal. Keep the backend suite lint-clean; a step the lint mis-flags belongs on the `given_lint_ignore` list, whose entries must each suppress a finding (stale entries fail the run). The rule catalog and the ignore mechanics live in the [authoring skill](src/pytest_given/skills_data/pytest-given-authoring/references/scenarios.md) under "Mechanical counterparts"; the honest-two-phase test an ignored `missing-phase` has to pass is under "Phase structure" in the same file.
- `uv run nox -s benchmark` generates the large-scenarios suite and renders its JSON + HTML into `benchmarks/` (gitignored). Run it when a change could move report-generation cost; `benchmarks/bench.py` does size sweeps and cProfile runs directly.
- `uv run nox -s build` builds the wheel + sdist and verifies them the way a consumer would: it checks the wheel carries `py.typed`, the report templates and the bundled skills, then installs it into a throwaway environment and runs a real scenario through it. The in-repo suite imports from `src/`, so it cannot see a packaging regression — this session is the only thing that can. CI runs it on every push; the release workflow runs the same session.

## Releasing

Releases go to PyPI via a manually dispatched [Release workflow](.github/workflows/release.yml), authenticated with Trusted Publishing (no tokens anywhere) and always rehearsed on TestPyPI first. The step-by-step checklist lives in [docs/releasing.md](docs/releasing.md).

The short version: bump `version` in `pyproject.toml` and add a matching `## [x.y.z]` section to `CHANGELOG.md`, land it on `main` (a PR is optional — CI gates direct pushes too), dispatch with `testpypi`, run `uv run nox -s check_release -- testpypi`, then dispatch with `pypi` and re-check with `uv run nox -s check_release`.

## Architecture

`src/pytest_given/` is five library subpackages plus two entry points, with a
strict dependency direction (convention, not lint-enforced):

```
model/                     the leaf — schema, serde, slugs, errors, shared text rules
capture/  lint/  report/   each on model/ only, never on each other
grouping/                  on model/ + capture/
plugin/   cli/             the entry points; may import all five, and hold
                           nothing the five could
```

**Every module has a docstring saying what it is for and why it is shaped that
way.** That is where the detail lives, and it stays true because it sits next
to the code — read it before changing a module. What no filename tells you:

- `grouping/` — the parametrize pass: a scenario's cases collapsed into one
  narrated tree plus a parameter table, refusing the authoring forms that would
  make that tree lie. Runs at session finish *before* the sinks are written, so
  a bare `pytest` failing on one is the point, not a side effect.
- `plugin/__init__.py` is the hook surface pluggy registers — the `pytest11`
  entry point is the package, and pluggy scans a module's attributes for
  `pytest_*` names, so the re-exports there *are* the registration.
- `capture/` imports pytest nowhere, so all of it is unit-testable without a
  session; a stray step warns with `model.PytestGivenWarning`, not pytest's.
- `Glossary` exists twice on purpose: `model/schema.py` holds the storage the
  report carries and serde rebuilds, and `capture/glossary.py` subclasses it
  with the registration API, which needs a caller source location that the leaf
  may not reach for. `pytest_given.Glossary` is the subclass; everything
  internal annotates the base.
- Each package exposes the *whole* job, not its parts: `report.emit_sinks`
  (render → write → discard-on-failure, so a failure leaves no half-written
  report) and `lint.run_lint`. Both entry points go through them, which is what
  keeps `pytest-given report` behaving like the plugin.

`tests/` splits `unit/` (no pytest session needed) from `integration/`, which drives the plugin end to end through `pytester` inner runs (enabled by the root `conftest.py`). Narration written inside an inner run belongs to *that* run's collector — only the outer, decorated test reaches the self-report.

The public API is re-exported from `__init__.py` and documented in the skill's
[references/api.md](src/pytest_given/skills_data/pytest-given-authoring/references/api.md).

### Step text & placeholders

The authoring forms (t-string vs `Template` vs plain string, and where each is rejected) are documented in the skill's [references/api.md](src/pytest_given/skills_data/pytest-given-authoring/references/api.md); design rationale in the [design spec](docs/specs/2026-05-23-structured-step-text-design.md).

## Handling report output

Outputs are opt-in; a bare `uv run pytest` writes nothing. The workflow for reading a run's narration (`--given-md`), querying the JSON report with `jq` by tag/term/status, re-rendering a saved run, and the bare-flag-order trap lives in the [navigating skill](src/pytest_given/skills_data/pytest-given-navigating/SKILL.md).

## Report testing

Any change to `report/templates/` (Jinja, CSS, `app.js`) or the `narration` filter in `html_renderer.py` **must** be Playwright-verified before commit — Python-side regex tests on rendered HTML do not catch broken Alpine expressions, malformed `:class` bindings, or other runtime browser issues (the substring matches even when the attribute is unparseable). Open e.g. `examples/coffeeshop/coffeeshop.html` (regenerate via `uv run nox -s examples`) with the Playwright MCP server, check `browser_console_messages` for errors after init, then drive the changed surface (hover, click, URL hash). Use `browser_snapshot` (not screenshots) to read page content and interact with elements.

- **Don't write Python tests that pin frontend markup** (specific class names, wrapper structure, inline-handler shape, SVG strings). They check implementation details, not behavior, and rot the moment the renderer is refactored. The project has no JS-side UI tests; Playwright is the only verification for frontend concerns. Python tests stay on the renderer's data-shaped contract (what `data-param` value, which scenario IDs, which counts) — not on how the markup is assembled.
- **Don't TDD frontend changes** for the same reason: a failing markup assertion isn't proving the bug exists in the browser, and a passing one isn't proving the fix works. Apply the change, regenerate `examples/`, drive it in Playwright, capture the result.

- The report targets desktop only — assume a minimum viewport width of ~900px. No mobile/responsive layout needed.
- Traceback display and header metadata formatting are known limitations, not current priorities.
- Never save Playwright screenshots into the project directory. Use `/tmp/` or omit the `filename` parameter.

**Setup and known traps** (`.mcp.json`, the `file://` page cache, browser installs) live in [docs/playwright-setup.md](docs/playwright-setup.md). `.mcp.json` is read at **session start**, so check that the `browser_*` tools exist before planning a task that ends in Playwright verification.

## Writing self-report scenarios

The narration rules live in the **`pytest-given-authoring` skill** — whose canonical source is [src/pytest_given/skills_data/](src/pytest_given/skills_data/pytest-given-authoring/SKILL.md) — every link in this document points there. Contributor agents auto-discover the mirrored copy under `.claude/skills/`, and downstream projects get it via `pytest-given skills install`. After editing the canonical copy, regenerate the committed copy with `uv run pytest-given skills install` and commit both (a sync test fails otherwise).

**The skill is documentation with the same sync duty as the README.** A change to the public API surface or its rules updates the README *and* the skill's [references/api.md](src/pytest_given/skills_data/pytest-given-authoring/references/api.md) (which downstream agents rely on instead of the README — it ships in the wheel, version-matched); a change to narration/lint semantics updates [references/scenarios.md](src/pytest_given/skills_data/pytest-given-authoring/references/scenarios.md) and friends. No mechanical check catches content drift between README and skill — treat "does the skill need this too?" as part of every user-facing change.

What is specific to this repo's self-report:

- The glossary handle is `pg` — `GLOSSARY.md` loaded as a `FileGlossary` in `tests/conftest.py` via `tests/ubiquitous_language.py`. Term-rename mechanics live under [Conventions](#conventions); regeneration and lint gating under [Quality gates](#quality-gates).
- **New or changed user-facing behavior needs a scenario, not just a test** — otherwise the behavior is invisible in the report. Decorate the test that best *states* the rule, one per rule, not per branch; the edge cases around it stay plain. Two gaps to check for: a rule the [CHANGELOG](CHANGELOG.md) announces that no scenario names, and a [GLOSSARY.md](GLOSSARY.md) row *asserting* behavior (`Templatize`, `Parameter table`) that no scenario demonstrates.

## Conventions

- Use the canonical vocabulary from [GLOSSARY.md](GLOSSARY.md) in prose as well as code — docs, skill references, and specs say the official term (`term ref`, not a paraphrase like "narrated term"). Naming and rename mechanics live in the skill's [references/glossaries.md](src/pytest_given/skills_data/pytest-given-authoring/references/glossaries.md); here, a rename lands in one commit (glossary row, `pg\[` references, implementation naming) plus a regenerated `uv run nox -s self_report`. Adding a term is safe, but still regenerate.
- Avoid `Any` — use precise types, generics, `TYPE_CHECKING` imports, or `ContextVar[T]` over untyped `threading.local`.
- Use `NewType` for domain-specific IDs (e.g., `NodeId`) and PEP 695 `type` statements for aliases. Avoid raw complex types like `dict[str, tuple[list[str], list[Any]]]` — introduce named types instead.
- Only module-level imports — no inline/function-level imports.
- **pytest config lives in `[tool.pytest]`** — native TOML mode since pytest 8.4/9.0, where lists are real arrays rather than newline-separated strings. `[tool.pytest.ini_options]` is the legacy INI-compat table; **never add it alongside** — pytest raises `UsageError` if both are present. New `addini` options take native types (a `type='linelist'` ini takes a TOML array).
- Cross-platform: plugin and tests must pass on native Windows, macOS, Linux, and WSL (Linux interpreter over a `/mnt/<drive>` Windows checkout). Never hardcode a path separator or assume POSIX semantics — go through `pathlib`, `as_posix()` for stored/serialized paths, resolve before comparing. Path-form folding is confined to `capture/source.py` (mechanics in its docstrings; the why, and how to run one checkout from both Windows and WSL without the venvs colliding, in [docs/wsl-development.md](docs/wsl-development.md)). Only tests asserting WSL `/mnt`-absolute behavior may `skipif(sys.platform == 'win32', …)` — native-Windows pathlib reads `/mnt/<drive>` as drive-relative, not absolute — everything else passes on all four targets.
- Relative imports inside the package throughout — `from .schema import Scenario` for siblings, `from ..model import Scenario` across subpackages (always through the subpackage root, never into its submodules). Tests use absolute imports and may reach into any internal path. The dependency direction those imports must respect is under [Architecture](#architecture).
- Prefer `assert` over `# pragma: no cover` for invariant guards. Asserts document the invariant and fail loudly if violated; pragmas hide the line and silently bail. Reserve `# pragma: no cover` for code that genuinely cannot be exercised by a test (e.g. `if __name__ == '__main__':` script entry).
- Step-down rule: callers before callees, public before private. Read each file top-down from high-level API to implementation details.
- TDD: write tests first
- Commit messages: single line, no co-author trailers, no leading file/area labels like `TODO:` or `README:` — just describe the change ("note example cleanup as todo", not "TODO: note example cleanup"). Conventional-commit-style scope prefixes like `docs:` / `examples:` / `renderer:` are fine when they add information.
- Keep commits coherent: each commit should represent one logical change. Don't split "do X", "tests for X", and "review-fixup for X" into separate commits — squash them before pushing. Don't bundle unrelated changes either.
- **A user-facing change adds its `CHANGELOG.md` entry in the same commit**, under `## [Unreleased]`, in the fitting Keep a Changelog category (each category appears at most once per version — extend the existing heading rather than adding a second one). User-facing = public API, CLI flags, report output, lint rules, bundled skills; internal work (refactors, tests, CI, contributor docs) gets no entry. Release-time version bumps live under [Releasing](#releasing).
- **One sentence per entry**, written for someone upgrading the package: name the symbol, flag, or surface, and say what changed. Only a breaking change earns more — the migration it needs. Cut the rest: rationale, measurements, before/after detail, and anything the reader would discover the moment they look at the thing. Visual and interaction polish is worth mentioning but not itemizing: give it one short collective bullet per release ("the sidebar and its chips are visually tidied"), never a bullet per restyled element. Accessibility fixes are the exception — they stay on their own line, since they change who can use the thing. If a change isn't worth an upgrader's attention at all, it gets none. When in doubt, the shorter entry is the right one.
- Plan files under `docs/superpowers/plans/` are scratch artifacts — never commit them. Spec files under `docs/specs/` are committed.
- New specs land under `docs/specs/proposed/`. When a spec's implementation lands, `git mv` it up one level into `docs/specs/` in the same commit, and fix its relative links in the same edit — a `../`-prefixed link to a sibling spec resolves into `docs/` once the file moves. `ls docs/specs/proposed` is the canonical list of outstanding design work.
- Always run `uv run nox` (or at minimum `uv run nox -s format lint mypy test`) before committing
