# pytest-imports Adoption — Design Spec

## Goal

Replace the AGENTS.md "convention, not lint-enforced" subpackage-boundary disclaimers with a real, fast, in-tree architecture test backed by [`pytest-imports`](https://github.com/nwilbert/pytest-imports). The test enforces — by running, not by reviewer discipline — the dependency direction, the submodule encapsulation boundary, the intra-package relative-import convention, and a project-wide ban on private-symbol imports.

## Background

This is the third iteration of the same problem:

1. **Ruff `TID251` + `TID253`** (commits `7c6da88` → `b3973c0`). Worked, but the config required two rules with mirrored ban lists and opposing per-file-ignores — `from` clauses prefix-match against banned-api entries, so the relative imports inside a subpackage would fire its own rule. Backed out in favor of convention.

   *Note (2026-08-08).* One variant was not tried at the time: a per-directory `ruff.toml` inside each subpackage, each `extend`-ing the root `pyproject.toml` and declaring only its own **outgoing** bans. Verified against ruff 0.15.13 — `extend` inheritance works, `TID251` resolves relative imports (`from ..capture import x` is reported as `pytest_given.capture`), and banning a subpackage root also matches its submodules. Because each directory names only what *it* may not import, both the mirrored-ban-list and the opposing-per-file-ignore problems above disappear. Still not preferred: it reaches rules 1 and 2 only. Rule 3 would need `TID252`, which bans the very relative imports this project mandates, and rule 4 has no ruff equivalent — so the ruff route buys two of four rules at the cost of four extra config files.
2. **`pytest-imports` initial sketch**. Cleanly expressed dependency direction and no-private-imports, but the submodule-boundary rule had to enumerate every submodule by name (silently stale on additions), and the intra-package relative-imports rule had to repeat per subpackage to dodge the `plugin.py` / `__init__.py` carve-out.
3. **This spec**. Written initially against a forward-looking `pytest-imports` API; the relevant upstream additions have since landed (see [Upstream status](#upstream-status)), and the spec uses the `internal()` target helper now documented as the canonical idiom for the intra-package rule.

In parallel with iteration 3, `plugin.py` and `pytest_given/__init__.py` were switched to relative imports (commit `9163e42`) so the intra-package rule applies uniformly, with no carve-outs.

## Upstream status

When this spec was first drafted, four `pytest-imports` features were prerequisites. All have landed:

| Feature | Status |
|---|---|
| `descendants('package')` target helper — matches every module nested under `package` at any depth, excluding `package` itself. | Landed. Used by the submodule-boundary rule. |
| `scope(..., without=…)` accepts top-level module names (`.py` files like `plugin.py`), not only subpackage names. | Landed and explicitly documented in the README. |
| `internal()` target helper — matches any import that resolves to a module under the configured source roots. | Landed (not originally in the prereq list; supersedes our original `descendants('pytest_given')` formulation of the intra-package relative-imports rule — see [Rule notes](#rule-notes)). |
| Terminology docs (submodule / subpackage / descendant). | Landed in README and `GLOSSARY.md`. |

The originally optional cosmetic rename `must_not_import_within_parent → must_not_import_siblings` is moot — neither symbol exists in the current API.

The full test below is implementable today against `pytest-imports@c0b2bd0` (main, 2026-06-05). No phased adoption is needed.

## Dependency change

Add `pytest-imports` to the `test` dependency group, pinned to a specific commit:

```toml
[dependency-groups]
test = [
    "pytest-imports @ git+https://github.com/nwilbert/pytest-imports@c0b2bd04fece15e10977045ac41209401011e7bd",
]
```

`test` (not `dev`) so the `nox -s test`, `coverage`, and `audit` sessions all pick it up. `pytest-imports` ships a pytest plugin and is needed at test runtime.

**Risk to verify on landing:** `pip-audit` against a git URL may behave unexpectedly. If it does, either pin to a PyPI release once one exists, or scope `pip-audit` to skip the package.

## Test file

`tests/architecture/__init__.py` (empty, matching the `tests/unit/` convention) and `tests/architecture/test_imports.py`:

```python
from pytest_imports import (
    descendants,
    internal,
    must_not_import,
    must_not_import_private,
    project,
    scope,
)


def test_dependency_direction(imports):
    imports.check({
        'pytest_given.capture': must_not_import('pytest_given.report'),
        'pytest_given.report': must_not_import('pytest_given.capture'),
        'pytest_given.model': [
            must_not_import('pytest_given.capture'),
            must_not_import('pytest_given.report'),
        ],
    })


def test_submodule_boundary(imports):
    imports.check({
        scope('pytest_given', without='capture'): must_not_import(
            descendants('pytest_given.capture')
        ),
        scope('pytest_given', without='report'): must_not_import(
            descendants('pytest_given.report')
        ),
        scope('pytest_given', without='model'): must_not_import(
            descendants('pytest_given.model')
        ),
    })


def test_intra_package_imports_are_relative(imports):
    imports.check({
        scope('pytest_given'): must_not_import(internal(), via='absolute'),
    })


def test_no_private_imports(imports):
    imports.check({
        project(): must_not_import_private(),
    })
```

### Rule notes

- **Direction.** `plugin.py` lives at `pytest_given.plugin` and is outside every subpackage scope, so it can legitimately import from all three. No carve-out needed. `model/` is the leaf, so it gets explicit outgoing bans against the other two subpackages — the submodule-boundary rule already catches most of this, but a bare `import pytest_given.capture` (root, not a descendant) would otherwise slip through both rules; the direction entry closes that gap.
- **Submodule boundary.** `descendants('pytest_given.capture')` matches `pytest_given.capture.X` for any X (including any future submodule) but not `pytest_given.capture` itself. Combined with `must_not_import`, this bans reaching into capture from outside while leaving the bare root accessible. `scope('pytest_given', without='capture')` covers `plugin.py`, the top-level `__init__.py`, and the other two subpackages. The rule self-extends — adding `capture/newthing.py` doesn't require a test edit.
- **Intra-package relative imports.** `must_not_import(internal(), via='absolute')` fires when any module inside `pytest_given` absolutely imports any other module that resolves under the configured source roots. This is the upstream README's documented idiom for "all internal imports must be relative" and is strictly stronger than the original `descendants('pytest_given')` formulation: it also catches a bare absolute import of the root package (`import pytest_given`) from within. `scope('pytest_given')` covers the whole source tree uniformly; `tests/` is excluded because we have a `src/` layout (see Configuration in the upstream README), preserving the existing test-side convention of absolute imports.
- **No private imports.** `project()` scopes globally. With our `src/` layout, `project()` covers only `src/pytest_given/` and excludes `tests/`. The codebase currently has zero `_foo` imports; the rule acts as a forward-looking guard.

## `plugin.py` / `__init__.py` import-style change

**Already landed in commit `9163e42`** as a standalone refactor on `main`:

- `pytest_given/__init__.py`: `from pytest_given.capture import …` → `from .capture import …` (same for `.model`).
- `pytest_given/plugin.py`: `from pytest_given.{capture,model,report} import …` → `from .{capture,model,report} import …`.

This eliminates the "top-level files use absolute imports because they assemble / orchestrate" carve-out previously documented in AGENTS.md. The convention inside `src/pytest_given/` is now uniformly relative.

## AGENTS.md update

The Conventions entry that read:

> Subpackage boundaries (convention, not lint-enforced): …

becomes:

> Subpackage boundaries (enforced by `tests/architecture/test_imports.py`): `src/pytest_given/` is split into three subpackages. `model/` is the leaf; `capture/` and `report/` both depend on `model/`; they do not depend on each other. `plugin.py` at the top level orchestrates and may import from all three. Inside the package, use relative imports throughout — `from .schema import Scenario` for siblings, `from ..model import Scenario` for cross-subpackage (always through the subpackage root, not into its submodules). Tests use absolute imports and may reach into any internal path.

The "(convention, not lint-enforced)" parenthetical is replaced by the test-file pointer. The rest of the text is unchanged.

## Verification

- `nox -s test` passes with the new test file (all four checks green against the current source tree).
- Adding a deliberate violation (e.g. `from pytest_given.report import render_html` inside `capture/`) causes `test_dependency_direction` to fail with a message identifying the offending import.
- Adding a `model/` → `capture/` import (e.g. `from pytest_given.capture import collector` inside `model/schema.py`) causes `test_dependency_direction` to fail on the new `pytest_given.model` entry.
- Adding a submodule reach-in (e.g. `from pytest_given.model.schema import Scenario` inside `capture/`) causes `test_submodule_boundary` to fail.
- Adding an absolute intra-package import (e.g. `from pytest_given.capture.template import …` inside `pytest_given/capture/collector.py`) causes `test_intra_package_imports_are_relative` to fail.
- Adding a private-symbol import anywhere under `src/pytest_given/` causes `test_no_private_imports` to fail.
- `nox -s lint`, `nox -s mypy`, `nox -s coverage`, `nox -s audit` all continue to pass.

## Recommendations for `pytest-imports`

The library now covers this project's use case cleanly — every rule is one line, with no enumeration and no per-subpackage repetition. One feature would let us retire the remaining AGENTS.md convention disclaimer:

- **Top-level-only import predicate.** AGENTS.md currently says "Only module-level imports — no inline/function-level imports." `pytest-imports` already parses the AST and walks `module_node.imports`; an additional predicate like `must_import_at_top_level()` (or a `top_level=True` flag on the existing scope) that flags imports whose AST ancestor chain includes a `FunctionDef` / `AsyncFunctionDef` / `ClassDef` would make this a checked rule rather than a convention. Out of scope for this spec, but the natural next request.

No other gaps. The current API expresses every rule we want, including the model-is-the-leaf addition.

## Tool comparison: pytestarch

The closest alternative is [`pytestarch`](https://github.com/zyskarch/pytestarch) — more mature (on PyPI, broader feature set including `LayeredArchitecture`, PlantUML import, and dependency-graph visualization), but a worse fit for this project's four rules.

The same four rules in pytestarch:

```python
import pytest
from pytestarch import EvaluableArchitecture, Rule, get_evaluable_architecture

@pytest.fixture(scope="session")
def arch() -> EvaluableArchitecture:
    return get_evaluable_architecture(
        "src/pytest_given", "src/pytest_given", ("*__pycache__",),
    )

# 1. Dependency direction — one Rule per edge
def test_capture_does_not_import_report(arch):
    Rule().modules_that().are_named("pytest_given.capture") \
        .should_not().import_modules_that().are_named("pytest_given.report") \
        .assert_applies(arch)

def test_report_does_not_import_capture(arch):
    Rule().modules_that().are_named("pytest_given.report") \
        .should_not().import_modules_that().are_named("pytest_given.capture") \
        .assert_applies(arch)

def test_model_is_a_leaf(arch):
    Rule().modules_that().are_named("pytest_given.model") \
        .should_not().import_modules_that() \
        .are_named(["pytest_given.capture", "pytest_given.report"]) \
        .assert_applies(arch)

# 2. Submodule boundary — inverted perspective (object, not subject); one Rule per subpackage
def test_capture_internals_encapsulated(arch):
    Rule().modules_that().are_submodules_of("pytest_given.capture") \
        .should_not().be_imported_by_modules_except_modules_that() \
        .are_named("pytest_given.capture") \
        .assert_applies(arch)
# … repeated for report and model

# 3. Intra-package relative imports — NOT EXPRESSIBLE
# pytestarch has no via='absolute'|'relative' filter on import edges.

# 4. No private imports — approximation via regex on module names
def test_no_private_imports(arch):
    Rule().modules_that().have_name_matching(r".*\._[^.]+(\..*)?$") \
        .should_not().be_imported_by_anything() \
        .assert_applies(arch)
# Misses `from public_module import _symbol`: pytestarch tracks module-to-module
# edges, so a private *symbol* imported from a public module isn't visible.
# pytest-imports's resolver treats the symbol as the trailing dot-path part and
# checks every part for `_`-prefix.
```

Comparison:

| Aspect | pytest-imports | pytestarch |
|---|---|---|
| Rule packaging | One dict per test; scopes and predicates batched | One `Rule()` object per assertion |
| Our 4 tests in lines | ~25 | ~55+ |
| Dependency direction | One dict entry per edge; list-target batches model→{capture,report} | One `Rule` per edge; list-target works the same way |
| Submodule encapsulation | Subject-side: "outside-X must not import X.internals" | Inverted: "X.internals must not be imported by anything except X" — equivalent, but reads object-first |
| **Intra-package relative imports** | `must_not_import(internal(), via='absolute')` — one line | **Not expressible.** No import-style predicate. |
| **No private imports** | `must_not_import_private()` predicate; sees private *names* via dot-path parts | Regex on module names only; misses `from public import _symbol`. Catching `pytest._pytest` also requires `exclude_external_libraries=False`, which bloats the graph. |
| "Internal" notion | First-class `internal()` target | Implicit via `exclude_external_libraries` at construction time |
| Failure reporting | All failures collected per `check()` call | One `AssertionError` per `Rule.assert_applies` — re-run after each fix |
| Maturity | Pre-release, git-only pin | On PyPI, broader feature set |
| Project scope | Narrow: import rules only | Broader: layered architecture, diagram-driven rules, visualization |

**Verdict.** Rule 3 is the dealbreaker — "intra-package imports must be relative" can't be expressed in pytestarch at all, so adopting it would force a mixed setup (e.g. ruff `TID252` alongside pytestarch, with the same per-file-ignore problems that pushed us off ruff in the first place). Rule 4 is awkward for the same family of reasons. pytestarch's strengths (layered architecture, PlantUML import, visualization) don't apply to a three-subpackage project with a fixed dependency direction. If pytest-imports ever fell over for our needs, the natural escape hatch is to add a missing predicate upstream, not to switch tools.

## Out of scope

- Adopting `import-linter` or `pytest-archon`. `pytestarch` is covered above; `import-linter` and `pytest-archon` weren't evaluated in depth — `pytest-imports` already covers our four rules cleanly.
- Enforcing the "module-level imports only — no inline/function-level imports" convention (see [Recommendations](#recommendations-for-pytest-imports)). Ruff's `PLC0415` (`import-outside-top-level`) already expresses exactly this rule, so it need not wait on a `pytest-imports` predicate: as of 2026-08-08 it reports 22 findings, all in `tests/` and none under `src/`, meaning it could be enabled today with a `tests/**` per-file-ignore.
- Stricter rules on third-party imports (e.g. forbidding `pytest._pytest` reach-ins beyond what `must_not_import_private` already catches).
