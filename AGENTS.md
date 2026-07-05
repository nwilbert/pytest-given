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

- `uv run nox -s examples` regenerates the JSON and HTML files under `examples/coffeeshop/`, `examples/hotel-booking/`, and `examples/file-glossary-booking/`. Run after changes to the renderer, templates, plugin output schema, or any example test file, and commit the updated outputs.
- `uv run nox -s self_report` regenerates `examples/self-report/` — pytest-given applied to its own backend tests. Many unit tests are `@scenario`-decorated and narrate the plugin's behaviour in the vocabulary of [GLOSSARY.md](GLOSSARY.md), loaded as a `FileGlossary` in `tests/conftest.py` (via `tests/_vocab.py`). Run after decorating more tests, and commit the updated outputs. See [Writing self-report scenarios](#writing-self-report-scenarios) for the tagging and narration conventions.
- **Only commit a regenerated report when its *content* actually changed.** Every regeneration rewrites `commit_sha` (to current HEAD) and `duration_ms` (timing noise), so a report whose real content is untouched by your change will still show a diff — `git checkout` those files rather than committing the noise. Regenerate only the reports a change can affect: the `examples` reports narrate the `examples/**` test files, and the `self_report` narrates the backend tests under `tests/**` (so a shifted line number in a decorated backend test — e.g. from adding or removing code above it — is a real self-report change worth committing, even when no example changed).
- `uv run nox -s coverage` enforces a 100% coverage target.

## Architecture

- `src/pytest_given/__init__.py` — Public API: `scenario`, `given`, `when`, `then`, `attach`, `Template`
- `src/pytest_given/plugin.py` — pytest hooks, parametrized test grouping, structural templatize, scenario-source capture from `item.location`. Top-level orchestrator; allowed to import from all three subpackages.
- `src/pytest_given/capture/decorators.py` — `StepDescriptor` + `ScenarioDecorator`: dual context-manager/decorator, cross-phase nesting detection, thread-local state
- `src/pytest_given/capture/collector.py` — Step stack, collects scenario data during test execution
- `src/pytest_given/capture/template.py` — `Template` (deferred brace substitution for `@scenario(...)`) + `narration_from(...)` (dispatches `str` / `Template` / t-string into a `Narration`) + `parse_tstring(...)`
- `src/pytest_given/capture/source.py` — Rootdir-aware `capture_caller_source(skip=...)` helper using `inspect.stack`; used by `story()` and glossary registration to record their construction site as a `SourceLocation`
- `src/pytest_given/model/schema.py` — Frozen / mutable dataclasses for the report tree (`ReportData`, `Metadata`, `Scenario`, `Step`, `Attachment`, `ErrorInfo`, `ParameterTable`, `ParameterCase`, `SourceLocation`); `Narration` + `NarrationLiteral` / `NarrationValue` / `NarrationPlaceholder` / `NarrationPart` union; `NodeId` / `Phase` aliases
- `src/pytest_given/model/serde.py` — `report_to_dict` / `report_from_dict` boundary between JSON and the dataclass model; discriminates the three `NarrationPart` variants by key
- `src/pytest_given/model/errors.py` — `PytestGivenError`
- `src/pytest_given/report/renderer.py` — Reads JSON via `report_from_dict` and walks typed dataclasses; emits self-contained HTML (Jinja2 + Alpine.js); single structural `narration` filter dispatching on `NarrationPart` variants via `match`/`case`
- `src/pytest_given/report/source_link.py` — Preset resolution (`vscode` / `cursor` / `zed` / `pycharm` / `github`), template variable substitution, GitHub org/repo + commit-SHA detection for `--given-source-link`
- `src/pytest_given/report/cli.py` — Standalone `pytest-given report` command (mirrors `--given-source-link` as `--source-link`)
- `src/pytest_given/report/templates/` — Jinja2 template, CSS, bundled Alpine.js

### Step text & placeholders

Three authoring forms (see [README](README.md#step-text--placeholders) for user-facing docs and the [design spec](docs/specs/2026-05-23-structured-step-text-design.md)):

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

Any change to `report/templates/` (Jinja, CSS, `app.js`) or the `narration` filter in `renderer.py` **must** be Playwright-verified before commit — Python-side regex tests on rendered HTML do not catch broken Alpine expressions, malformed `:class` bindings, or other runtime browser issues (the substring matches even when the attribute is unparseable). Open e.g. `examples/coffeeshop/coffeeshop.html` (regenerate via `uv run nox -s examples`) with the Playwright MCP server, check `browser_console_messages` for errors after init, then drive the changed surface (hover, click, URL hash). Use `browser_snapshot` (not screenshots) to read page content and interact with elements.

- **Don't write Python tests that pin frontend markup** (specific class names, wrapper structure, inline-handler shape, SVG strings). They check implementation details, not behavior, and rot the moment the renderer is refactored. The project has no JS-side UI tests; Playwright is the only verification for frontend concerns. Python tests stay on the renderer's data-shaped contract (what `data-param` value, which scenario IDs, which counts) — not on how the markup is assembled.
- **Don't TDD frontend changes** for the same reason: a failing markup assertion isn't proving the bug exists in the browser, and a passing one isn't proving the fix works. Apply the change, regenerate `examples/`, drive it in Playwright, capture the result.

- The report targets desktop only — assume a minimum viewport width of ~900px. No mobile/responsive layout needed.
- Traceback display and header metadata formatting are known limitations, not current priorities.
- Never save Playwright screenshots into the project directory. Use `/tmp/` or omit the `filename` parameter.
- If the Playwright MCP browser install hangs after the download reaches 100% (microsoft/playwright#40998 in alpha builds), switch `.mcp.json` from `--browser chromium` to `--browser chrome` to use system Chrome.

## Writing self-report scenarios

When decorating a backend test with `@scenario`, the goal is a report that reads as a truthful behavioural spec. Keep these rules:

- **Narrate in glossary vocabulary.** Reference terms as `pg['Term']` inside t-string step text (e.g. `t'a {pg["File glossary"]} loaded from a file'`). Term refs are what power the Glossary tab's per-term filter, and they render as pills.
- **Every step maps to load-bearing code.** `given` arranges, `when` performs the one call under test, `then` asserts its result. Never write a placeholder step like `with given(...): pass` — a step with no code is a lie in the report. Delete it.
- **Put the system-under-test call in `when`, not folded into the `then` assertion.** Prefer `with when(...): result = sut(x)` then `with then(...): assert result == …` over `with then(...): assert sut(x) == …`. The report should show the action, not hide it inside a check.
- **When the construction *is* the action under test, `when` builds it and `given` shows only the input.** Don't fold the constructor into the `given` (it hides the action) or into the `then` (it hides it inside a check). If a scenario asserts a property of a freshly-loaded/parsed/built object — `FileGlossary(path)` starts kindless, `story(title)` derives its id, `path(*words)` yields all words — split it: `given` holds and (when useful) `attach`es the raw input (the Markdown file, the title, the word list); `when` runs the constructor; `then` asserts on the result. A two-phase `given` that both arranges the input *and* constructs the object under test is the most common missed `when`.
- **Two phases is fine when honest.** If the assertion inspects a *static property of the arranged state* (not a return value of an action), `given` + `then` is truthful — don't invent a `when`. Likewise a pure "constructing X raises" check needs no `given`.
- **Surface the arrangement as a `given`, don't hide it in the assertion.** If a scenario feeds the action a module constant or a value it builds on the fly (a document string, a path, a list of rows), bind that input in a `given` step rather than passing the literal straight into the `when`/`then`/`pytest.raises` call. For a one-off, construct it in an explicit `with given(...)` block.
- **Decide a fixture's `given` by what it holds, not by the fact that it's a fixture.** A fixture carrying a **domain value the scenario is about** — an actor, a document, an entity it acts on — *is* arrangement: decorate it `@given('…')` (a `@pytest.fixture` wrapped with `@given`) so it surfaces as a `given` step, the same way you'd narrate that value if you built it inline. A fixture that is only **infrastructure** (a `Glossary()`, `tmp_path`, a connection) stays a bare `@pytest.fixture` — it's plumbing, not story. The deciding test: *would you write a `given` for this value if you constructed it inline in the test body?* If yes, decorate the fixture, so fixture-sourced scenarios read the same as inline ones (the `guest`/`search`/`room` handles in `test_story.py` are `@given`-decorated for exactly this reason; the `g` `Glossary()` they build on is not). Don't leave the same arrangement visible in one scenario and hidden in another just because one built it inline and the other pulled a fixture.
- **A parametrized value can be a `given` too.** Inputs from `@pytest.mark.parametrize` already show in the parameter table, so they don't *need* a `given`. When one reads as an *arrangement* the reader should see named up front (rather than as the subject of the action), surface it as a `given` via `Annotated[..., given(Template('… {col} …'))]` on that parameter (see the `id_derive` slug tests in `test_glossary.py` and the `Template` placeholder test in `test_template.py`). For a one-arg pure function either reading is honest — it's a judgment call, not a mandate.
- **Keep pytest-given narration and real assertions separate.** Nest the vanilla `pytest.raises` inside the narration — never fold it into a narration-named helper. The report step and the actual assertion stay visibly distinct constructs. (Tests are exempt from ruff `SIM117` so this nesting is allowed.)
- **Narrate an expected raise as `when_then` — the action and the raise are two steps.** The raise *is* an outcome, so keep it distinct from the action that triggered it: `with when_then('the action', 'a `PytestGivenError` is raised'), pytest.raises(Exc, match=…): sut(x)` emits a `when` (wrapping the call) and a sibling `then` (the outcome). Write the `then` as a real outcome, not the bare mechanism: name the exception type (`'a `PytestGivenError` is raised'`) and, when the `match=` pins a specific message, reflect that finding in domain terms (`'no pipe table is reported'`, `'the misspelt term is flagged with a hint'`). Avoid a contentless `'it raises'`. The `when` runs the body; the `then` is emitted once the inner `pytest.raises` swallows the error.
- **Tag orthogonally to the glossary — never duplicate a term.** A tag that restates a glossary term (there is no `coverage` / `file-glossary` / `glossary` tag) is redundant: filter those feature areas via the term instead, and make sure the scenarios reference that term. Tags carry only what the glossary can't: behaviour (`happy-path`, `validation`), mechanism (`parametrization`), and feature areas with no matching term (`markdown`, `step-text`, `story-grammar`, `kind-inference`).
- **Convert behaviour, not plumbing.** Decorate tests that assert a rule (inference, grammar, dispatch, coverage). Leave trivial getters, constructors, and dataclass round-trips as plain tests — they add report noise, not behaviour.
- **Attach the concrete artifact a `given` can only describe.** When a step arranges a multi-line input the step text abstracts — a Markdown glossary document, a source snippet — `attach('label', text)` it onto that step so a report reader sees the real input inline instead of chasing a source link. Attach on the arranging step (`given` or a `@given` fixture body), never on `when`/`then`, and only for inputs the step text can't carry (skip it when the arrangement is a bare path or a small value already shown in the parameter table). See the `test_markdown_glossary.py` / `test_file_glossary.py` scenarios for the pattern.
- **Keep step text short.** A t-string with two or three pills reaches the 88-column limit fast; move detail into the node structure rather than one long sentence.

## Conventions

- Use the project's canonical vocabulary — see [GLOSSARY.md](GLOSSARY.md). Renames touch the glossary in the same commit.
  - **Term headers are natural-language, not class names.** Name a term for the concept a human would say (`Activity Part`, `File glossary`, `Deferred term`) and spell the implementing class (`ActivityPart`, `FileGlossary`, `DeferredTermHandle`) inside the *meaning* column. A one-word term may coincide with its class (`Scenario`, `Step`, `Story`) only because the class is already the natural word — multi-word CamelCase never is.
  - **Renaming or removing a term header is a code change, not just a doc edit.** `GLOSSARY.md` is loaded live as a `FileGlossary` (`pg`) by the backend tests (`tests/_vocab.py`), and a header's slug (`id_derive`: lowercased, non-alnum → `-`) is the lookup key. `FileGlossary` and `File glossary` derive *different* slugs, so a rename breaks every `pg['OldName']` reference. When you rename/remove a term: grep `pg\[` for the old name, update the references, then `uv run nox -s self_report` and commit the regenerated report. Adding a new term is safe (it just appears in the Glossary tab), but still regenerate the self-report since its content changed.
- Avoid `Any` — use precise types, generics, `TYPE_CHECKING` imports, or `ContextVar[T]` over untyped `threading.local`.
- Use `NewType` for domain-specific IDs (e.g., `NodeId`) and PEP 695 `type` statements for aliases. Avoid raw complex types like `dict[str, tuple[list[str], list[Any]]]` — introduce named types instead.
- Only module-level imports — no inline/function-level imports.
- Cross-platform: the plugin and its tests must run on native Windows, macOS, Linux, and WSL (Linux interpreter over a `/mnt/<drive>` Windows checkout). Never hardcode a path separator or assume POSIX semantics — go through `pathlib`, normalize with `as_posix()` for stored/serialized paths, and resolve before comparing. The one platform seam is `capture/source.py` (`_co_filename_to_path`, `_IS_WSL`, `_IS_WINDOWS`): the same file can reach us as a Windows path (`C:\…`) or a WSL-mount POSIX path (`/mnt/<drive>/…`) regardless of the running interpreter — e.g. native Windows reusing an assertion-rewritten `.pyc` compiled under WSL carries a `/mnt/c/…` co_filename. `_co_filename_to_path` folds whichever foreign form appears into the native one (`C:\…`→`/mnt/c/…` on WSL, `/mnt/<drive>/…`→`<drive>:\…` on Windows) *before* any `.resolve()`, and `set_rootdir` does the same so both sides of a `relative_to` share a drive anchor. Tests that assert WSL/`/mnt`-absolute behavior must `skipif(sys.platform == 'win32', …)`, since native-Windows pathlib treats `/mnt/<drive>` as drive-relative, not absolute — but every other test must pass on all four targets.
- Subpackage boundaries (convention, not lint-enforced): `src/pytest_given/` is split into three subpackages with a strict dependency direction. `model/` is the leaf; `capture/` and `report/` both depend on `model/`; they do not depend on each other. `plugin.py` sits at the top level as the orchestrator and is allowed to import from all three. Inside the package, use relative imports throughout — `from .schema import Scenario` for siblings, `from ..model import Scenario` for cross-subpackage (always through the subpackage root, not into its submodules). The top-level `__init__.py` and `plugin.py` also use relative imports (`from .capture import …`). Tests use absolute imports and may reach into any internal path.
- Prefer `assert` over `# pragma: no cover` for invariant guards. Asserts document the invariant and fail loudly if violated; pragmas hide the line and silently bail. Reserve `# pragma: no cover` for code that genuinely cannot be exercised by a test (e.g. `if __name__ == '__main__':` script entry).
- Step-down rule: callers before callees, public before private. Read each file top-down from high-level API to implementation details.
- TDD: write tests first
- Commit messages: single line, no co-author trailers, no leading file/area labels like `TODO:` or `README:` — just describe the change ("note example cleanup as todo", not "TODO: note example cleanup"). Conventional-commit-style scope prefixes like `docs:` / `examples:` / `renderer:` are fine when they add information.
- Keep commits coherent: each commit should represent one logical change. Don't split "do X", "tests for X", and "review-fixup for X" into separate commits — squash them before pushing. Don't bundle unrelated changes either.
- Plan files under `docs/superpowers/plans/` are scratch artifacts — never commit them. Spec files under `docs/specs/` are committed.
- New specs land under `docs/specs/proposed/`. When a spec's implementation lands, `git mv` it up one level into `docs/specs/` in the same commit. `ls docs/specs/proposed` is the canonical list of outstanding design work.
- Always run `uv run nox` (or at minimum `uv run nox -s format lint mypy test`) before committing
