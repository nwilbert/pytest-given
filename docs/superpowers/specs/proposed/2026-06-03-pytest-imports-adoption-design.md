# pytest-imports Adoption — Design Spec

## Goal

Replace the AGENTS.md "convention, not lint-enforced" subpackage-boundary disclaimers with a real, fast, in-tree architecture test backed by [`pytest-imports`](https://github.com/nwilbert/pytest-imports). The test enforces — by running, not by reviewer discipline — the dependency direction, the submodule encapsulation boundary, the intra-package relative-import convention, and a project-wide ban on private-symbol imports.

This spec is the eventual end state. It is **gated on a set of upstream additions to `pytest-imports`** (see Prerequisites). It is not implementable today.

## Background

This is the third iteration of the same problem:

1. **Ruff `TID251` + `TID253`** (commits `7c6da88` → `b3973c0`). Worked, but the config required two rules with mirrored ban lists and opposing per-file-ignores — `from` clauses prefix-match against banned-api entries, so the relative imports inside a subpackage would fire its own rule. Backed out in favor of convention.
2. **`pytest-imports` initial sketch**. Cleanly expresses dependency direction and no-private-imports, but the submodule-boundary rule had to enumerate every submodule by name (silently stale on additions), and the intra-package relative-imports rule had to repeat per subpackage to dodge the `plugin.py` / `__init__.py` carve-out.
3. **This spec**, written against a forward-looking `pytest-imports` API (see [issues filed](#prerequisites)). Single line per rule, no enumeration, no per-subpackage repetition.

In parallel with iteration 3, `plugin.py` and `pytest_given/__init__.py` were switched to relative imports (commit `9163e42`) so the intra-package rule applies uniformly, with no carve-outs.

## Prerequisites

This spec assumes the following `pytest-imports` features have landed. Each corresponds to an upstream issue filed alongside this spec:

| Feature | Used by |
|---|---|
| `descendants('package')` target helper — matches every module nested under `package` at any depth, excluding `package` itself. Composes with the existing `must_not_import` / `must_import` predicates and their `via=` argument. | Submodule boundary rule **and** intra-package relative-imports rule. |
| Clarification that `scope(..., without=…)` accepts top-level module names, not only subpackage names. | Documentation; not load-bearing in this spec. |
| Docs on subpackage / submodule / descendant terminology. | Documentation; not load-bearing. |
| (Optional) Rename `must_not_import_within_parent` → `must_not_import_siblings`. | Cosmetic; affects spec wording, not behavior. |

If a subset of these lands first, the test in this spec can be implemented in stages — see [Phased adoption](#phased-adoption).

## Dependency change

Add `pytest-imports` to the `test` dependency group, pinned to a specific commit:

```toml
[dependency-groups]
test = [
    "pytest-imports @ git+https://github.com/nwilbert/pytest-imports@<sha>",
]
```

`test` (not `dev`) so the `nox -s test`, `coverage`, and `audit` sessions all pick it up. `pytest-imports` ships a pytest plugin and is needed at test runtime.

**Risk to verify on landing:** `pip-audit` against a git URL may behave unexpectedly. If it does, either pin to a PyPI release once one exists, or scope `pip-audit` to skip the package.

## Test file

`tests/architecture/__init__.py` (empty, matching the `tests/unit/` convention) and `tests/architecture/test_imports.py`:

```python
from pytest_imports import (
    descendants,
    must_not_import,
    must_not_import_private,
    project,
    scope,
)


def test_dependency_direction(imports):
    imports.check({
        'pytest_given.capture': must_not_import('pytest_given.report'),
        'pytest_given.report': must_not_import('pytest_given.capture'),
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
        scope('pytest_given'): must_not_import(
            descendants('pytest_given'), via='absolute'
        ),
    })


def test_no_private_imports(imports):
    imports.check({
        project(): must_not_import_private(),
    })
```

### Rule notes

- **Direction.** `plugin.py` lives at `pytest_given.plugin` and is outside both subpackage scopes, so it can legitimately import from both `capture` and `report`. No carve-out needed.
- **Submodule boundary.** `descendants('pytest_given.capture')` matches `pytest_given.capture.X` for any X (including any future submodule) but not `pytest_given.capture` itself. Combined with `must_not_import`, this bans reaching into capture from outside while leaving the bare root accessible. `scope('pytest_given', without='capture')` covers `plugin.py`, the top-level `__init__.py`, and the other two subpackages. The rule self-extends — adding `capture/newthing.py` doesn't require a test edit.
- **Intra-package relative imports.** `must_not_import(descendants('pytest_given'), via='absolute')` fires when any module inside `pytest_given` absolutely imports another module inside `pytest_given`. `scope('pytest_given')` covers the whole source tree uniformly; `tests/` is a separate top-level package and is excluded, preserving the existing test-side convention of absolute imports. Now that `plugin.py` and `__init__.py` use relative imports, no per-module carve-outs are needed.
- **No private imports.** `project()` scopes globally. The codebase currently has zero `_foo` imports; the rule acts as a forward-looking guard.

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

## Phased adoption

The full test depends on the `descendants()` target helper landing upstream. Two of the four rules — direction and no-private — are expressible today against `pytest-imports@8cf363da` and could land as a partial test first. The other two (submodule boundary, intra-package relative imports) both depend on `descendants()` and should land together once it ships, to avoid a half-strength version that then gets rewritten.

Recommended path: wait for `descendants()` and adopt all four rules in one go.

## Verification

- `nox -s test` passes with the new test file (all four checks green against the current source tree).
- Adding a deliberate violation (e.g. `from pytest_given.report import render_html` inside `capture/`) causes `test_dependency_direction` to fail with a message identifying the offending import.
- Adding a submodule reach-in (e.g. `from pytest_given.model.schema import Scenario` inside `capture/`) causes `test_submodule_boundary` to fail.
- Adding an absolute intra-package import (e.g. `from pytest_given.capture.template import …` inside `pytest_given/capture/collector.py`) causes `test_intra_package_imports_are_relative` to fail.
- Adding a private-symbol import anywhere causes `test_no_private_imports` to fail.
- `nox -s lint`, `nox -s mypy`, `nox -s coverage`, `nox -s audit` all continue to pass.

## Out of scope

- Adopting a different architecture-test tool (`import-linter`, `pytestarch`, `pytest-archon`). `pytest-imports` was chosen and the prerequisite-issue work is what justifies the bet; revisiting tool choice is a separate decision.
- Enforcing the "module-level imports only — no inline/function-level imports" convention. `pytest-imports` can in principle observe top-level-only via AST, but no current predicate expresses this; out of scope here.
- Stricter rules on third-party imports (e.g. forbidding `pytest._pytest` reach-ins beyond what `must_not_import_private` already catches).
