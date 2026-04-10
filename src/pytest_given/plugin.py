"""pytest-given plugin entry point."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from pytest_given.collector import Collector
from pytest_given.model import (
    Metadata,
    ParameterCase,
    ParameterTable,
    ReportData,
    Scenario,
    Step,
)
from pytest_given.serializer import write_json
from pytest_given.step_descriptor import set_active_collector

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


def _get_scenario_marker(item: pytest.Item) -> Any | None:
    """Get the _scenario attribute from a test function, if present."""
    func = getattr(item, 'function', None)
    if func is None:  # pragma: no cover
        return None
    return getattr(func, '_scenario', None)


def _get_fixture_steps(item: pytest.Item) -> list[tuple[str, str]]:
    """Collect step descriptors from fixtures used by this item."""
    steps: list[tuple[str, str]] = []
    if not hasattr(item, 'fixturenames'):  # pragma: no cover
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


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item: pytest.Item) -> None:
    scenario_marker = _get_scenario_marker(item)
    if scenario_marker is None:
        return
    mod = getattr(item, 'module', None)
    module = mod.__name__ if mod else item.nodeid.split('::')[0]
    collector.start_scenario(
        scenario_id=item.nodeid,
        name=scenario_marker.name,
        module=module,
        tags=scenario_marker.tags,
    )
    set_active_collector(collector)
    # Capture parametrize info if present
    callspec = getattr(item, 'callspec', None)
    if callspec is not None:
        names = list(callspec.params.keys())
        values = [callspec.params[n] for n in names]
        collector.param_info[item.nodeid] = (names, values)
    # Add fixture steps
    for phase, text in _get_fixture_steps(item):
        collector.push_step(phase, text, source='fixture')
        collector.pop_step()
    collector.start_times[item.nodeid] = time.monotonic()


@pytest.hookimpl(trylast=True)
def pytest_runtest_teardown(item: pytest.Item) -> None:  # pragma: no cover
    if collector.active_scenario_id != item.nodeid:
        return
    set_active_collector(None)


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo[None]) -> None:
    if collector.active_scenario_id != item.nodeid:
        return
    if call.when == 'call' and call.excinfo is not None:
        error_repr = call.excinfo.getrepr(style='short')
        message = str(call.excinfo.value)
        diff = str(error_repr)
        collector.fail_scenario(message=message, diff=diff)


@pytest.hookimpl(trylast=True)
def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    if report.when != 'call':
        return
    if collector.active_scenario_id != report.nodeid:
        return
    elapsed = time.monotonic() - collector.start_times.pop(
        report.nodeid, time.monotonic()
    )
    duration_ms = int(elapsed * 1000)
    status = 'passed' if report.passed else 'failed' if report.failed else 'skipped'
    collector.finish_scenario(status=status, duration_ms=duration_ms)


def _templatize_step_text(text: str, param_names: list[str], values: list[Any]) -> str:
    """Replace parameter values in step text with {param_name} placeholders.

    Replaces longer string representations first to avoid partial matches.
    """
    result = text
    # Sort by length of string representation (longest first) to avoid
    # partial replacements (e.g., replacing "1" inside "10").
    pairs = sorted(
        zip(param_names, values, strict=True),
        key=lambda p: len(str(p[1])),
        reverse=True,
    )
    for name, value in pairs:
        result = result.replace(str(value), '{' + name + '}')
    return result


def _templatize_steps(
    steps: list[Step],
    param_names: list[str],
    values: list[Any],
) -> list[Step]:
    """Create template steps by replacing param values with {name} placeholders."""
    result: list[Step] = []
    for step in steps:
        new_text = _templatize_step_text(step.text, param_names, values)
        new_children = _templatize_steps(step.children, param_names, values)
        result.append(
            Step(
                phase=step.phase,
                text=new_text,
                status=step.status,
                source=step.source,
                children=new_children,
                attachments=step.attachments,
                error=step.error,
            )
        )
    return result


def _group_parameterized(scenarios: list[Scenario]) -> list[Scenario]:
    """Group parameterized scenarios into single scenarios with parameter tables."""
    result: list[Scenario] = []
    groups: dict[tuple[str, str], list[Scenario]] = {}
    group_order: list[tuple[str, str]] = []

    for scenario in scenarios:
        if scenario.id in collector.param_info:
            key = (scenario.name, scenario.module)
            if key not in groups:
                groups[key] = []
                group_order.append(key)
            groups[key].append(scenario)
        else:
            result.append(scenario)

    for key in group_order:
        group = groups[key]
        first = group[0]
        param_names, first_values = collector.param_info[first.id]

        # Build template steps from the first run's steps,
        # replacing concrete values with {param_name} placeholders
        template_steps = _templatize_steps(first.steps, param_names, first_values)

        cases: list[ParameterCase] = []
        any_failed = False
        total_duration = 0
        for scenario in group:
            _, values = collector.param_info[scenario.id]
            cases.append(
                ParameterCase(
                    values=values,
                    status=scenario.status,
                    error=scenario.error,
                )
            )
            if scenario.status == 'failed':
                any_failed = True
            total_duration += scenario.duration_ms

        merged = Scenario(
            id=first.id,
            name=first.name,
            module=first.module,
            tags=first.tags,
            status='failed' if any_failed else 'passed',
            duration_ms=total_duration,
            steps=template_steps,
            parameters=ParameterTable(names=param_names, cases=cases),
        )
        result.append(merged)

    collector.param_info.clear()
    return result


def pytest_sessionfinish(session: pytest.Session) -> None:
    json_path = Path(session.config.getoption('given_json'))
    scenarios = _group_parameterized(collector.scenarios)
    report = ReportData(
        metadata=Metadata(
            project=session.config.rootpath.name,
            timestamp=datetime.now(tz=UTC).isoformat(),
            pytest_version=pytest.__version__,
            plugin_version='0.1.0',
        ),
        scenarios=scenarios,
    )
    write_json(report, json_path)
    if session.config.getoption('given_html'):
        from pytest_given.renderer import render_html

        html_path = Path(session.config.getoption('given_html_output'))
        render_html(json_path, html_path)
