"""pytest-given plugin entry point."""

from __future__ import annotations

import dataclasses
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from pytest_given.collector import Collector, set_active_collector
from pytest_given.model import (
    Metadata,
    NodeId,
    ParameterCase,
    ParameterTable,
    ParamInfo,
    ParamSpec,
    Phase,
    ReportData,
    Scenario,
    Step,
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


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item: pytest.Item) -> None:
    scenario_marker = _get_scenario_marker(item)
    if scenario_marker is None:
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
    # Capture parametrize info if present
    callspec = getattr(item, 'callspec', None)
    if callspec is not None:
        names = list(callspec.params.keys())
        values = [callspec.params[n] for n in names]
        collector.param_info[node_id] = ParamSpec(names=names, values=values)
    # Add fixture steps
    for phase, text in _get_fixture_steps(item):
        collector.push_step(phase, text)
        collector.pop_step()
    collector.start_times[node_id] = time.monotonic()


def _get_scenario_marker(item: pytest.Item) -> Any | None:
    """Get the _scenario attribute from a test function, if present."""
    func = getattr(item, 'function', None)
    if func is None:  # pragma: no cover
        return None
    return getattr(func, '_scenario', None)


def _get_fixture_steps(item: pytest.Item) -> list[tuple[Phase, str]]:
    """Collect step descriptors from fixtures used by this item."""
    steps: list[tuple[Phase, str]] = []
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


@pytest.hookimpl(trylast=True)
def pytest_runtest_teardown(item: pytest.Item) -> None:  # pragma: no cover
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
    if report.when != 'call':
        return
    node_id = NodeId(report.nodeid)
    if collector.active_scenario_id != node_id:
        return
    elapsed = time.monotonic() - collector.start_times.pop(node_id, time.monotonic())
    duration_ms = int(elapsed * 1000)
    status = 'passed' if report.passed else 'failed' if report.failed else 'skipped'
    collector.finish_scenario(status=status, duration_ms=duration_ms)


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
        param_names, first_values = param_info[first.id]

        # Pre-sort replacements by length (longest first) to avoid
        # partial matches (e.g., replacing "1" inside "10").
        replacements = sorted(
            zip(param_names, [str(v) for v in first_values], strict=True),
            key=lambda p: len(p[1]),
            reverse=True,
        )
        template_steps = _templatize_steps(first.steps, replacements)

        cases: list[ParameterCase] = []
        any_failed = False
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

    return result


def _templatize_steps(
    steps: list[Step],
    replacements: list[tuple[str, str]],
) -> list[Step]:
    """Create template steps by replacing param values with {name} placeholders."""
    result: list[Step] = []
    for step in steps:
        new_text = _templatize_step_text(step.text, replacements)
        new_children = _templatize_steps(step.children, replacements)
        result.append(dataclasses.replace(step, text=new_text, children=new_children))
    return result


def _templatize_step_text(text: str, replacements: list[tuple[str, str]]) -> str:
    """Replace parameter values in step text with {param_name} placeholders."""
    result = text
    for name, str_value in replacements:
        # Simple text replacement — may match unrelated occurrences of the same
        # value in the step text. Longest-first ordering mitigates partial matches.
        result = result.replace(str_value, '{' + name + '}')
    return result
