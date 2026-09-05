"""The session's two edges.

On the way in, rootdir and the capture globals; on the way out, the grouped
report, the sinks, the lint, and the terminal summary.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from ..capture import (
    begin_capture_session,
    capture_snapshot,
    infer_glossary_kinds,
    resolve_glossary,
    restore_capture_state,
)
from ..grouping import group_parametrized
from ..lint import Finding, error_count, run_lint, summary_rows, summary_title
from ..model import (
    Glossary,
    Metadata,
    PytestGivenError,
    ReportData,
    Scenario,
    Story,
    report_to_dict,
)
from ..report import detect_commit_sha, emit_sinks, sink_failure
from .state import (
    given_config,
    init_session_stash,
    session_collector,
    session_outcome,
    session_state,
)


def pytest_load_initial_conftests(early_config: pytest.Config) -> None:
    """Publish pytest's rootdir to the capture module so `Story` and
    `GlossaryTerm` constructed at user-code import time can compute
    rootdir-relative source paths.

    Uses `pytest_load_initial_conftests` (not `pytest_configure`) so that
    rootdir is set *before* root conftest.py is imported — users commonly
    declare shared glossaries / stories at conftest module level. The story
    registry is snapshotted and cleared here for the same reason: a nested
    in-process run's conftests import before its sessionstart, so clearing
    there would leave the outer session's registrations visible as spurious
    `already declared` collisions."""
    displaced = capture_snapshot()

    def restore_displaced_state() -> None:
        """Put back the process-global capture state this config displaced, so
        a nested in-process run (pytester, `pytest.main`) leaves the outer
        session's as it found it.

        A config cleanup rather than `pytest_unconfigure`: the cleanup stack
        drains whether or not the run ever configured, while
        `pytest_unconfigure` only fires for one that did. A nested run that
        dies during argument parsing would otherwise strand the outer
        session's capture state at the nested run's.
        """
        restore_capture_state(displaced)

    early_config.add_cleanup(restore_displaced_state)
    begin_capture_session(Path(early_config.rootpath))


def pytest_sessionstart(session: pytest.Session) -> None:
    """Give the session its own collector and hook bookkeeping.

    Three of the stash's four values are seeded here; only `GivenConfig` has to
    be built in `pytest_configure`, because there is one such hook per plugin
    and the collector above reads `lint_enabled` out of it.
    """
    init_session_stash(session.config)


@dataclass(frozen=True, kw_only=True)
class _SessionReport:
    """A finished session's report: what the lint reads, and the serialized
    report the sinks are rendered from.

    `scenarios` is the grouped list as built, *before* the serde round-trip —
    `Step.source` is deliberately not serialized, and the AST lint rules have
    nothing to anchor to without it. `report_dict` is None on a run with no
    sink configured, which skips serializing entirely.
    """

    scenarios: list[Scenario]
    glossary: Glossary | None
    stories: list[Story]
    report_dict: dict[str, Any] | None


def pytest_sessionfinish(session: pytest.Session) -> None:
    """Build the report and write the configured sinks.

    Building a report fails with a `PytestGivenError` and writing one with an
    `OSError`. An exception leaving this hook is neither a test failure nor an
    INTERNALERROR: pytest lets it out of `console_main` as a bare traceback,
    with no summary line and no exit code at all. So both run under one handler
    that reports through the terminal summary, discards the sinks this run
    would have written, and fails the run.

    `emit_sinks` already discards on its own failure; the handler here also
    covers a report that failed to *build*, where nothing reached the sinks and
    a previous run's report would otherwise survive. Discarding twice is
    harmless — the second pass finds the files already gone.

    The lint runs outside that handler: by then the sinks are written, and the
    lint neither writes them nor owns them, so a failure in it must not delete
    a report that is on disk and correct.
    """
    config = session.config
    try:
        built = _build_report(session)
        if built.report_dict is not None:
            rendered = emit_sinks(built.report_dict, given_config(config).sinks)
            if rendered.md_stdout is not None:
                session_outcome(config).md_stdout = rendered.md_stdout
    except (PytestGivenError, OSError) as error:
        session_outcome(config).report_error = sink_failure(
            error, given_config(config).sinks
        )
        _fail_run(session)
        return
    try:
        _run_lint(session, built)
    except (PytestGivenError, OSError) as error:
        session_outcome(config).report_error = str(error)
        _fail_run(session)


def _fail_run(session: pytest.Session) -> None:
    """Fail a run pytest was otherwise about to call successful.

    Only escalates from OK: overwriting the status unconditionally would
    report an interrupted or nothing-collected run as a plain test failure.
    Reads `session.exitstatus` rather than the hook's `exitstatus` argument —
    pytest passes the same value, but a plugin ordered before us may already
    have escalated it, which leaves the argument stale and the attribute
    current.
    """
    if session.exitstatus == pytest.ExitCode.OK:
        session.exitstatus = pytest.ExitCode.TESTS_FAILED


def _build_report(session: pytest.Session) -> _SessionReport:
    """Group, resolve, and serialize — everything that can fail before a sink
    is touched.

    Grouping and the glossary passes run on every run — each refuses its own
    authoring forms. Everything after them is sink-only work, so a run with no
    sink skips it and keeps just what the lint reads.
    """
    config = session.config
    given = given_config(config)
    collector = session_collector(config)
    scenarios = group_parametrized(
        collector.scenarios, session_state(config).param_info
    )
    stories = collector.stories
    # Registered plugins include class instances; only modules can declare a
    # conftest glossary, so the filter is the caller's and `resolve_glossary`
    # keeps a precise signature.
    conftests = [
        plugin
        for plugin in config.pluginmanager.get_plugins()
        if isinstance(plugin, ModuleType)
    ]
    glossary = resolve_glossary(stories, conftests)
    if glossary is not None:
        glossary = infer_glossary_kinds(glossary, stories)
    report_dict = None
    if given.sinks.writes_anything():
        report = ReportData(
            metadata=Metadata(
                project=config.rootpath.name,
                timestamp=datetime.now(tz=UTC).isoformat(),
                pytest_version=pytest.__version__,
                plugin_version=version('pytest-given'),
                commit_sha=detect_commit_sha(),
                title=given.title,
            ),
            scenarios=scenarios,
            stories=stories,
            glossary=glossary,
        )
        report_dict = report_to_dict(report)
    return _SessionReport(
        scenarios=scenarios,
        glossary=glossary,
        stories=stories,
        report_dict=report_dict,
    )


def _run_lint(session: pytest.Session, built: _SessionReport) -> None:
    config = session.config
    given = given_config(config)
    if not given.lint_enabled:
        return
    findings = run_lint(
        built.scenarios,
        built.glossary,
        built.stories,
        Path(config.rootpath),
        given.lint,
    )
    if not findings:
        return
    session_outcome(config).findings = findings
    if error_count(findings):
        _fail_run(session)


def pytest_terminal_summary(terminalreporter: pytest.TerminalReporter) -> None:
    outcome = session_outcome(terminalreporter.config)
    _write_report_error(
        terminalreporter,
        outcome.report_error,
        wrote_sinks=given_config(terminalreporter.config).sinks.writes_anything(),
    )
    _write_lint_findings(terminalreporter, outcome.findings)
    _write_md(terminalreporter, outcome.md_stdout)


def _write_report_error(
    terminalreporter: pytest.TerminalReporter,
    report_error: str | None,
    *,
    wrote_sinks: bool,
) -> None:
    if report_error is None:
        return
    # Grouping refuses on every run, sinks or not, so a run that was never
    # going to write must not be told its report was skipped.
    title = (
        'pytest-given: report not written'
        if wrote_sinks
        else 'pytest-given: scenario refused'
    )
    terminalreporter.write_sep('=', title, red=True)
    terminalreporter.line(report_error)
    _count_as_error(terminalreporter, title)


def _write_lint_findings(
    terminalreporter: pytest.TerminalReporter, findings: list[Finding]
) -> None:
    if not findings:
        return
    errors = error_count(findings)
    title = summary_title(findings)
    if errors:
        _count_as_error(terminalreporter, title)
    terminalreporter.write_sep('=', title, red=errors > 0, yellow=errors == 0)
    for row in summary_rows(findings):
        terminalreporter.line(row)


def _write_md(terminalreporter: pytest.TerminalReporter, md: str | None) -> None:
    if md is None:
        return
    terminalreporter.write_line('<!-- pytest-given:md:start -->')
    for line in md.splitlines():
        terminalreporter.write_line(line)
    terminalreporter.write_line('<!-- pytest-given:md:end -->')


def _count_as_error(terminalreporter: pytest.TerminalReporter, summary: str) -> None:
    """Register a pytest-given failure with the reporter, so the summary line
    counts it and turns red.

    By the time session finish sets the exit code, the terminal reporter has
    already bound the `exitstatus` it was called with — the summary line is
    built from `stats` alone. Without this, a run that writes no report (or
    fails its lint) prints `N passed` in green and exits non-zero.

    A real `CollectReport` rather than a stand-in: `short_test_summary` renders
    whatever lands in `stats` under `-ra`, and a `str` longrepr is the shape it
    reads a message off.
    """
    terminalreporter.stats.setdefault('error', []).append(
        pytest.CollectReport(
            nodeid='pytest-given', outcome='failed', longrepr=summary, result=[]
        )
    )
