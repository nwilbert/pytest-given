# Subpackage Split

## Motivation

`src/pytest_given/` has grown to 11 Python modules in a flat layout. The package has two clear runtime responsibilities — capturing scenarios during a pytest run, and rendering reports afterwards — plus a shared data model that both sides depend on. Grouping files by responsibility makes that structure visible, gives each area a public surface to import through, and leaves room for each area to grow without further crowding the package root.

This is a pure refactor: no behavioral changes, no public-API changes for downstream users.

## Target layout

```
src/pytest_given/
  __init__.py                  # re-exports public API
  plugin.py                    # pytest11 orchestrator (top-level, imports from all subpackages)
  capture/
    __init__.py                # re-exports cross-boundary names
    decorators.py
    collector.py
    template.py                # Template + narration_from + parse_tstring (was top-level)
  report/
    __init__.py                # re-exports cross-boundary names
    renderer.py
    source_link.py
    cli.py
  model/
    __init__.py                # re-exports cross-boundary names
    schema.py                  # absorbs old model.py + Narration types from old template.py
    serde.py
    errors.py
```

### Subpackage responsibilities

- **`plugin.py` (top-level)** — pytest11 entry point and orchestrator. Implements pytest hooks, wires the collector to test events, and (when `--given-html` is set) triggers the integrated HTML render. As the orchestrator it sits above the three subpackages and is allowed to import from all of them.
- **`capture/`** — pure capture machinery: GWT decorators, scenario collector, and the `Template` class users construct in their tests (plus the t-string handling that converts user input into `Narration`). Does not depend on `report/`.
- **`report/`** — post-run HTML generation: Jinja-based renderer, source-link rewriting, and the `pytest-given` CLI. Does not depend on `capture/`.
- **`model/`** — the shared schema (dataclasses for `Scenario`, `Step`, `ReportData`, plus the `Narration*` dataclasses used to carry structured step text), JSON serde, and the package's exception type. Leaf subpackage.

### Dependency direction

- `capture` → `model`
- `report` → `model`
- No imports between `capture` and `report`.

## Import discipline

### Selective re-exports per subpackage

Each subpackage's `__init__.py` re-exports only the names that cross a subpackage boundary — names used by siblings or by the top-level `__init__.py`. Names used only within the subpackage stay reachable solely through their submodule.

Each subpackage `__init__.py` declares `__all__` listing the re-exports. This is required for ruff's `F401` rule (already enabled via `select = ["F"]`): without `__all__`, the re-exported names look like unused imports. (The PEP-484 redundant-alias form, `from .schema import Scenario as Scenario`, is the equivalent canonical alternative; `__all__` is chosen here for compactness.) The top-level `pytest_given/__init__.py` also declares `__all__` — that's the package's outward-facing public API.

### Import style: explicit relative within the package

Within `src/pytest_given/`, all intra-package imports use explicit relative form:

- **Within a subpackage** — single-dot relative: `from .schema import Scenario`
- **Across subpackages** — double-dot relative, always through the sibling subpackage root, never reaching into its submodules: `from ..model import Scenario` (allowed), `from ..model.schema import Scenario` (not allowed).

Rationale: this matches modern Python library convention (Black, Rich, Pydantic, FastAPI, Starlette, httpx, Click all use relative imports within the package) and makes the subpackage boundary visible at the call site — `.template` reads as "sibling file," `..model` reads as "cross-boundary, going through the public surface."

Tests and other code outside `src/pytest_given/` use absolute imports as usual (`from pytest_given.model import Scenario`).

### Boundary and direction (convention, not lint-enforced)

The convention has two parts, both carried by reviewer/agent discipline rather than by a lint rule:

1. **Dependency direction** — `capture` and `report` must not depend on each other; both may depend on `model`.
2. **Submodule boundary** — siblings should go through the subpackage root (`from ..model import Scenario`) rather than reaching into submodules (`from ..model.schema import Scenario`).

An earlier draft of this spec proposed enforcing both via ruff's `flake8-tidy-imports` (`TID251` + `TID253`) with per-file-ignores. The implementation worked but the config was hard to maintain: ruff prefix-matches the `from` clause against banned-api entries, which forced a two-rule scheme with mirrored ban lists and per-file-ignores arranged in opposing pairs. We backed it out in favor of the convention-only approach plus AGENTS.md documentation. If we later want lint-level enforcement, `import-linter` is the canonical tool — its `layers` contract expresses the direction rule cleanly in one block.

Inside the package, use relative imports throughout (`from .schema import X` for siblings, `from ..model import X` for cross-subpackage through the root). The top-level `__init__.py` and `plugin.py` use absolute imports — both reach into all subpackages by design.

## File renames and content moves

- `model.py` → `model/schema.py`. The file holds the report schema (`Scenario`, `Step`, `Attachment`, `Metadata`, `ReportData`, etc.); `schema` describes its role more accurately than `model` and avoids the `model.model` redundancy.
- **`template.py` is split.** The current file mixes pure data (`Narration` family) with the user-facing `Template` authoring API and the t-string conversion. These have different homes under the new layout:
  - The dataclasses `NarrationLiteral`, `NarrationValue`, `NarrationPlaceholder`, `NarrationPart`, and `Narration` move into `model/schema.py` alongside the rest of the report schema.
  - The `Template` class, `narration_from()`, and `parse_tstring()` move to `capture/template.py`. These are the authoring API (what users construct in their test code) and the conversion from user input to `Narration` — they belong with the rest of the capture machinery and may import their `Narration*` types from `model`.
  - The old top-level `template.py` is removed.
- `errors.py` → `model/errors.py`. Kept as its own module despite being only 2 lines; the small explicit module is preferred over folding into `schema.py`.
- All other files keep their current names; only their location changes.

No content merging, splitting, or restructuring beyond what's listed above.

## External-surface updates

### `pyproject.toml`

- `[project.entry-points."pytest11"] given` — stays at `pytest_given.plugin` (plugin.py remains at the top level as the orchestrator).
- `[project.scripts] pytest-given` — change from `pytest_given.cli:main` to `pytest_given.report.cli:main`.

### Top-level `pytest_given/__init__.py`

The exported names stay identical: `attach`, `given`, `scenario`, `then`, `when`, `PytestGivenError`, `Template`. Only the import sources update — pulling from the new subpackage roots:

```python
from pytest_given.capture import Template, attach, given, scenario, then, when
from pytest_given.model import PytestGivenError

__all__ = [
    'PytestGivenError',
    'Template',
    'attach',
    'given',
    'scenario',
    'then',
    'when',
]
```

## Test tree

Mirror the source layout under `tests/unit/`:

```
tests/unit/
  test_plugin.py                # tests for the top-level plugin.py orchestrator
  capture/
    test_collector.py
    test_step_descriptor.py     # tests decorator behavior
    test_template.py            # tests Template + narration_from + parse_tstring
  report/
    test_renderer.py
    test_source_link.py
  model/
    test_schema.py
    test_serde.py
    test_serializer.py
    test_errors.py
```

`tests/integration/` stays flat — integration tests cross subpackage boundaries by design, so mirroring there would be misleading.

`tests/unit/__init__.py` is preserved; each new subdirectory gets its own `__init__.py`.

## Documentation updates

`AGENTS.md` gets a new entry under **Conventions** documenting the import convention so it carries beyond this refactor. Approximate wording:

> Subpackage boundaries (convention, not lint-enforced): each subpackage under `src/pytest_given/` (`capture/`, `report/`, `model/`) has a public surface defined by its `__init__.py`. Dependency direction: `capture` and `report` both depend on `model`; neither may depend on the other. `plugin.py` at the top level is the orchestrator and imports from all subpackages. Inside the package, use relative imports — single-dot for siblings, double-dot through the subpackage root for cross-subpackage. The top-level `__init__.py` and `plugin.py` use absolute imports. Tests use absolute imports and may reach into any internal path.

`GLOSSARY.md`, `README.md`, and other docs are not expected to need changes — the public API surface is unchanged.

## Out of scope

- No behavioral changes to capture, rendering, CLI, or schema.
- No merging, splitting, or restructuring of file contents beyond the `model.py` → `schema.py` rename and the `__init__.py` import updates.
- No changes to `noxfile.py`, top-level `conftest.py`, or the docs structure.
- No documentation updates beyond what's needed to keep examples runnable (none expected — the public API surface is unchanged).

## Verification

The refactor is complete when:

- `nox` test session passes (unit + integration).
- `nox -s lint` (ruff) and `nox -s typecheck` (mypy) pass.
- The `pytest-given` console script resolves and runs against `examples/`.
- The `pytest11` entry point is picked up by pytest (verified by running the plugin against `examples/`).
- `from pytest_given import attach, given, scenario, then, when, PytestGivenError, Template` works unchanged.
