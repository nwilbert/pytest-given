"""pytest-given plugin entry point."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from pytest_given.collector import Collector
from pytest_given.model import ErrorInfo, Metadata, ReportData
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


def pytest_sessionstart(session: pytest.Session) -> None:  # noqa: ARG001
    """Reset the collector at the start of each session."""
    global collector
    collector = Collector()


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


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo[None]) -> None:  # type: ignore[type-arg]
    if collector.active_scenario_id != item.nodeid:
        return
    if call.when == 'call' and call.excinfo is not None:
        error_repr = call.excinfo.getrepr(style='short')
        message = str(call.excinfo.value)
        diff = str(error_repr)

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
