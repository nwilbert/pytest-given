# pytest-given Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a pytest plugin that generates interactive HTML reports from Given/When/Then annotated Python tests.

**Architecture:** A pytest plugin collects step data via context managers and decorators during test execution, serializes to JSON, and renders a single self-contained HTML file with Alpine.js interactivity. The plugin hooks into pytest's execution lifecycle; the renderer uses Jinja2 templates.

**Tech Stack:** Python 3.12+, pytest 9.0+, Jinja2, Alpine.js (bundled), hatchling, nox, uv, ruff, mypy

---

## File Structure

```
pytest-given/
  src/pytest_given/
    __init__.py          # Public API: scenario, given, when, then, attach
    model.py             # Dataclasses: Scenario, Step, ParameterTable, Attachment, ErrorInfo
    step_descriptor.py   # StepDescriptor: dual context-manager/decorator
    collector.py         # Thread-local step stack, active scenario tracking
    plugin.py            # pytest hooks: addoption, runtest_*, sessionfinish
    serializer.py        # Model -> JSON dict -> file
    renderer.py          # JSON -> HTML via Jinja2
    cli.py               # Entry point: pytest-given report
    templates/
      report.html.j2     # Jinja2 template (HTML + Alpine.js + CSS)
  tests/
    __init__.py
    conftest.py
    unit/
      __init__.py
      test_model.py
      test_step_descriptor.py
      test_collector.py
      test_serializer.py
      test_renderer.py
    integration/
      __init__.py
      test_plugin.py
      test_cli.py
  pyproject.toml
  noxfile.py
  LICENSE.md
```

---

### Task 1: Project Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `noxfile.py`
- Create: `LICENSE.md`
- Create: `src/pytest_given/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/unit/__init__.py`
- Create: `tests/integration/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Create pyproject.toml**

```toml
[project]
name = "pytest-given"
version = "0.1.0"
description = "A pytest plugin that generates interactive HTML reports from Given/When/Then annotated tests."
license = { text = "Apache-2.0" }
authors = [{ name = "Niko Wilbert", email = "mail@nikowilbert.de" }]
classifiers = ["Framework :: Pytest"]
requires-python = ">=3.12"
dependencies = [
    "pytest>=9.0",
    "jinja2>=3.1",
]

[project.entry-points."pytest11"]
given = "pytest_given.plugin"

[project.scripts]
pytest-given = "pytest_given.cli:main"

[dependency-groups]
lint = ["ruff>=0.15.8"]
typecheck = ["mypy>=1.20.0"]
test = []
coverage = [{ include-group = "test" }, "coverage>=7.13.5"]
audit = ["pip-audit>=2.10.0"]
dev = [
    "nox>=2026.2.9",
    { include-group = "lint" },
    { include-group = "typecheck" },
    { include-group = "coverage" },
    { include-group = "audit" },
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/pytest_given"]

[tool.ruff.format]
quote-style = "single"

[tool.ruff.lint]
select = ["B", "C4", "E", "F", "I", "PT", "RUF", "SIM", "UP", "W"]

[tool.mypy]
python_version = "3.12"
ignore_missing_imports = true
no_implicit_optional = true
warn_return_any = true
show_error_codes = true
warn_unused_ignores = true
disallow_untyped_defs = true
```

- [ ] **Step 2: Create noxfile.py**

```python
import webbrowser
from pathlib import Path

import nox

src_path = 'src'
code_paths = [src_path, 'tests', 'noxfile.py']

nox.options.default_venv_backend = 'uv'
nox.options.sessions = [
    'format',
    'lint',
    'mypy',
    'test',
    'coverage',
    'audit',
]


def _sync(session: nox.Session, group: str) -> None:
    session.run('uv', 'sync', '--group', group, '--active', external=True)


@nox.session
def format(session: nox.Session) -> None:
    _sync(session, 'lint')
    session.run('ruff', 'format', *session.posargs, *code_paths)


@nox.session
def lint(session: nox.Session) -> None:
    _sync(session, 'lint')
    session.run('ruff', 'check', *code_paths)


@nox.session
def mypy(session: nox.Session) -> None:
    _sync(session, 'typecheck')
    session.run('mypy', src_path)


@nox.session
def test(session: nox.Session) -> None:
    _sync(session, 'test')
    session.run('pytest')


@nox.session
def coverage(session: nox.Session) -> None:
    _sync(session, 'coverage')
    session.run(
        'coverage',
        'run',
        '--source',
        'pytest_given',
        '-m',
        'pytest',
        'tests/unit',
        'tests/integration',
    )
    try:
        session.run('coverage', 'report', '--fail-under', '100', '--show-missing')
    finally:
        if 'html' in session.posargs:
            session.run('coverage', 'html', '--skip-covered')
            webbrowser.open((Path.cwd() / 'htmlcov' / 'index.html').as_uri())


@nox.session
def audit(session: nox.Session) -> None:
    _sync(session, 'audit')
    session.run('pip-audit', '--local')
```

- [ ] **Step 3: Create LICENSE.md**

Use the Apache 2.0 license text with copyright line: `Copyright 2026 Niko Wilbert`

- [ ] **Step 4: Create minimal package files**

`src/pytest_given/__init__.py`:
```python
"""pytest-given: Generate interactive HTML reports from Given/When/Then annotated tests."""
```

`tests/__init__.py`: empty file
`tests/unit/__init__.py`: empty file
`tests/integration/__init__.py`: empty file
`tests/conftest.py`: empty file

- [ ] **Step 5: Install the project and verify**

Run: `uv sync --group dev`
Expected: Dependencies install, project is editable-installed.

Run: `uv run pytest --co`
Expected: No errors, no tests collected (yet).

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml noxfile.py LICENSE.md src/ tests/
git commit -m "Project scaffolding with nox, uv, ruff, mypy"
```

---

### Task 2: Data Model

**Files:**
- Create: `src/pytest_given/model.py`
- Create: `tests/unit/test_model.py`

- [ ] **Step 1: Write the failing test for data model**

`tests/unit/test_model.py`:
```python
from pytest_given.model import (
    Attachment,
    ErrorInfo,
    Metadata,
    ParameterCase,
    ParameterTable,
    ReportData,
    Scenario,
    Step,
)


def test_step_defaults() -> None:
    step = Step(phase='given', text='a coffee machine')
    assert step.phase == 'given'
    assert step.text == 'a coffee machine'
    assert step.status == 'passed'
    assert step.children == []
    assert step.attachments == []
    assert step.source is None
    assert step.error is None


def test_step_with_children() -> None:
    child = Step(phase='when', text='validating coin')
    parent = Step(phase='when', text='insert money', children=[child])
    assert len(parent.children) == 1
    assert parent.children[0].text == 'validating coin'


def test_attachment() -> None:
    att = Attachment(label='Machine log', content='log line 1\nlog line 2')
    assert att.label == 'Machine log'
    assert att.content == 'log line 1\nlog line 2'


def test_error_info() -> None:
    err = ErrorInfo(message='assert 1 == 2', diff='- 1\n+ 2')
    assert err.message == 'assert 1 == 2'
    assert err.diff == '- 1\n+ 2'


def test_error_info_without_diff() -> None:
    err = ErrorInfo(message='assert False')
    assert err.diff is None


def test_scenario_defaults() -> None:
    s = Scenario(
        id='test_file.py::test_foo',
        name='Foo scenario',
        module='test_file',
    )
    assert s.tags == []
    assert s.status == 'passed'
    assert s.duration_ms == 0
    assert s.steps == []
    assert s.parameters is None
    assert s.error is None


def test_parameter_table() -> None:
    case1 = ParameterCase(values=[1, 0], status='passed')
    case2 = ParameterCase(values=[2, 1], status='failed', error=ErrorInfo(message='fail'))
    table = ParameterTable(names=['euros', 'coffees'], cases=[case1, case2])
    assert table.names == ['euros', 'coffees']
    assert len(table.cases) == 2
    assert table.cases[1].error is not None


def test_metadata() -> None:
    m = Metadata(
        project='coffee-shop',
        timestamp='2026-04-09T14:30:00Z',
        pytest_version='9.0',
        plugin_version='0.1.0',
    )
    assert m.project == 'coffee-shop'


def test_report_data() -> None:
    report = ReportData(
        metadata=Metadata(
            project='test',
            timestamp='now',
            pytest_version='9',
            plugin_version='0.1',
        ),
        scenarios=[],
    )
    assert report.scenarios == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_model.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pytest_given.model'`

- [ ] **Step 3: Write the implementation**

`src/pytest_given/model.py`:
```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Attachment:
    label: str
    content: str


@dataclass
class ErrorInfo:
    message: str
    diff: str | None = None


@dataclass
class Step:
    phase: str  # 'given', 'when', 'then'
    text: str
    status: str = 'passed'
    source: str | None = None  # 'fixture' if from a decorated fixture
    children: list[Step] = field(default_factory=list)
    attachments: list[Attachment] = field(default_factory=list)
    error: ErrorInfo | None = None


@dataclass
class ParameterCase:
    values: list[Any]
    status: str = 'passed'
    error: ErrorInfo | None = None


@dataclass
class ParameterTable:
    names: list[str]
    cases: list[ParameterCase] = field(default_factory=list)


@dataclass
class Scenario:
    id: str
    name: str
    module: str
    tags: list[str] = field(default_factory=list)
    status: str = 'passed'
    duration_ms: int = 0
    steps: list[Step] = field(default_factory=list)
    parameters: ParameterTable | None = None
    error: ErrorInfo | None = None


@dataclass
class Metadata:
    project: str
    timestamp: str
    pytest_version: str
    plugin_version: str


@dataclass
class ReportData:
    metadata: Metadata
    scenarios: list[Scenario] = field(default_factory=list)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_model.py -v`
Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/pytest_given/model.py tests/unit/test_model.py
git commit -m "Add data model dataclasses"
```

---

### Task 3: StepDescriptor (Dual Context Manager / Decorator)

**Files:**
- Create: `src/pytest_given/step_descriptor.py`
- Create: `tests/unit/test_step_descriptor.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/test_step_descriptor.py`:
```python
from pytest_given.step_descriptor import StepDescriptor


def test_context_manager_basic() -> None:
    """StepDescriptor works as a context manager."""
    desc = StepDescriptor('given', 'a coffee machine')
    with desc:
        pass
    assert desc.phase == 'given'
    assert desc.text == 'a coffee machine'


def test_decorator_basic() -> None:
    """StepDescriptor works as a function decorator."""
    desc = StepDescriptor('when', 'inserting money')

    @desc
    def insert_money() -> str:
        return 'done'

    assert insert_money() == 'done'
    assert hasattr(insert_money, '_step_descriptor')
    assert insert_money._step_descriptor.text == 'inserting money'


def test_decorator_preserves_function_metadata() -> None:
    """Decorated function keeps its original name and docstring."""
    desc = StepDescriptor('given', 'a machine')

    @desc
    def my_func() -> None:
        """My docstring."""

    assert my_func.__name__ == 'my_func'
    assert my_func.__doc__ == 'My docstring.'


def test_cross_phase_nesting_raises() -> None:
    """Nesting a different phase inside another raises an error."""
    import pytest

    outer = StepDescriptor('then', 'result is correct')
    inner = StepDescriptor('given', 'some precondition')
    with pytest.raises(
        RuntimeError,
        match="Cannot nest 'given' inside 'then'",
    ):
        with outer:
            with inner:
                pass


def test_same_phase_nesting_allowed() -> None:
    """Nesting the same phase inside itself is allowed."""
    outer = StepDescriptor('when', 'outer step')
    inner = StepDescriptor('when', 'inner step')
    with outer:
        with inner:
            pass  # no error


def test_sequential_different_phases_allowed() -> None:
    """Different phases at the top level (not nested) is fine."""
    with StepDescriptor('given', 'setup'):
        pass
    with StepDescriptor('when', 'action'):
        pass
    with StepDescriptor('then', 'check'):
        pass
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_step_descriptor.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

`src/pytest_given/step_descriptor.py`:
```python
from __future__ import annotations

import functools
import threading
from typing import Any

# Thread-local stack tracking active phases for cross-phase nesting detection
_phase_stack: threading.local = threading.local()


def _get_phase_stack() -> list[str]:
    if not hasattr(_phase_stack, 'stack'):
        _phase_stack.stack = []
    return _phase_stack.stack


class StepDescriptor:
    """Dual context-manager / decorator for Given/When/Then steps.

    As a context manager:
        with given("a coffee machine"):
            ...

    As a decorator:
        @given("a coffee machine")
        def coffee_machine():
            ...
    """

    def __init__(self, phase: str, text: str) -> None:
        self.phase = phase
        self.text = text

    def __enter__(self) -> StepDescriptor:
        stack = _get_phase_stack()
        if stack and stack[-1] != self.phase:
            raise RuntimeError(
                f"Cannot nest '{self.phase}' inside '{stack[-1]}'"
                ' — restructure your test or use a phase-neutral helper'
            )
        stack.append(self.phase)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        _get_phase_stack().pop()

    def __call__(self, func: Any) -> Any:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return func(*args, **kwargs)

        wrapper._step_descriptor = self  # type: ignore[attr-defined]
        return wrapper
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_step_descriptor.py -v`
Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/pytest_given/step_descriptor.py tests/unit/test_step_descriptor.py
git commit -m "Add StepDescriptor with context manager and decorator support"
```

---

### Task 4: Collector (Step Stack)

**Files:**
- Create: `src/pytest_given/collector.py`
- Create: `tests/unit/test_collector.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/test_collector.py`:
```python
from pytest_given.collector import Collector
from pytest_given.model import Scenario, Step
from pytest_given.step_descriptor import StepDescriptor


def test_start_and_finish_scenario() -> None:
    collector = Collector()
    collector.start_scenario('test.py::test_x', 'Test X', 'test_module', ['tag1'])
    scenario = collector.finish_scenario(status='passed', duration_ms=10)
    assert scenario.name == 'Test X'
    assert scenario.status == 'passed'
    assert scenario.duration_ms == 10
    assert scenario.tags == ['tag1']


def test_collect_steps() -> None:
    collector = Collector()
    collector.start_scenario('id', 'name', 'mod', [])
    collector.push_step('given', 'a machine')
    collector.pop_step()
    collector.push_step('when', 'I press start')
    collector.pop_step()
    scenario = collector.finish_scenario(status='passed', duration_ms=0)
    assert len(scenario.steps) == 2
    assert scenario.steps[0].phase == 'given'
    assert scenario.steps[0].text == 'a machine'
    assert scenario.steps[1].phase == 'when'


def test_nested_steps() -> None:
    collector = Collector()
    collector.start_scenario('id', 'name', 'mod', [])
    collector.push_step('when', 'outer')
    collector.push_step('when', 'inner')
    collector.pop_step()
    collector.pop_step()
    scenario = collector.finish_scenario(status='passed', duration_ms=0)
    assert len(scenario.steps) == 1
    outer = scenario.steps[0]
    assert outer.text == 'outer'
    assert len(outer.children) == 1
    assert outer.children[0].text == 'inner'


def test_attach_to_current_step() -> None:
    collector = Collector()
    collector.start_scenario('id', 'name', 'mod', [])
    collector.push_step('then', 'check result')
    collector.attach('Log output', 'line1\nline2')
    collector.pop_step()
    scenario = collector.finish_scenario(status='passed', duration_ms=0)
    step = scenario.steps[0]
    assert len(step.attachments) == 1
    assert step.attachments[0].label == 'Log output'
    assert step.attachments[0].content == 'line1\nline2'


def test_step_failure() -> None:
    collector = Collector()
    collector.start_scenario('id', 'name', 'mod', [])
    collector.push_step('then', 'should fail')
    collector.fail_current_step('assert 1 == 2', diff='- 1\n+ 2')
    collector.pop_step()
    scenario = collector.finish_scenario(status='failed', duration_ms=0)
    step = scenario.steps[0]
    assert step.status == 'failed'
    assert step.error is not None
    assert step.error.message == 'assert 1 == 2'


def test_no_active_scenario_returns_none() -> None:
    collector = Collector()
    assert collector.active_scenario_id is None


def test_active_scenario_id_set() -> None:
    collector = Collector()
    collector.start_scenario('test.py::test_x', 'X', 'mod', [])
    assert collector.active_scenario_id == 'test.py::test_x'
    collector.finish_scenario(status='passed', duration_ms=0)
    assert collector.active_scenario_id is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_collector.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

`src/pytest_given/collector.py`:
```python
from __future__ import annotations

from pytest_given.model import Attachment, ErrorInfo, Scenario, Step


class Collector:
    """Collects step data during test execution.

    Maintains a stack of active steps. Context managers push/pop steps.
    Nested context managers create child steps.
    """

    def __init__(self) -> None:
        self._scenarios: list[Scenario] = []
        self._current_scenario: Scenario | None = None
        self._step_stack: list[Step] = []

    @property
    def active_scenario_id(self) -> str | None:
        if self._current_scenario is None:
            return None
        return self._current_scenario.id

    @property
    def scenarios(self) -> list[Scenario]:
        return self._scenarios

    def start_scenario(
        self,
        scenario_id: str,
        name: str,
        module: str,
        tags: list[str],
    ) -> None:
        self._current_scenario = Scenario(
            id=scenario_id,
            name=name,
            module=module,
            tags=tags,
        )
        self._step_stack = []

    def finish_scenario(self, status: str, duration_ms: int) -> Scenario:
        assert self._current_scenario is not None
        self._current_scenario.status = status
        self._current_scenario.duration_ms = duration_ms
        scenario = self._current_scenario
        self._scenarios.append(scenario)
        self._current_scenario = None
        self._step_stack = []
        return scenario

    def push_step(self, phase: str, text: str, source: str | None = None) -> Step:
        step = Step(phase=phase, text=text, source=source)
        if self._step_stack:
            self._step_stack[-1].children.append(step)
        elif self._current_scenario is not None:
            self._current_scenario.steps.append(step)
        self._step_stack.append(step)
        return step

    def pop_step(self) -> Step | None:
        if not self._step_stack:
            return None
        return self._step_stack.pop()

    def attach(self, label: str, content: str) -> None:
        if self._step_stack:
            self._step_stack[-1].attachments.append(
                Attachment(label=label, content=content)
            )

    def fail_current_step(
        self, message: str, diff: str | None = None
    ) -> None:
        if self._step_stack:
            step = self._step_stack[-1]
            step.status = 'failed'
            step.error = ErrorInfo(message=message, diff=diff)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_collector.py -v`
Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/pytest_given/collector.py tests/unit/test_collector.py
git commit -m "Add Collector for step data collection"
```

---

### Task 5: Public API and Wiring

**Files:**
- Modify: `src/pytest_given/__init__.py`
- Modify: `src/pytest_given/step_descriptor.py`
- Modify: `tests/unit/test_step_descriptor.py`

This task wires the `StepDescriptor` to the `Collector` so that context managers actually record steps, and exports the public API.

- [ ] **Step 1: Write the failing test for collector integration**

Add to `tests/unit/test_step_descriptor.py`:
```python
from pytest_given.collector import Collector
from pytest_given.step_descriptor import StepDescriptor, set_active_collector


def test_context_manager_records_step_in_collector() -> None:
    collector = Collector()
    collector.start_scenario('id', 'name', 'mod', [])
    set_active_collector(collector)
    try:
        desc = StepDescriptor('given', 'a coffee machine')
        with desc:
            pass
        scenario = collector.finish_scenario(status='passed', duration_ms=0)
        assert len(scenario.steps) == 1
        assert scenario.steps[0].text == 'a coffee machine'
    finally:
        set_active_collector(None)


def test_context_manager_without_collector_is_noop() -> None:
    """When no collector is active, context manager still works (no recording)."""
    set_active_collector(None)
    desc = StepDescriptor('given', 'a thing')
    with desc:
        pass  # no error
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_step_descriptor.py::test_context_manager_records_step_in_collector -v`
Expected: FAIL with `ImportError: cannot import name 'set_active_collector'`

- [ ] **Step 3: Update StepDescriptor to integrate with Collector**

Update `src/pytest_given/step_descriptor.py` — add a module-level active collector and wire `__enter__`/`__exit__` to push/pop steps:

```python
from __future__ import annotations

import functools
import threading
from typing import Any

_local: threading.local = threading.local()


def _get_phase_stack() -> list[str]:
    if not hasattr(_local, 'phase_stack'):
        _local.phase_stack = []
    return _local.phase_stack


def set_active_collector(collector: Any) -> None:
    """Set the active collector for the current thread."""
    _local.collector = collector


def get_active_collector() -> Any:
    """Get the active collector for the current thread, or None."""
    return getattr(_local, 'collector', None)


class StepDescriptor:
    """Dual context-manager / decorator for Given/When/Then steps."""

    def __init__(self, phase: str, text: str) -> None:
        self.phase = phase
        self.text = text

    def __enter__(self) -> StepDescriptor:
        stack = _get_phase_stack()
        if stack and stack[-1] != self.phase:
            raise RuntimeError(
                f"Cannot nest '{self.phase}' inside '{stack[-1]}'"
                ' — restructure your test or use a phase-neutral helper'
            )
        stack.append(self.phase)
        collector = get_active_collector()
        if collector is not None:
            collector.push_step(self.phase, self.text)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        _get_phase_stack().pop()
        collector = get_active_collector()
        if collector is not None:
            collector.pop_step()

    def __call__(self, func: Any) -> Any:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return func(*args, **kwargs)

        wrapper._step_descriptor = self  # type: ignore[attr-defined]
        return wrapper
```

- [ ] **Step 4: Run all step_descriptor tests to verify they pass**

Run: `uv run pytest tests/unit/test_step_descriptor.py -v`
Expected: All tests PASS.

- [ ] **Step 5: Update `__init__.py` with public API**

`src/pytest_given/__init__.py`:
```python
"""pytest-given: Generate interactive HTML reports from Given/When/Then annotated tests."""

from pytest_given.step_descriptor import StepDescriptor, get_active_collector

__all__ = ['attach', 'given', 'scenario', 'then', 'when']

_PHASE_VALID_ORDER = {'given': 0, 'when': 1, 'then': 2}


def given(text: str) -> StepDescriptor:
    """Create a Given step (context manager or decorator)."""
    return StepDescriptor('given', text)


def when(text: str) -> StepDescriptor:
    """Create a When step (context manager or decorator)."""
    return StepDescriptor('when', text)


def then(text: str) -> StepDescriptor:
    """Create a Then step (context manager or decorator)."""
    return StepDescriptor('then', text)


def attach(label: str, content: str) -> None:
    """Attach text to the current step."""
    collector = get_active_collector()
    if collector is not None:
        collector.attach(label, content)


def scenario(
    name: str, tags: list[str] | None = None
) -> _ScenarioDecorator:
    """Mark a test for inclusion in the report."""
    return _ScenarioDecorator(name, tags or [])


class _ScenarioDecorator:
    def __init__(self, name: str, tags: list[str]) -> None:
        self.name = name
        self.tags = tags

    def __call__(self, func: Any) -> Any:
        import functools

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return func(*args, **kwargs)

        wrapper._scenario = self  # type: ignore[attr-defined]
        return wrapper
```

- [ ] **Step 6: Run all unit tests**

Run: `uv run pytest tests/unit/ -v`
Expected: All tests PASS.

- [ ] **Step 7: Commit**

```bash
git add src/pytest_given/__init__.py src/pytest_given/step_descriptor.py tests/unit/test_step_descriptor.py
git commit -m "Wire StepDescriptor to Collector, export public API"
```

---

### Task 6: Serializer (Model to JSON)

**Files:**
- Create: `src/pytest_given/serializer.py`
- Create: `tests/unit/test_serializer.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/test_serializer.py`:
```python
import json

from pytest_given.model import (
    Attachment,
    ErrorInfo,
    Metadata,
    ParameterCase,
    ParameterTable,
    ReportData,
    Scenario,
    Step,
)
from pytest_given.serializer import serialize_report


def test_serialize_empty_report() -> None:
    report = ReportData(
        metadata=Metadata(
            project='test',
            timestamp='2026-04-09T00:00:00Z',
            pytest_version='9.0',
            plugin_version='0.1.0',
        ),
        scenarios=[],
    )
    data = serialize_report(report)
    assert data['metadata']['project'] == 'test'
    assert data['scenarios'] == []
    # Verify it's JSON-serializable
    json.dumps(data)


def test_serialize_scenario_with_steps() -> None:
    report = ReportData(
        metadata=Metadata(
            project='p',
            timestamp='t',
            pytest_version='9',
            plugin_version='0.1',
        ),
        scenarios=[
            Scenario(
                id='test.py::test_x',
                name='Test X',
                module='test_mod',
                tags=['billing'],
                status='passed',
                duration_ms=42,
                steps=[
                    Step(
                        phase='given',
                        text='a machine',
                        source='fixture',
                    ),
                    Step(
                        phase='when',
                        text='I press start',
                        children=[
                            Step(phase='when', text='validating'),
                        ],
                    ),
                ],
            )
        ],
    )
    data = serialize_report(report)
    scenario = data['scenarios'][0]
    assert scenario['name'] == 'Test X'
    assert scenario['tags'] == ['billing']
    assert len(scenario['steps']) == 2
    assert scenario['steps'][0]['source'] == 'fixture'
    assert len(scenario['steps'][1]['children']) == 1
    json.dumps(data)


def test_serialize_with_parameters() -> None:
    report = ReportData(
        metadata=Metadata(project='p', timestamp='t', pytest_version='9', plugin_version='0.1'),
        scenarios=[
            Scenario(
                id='test.py::test_param',
                name='Param test',
                module='mod',
                status='failed',
                parameters=ParameterTable(
                    names=['a', 'b'],
                    cases=[
                        ParameterCase(values=[1, 2], status='passed'),
                        ParameterCase(
                            values=[3, 4],
                            status='failed',
                            error=ErrorInfo(message='assert 3 == 4'),
                        ),
                    ],
                ),
            )
        ],
    )
    data = serialize_report(report)
    params = data['scenarios'][0]['parameters']
    assert params['names'] == ['a', 'b']
    assert params['cases'][1]['error']['message'] == 'assert 3 == 4'
    json.dumps(data)


def test_serialize_with_attachments() -> None:
    report = ReportData(
        metadata=Metadata(project='p', timestamp='t', pytest_version='9', plugin_version='0.1'),
        scenarios=[
            Scenario(
                id='id',
                name='n',
                module='m',
                steps=[
                    Step(
                        phase='then',
                        text='check',
                        attachments=[Attachment(label='Log', content='data')],
                    )
                ],
            )
        ],
    )
    data = serialize_report(report)
    att = data['scenarios'][0]['steps'][0]['attachments'][0]
    assert att == {'label': 'Log', 'content': 'data'}
    json.dumps(data)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_serializer.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

`src/pytest_given/serializer.py`:
```python
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pytest_given.model import (
    Attachment,
    ErrorInfo,
    Metadata,
    ParameterCase,
    ParameterTable,
    ReportData,
    Scenario,
    Step,
)


def _serialize_attachment(att: Attachment) -> dict[str, Any]:
    return {'label': att.label, 'content': att.content}


def _serialize_error(err: ErrorInfo) -> dict[str, Any]:
    result: dict[str, Any] = {'message': err.message}
    result['diff'] = err.diff
    return result


def _serialize_step(step: Step) -> dict[str, Any]:
    return {
        'phase': step.phase,
        'text': step.text,
        'status': step.status,
        'source': step.source,
        'children': [_serialize_step(c) for c in step.children],
        'attachments': [_serialize_attachment(a) for a in step.attachments],
        'error': _serialize_error(step.error) if step.error else None,
    }


def _serialize_parameter_case(case: ParameterCase) -> dict[str, Any]:
    return {
        'values': case.values,
        'status': case.status,
        'error': _serialize_error(case.error) if case.error else None,
    }


def _serialize_parameter_table(table: ParameterTable) -> dict[str, Any]:
    return {
        'names': table.names,
        'cases': [_serialize_parameter_case(c) for c in table.cases],
    }


def _serialize_scenario(scenario: Scenario) -> dict[str, Any]:
    return {
        'id': scenario.id,
        'name': scenario.name,
        'module': scenario.module,
        'tags': scenario.tags,
        'status': scenario.status,
        'duration_ms': scenario.duration_ms,
        'steps': [_serialize_step(s) for s in scenario.steps],
        'parameters': (
            _serialize_parameter_table(scenario.parameters)
            if scenario.parameters
            else None
        ),
        'error': _serialize_error(scenario.error) if scenario.error else None,
    }


def _serialize_metadata(meta: Metadata) -> dict[str, Any]:
    return {
        'project': meta.project,
        'timestamp': meta.timestamp,
        'pytest_version': meta.pytest_version,
        'plugin_version': meta.plugin_version,
    }


def serialize_report(report: ReportData) -> dict[str, Any]:
    """Convert a ReportData to a JSON-serializable dict."""
    return {
        'metadata': _serialize_metadata(report.metadata),
        'scenarios': [_serialize_scenario(s) for s in report.scenarios],
    }


def write_json(report: ReportData, path: Path) -> None:
    """Serialize report data and write to a JSON file."""
    data = serialize_report(report)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_serializer.py -v`
Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/pytest_given/serializer.py tests/unit/test_serializer.py
git commit -m "Add JSON serializer for report data"
```

---

### Task 7: Pytest Plugin (Hooks)

**Files:**
- Create: `src/pytest_given/plugin.py`
- Create: `tests/integration/test_plugin.py`

- [ ] **Step 1: Write the failing integration test**

`tests/integration/test_plugin.py`:
```python
import json
from pathlib import Path


def test_basic_scenario_generates_json(pytester, tmp_path):
    """A simple @scenario test produces JSON output."""
    pytester.makepyfile(
        """
        from pytest_given import scenario, given, when, then

        @scenario("My scenario", tags=["smoke"])
        def test_example():
            with given("a value"):
                x = 1
            with when("I double it"):
                result = x * 2
            with then("it is 2"):
                assert result == 2
        """
    )
    json_path = tmp_path / 'report.json'
    result = pytester.runpytest(f'--given-json={json_path}')
    result.assert_outcomes(passed=1)
    assert json_path.exists()
    data = json.loads(json_path.read_text())
    assert len(data['scenarios']) == 1
    s = data['scenarios'][0]
    assert s['name'] == 'My scenario'
    assert s['tags'] == ['smoke']
    assert s['status'] == 'passed'
    assert len(s['steps']) == 3
    assert s['steps'][0]['phase'] == 'given'
    assert s['steps'][0]['text'] == 'a value'


def test_nested_steps(pytester, tmp_path):
    """Nested context managers produce nested steps."""
    pytester.makepyfile(
        """
        from pytest_given import scenario, when

        @scenario("Nested test")
        def test_nested():
            with when("outer"):
                with when("inner"):
                    pass
        """
    )
    json_path = tmp_path / 'report.json'
    result = pytester.runpytest(f'--given-json={json_path}')
    result.assert_outcomes(passed=1)
    data = json.loads(json_path.read_text())
    steps = data['scenarios'][0]['steps']
    assert len(steps) == 1
    assert steps[0]['text'] == 'outer'
    assert len(steps[0]['children']) == 1
    assert steps[0]['children'][0]['text'] == 'inner'


def test_failed_scenario(pytester, tmp_path):
    """A failing assertion is captured in the step error."""
    pytester.makepyfile(
        """
        from pytest_given import scenario, then

        @scenario("Failing test")
        def test_fail():
            with then("this fails"):
                assert 1 == 2
        """
    )
    json_path = tmp_path / 'report.json'
    result = pytester.runpytest(f'--given-json={json_path}')
    result.assert_outcomes(failed=1)
    data = json.loads(json_path.read_text())
    s = data['scenarios'][0]
    assert s['status'] == 'failed'
    assert s['error'] is not None


def test_unannotated_test_not_in_report(pytester, tmp_path):
    """Tests without @scenario don't appear in the report."""
    pytester.makepyfile(
        """
        def test_plain():
            assert True
        """
    )
    json_path = tmp_path / 'report.json'
    result = pytester.runpytest(f'--given-json={json_path}')
    result.assert_outcomes(passed=1)
    data = json.loads(json_path.read_text())
    assert len(data['scenarios']) == 0


def test_attachment_in_report(pytester, tmp_path):
    """Attachments on steps appear in the JSON."""
    pytester.makepyfile(
        """
        from pytest_given import scenario, then, attach

        @scenario("Attach test")
        def test_attach():
            with then("check"):
                attach("my log", "log content")
        """
    )
    json_path = tmp_path / 'report.json'
    result = pytester.runpytest(f'--given-json={json_path}')
    result.assert_outcomes(passed=1)
    data = json.loads(json_path.read_text())
    att = data['scenarios'][0]['steps'][0]['attachments']
    assert len(att) == 1
    assert att[0]['label'] == 'my log'


def test_decorated_fixture_appears_as_given_step(pytester, tmp_path):
    """A fixture decorated with @given appears as a given step."""
    pytester.makepyfile(
        """
        import pytest
        from pytest_given import scenario, given, then

        @pytest.fixture
        @given("a prepared value")
        def value():
            return 42

        @scenario("Fixture test")
        def test_fixture(value):
            with then(f"value is {value}"):
                assert value == 42
        """
    )
    json_path = tmp_path / 'report.json'
    result = pytester.runpytest(f'--given-json={json_path}')
    result.assert_outcomes(passed=1)
    data = json.loads(json_path.read_text())
    steps = data['scenarios'][0]['steps']
    assert steps[0]['phase'] == 'given'
    assert steps[0]['text'] == 'a prepared value'
    assert steps[0]['source'] == 'fixture'
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/integration/test_plugin.py -v`
Expected: FAIL — plugin.py doesn't exist yet.

- [ ] **Step 3: Write the plugin implementation**

`src/pytest_given/plugin.py`:
```python
from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from pytest_given.collector import Collector
from pytest_given.model import Metadata, ReportData
from pytest_given.serializer import write_json
from pytest_given.step_descriptor import set_active_collector

collector = Collector()


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup('given', 'pytest-given report generation')
    group.addoption(
        '--given-json',
        default='given-report/report-data.json',
        help='Output path for JSON report data (default: given-report/report-data.json)',
    )
    group.addoption(
        '--given-html',
        action='store_true',
        default=False,
        help='Also generate HTML report from JSON data',
    )
    group.addoption(
        '--given-html-output',
        default='given-report/report.html',
        help='Output path for HTML report (default: given-report/report.html)',
    )


def _get_scenario_marker(item: pytest.Item) -> Any | None:
    """Get the _scenario attribute from a test function, if present."""
    func = getattr(item, 'function', None)
    if func is None:
        return None
    return getattr(func, '_scenario', None)


def _get_fixture_steps(item: pytest.Item) -> list[tuple[str, str]]:
    """Collect step descriptors from fixtures used by this item."""
    steps: list[tuple[str, str]] = []
    if not hasattr(item, 'fixturenames'):
        return steps
    fm = item.session._fixturemanager
    for name in item.fixturenames:
        defs = fm.getfixturedefs(name, item)
        if not defs:
            continue
        func = defs[-1].func
        desc = getattr(func, '_step_descriptor', None)
        if desc is not None:
            steps.append((desc.phase, desc.text))
    return steps


_start_times: dict[str, float] = {}


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item: pytest.Item) -> None:
    scenario_marker = _get_scenario_marker(item)
    if scenario_marker is None:
        return
    module = item.module.__name__ if item.module else item.nodeid.split('::')[0]
    collector.start_scenario(
        scenario_id=item.nodeid,
        name=scenario_marker.name,
        module=module,
        tags=scenario_marker.tags,
    )
    set_active_collector(collector)
    # Add fixture steps
    for phase, text in _get_fixture_steps(item):
        collector.push_step(phase, text, source='fixture')
        collector.pop_step()
    _start_times[item.nodeid] = time.monotonic()


@pytest.hookimpl(trylast=True)
def pytest_runtest_teardown(item: pytest.Item) -> None:
    if collector.active_scenario_id != item.nodeid:
        return
    set_active_collector(None)


@pytest.hookimpl(hookimpl=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo[None]) -> None:  # type: ignore[type-arg]
    if collector.active_scenario_id != item.nodeid:
        return
    if call.when == 'call' and call.excinfo is not None:
        error_repr = call.excinfo.getrepr(style='short')
        message = str(call.excinfo.value)
        diff = str(error_repr)
        from pytest_given.model import ErrorInfo

        assert collector._current_scenario is not None
        collector._current_scenario.error = ErrorInfo(message=message, diff=diff)
        collector._current_scenario.status = 'failed'


@pytest.hookimpl(trylast=True)
def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    if report.when != 'call':
        return
    if collector.active_scenario_id != report.nodeid:
        return
    elapsed = time.monotonic() - _start_times.pop(report.nodeid, time.monotonic())
    duration_ms = int(elapsed * 1000)
    status = 'passed' if report.passed else 'failed' if report.failed else 'skipped'
    collector.finish_scenario(status=status, duration_ms=duration_ms)


def pytest_sessionfinish(session: pytest.Session) -> None:
    if not collector.scenarios:
        # Still write empty report so downstream tools don't break
        pass
    json_path = Path(session.config.getoption('given_json'))
    report = ReportData(
        metadata=Metadata(
            project=session.config.rootpath.name,
            timestamp=datetime.now(tz=timezone.utc).isoformat(),
            pytest_version=pytest.__version__,
            plugin_version='0.1.0',
        ),
        scenarios=collector.scenarios,
    )
    write_json(report, json_path)
    if session.config.getoption('given_html'):
        from pytest_given.renderer import render_html

        html_path = Path(session.config.getoption('given_html_output'))
        render_html(json_path, html_path)
```

- [ ] **Step 4: Run integration tests**

Run: `uv run pytest tests/integration/test_plugin.py -v`
Expected: All tests PASS.

- [ ] **Step 5: Run all tests**

Run: `uv run pytest tests/ -v`
Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/pytest_given/plugin.py tests/integration/test_plugin.py
git commit -m "Add pytest plugin hooks for scenario collection"
```

---

### Task 8: Renderer (JSON to HTML)

**Files:**
- Create: `src/pytest_given/renderer.py`
- Create: `src/pytest_given/templates/report.html.j2`
- Create: `src/pytest_given/templates/styles.css`
- Create: `tests/unit/test_renderer.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/test_renderer.py`:
```python
import json
from pathlib import Path

from pytest_given.renderer import render_html


def test_render_produces_html_file(tmp_path: Path) -> None:
    json_path = tmp_path / 'data.json'
    json_path.write_text(
        json.dumps(
            {
                'metadata': {
                    'project': 'test-proj',
                    'timestamp': '2026-04-09T00:00:00Z',
                    'pytest_version': '9.0',
                    'plugin_version': '0.1.0',
                },
                'scenarios': [],
            }
        )
    )
    html_path = tmp_path / 'report.html'
    render_html(json_path, html_path)
    assert html_path.exists()
    content = html_path.read_text()
    assert 'test-proj' in content
    assert 'Alpine' in content or 'x-data' in content


def test_render_includes_scenario_data(tmp_path: Path) -> None:
    json_path = tmp_path / 'data.json'
    json_path.write_text(
        json.dumps(
            {
                'metadata': {
                    'project': 'p',
                    'timestamp': 't',
                    'pytest_version': '9',
                    'plugin_version': '0.1',
                },
                'scenarios': [
                    {
                        'id': 'test.py::test_x',
                        'name': 'My Scenario',
                        'module': 'test_mod',
                        'tags': ['billing'],
                        'status': 'passed',
                        'duration_ms': 10,
                        'steps': [
                            {
                                'phase': 'given',
                                'text': 'a thing',
                                'status': 'passed',
                                'source': None,
                                'children': [],
                                'attachments': [],
                                'error': None,
                            }
                        ],
                        'parameters': None,
                        'error': None,
                    }
                ],
            }
        )
    )
    html_path = tmp_path / 'report.html'
    render_html(json_path, html_path)
    content = html_path.read_text()
    assert 'My Scenario' in content
    assert 'billing' in content
    assert 'a thing' in content


def test_render_self_contained(tmp_path: Path) -> None:
    """The output HTML has no external dependencies."""
    json_path = tmp_path / 'data.json'
    json_path.write_text(
        json.dumps(
            {
                'metadata': {
                    'project': 'p',
                    'timestamp': 't',
                    'pytest_version': '9',
                    'plugin_version': '0.1',
                },
                'scenarios': [],
            }
        )
    )
    html_path = tmp_path / 'report.html'
    render_html(json_path, html_path)
    content = html_path.read_text()
    assert '<style>' in content
    assert '<script>' in content
    # No external CSS/JS links
    assert 'href="http' not in content
    assert 'src="http' not in content
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_renderer.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Create the CSS file**

`src/pytest_given/templates/styles.css`:
```css
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0d0d1a; color: #e0e0e0; display: flex; min-height: 100vh; }

/* Sidebar */
.sidebar { width: 260px; background: #141422; border-right: 1px solid #333; padding: 16px; flex-shrink: 0; overflow-y: auto; max-height: 100vh; position: sticky; top: 0; }
.sidebar input[type="text"] { width: 100%; padding: 8px 12px; background: #1a1a2e; border: 1px solid #333; border-radius: 6px; color: #e0e0e0; font-size: 13px; outline: none; }
.sidebar input[type="text"]:focus { border-color: #7ecfff; }
.sidebar-section { margin-top: 16px; }
.sidebar-label { color: #888; font-size: 11px; text-transform: uppercase; margin-bottom: 8px; }
.view-toggle { display: flex; gap: 4px; }
.view-btn { padding: 4px 10px; border-radius: 4px; font-size: 12px; cursor: pointer; border: 1px solid #333; background: #1a1a2e; color: #888; }
.view-btn.active { color: #7ecfff; border-color: #7ecfff; background: #2a2a4a; }
.status-filter label { display: flex; align-items: center; gap: 6px; color: #ccc; font-size: 12px; cursor: pointer; padding: 2px 0; }
.tag-tree { font-size: 12px; }
.tag-item { color: #7ecfff; cursor: pointer; padding: 2px 0; }
.tag-scenario { color: #ccc; padding-left: 12px; font-size: 11px; cursor: pointer; padding-top: 1px; padding-bottom: 1px; }

/* Main */
.main { flex: 1; padding: 20px; overflow-y: auto; }
.header { margin-bottom: 20px; }
.header h1 { font-size: 20px; font-weight: 600; }
.header .meta { color: #888; font-size: 12px; margin-top: 4px; }

/* Scenario cards */
.scenario { background: #1a1a2e; border-radius: 8px; padding: 16px; margin-bottom: 16px; border-left: 3px solid #4caf50; }
.scenario.failed { border-left-color: #f44336; }
.scenario.skipped { border-left-color: #ff9800; }
.scenario-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.scenario-name { font-size: 15px; font-weight: 600; }
.scenario-tag { background: #2a2a4a; color: #7ecfff; font-size: 11px; padding: 2px 8px; border-radius: 10px; margin-left: 6px; }
.scenario-status { font-size: 12px; }
.scenario-status.passed { color: #4caf50; }
.scenario-status.failed { color: #f44336; }
.scenario-status.skipped { color: #ff9800; }

/* Steps */
.steps { font-size: 13px; line-height: 1.8; }
.phase-label { font-weight: 600; margin-bottom: 2px; }
.phase-given { color: #c792ea; }
.phase-when { color: #ffcb6b; }
.phase-then { color: #82aaff; }
.step-text { color: #ccc; padding-left: 16px; margin-bottom: 2px; }
.step-children { padding-left: 16px; border-left: 1px solid #333; margin-left: 8px; }
.step-toggle { cursor: pointer; user-select: none; }

/* Param table */
.param-table { width: 100%; border-collapse: collapse; font-size: 13px; background: #0d0d1a; border-radius: 6px; overflow: hidden; margin-top: 8px; }
.param-table th { text-align: left; padding: 8px 12px; color: #888; font-weight: 500; background: #1e1e3a; }
.param-table td { padding: 8px 12px; color: #ccc; border-top: 1px solid #1a1a2e; }
.param-table tr.failed-row { background: #2a1015; }

/* Error */
.error-block { margin-top: 8px; background: #2a1015; border-radius: 6px; padding: 12px; font-size: 12px; border: 1px solid rgba(244, 67, 54, 0.2); }
.error-message { color: #f44336; font-weight: 600; margin-bottom: 4px; }
.error-diff { color: #ccc; font-size: 11px; line-height: 1.5; white-space: pre-wrap; font-family: monospace; }

/* Attachments */
.attachment-badge { color: #888; font-size: 11px; cursor: pointer; background: #0d0d1a; display: inline-block; padding: 2px 8px; border-radius: 4px; margin-top: 4px; }
.attachment-content { background: #0d0d1a; padding: 8px 12px; border-radius: 4px; font-size: 12px; font-family: monospace; white-space: pre-wrap; color: #ccc; margin-top: 4px; }

/* Counts */
.count-badge { font-size: 11px; color: #888; margin-left: 4px; }
.dot-passed { color: #4caf50; }
.dot-failed { color: #f44336; }
.dot-skipped { color: #ff9800; }
```

- [ ] **Step 4: Create the Jinja2 template**

`src/pytest_given/templates/report.html.j2`:

This is a large file. The template should:
1. Embed the CSS from `styles.css` in a `<style>` tag
2. Embed Alpine.js (minified, ~17kB) in a `<script>` tag — for now use the CDN URL in a comment and a TODO to bundle it; we'll inline it in a later step
3. Embed the report JSON data in a `<script>` tag as `window.__REPORT_DATA__`
4. Render the sidebar with Alpine.js directives for filtering
5. Render scenario cards with steps, params, errors, attachments
6. Support recursive step rendering via a Jinja2 macro

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{{ metadata.project }} — pytest-given Report</title>
<style>
{{ css }}
</style>
</head>
<body x-data="reportApp()">

<div class="sidebar">
  <input type="text" placeholder="Filter scenarios..." x-model="search">

  <div class="sidebar-section">
    <div class="sidebar-label">View by</div>
    <div class="view-toggle">
      <div class="view-btn" :class="{ active: view === 'tags' }" @click="view = 'tags'">Tags</div>
      <div class="view-btn" :class="{ active: view === 'modules' }" @click="view = 'modules'">Modules</div>
    </div>
  </div>

  <div class="sidebar-section">
    <div class="sidebar-label">Status</div>
    <div class="status-filter">
      <label><input type="checkbox" x-model="showPassed"> <span class="dot-passed">●</span> Passed (<span x-text="counts.passed"></span>)</label>
      <label><input type="checkbox" x-model="showFailed"> <span class="dot-failed">●</span> Failed (<span x-text="counts.failed"></span>)</label>
      <label><input type="checkbox" x-model="showSkipped"> <span class="dot-skipped">●</span> Skipped (<span x-text="counts.skipped"></span>)</label>
    </div>
  </div>

  <div class="sidebar-section">
    <div class="sidebar-label" x-text="view === 'tags' ? 'Tags' : 'Modules'"></div>
    <div class="tag-tree">
      <template x-for="group in groups" :key="group.name">
        <div>
          <div class="tag-item" @click="toggleGroup(group.name)">
            <span x-text="expandedGroups.has(group.name) ? '▾' : '▸'"></span>
            <span x-text="group.name"></span>
            <span class="count-badge" x-text="'(' + group.scenarios.length + ')'"></span>
          </div>
          <template x-if="expandedGroups.has(group.name)">
            <div>
              <template x-for="s in group.scenarios" :key="s.id">
                <div class="tag-scenario" @click="scrollTo(s.id)" x-text="s.name"></div>
              </template>
            </div>
          </template>
        </div>
      </template>
    </div>
  </div>
</div>

<div class="main">
  <div class="header">
    <h1>{{ metadata.project }}</h1>
    <div class="meta">Generated {{ metadata.timestamp }} · pytest {{ metadata.pytest_version }} · pytest-given {{ metadata.plugin_version }}</div>
  </div>

  {% for scenario in scenarios %}
  <div class="scenario {{ scenario.status }}"
       x-show="isVisible({{ scenario | tojson }})"
       :id="'scenario-' + {{ loop.index0 }}">
    <div class="scenario-header">
      <div>
        <span class="scenario-name">{{ scenario.name }}</span>
        {% for tag in scenario.tags %}
        <span class="scenario-tag">{{ tag }}</span>
        {% endfor %}
      </div>
      <span class="scenario-status {{ scenario.status }}">
        {% if scenario.status == 'passed' %}✓ passed{% elif scenario.status == 'failed' %}✗ failed{% else %}○ skipped{% endif %}
      </span>
    </div>

    <div class="steps">
      {{ render_steps(scenario.steps) }}
    </div>

    {% if scenario.parameters %}
    <table class="param-table">
      <thead>
        <tr>
          {% for name in scenario.parameters.names %}
          <th>{{ name }}</th>
          {% endfor %}
          <th style="text-align:right">status</th>
        </tr>
      </thead>
      <tbody>
        {% for case in scenario.parameters.cases %}
        <tr class="{{ 'failed-row' if case.status == 'failed' else '' }}">
          {% for val in case.values %}
          <td>{{ val }}</td>
          {% endfor %}
          <td style="text-align:right">
            {% if case.status == 'passed' %}<span class="dot-passed">✓</span>{% else %}<span class="dot-failed">✗</span>{% endif %}
          </td>
        </tr>
        {% if case.error %}
        <tr>
          <td colspan="{{ scenario.parameters.names | length + 1 }}">
            <div class="error-block">
              <div class="error-message">{{ case.error.message }}</div>
              {% if case.error.diff %}<pre class="error-diff">{{ case.error.diff }}</pre>{% endif %}
            </div>
          </td>
        </tr>
        {% endif %}
        {% endfor %}
      </tbody>
    </table>
    {% endif %}

    {% if scenario.error %}
    <div class="error-block">
      <div class="error-message">{{ scenario.error.message }}</div>
      {% if scenario.error.diff %}<pre class="error-diff">{{ scenario.error.diff }}</pre>{% endif %}
    </div>
    {% endif %}
  </div>
  {% endfor %}
</div>

<script>
window.__REPORT_DATA__ = {{ report_json }};
</script>
<script>
/* Alpine.js v3 will be inlined here — for now use a minimal reactive implementation */
document.addEventListener('alpine:init', () => {});
</script>
<script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3.x.x/dist/cdn.min.js"></script>
<script>
function reportApp() {
  const data = window.__REPORT_DATA__;
  return {
    search: '',
    view: 'tags',
    showPassed: true,
    showFailed: true,
    showSkipped: true,
    expandedGroups: new Set(),
    expandedSteps: new Set(),
    expandedAttachments: new Set(),
    get counts() {
      return {
        passed: data.scenarios.filter(s => s.status === 'passed').length,
        failed: data.scenarios.filter(s => s.status === 'failed').length,
        skipped: data.scenarios.filter(s => s.status === 'skipped').length,
      };
    },
    get groups() {
      const grouped = {};
      for (const s of data.scenarios) {
        const keys = this.view === 'tags'
          ? (s.tags.length ? s.tags : ['untagged'])
          : [s.module];
        for (const k of keys) {
          if (!grouped[k]) grouped[k] = { name: k, scenarios: [] };
          grouped[k].scenarios.push(s);
        }
      }
      return Object.values(grouped).sort((a, b) => a.name.localeCompare(b.name));
    },
    toggleGroup(name) {
      if (this.expandedGroups.has(name)) this.expandedGroups.delete(name);
      else this.expandedGroups.add(name);
    },
    isVisible(scenario) {
      if (scenario.status === 'passed' && !this.showPassed) return false;
      if (scenario.status === 'failed' && !this.showFailed) return false;
      if (scenario.status === 'skipped' && !this.showSkipped) return false;
      if (this.search) {
        const q = this.search.toLowerCase();
        const text = (scenario.name + ' ' + scenario.tags.join(' ')).toLowerCase();
        if (!text.includes(q)) return false;
      }
      return true;
    },
    scrollTo(id) {
      const el = document.getElementById('scenario-' + data.scenarios.findIndex(s => s.id === id));
      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    },
  };
}
</script>
</body>
</html>
```

Note: The template uses a CDN link for Alpine.js initially. We'll inline Alpine.js in a later task to make the file fully self-contained. The `render_steps` macro is defined in the renderer.

- [ ] **Step 5: Write the renderer**

`src/pytest_given/renderer.py`:
```python
from __future__ import annotations

import json
from pathlib import Path

import jinja2


def _build_step_html(steps: list[dict], depth: int = 0) -> str:  # type: ignore[type-arg]
    """Recursively build HTML for steps."""
    html_parts: list[str] = []
    current_phase: str | None = None

    for step in steps:
        phase = step['phase']
        if phase != current_phase:
            current_phase = phase
            html_parts.append(
                f'<div class="phase-label phase-{phase}">'
                f'{phase.capitalize()}</div>'
            )

        html_parts.append(f'<div class="step-text">{_escape(step["text"])}</div>')

        if step.get('attachments'):
            for att in step['attachments']:
                att_id = id(att)
                html_parts.append(
                    f'<div class="step-text">'
                    f'<span class="attachment-badge" '
                    f'@click="expandedAttachments.has({att_id!r}) '
                    f'? expandedAttachments.delete({att_id!r}) '
                    f': expandedAttachments.add({att_id!r})">'
                    f'📎 {_escape(att["label"])}</span>'
                    f'<div class="attachment-content" '
                    f'x-show="expandedAttachments.has({att_id!r})">'
                    f'{_escape(att["content"])}</div>'
                    f'</div>'
                )

        if step.get('children'):
            html_parts.append('<div class="step-children">')
            html_parts.append(_build_step_html(step['children'], depth + 1))
            html_parts.append('</div>')

        if step.get('error'):
            err = step['error']
            html_parts.append('<div class="error-block">')
            html_parts.append(
                f'<div class="error-message">{_escape(err["message"])}</div>'
            )
            if err.get('diff'):
                html_parts.append(
                    f'<pre class="error-diff">{_escape(err["diff"])}</pre>'
                )
            html_parts.append('</div>')

    return '\n'.join(html_parts)


def _escape(text: str) -> str:
    """HTML-escape text."""
    return (
        text.replace('&', '&amp;')
        .replace('<', '&lt;')
        .replace('>', '&gt;')
        .replace('"', '&quot;')
    )


def render_html(json_path: Path, html_path: Path) -> None:
    """Render a JSON report to a self-contained HTML file."""
    data = json.loads(json_path.read_text())

    # Pre-render steps to HTML
    for scenario in data['scenarios']:
        scenario['_steps_html'] = _build_step_html(scenario.get('steps', []))

    templates_dir = Path(__file__).parent / 'templates'
    css = (templates_dir / 'styles.css').read_text()

    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(templates_dir)),
        autoescape=False,
    )
    template = env.get_template('report.html.j2')
    html = template.render(
        metadata=data['metadata'],
        scenarios=data['scenarios'],
        report_json=json.dumps(data),
        css=css,
        render_steps=lambda steps: _build_step_html(steps),
    )
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(html)
```

- [ ] **Step 6: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_renderer.py -v`
Expected: All tests PASS.

- [ ] **Step 7: Commit**

```bash
git add src/pytest_given/renderer.py src/pytest_given/templates/ tests/unit/test_renderer.py
git commit -m "Add HTML renderer with Jinja2 template and Alpine.js"
```

---

### Task 9: CLI (Standalone Report Generation)

**Files:**
- Create: `src/pytest_given/cli.py`
- Create: `tests/integration/test_cli.py`

- [ ] **Step 1: Write the failing test**

`tests/integration/test_cli.py`:
```python
import json
import subprocess
import sys
from pathlib import Path


def test_cli_generates_html(tmp_path: Path) -> None:
    json_path = tmp_path / 'data.json'
    json_path.write_text(
        json.dumps(
            {
                'metadata': {
                    'project': 'cli-test',
                    'timestamp': '2026-04-09',
                    'pytest_version': '9',
                    'plugin_version': '0.1',
                },
                'scenarios': [],
            }
        )
    )
    html_path = tmp_path / 'out.html'
    result = subprocess.run(
        [sys.executable, '-m', 'pytest_given.cli', 'report', str(json_path), '-o', str(html_path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert html_path.exists()
    assert 'cli-test' in html_path.read_text()


def test_cli_missing_input_file(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, '-m', 'pytest_given.cli', 'report', str(tmp_path / 'nonexistent.json')],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/integration/test_cli.py -v`
Expected: FAIL

- [ ] **Step 3: Write the implementation**

`src/pytest_given/cli.py`:
```python
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pytest_given.renderer import render_html


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog='pytest-given',
        description='Generate HTML reports from pytest-given JSON data.',
    )
    subparsers = parser.add_subparsers(dest='command')

    report_parser = subparsers.add_parser(
        'report', help='Generate HTML report from JSON data'
    )
    report_parser.add_argument('json_file', type=Path, help='Path to JSON report data')
    report_parser.add_argument(
        '-o',
        '--output',
        type=Path,
        default=Path('given-report/report.html'),
        help='Output HTML file path (default: given-report/report.html)',
    )

    args = parser.parse_args(argv)

    if args.command == 'report':
        if not args.json_file.exists():
            print(f'Error: {args.json_file} not found', file=sys.stderr)
            return 1
        render_html(args.json_file, args.output)
        print(f'Report generated: {args.output}')
        return 0

    parser.print_help()
    return 1


if __name__ == '__main__':
    sys.exit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/integration/test_cli.py -v`
Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/pytest_given/cli.py tests/integration/test_cli.py
git commit -m "Add CLI for standalone report generation"
```

---

### Task 10: Parameterized Test Support

**Files:**
- Modify: `src/pytest_given/plugin.py`
- Modify: `tests/integration/test_plugin.py`

- [ ] **Step 1: Write the failing integration test**

Add to `tests/integration/test_plugin.py`:
```python
def test_parameterized_test_as_table(pytester, tmp_path):
    """Parameterized tests produce a parameter table in the report."""
    pytester.makepyfile(
        """
        import pytest
        from pytest_given import scenario, given, when, then

        @scenario("Param test", tags=["math"])
        @pytest.mark.parametrize("a,b,expected", [(1, 2, 3), (2, 3, 5)])
        def test_add(a, b, expected):
            with given(f"a={a} and b={b}"):
                pass
            with then(f"sum is {expected}"):
                assert a + b == expected
        """
    )
    json_path = tmp_path / 'report.json'
    result = pytester.runpytest(f'--given-json={json_path}')
    result.assert_outcomes(passed=2)
    data = json.loads(json_path.read_text())
    # Parameterized tests should be grouped under one scenario name
    # Each run is a separate scenario entry (pytest creates separate items)
    assert len(data['scenarios']) == 2
    assert all(s['name'] == 'Param test' for s in data['scenarios'])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/integration/test_plugin.py::test_parameterized_test_as_table -v`
Expected: FAIL (need `import json` at the top of the test file if not already there)

- [ ] **Step 3: Verify it works with existing plugin**

Parameterized tests in pytest create separate test items, each with a unique nodeid (e.g., `test.py::test_add[1-2-3]`). The `@scenario` decorator is on the function, so each parameterized call picks it up. The current plugin should already handle this — each call becomes its own scenario entry with the same name but different steps (because f-strings contain the actual parameter values).

This may already pass with the existing plugin code. If it does, commit the test. If not, update the plugin to handle parametrize markers.

Run: `uv run pytest tests/integration/test_plugin.py::test_parameterized_test_as_table -v`

- [ ] **Step 4: Commit**

```bash
git add tests/integration/test_plugin.py
git commit -m "Add integration test for parameterized tests"
```

---

### Task 11: Inline Alpine.js for Self-Contained Report

**Files:**
- Modify: `src/pytest_given/templates/report.html.j2`
- Modify: `src/pytest_given/renderer.py`
- Create: `src/pytest_given/templates/alpine.min.js`

- [ ] **Step 1: Download Alpine.js**

Run: `curl -L https://cdn.jsdelivr.net/npm/alpinejs@3/dist/cdn.min.js -o src/pytest_given/templates/alpine.min.js`

Verify: `wc -c src/pytest_given/templates/alpine.min.js` should show ~45-50kB

- [ ] **Step 2: Update the template to use inlined Alpine.js**

Replace the CDN `<script>` tag in `report.html.j2`:

Replace:
```html
<script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3.x.x/dist/cdn.min.js"></script>
```

With:
```html
<script>{{ alpine_js }}</script>
```

- [ ] **Step 3: Update the renderer to read and embed Alpine.js**

In `src/pytest_given/renderer.py`, add Alpine.js reading alongside CSS:

```python
alpine_js = (templates_dir / 'alpine.min.js').read_text()
```

And pass it to the template:
```python
html = template.render(
    ...,
    alpine_js=alpine_js,
)
```

- [ ] **Step 4: Run self-contained test**

Run: `uv run pytest tests/unit/test_renderer.py::test_render_self_contained -v`
Expected: PASS (no external `src="http` links)

- [ ] **Step 5: Commit**

```bash
git add src/pytest_given/templates/alpine.min.js src/pytest_given/templates/report.html.j2 src/pytest_given/renderer.py
git commit -m "Inline Alpine.js for fully self-contained HTML report"
```

---

### Task 12: Integration Test — Full End-to-End

**Files:**
- Modify: `tests/integration/test_plugin.py`

- [ ] **Step 1: Write end-to-end test that generates HTML**

Add to `tests/integration/test_plugin.py`:
```python
def test_full_html_report_generation(pytester, tmp_path):
    """Full pipeline: tests -> JSON -> HTML."""
    pytester.makepyfile(
        """
        import pytest
        from pytest_given import scenario, given, when, then, attach

        @pytest.fixture
        @given("a calculator")
        def calc():
            return {"value": 0}

        @scenario("Basic addition", tags=["math"])
        def test_add(calc):
            with when("I add 2 and 3"):
                calc["value"] = 2 + 3
            with then("the result is 5"):
                assert calc["value"] == 5
                attach("debug", f"result was {calc['value']}")

        @scenario("Failing test", tags=["math"])
        def test_fail(calc):
            with then("this will fail"):
                assert 1 == 2
        """
    )
    json_path = tmp_path / 'report.json'
    html_path = tmp_path / 'report.html'
    result = pytester.runpytest(
        f'--given-json={json_path}',
        '--given-html',
        f'--given-html-output={html_path}',
    )
    result.assert_outcomes(passed=1, failed=1)
    assert json_path.exists()
    assert html_path.exists()

    # Verify JSON structure
    data = json.loads(json_path.read_text())
    assert len(data['scenarios']) == 2
    names = {s['name'] for s in data['scenarios']}
    assert names == {'Basic addition', 'Failing test'}

    # Verify HTML content
    html = html_path.read_text()
    assert 'Basic addition' in html
    assert 'Failing test' in html
    assert 'a calculator' in html
    assert 'x-data' in html  # Alpine.js reactive
```

- [ ] **Step 2: Run the test**

Run: `uv run pytest tests/integration/test_plugin.py::test_full_html_report_generation -v`
Expected: PASS

- [ ] **Step 3: Run the full test suite**

Run: `uv run pytest tests/ -v`
Expected: All tests PASS.

- [ ] **Step 4: Run linting and type checking**

Run: `nox -s lint` and `nox -s mypy`

Fix any issues found.

- [ ] **Step 5: Commit**

```bash
git add tests/integration/test_plugin.py
git commit -m "Add end-to-end integration test for full report pipeline"
```

---

### Task 13: Polish and Quality Gates

**Files:**
- Various fixes across all source files

- [ ] **Step 1: Run `nox -s format`**

Run: `nox -s format`
Fix any formatting issues, re-run to verify clean.

- [ ] **Step 2: Run `nox -s lint`**

Run: `nox -s lint`
Fix any linting issues.

- [ ] **Step 3: Run `nox -s mypy`**

Run: `nox -s mypy`
Fix any type errors. Common issues:
- Add type annotations to any untyped functions
- Fix `Any` usage where specific types are needed

- [ ] **Step 4: Run `nox -s test`**

Run: `nox -s test`
All tests should pass.

- [ ] **Step 5: Check coverage**

Run: `nox -s coverage`
Identify any uncovered lines and add tests for them.

- [ ] **Step 6: Commit any fixes**

```bash
git add -A
git commit -m "Fix linting, type errors, and coverage gaps"
```

---

### Task 14: Verify Full Pipeline Manually

- [ ] **Step 1: Create a sample test file**

Create `examples/test_sample.py` (not committed, just for manual verification):
```python
import pytest
from pytest_given import scenario, given, when, then, attach


@pytest.fixture
@given("a coffee machine")
def machine():
    return {"coffees": 10, "price": 2}


@scenario("Buy coffee", tags=["billing", "happy-path"])
def test_buy_coffee(machine):
    with when("I insert $2"):
        machine["coffees"] -= 1
    with then("I get a coffee"):
        assert machine["coffees"] == 9
        attach("Machine state", str(machine))


@scenario("Not enough money", tags=["billing", "edge-case"])
def test_not_enough(machine):
    with when("I insert $1"):
        paid = 1
    with then("I don't get a coffee"):
        assert paid < machine["price"]


@scenario("Pricing", tags=["billing"])
@pytest.mark.parametrize("euros,expect", [(1, False), (2, True), (3, True)])
def test_pricing(machine, euros, expect):
    with when(f"I insert ${euros}"):
        can_buy = euros >= machine["price"]
    with then(f"can_buy is {expect}"):
        assert can_buy == expect
```

- [ ] **Step 2: Run pytest with HTML generation**

Run: `uv run pytest examples/test_sample.py --given-json=given-report/report-data.json --given-html --given-html-output=given-report/report.html -v`

Expected: Tests run, JSON and HTML files generated.

- [ ] **Step 3: Open the HTML report in a browser**

Run: `open given-report/report.html` (macOS)

Verify:
- Sidebar shows tags (billing, happy-path, edge-case) with counts
- Scenarios are listed with correct steps
- "Buy coffee" shows the fixture as a Given step
- Parameterized "Pricing" shows all 3 entries
- Attachments expand when clicked
- Search and status filters work

- [ ] **Step 4: Clean up**

```bash
rm -rf examples/ given-report/
```
