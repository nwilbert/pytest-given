# Glossary

Canonical vocabulary for pytest-given. Use these terms in code, docs, commit messages, and conversation; flag inconsistencies in review.

This glossary covers pytest-given's own bounded context. The terminology a *user's* test suite adopts (the domain the user is testing — e.g., the coffee domain in `examples/test_examples.py`) is a separate concern.

**Update rule:** rename or repurpose a term → update this file in the same commit.

## Core test model

| Term | Meaning |
|---|---|
| **Scenario** | A test function decorated with `@scenario(...)`. Not every pytest test is a scenario — undecorated tests are tolerated but not collected. |
| **Step** | A unit of narration: a `with given(...)` / `when(...)` / `then(...)` block, or the root recording from a step fixture. Steps nest. Each carries a phase, text, status (`'passed'` by default; set to `'failed'` on the step where a scenario fails, for highlighting in the report), optional error, attachments, and children. |
| **Narration** | The human-readable text on a step or scenario name. Modeled as a `Narration` dataclass bundling a flat rendered `text: str` with a `parts: list[NarrationPart]` (empty for plain-string authoring; populated when the source was a t-string or `pytest_given.Template`, with `NarrationLiteral` / `NarrationValue` / `NarrationPlaceholder` pieces). The structured form lets the templatizer and renderer treat parametrize-bound values specially without regex tricks. |
| **Phase** | The category of a step: `given`, `when`, or `then`. A step has exactly one phase. |
| **Tag** | Free-form string label attached via `@scenario(name, tags=[...])`. Used by the report's filter UI. |
| **Attachment** | A labeled blob (text or JSON) bound to the currently-active step via `attach(label, content)`. |

## Parametrization

| Term | Meaning |
|---|---|
| **Parametrized scenario** | A `@scenario`-decorated test that also carries `@pytest.mark.parametrize(...)`. Produces multiple scenario records during a run; pytest-given groups them. |
| **Case** | One row of a parametrized scenario — a single tuple of parameter values, its status, and any error. |
| **Parameter table** | The per-scenario grouping of column names + cases. Appears in the report below the grouped-template steps. |
| **Group** | Collapsing the N scenario records of a parametrized scenario into one logical scenario carrying a parameter table. Scenarios group when they share the same name and module. |
| **Templatize** | Derive the grouped-template step text from the first case, so the report shows a single set of steps with `{name}` placeholders that the parameter table fills in per case. Non-first cases' structured text is discarded. |

## Fixtures and recording

| Term | Meaning |
|---|---|
| **Step fixture** | A pytest fixture whose function is wrapped with `@given(text)`. Only `@given` is allowed on fixtures; `@when` / `@then` are rejected. |
| **Plain fixture** | A pytest fixture without a pytest-given decorator. Used by tests but produces no step in the report. |
| **Fixture recording** | A captured subtree of steps + attachments produced while a step fixture is being set up (and, for generator fixtures, torn down). Stored keyed by fixture-instance identity. |
| **Graft** | Attaching a fixture recording into the active scenario's step tree at the moment its host test starts. |

## Collector state

| Term | Meaning |
|---|---|
| **Collector** | The module-level singleton that accumulates scenarios, fixture recordings, and parameter info during a pytest session. Reset at the start of each session. |
| **Active scenario** | The scenario currently being recorded into; tracked by node ID. |
| **Node ID** | A pytest test identifier (e.g., `tests/test_x.py::test_y[a-b]`). Used as a key throughout the collector. |
| **Step stack** | The chain of currently-open steps; entered by `with given(...)`, popped on exit. Mirrored inside a fixture recording while a fixture body is running. |

## Report

| Term | Meaning |
|---|---|
| **Report** | The output artifact: a JSON data file and an optional self-contained HTML page derived from it. The JSON is the source of truth. |
| **Renderer** | Converts a JSON report into a self-contained HTML page. |
| **Parameter coloring** | Each parametrize column gets a stable highlight color; placeholders and matching values share that color wherever they appear in step text and the parameter table. |
| **Value highlight** | A neutral highlight applied to t-string interpolation values that don't correspond to a parametrize column (e.g., a computed expression like `price * 1.2`). |
