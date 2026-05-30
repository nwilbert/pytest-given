"""pytest-given plugin entry point."""

import contextlib
import dataclasses
import functools
import inspect
import json
import time
from collections.abc import Generator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pytest
from _pytest.fixtures import SubRequest

from pytest_given.collector import (
    Collector,
    FixtureInstanceKey,
    set_active_collector,
)
from pytest_given.errors import PytestGivenError
from pytest_given.model import (
    FixtureRecording,
    Metadata,
    NodeId,
    ParameterCase,
    ParameterTable,
    ParamInfo,
    ParamSpec,
    ReportData,
    Scenario,
    Step,
)
from pytest_given.template import (
    Narration,
    NarrationLiteral,
    NarrationPart,
    NarrationPlaceholder,
    NarrationValue,
    Template,
)

collector = Collector()


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup('given', 'pytest-given report generation')
    group.addoption(
        '--given-json',
        default='given-report/report-data.json',
        help='Output path for JSON report data',
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


def pytest_sessionstart(session: pytest.Session) -> None:
    """Reset the collector at the start of each session."""
    global collector
    collector = Collector()


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Validate Template-named scenarios eagerly at collection time.

    Two checks:
    1. A Template-named scenario must be parametrized (its substitution source
       is `callspec.params`).
    2. Every Template placeholder must match a parametrize column name —
       catches typos at `pytest --collect-only` rather than at session-finish
       merge, where the error would escape `pytest_sessionfinish` opaquely.

    Deferred to collection time (rather than decoration time) because
    @scenario and @pytest.mark.parametrize can appear in either order, and
    decoration-time inspection only sees markers from earlier (bottom-up)
    decorators.
    """
    for item in items:
        marker = _get_scenario_marker(item)
        if marker is None:
            continue
        if not isinstance(marker.name, Template):
            continue
        callspec = getattr(item, 'callspec', None)
        if callspec is None:
            raise PytestGivenError(
                f'@scenario(Template(...)) on {item.nodeid!r} requires '
                f'@pytest.mark.parametrize; the substitution source is '
                f'callspec.params only. Use a plain string for static '
                f'scenario names, or add @pytest.mark.parametrize.'
            )
        param_names = list(callspec.params.keys())
        for placeholder in marker.name.get_identifiers():
            if placeholder not in param_names:
                raise PytestGivenError(
                    f"pytest_given.Template placeholder '{{{placeholder}}}' "
                    f'in @scenario(...) on {item.nodeid!r} does not match '
                    f'any parametrize column (have: {sorted(param_names)}).'
                )


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_setup(item: pytest.Item) -> Generator[None]:
    scenario_marker = _get_scenario_marker(item)
    if scenario_marker is None:
        # Unannotated test: set the flag so `with given(...)` inside it warns
        # instead of raising. Teardown clears the flag and active collector.
        collector.inside_unannotated_test = True
        set_active_collector(collector)
        yield
        return

    mod = getattr(item, 'module', None)
    module = mod.__name__ if mod else item.nodeid.split('::')[0]
    node_id = NodeId(item.nodeid)
    collector.start_scenario(
        scenario_id=node_id,
        name=scenario_marker.name,
        module=module,
        tags=scenario_marker.tags,
    )
    set_active_collector(collector)
    callspec = getattr(item, 'callspec', None)
    if callspec is not None:
        names = list(callspec.params.keys())
        values = [callspec.params[n] for n in names]
        collector.param_info[node_id] = ParamSpec(names=names, values=values)
    # Pre-fixture-setup work done; let pytest run fixture setup here.
    yield
    _graft_fixture_recordings(item)
    collector.start_times[node_id] = time.monotonic()


@pytest.hookimpl(hookwrapper=True)
def pytest_fixture_setup(
    fixturedef: pytest.FixtureDef[object],
    request: pytest.FixtureRequest,
) -> Generator[None]:
    desc = getattr(fixturedef.func, '_step_descriptor', None)
    if desc is None:
        yield
        return
    if desc.phase != 'given':
        raise PytestGivenError(
            f"Fixture '{fixturedef.argname}' is decorated with @{desc.phase}, "
            'but only @given is allowed on fixtures (fixtures are setup). '
            'Use @given(...) on the fixture, or move the step into the test body.'
        )
    if collector.state == 'idle':
        # Fixture is being set up outside any tracked scenario (e.g. unannotated
        # test pulling in a step fixture). Don't record.
        yield
        return
    _ensure_teardown_wrapped(fixturedef)
    recording = FixtureRecording(root=Step(phase=desc.phase, narration=desc.narration))
    token = collector.enter_fixture_setup(recording, descriptor=desc)
    try:
        yield
    finally:
        collector.exit_fixture_setup(token)
        key = _fixture_instance_key(fixturedef, request)
        collector.store_recording(key, recording)


def _ensure_teardown_wrapped(fixturedef: pytest.FixtureDef[object]) -> None:
    """Wrap a generator fixture's body once so post-yield code runs in
    fixture_teardown state. Idempotent."""
    func = fixturedef.func
    if getattr(func, '_pytest_given_teardown_wrapped', False):
        return
    if not inspect.isgeneratorfunction(func):
        return
    original = func
    desc = original._step_descriptor  # type: ignore[attr-defined]

    @functools.wraps(original)
    def wrapped(*args: object, **kwargs: object) -> Generator[object]:
        gen = original(*args, **kwargs)
        try:
            value = next(gen)
        except StopIteration:
            return
        yield value
        # Past the yield → teardown
        token = collector.enter_fixture_teardown()
        try:
            with contextlib.suppress(StopIteration):
                next(gen)
        finally:
            collector.exit_fixture_teardown(token)

    wrapped._pytest_given_teardown_wrapped = True  # type: ignore[attr-defined]
    wrapped._step_descriptor = desc  # type: ignore[attr-defined]
    fixturedef.func = wrapped  # type: ignore[misc]


def _fixture_instance_key(
    fixturedef: pytest.FixtureDef[object],
    request: pytest.FixtureRequest,
) -> FixtureInstanceKey:
    return (id(fixturedef), fixturedef.cache_key(cast(SubRequest, request)))


def _get_scenario_marker(item: pytest.Item) -> Any | None:
    """Get the _scenario attribute from a test function, if present.

    Returns None for items without a `.function` (e.g. DoctestItem) — those
    can't carry @scenario, so they're never load-bearing here.
    """
    func = getattr(item, 'function', None)
    if func is None:
        return None
    return getattr(func, '_scenario', None)


def _extract_skip_reason(longrepr: object) -> str | None:
    """Return a human-readable reason from pytest's TestReport.longrepr, or None.

    Pytest emits skipped longrepr as (path, lineno, message), where message is
    typically "Skipped: <reason>" (mark-based) or "<reason>" (call-time).
    Returns None for empty messages, the reasonless `<Skipped instance>`
    placeholder, pytest's default "unconditional skip" (emitted when
    @pytest.mark.skip is used with no reason), or any shape we don't recognise.
    """
    if not isinstance(longrepr, tuple) or len(longrepr) != 3:
        return None
    message = longrepr[2]
    if not isinstance(message, str):
        return None
    if message.startswith('Skipped: '):
        message = message[len('Skipped: ') :]
    message = message.strip()
    if not message or message in ('<Skipped instance>', 'unconditional skip'):
        return None
    return message


def _graft_fixture_recordings(item: pytest.Item) -> None:
    """Graft this item's step-fixture recordings in setup order.

    `collector._recordings` is insertion-ordered by setup time, so iterating it
    preserves narrative order even when `item.fixturenames` lists dependents
    before their dependencies.
    """
    assert hasattr(item, 'fixturenames'), f'expected fixturenames on {item!r}'
    fm = item.session._fixturemanager
    expected: dict[FixtureInstanceKey, str] = {}
    for name in item.fixturenames:
        defs = fm.getfixturedefs(name, item)
        if not defs:
            continue
        fixturedef = defs[-1]
        if getattr(fixturedef.func, '_step_descriptor', None) is None:
            continue
        if fixturedef.cached_result is None:
            continue
        key: FixtureInstanceKey = (id(fixturedef), fixturedef.cached_result[1])
        expected[key] = fixturedef.scope
    # Function-scoped recordings won't be re-consumed; drop after grafting so
    # the recordings dict doesn't grow unboundedly across the session.
    to_drop: list[FixtureInstanceKey] = []
    for key, recording in collector.recordings():
        if key in expected:
            collector.graft_recording(recording)
            if expected[key] == 'function':
                to_drop.append(key)
    for key in to_drop:
        collector.drop_recording(key)


@pytest.hookimpl(trylast=True)
def pytest_runtest_teardown(item: pytest.Item) -> None:
    if collector.inside_unannotated_test:
        collector.inside_unannotated_test = False
        set_active_collector(None)
        return
    if collector.active_scenario_id != NodeId(item.nodeid):
        return
    set_active_collector(None)


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo[None]) -> None:
    if collector.active_scenario_id != NodeId(item.nodeid):
        return
    if call.when == 'call' and call.excinfo is not None:
        error_repr = call.excinfo.getrepr(style='short')
        message = str(call.excinfo.value)
        diff = str(error_repr)
        collector.fail_scenario(message=message, diff=diff)


@pytest.hookimpl(trylast=True)
def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    node_id = NodeId(report.nodeid)
    if collector.active_scenario_id != node_id:
        return
    # Tests marked @pytest.mark.skip skip at setup time; in-body pytest.skip()
    # surfaces during 'call'. Both reach finish_scenario via this hook.
    setup_skip = report.when == 'setup' and report.skipped
    if report.when != 'call' and not setup_skip:
        return
    elapsed = time.monotonic() - collector.start_times.pop(node_id, time.monotonic())
    duration_ms = int(elapsed * 1000)
    status = 'passed' if report.passed else 'failed' if report.failed else 'skipped'
    skip_reason = _extract_skip_reason(report.longrepr) if status == 'skipped' else None
    collector.finish_scenario(
        status=status, duration_ms=duration_ms, skip_reason=skip_reason
    )


def pytest_sessionfinish(session: pytest.Session) -> None:
    json_path = Path(session.config.getoption('given_json'))
    scenarios = _group_parameterized(collector.scenarios, collector.param_info)
    collector.param_info.clear()
    report = ReportData(
        metadata=Metadata(
            project=session.config.rootpath.name,
            timestamp=datetime.now(tz=UTC).isoformat(),
            pytest_version=pytest.__version__,
            plugin_version='0.1.0',
        ),
        scenarios=scenarios,
    )
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(dataclasses.asdict(report), indent=2), encoding='utf-8'
    )
    if session.config.getoption('given_html'):
        from pytest_given.renderer import render_html

        html_path = Path(session.config.getoption('given_html_output'))
        render_html(json_path, html_path)


def _group_parameterized(
    scenarios: list[Scenario],
    param_info: ParamInfo,
) -> list[Scenario]:
    """Group parameterized scenarios into single scenarios with parameter tables."""
    result: list[Scenario] = []
    groups: dict[tuple[str, str], list[Scenario]] = {}
    group_order: list[tuple[str, str]] = []

    for scenario in scenarios:
        if scenario.id in param_info:
            key = (scenario.narration.text, scenario.module)
            if key not in groups:
                groups[key] = []
                group_order.append(key)
            groups[key].append(scenario)
        else:
            result.append(scenario)

    for key in group_order:
        group = groups[key]
        first = group[0]
        param_names, _ = param_info[first.id]

        template_steps = _templatize_steps(first.steps, param_names)
        merged_narration = _templatize_narration(first.narration, param_names)

        cases: list[ParameterCase] = []
        total_duration = 0
        for scenario in group:
            _, values = param_info[scenario.id]
            cases.append(
                ParameterCase(
                    values=values,
                    status=scenario.status,
                    error=scenario.error,
                )
            )
            total_duration += scenario.duration_ms

        if any(c.status == 'failed' for c in cases):
            merged_status = 'failed'
        elif all(c.status == 'skipped' for c in cases):
            merged_status = 'skipped'
        else:
            merged_status = 'passed'

        merged = Scenario(
            id=first.id,
            narration=merged_narration,
            module=first.module,
            tags=first.tags,
            status=merged_status,
            duration_ms=total_duration,
            steps=template_steps,
            parameters=ParameterTable(names=param_names, cases=cases),
        )
        result.append(merged)

    return result


def _templatize_steps(
    steps: list[Step],
    param_names: list[str],
) -> list[Step]:
    """Walk steps and templatize their narration."""
    result: list[Step] = []
    for step in steps:
        new_narration = _templatize_narration(step.narration, param_names)
        new_children = _templatize_steps(step.children, param_names)
        result.append(
            dataclasses.replace(step, narration=new_narration, children=new_children)
        )
    return result


def _templatize_narration(
    narration: Narration,
    param_names: list[str],
) -> Narration:
    """Convert matching NarrationValue entries to NarrationPlaceholder.

    NarrationLiteral parts pass through unchanged. A NarrationValue whose
    `expression` matches a parametrize column becomes a NarrationPlaceholder;
    otherwise it stays verbatim (the rendered value is shared across cases).
    A NarrationPlaceholder must reference a known parametrize column.
    """
    if not narration.parts:
        return narration
    out: list[NarrationPart] = []
    for part in narration.parts:
        match part:
            case NarrationLiteral():
                out.append(part)
            case NarrationValue(expression=expression, format_spec=fs, conversion=conv):
                if expression in param_names:
                    out.append(
                        NarrationPlaceholder(
                            name=expression,
                            format_spec=fs,
                            conversion=conv,
                        )
                    )
                else:
                    out.append(part)
            case NarrationPlaceholder(name=name):
                if name not in param_names:
                    raise PytestGivenError(
                        f"pytest_given.Template placeholder '{{{name}}}' does "
                        f'not match any parametrize column (have: '
                        f'{sorted(param_names)}).'
                    )
                out.append(part)
    return dataclasses.replace(narration, parts=out)
