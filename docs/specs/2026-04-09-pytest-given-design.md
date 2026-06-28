# pytest-given Design Spec

## Context

Automated tests are valuable documentation, but their value is locked inside code that domain experts can't easily read. JGiven (Java) solves this by generating human-readable reports from test code — no Gherkin DSL, no separate spec files. The code is the single source of truth.

**pytest-given** brings this concept to Python/pytest: a plugin that lets developers annotate their tests with Given/When/Then structure and generates interactive HTML reports that domain experts can explore.

## Test Authoring API

### Core imports

```python
from pytest_given import scenario, given, when, then, attach
```

### `@scenario` decorator

Marks a test for inclusion in the report. Tests without `@scenario` are invisible to the plugin.

```python
@scenario("Customer buys coffee", tags=["billing"])
def test_buy_coffee(coffee_machine):
    ...
```

- `name`: Human-readable scenario name (required)
- `tags`: List of strings for report organization (optional)

### `given`, `when`, `then` context managers

Provide Given/When/Then structure with step text. Used inside a `@scenario`-decorated test.

```python
@scenario("Customer buys coffee", tags=["billing"])
def test_buy_coffee(coffee_machine):
    with given("the price is $2 per coffee"):
        coffee_machine.set_price(2)

    with when("I insert $2"):
        result = coffee_machine.insert_money(2)

    with then("I get a coffee"):
        assert result.dispensed == "coffee"
```

**Nesting**: Steps can nest to arbitrary depth. If a helper function is called during a phase, it can use context managers to add sub-steps. These render as collapsible trees in the report.

**Cross-phase nesting is an error**: A `given` inside a `then` (or any other cross-phase nesting) raises a runtime error. This prevents semantically confused reports. Top-level ordering is not enforced — multiple given/when/then cycles in one test are allowed.

```python
def insert_money(machine, amount):
    with when(f"validating coin... {'accepted' if amount > 0 else 'rejected'}"):
        machine.validate(amount)
    with when("dispensing coffee"):
        machine.dispense()

@scenario("Customer buys coffee")
def test_buy_coffee(coffee_machine):
    with when("I insert $2"):
        insert_money(coffee_machine, 2)  # sub-steps appear nested
```

### `attach(label, text)`

Attaches a text snippet to the current step. Rendered as an expandable section in the report.

```python
with then("I get a coffee"):
    assert result.dispensed == "coffee"
    attach("Machine log", coffee_machine.get_log())
```

Only text attachments are supported (no binary/images).

### `given`, `when`, `then` as decorators

The same `given`, `when`, `then` names work as both context managers and function decorators. When used as a decorator on a pytest fixture, the description appears as a step in the report.

```python
# As decorator on a fixture
@pytest.fixture
@given("a standard coffee machine")
def coffee_machine():
    return CoffeeMachine()

# As decorator on a helper function
@when("inserting money")
def insert_money(machine, amount):
    machine.insert(amount)
```

Internally, `given("text")` returns a `StepDescriptor` that implements both `__enter__`/`__exit__` (context manager) and `__call__` (decorator). If `__call__` receives a function, it wraps it as a decorated step. If `__enter__` is called, it opens a context-managed step block.

### Parameterized tests

Use standard `@pytest.mark.parametrize`. The plugin detects parameterization and renders a collapsed table with per-row pass/fail status.

```python
@scenario("Coffee pricing", tags=["billing"])
@pytest.mark.parametrize("euros,coffees", [(1, 0), (2, 1), (4, 2)])
def test_coffee_pricing(coffee_machine, euros, coffees):
    with given("the price is $2"):
        coffee_machine.set_price(2)
    with when(f"I insert ${euros}"):
        result = coffee_machine.insert_money(euros)
    with then(f"I get {coffees} coffee(s)"):
        assert result.count == coffees
```

F-strings in step text are encouraged — the report shows the actual runtime values.

### Subtests (pytest >= 9.0)

Subtests render as nested collapsible steps by default. The author can explicitly opt in to table rendering (exact opt-in syntax TBD).

```python
@scenario("Validate all prices")
def test_validate_prices(subtests, coffee_machine):
    with then("all prices are valid"):
        for name, price in coffee_machine.prices.items():
            with subtests.test(msg=name):
                with then(f"{name}: ${price} is positive"):
                    assert price > 0
```

## Data Pipeline

Single code path: plugin collects data, writes JSON, renders HTML from JSON.

```
pytest run
  |-- plugin hooks collect data --> in-memory model
  |                                     |
  |                                     v
  |                              report-data.json (always written)
  |                                     |
  |   (if --given-html)                 v
  |                              report.html (rendered from JSON)
  |
  CLI: pytest-given report data.json -o report.html
       (same renderer, for re-generating without re-running tests)
```

### pytest CLI options

- `--given-json=PATH`: Output path for JSON data (default: `given-report/report-data.json`)
- `--given-html`: Also generate HTML report (default: off)
- `--given-html-output=PATH`: Output path for HTML (default: `given-report/report.html`)

### Standalone CLI

```bash
pytest-given report report-data.json -o report.html
```

Re-renders HTML from existing JSON. Same renderer code path.

## JSON Data Model

```json
{
  "metadata": {
    "project": "coffee-shop",
    "timestamp": "2026-04-09T14:30:00Z",
    "pytest_version": "9.x",
    "plugin_version": "0.1.0"
  },
  "scenarios": [
    {
      "id": "tests/test_billing.py::test_buy_coffee",
      "name": "Customer buys coffee",
      "module": "tests.billing.test_coffee",
      "tags": ["billing"],
      "status": "passed",
      "duration_ms": 42,
      "steps": [
        {
          "phase": "given",
          "text": "a standard coffee machine",
          "source": "fixture",
          "status": "passed",
          "children": [],
          "attachments": []
        },
        {
          "phase": "when",
          "text": "I insert $2",
          "status": "passed",
          "children": [
            {
              "phase": "when",
              "text": "validating coin... accepted",
              "status": "passed",
              "children": [],
              "attachments": []
            },
            {
              "phase": "when",
              "text": "dispensing coffee",
              "status": "passed",
              "children": [],
              "attachments": []
            }
          ],
          "attachments": []
        }
      ],
      "parameters": null,
      "error": null
    },
    {
      "id": "tests/test_billing.py::test_coffee_pricing",
      "name": "Coffee pricing",
      "module": "tests.billing.test_coffee",
      "tags": ["billing"],
      "status": "failed",
      "duration_ms": 15,
      "steps": [
        {
          "phase": "given",
          "text": "the price is $2",
          "status": "passed",
          "children": [],
          "attachments": []
        }
      ],
      "parameters": {
        "names": ["euros", "coffees"],
        "cases": [
          {"values": [1, 0], "status": "passed", "error": null},
          {"values": [2, 1], "status": "passed", "error": null},
          {"values": [4, 2], "status": "failed", "error": {"message": "assert 1 == 2", "diff": "..."}}
        ]
      },
      "error": null
    }
  ]
}
```

Steps are recursive (`children` can contain steps with their own `children`) — supporting unlimited nesting depth. Subtests include a `subtest` field with `msg` and `params`.

## HTML Report

### Technology

- Single self-contained HTML file with all data inline as JSON
- Jinja2 template for rendering (JSON to HTML)
- No build step, no npm, no bundling
- **Client-side interactivity**: Alpine.js (~17kB), embedded inline. Lightweight and declarative — handles filtering, toggling, search entirely client-side with no server needed.

### Layout

- **Sidebar** (left):
  - Text search (filters scenarios by name, step text, tags)
  - View toggle: Tags / Modules (switches primary grouping)
  - Status filter: Passed / Failed / Skipped checkboxes
  - Collapsible tree of tags (or modules) with scenario counts
  - Clicking a tag/module scrolls to and filters scenarios

- **Main area** (right):
  - Scenario cards with:
    - Color-coded left border (green = passed, red = failed, yellow = skipped)
    - Scenario name, tags as badges, status indicator
    - Given/When/Then steps with phase labels (color-coded: purple/amber/blue)
    - Nested steps rendered as collapsible trees with indentation and connector lines
    - Parameterized tests: step text with highlighted variables, followed by a data table with per-row pass/fail
    - Failed rows highlighted in the table
    - Expandable error sections on failed steps showing pytest's assertion introspection output
    - Structured diff view for JSON-serializable data on failures
    - Text attachment badges (clickable, expand inline)

### Interactivity (Alpine.js)

All interactivity is client-side via Alpine.js directives in the HTML:
- `x-data` for component state (search text, active filters, collapsed nodes)
- `x-show` / `x-if` for filtering scenarios by search text, tags, status
- `@click` for collapsing/expanding nested steps, error details, attachments
- `x-model` for search input binding and filter toggles
- `x-effect` for reactive sidebar counts when filters change

## Project Structure

```
pytest-given/
  src/pytest_given/
    __init__.py          # Public API exports
    plugin.py            # pytest plugin hooks (registration, collection, reporting)
    model.py             # Dataclasses: Scenario, Step, Parameter, Attachment, etc.
    collector.py         # Step stack (thread-local), collects data during execution
    serializer.py        # Model -> JSON
    renderer.py          # JSON -> HTML (Jinja2)
    cli.py               # Standalone CLI: pytest-given report
    templates/
      report.html.j2     # Jinja2 template
      styles.css          # CSS (embedded in output)
  tests/
    conftest.py
    unit/
    integration/
  pyproject.toml
  noxfile.py
  LICENSE.md
  README.md
```

### Key components

- **`plugin.py`**: Registers via `pytest11` entry point. Hooks: `pytest_addoption`, `pytest_runtest_setup`, `pytest_runtest_call`, `pytest_runtest_teardown`, `pytest_sessionfinish`. On session finish, serializes collected data to JSON and optionally renders HTML.

- **`collector.py`**: Maintains a thread-local stack of active steps. The `given`/`when`/`then` context managers push/pop steps on this stack. Nested context managers naturally create child steps. Captures fixture descriptions from `@scenario_fixture`. Captures subtest boundaries.

- **`model.py`**: Dataclasses for the in-memory model. `Scenario`, `Step` (recursive via `children`), `StepDescriptor` (dual context-manager/decorator), `ParameterTable`, `ParameterCase`, `Attachment`, `ErrorInfo`. Serializable to/from JSON.

- **`serializer.py`**: Converts the model to the JSON format described above. Handles dataclass serialization, duration formatting.

- **`renderer.py`**: Reads JSON, renders HTML via Jinja2. Embeds JSON data, CSS, and Alpine.js inline. Single file output.

- **`cli.py`**: Entry point for `pytest-given report`. Reads JSON, calls renderer, writes HTML.

## Tooling & Build

Modeled after pytest-arch, with adjustments:

- **Python >= 3.12**
- **pytest >= 9.0** (only latest; subtests built-in)
- **Build**: hatchling (src layout)
- **Automation**: nox with uv backend
- **Linting/formatting**: ruff (single quotes, same rule set as pytest-arch: B, C4, E, F, I, PT, RUF, SIM, UP, W)
- **Type checking**: mypy (strict, `disallow_untyped_defs`)
- **Coverage**: 100% target
- **Security**: pip-audit
- **Runtime dependencies**: pytest >= 9.0, Jinja2
- **Bundled**: Alpine.js (embedded in template, no runtime dependency)

### Nox sessions

- `format` — ruff format
- `lint` — ruff check
- `mypy` — type checking
- `test` — pytest
- `coverage` — 100% coverage enforcement
- `audit` — pip-audit
- `report` — generate sample report from test data (development aid)

### Dependency groups

- **lint**: ruff
- **typecheck**: mypy
- **test**: (test utilities as needed)
- **coverage**: coverage (includes test)
- **audit**: pip-audit
- **dev**: nox + all groups

## Failure Handling

- **Assertion errors**: Capture pytest's assertion introspection output (`ExceptionInfo.getrepr()`). Store as text in the step's error field.
- **Structured diffs**: For JSON-serializable data, render a side-by-side or inline diff view in the report. Detection: if both sides of the comparison are `dict` or `list`, render structured. Otherwise, plain text.
- **Step failure propagation**: A failed child step marks its parent as failed. A failed step marks its scenario as failed.
- **Exceptions in steps**: Non-assertion exceptions are captured the same way — error message and traceback stored on the step.

## Verification Plan

1. **Unit tests**: Test each component in isolation (collector stack behavior, serializer output, renderer HTML structure).
2. **Integration tests**: Write sample `@scenario` tests, run pytest programmatically, verify JSON output structure and HTML report content.
3. **Manual verification**: Generate a report from the integration tests, open in browser, verify:
   - Sidebar filtering works (search, tag toggle, status filter)
   - Nested steps collapse/expand
   - Parameterized table renders with per-row status
   - Failed scenario shows error details and structured diff
   - Attachments expand inline
4. **Nox sessions**: `nox` runs all quality gates (format, lint, mypy, test, coverage, audit).
