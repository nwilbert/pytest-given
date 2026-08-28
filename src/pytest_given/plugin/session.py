"""The session's two edges.

On the way in, rootdir and the capture globals; on the way out, the grouped
report, the sinks, the lint, and the terminal summary.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path

import pytest

from ..capture import (
    Collector,
    begin_capture_session,
    capture_snapshot,
    infer_glossary_kinds,
    resolve_glossary,
    restore_capture_state,
)
from ..grouping import group_parametrized
from ..lint import (
    apply_config,
    error_count,
    run_ast_rules,
    run_runtime_rules,
    summary_rows,
    summary_title,
)
from ..model import (
    Glossary,
    Metadata,
    ParamInfo,
    PytestGivenError,
    ReportData,
    Scenario,
    Story,
    report_from_dict,
    report_to_dict,
)
from ..report import (
    RenderedSinks,
    SinkConfig,
    detect_commit_sha,
    discard_stale_sinks,
    render_sinks,
    write_sinks,
)
from .state import (
    _collector,
    _collector_key,
    _given_config,
    _session_outcome,
    _session_state,
    _SessionOutcome,
    _SessionState,
    _state,
)


def pytest_load_initial_conftests(early_config: pytest.Config) -> None:
    """Publish pytest's rootdir to the capture module so `Story` and
    `GlossaryTerm` constructed at user-code import time can compute
    rootdir-relative source paths.

    Uses `pytest_load_initial_conftests` (not `pytest_configure`) so that
    rootdir is set *before* root conftest.py is imported — users commonly
    declare shared glossaries / stories at conftest module level, and that
    code runs during conftest import. The story registry is snapshotted and
    cleared here for the same reason: a nested in-process run's conftests
    import during *its* load-initial-conftests, before its sessionstart, so
    clearing at sessionstart would leave the outer session's registrations
    visible (spurious `already declared` collisions) and let the nested run's
    own registrations leak back into the outer session."""
    displaced = capture_snapshot()

    def restore_displaced_state() -> None:
        """Put back the process-global capture state this config displaced, so
        a nested in-process run (pytester, `pytest.main`) leaves the outer
        session's as it found it.

        A config cleanup rather than `pytest_unconfigure`: pytest drains the
        cleanup stack from `Config._ensure_unconfigure` whether or not the run
        ever configured, while `pytest_unconfigure` only fires for one that
        did. A nested run that dies during argument parsing — an unrecognized
        flag raises `UsageError` before `pytest_configure` — would otherwise
        strand the outer session's rootdir at the nested run's, and every step
        recorded afterwards would capture `source=None`, silently taking the
        lint's whole AST-rule surface down with it.

        Registered only once the snapshot is in hand, so a run that aborted
        before this point has nothing to restore.
        """
        restore_capture_state(displaced)

    early_config.add_cleanup(restore_displaced_state)
    begin_capture_session(Path(early_config.rootpath))


def pytest_sessionstart(session: pytest.Session) -> None:
    """Give the session its own collector."""
    collector = Collector()
    collector.capture_step_source = session.config.stash[_given_config].lint_enabled
    session.config.stash[_collector_key] = collector
    session.config.stash[_session_state] = _SessionState()


@dataclass(frozen=True, kw_only=True)
class _SessionReport:
    """A finished session's report: what the lint reads, and the sinks waiting
    to be written.

    `scenarios` is the grouped list as built, *before* the serde round-trip —
    `Step.source` is deliberately not serialized, and the AST lint rules have
    nothing to anchor to without it.
    """

    scenarios: list[Scenario]
    glossary: Glossary | None
    stories: list[Story]
    sinks: RenderedSinks


def pytest_sessionfinish(session: pytest.Session) -> None:
    """Build the report and write the configured sinks.

    Building a report fails with a `PytestGivenError` — a rejected grouping
    form, a suite reaching two glossaries, a term used in incompatible slots, an
    unusable source-link template, colliding scenario slugs — and writing one
    fails with an `OSError`: a read-only output directory, a full disk, a path
    whose parent cannot be created. An exception leaving this hook is neither a
    test failure nor an INTERNALERROR: pytest lets it out of `console_main` as a
    bare traceback, with no summary line and no exit code at all. So both run
    under one handler that reports through the terminal summary, discards the
    sinks this run would have written, and fails the run.

    Guarding only the grouping call is not enough, and neither is guarding each
    step separately: the sinks have to stay consistent *with each other*. They
    are therefore rendered in full before any of them is written, so a render
    that raises cannot leave this run's JSON beside the previous run's HTML —
    two reports that disagree, with nothing on either saying so. `write_sinks`
    is inside the same handler for that reason and not only for the traceback:
    it writes one file at a time, so a disk filling between the first and the
    second leaves exactly that pair, and only discarding both puts the run back
    to having no report rather than half of one.
    """
    collector = _collector(session.config)
    state = _state(session.config)
    try:
        built = _build_report(session, collector, state.param_info)
        write_sinks(built.sinks)
    except (PytestGivenError, OSError) as error:
        session.config.stash[_session_outcome].report_error = '\n'.join(
            [str(error), *discard_stale_sinks(_sink_config(session.config))]
        )
        session.exitstatus = pytest.ExitCode.TESTS_FAILED
        return
    finally:
        # Every way out drops the captured parametrize values: they are read
        # only here, and a nested in-process run must not inherit them.
        state.param_info.clear()
    if built.sinks.md_stdout is not None:
        session.config.stash[_session_outcome].md_stdout = built.sinks.md_stdout
    _run_lint(session, built.scenarios, built.glossary, built.stories)


def _build_report(
    session: pytest.Session, collector: Collector, param_info: ParamInfo
) -> _SessionReport:
    """Group, resolve, and render — everything that can fail, and nothing that
    touches the filesystem."""
    scenarios = group_parametrized(collector.scenarios, param_info)
    stories = collector.stories
    glossary = resolve_glossary(stories, session.config.pluginmanager.get_plugins())
    if glossary is not None:
        glossary = infer_glossary_kinds(glossary, stories)
    report = ReportData(
        metadata=Metadata(
            project=session.config.rootpath.name,
            timestamp=datetime.now(tz=UTC).isoformat(),
            pytest_version=pytest.__version__,
            plugin_version=version('pytest-given'),
            commit_sha=detect_commit_sha(),
            title=session.config.stash[_given_config].title,
        ),
        scenarios=scenarios,
        stories=stories,
        glossary=glossary,
    )
    report_dict = report_to_dict(report)
    rendered = report_from_dict(report_dict)  # serde round-trip = fidelity guarantee
    sinks = render_sinks(rendered, report_dict, _sink_config(session.config))
    return _SessionReport(
        scenarios=scenarios,
        glossary=glossary,
        stories=stories,
        sinks=sinks,
    )


def _sink_config(config: pytest.Config) -> SinkConfig:
    """This run's sink options, resolved into the pytest-free shape `report/`
    reads.

    The source-link template is the one `pytest_configure` already resolved —
    only an HTML run resolves one, and only an HTML run asks for it.
    """
    md_opt = config.getoption('given_md')
    json_opt = config.getoption('given_json')
    html_opt = config.getoption('given_html')
    return SinkConfig(
        json_path=Path(json_opt) if json_opt is not None else None,
        html_path=Path(html_opt) if html_opt is not None else None,
        md_path=Path(md_opt) if md_opt is not None and md_opt != '-' else None,
        md_to_stdout=md_opt == '-',
        source_link_template=config.stash[_given_config].source_link_template,
    )


def _run_lint(
    session: pytest.Session,
    scenarios: list[Scenario],
    glossary: Glossary | None,
    stories: list[Story],
) -> None:
    """Run the narration lint; stash the findings for the terminal summary
    and fail the run when any is error-level."""
    config = session.config
    given = config.stash[_given_config]
    if not given.lint_enabled:
        return
    findings = apply_config(
        run_runtime_rules(scenarios, glossary, stories)
        + run_ast_rules(scenarios, Path(config.rootpath)),
        given.rule_levels,
        given.ignore_entries,
    )
    if not findings:
        return
    config.stash[_session_outcome].findings = findings
    if any(finding.severity == 'error' for finding in findings):
        session.exitstatus = pytest.ExitCode.TESTS_FAILED


def pytest_terminal_summary(terminalreporter: pytest.TerminalReporter) -> None:
    outcome = terminalreporter.config.stash.get(_session_outcome, _SessionOutcome())
    report_error = outcome.report_error
    if report_error is not None:
        terminalreporter.write_sep('=', 'pytest-given: report not written', red=True)
        terminalreporter.line(report_error)
        _count_as_error(terminalreporter, 'pytest-given: report not written')
    findings = outcome.findings
    if findings:
        errors = error_count(findings)
        title = summary_title(findings)
        if errors:
            _count_as_error(terminalreporter, title)
        terminalreporter.write_sep('=', title, red=errors > 0, yellow=errors == 0)
        for row in summary_rows(findings):
            terminalreporter.line(row)
    md = outcome.md_stdout
    if md is not None:
        terminalreporter.write_line('<!-- pytest-given:md:start -->')
        for line in md.splitlines():
            terminalreporter.write_line(line)
        terminalreporter.write_line('<!-- pytest-given:md:end -->')


def _count_as_error(terminalreporter: pytest.TerminalReporter, summary: str) -> None:
    """Register a pytest-given failure with the reporter, so the summary line
    counts it and turns red.

    `pytest_sessionfinish` is where the exit code is set, and by then the
    terminal reporter has already bound the `exitstatus` it was called with —
    the summary line is built from `stats` alone. Without this, a run that
    writes no report (or fails its lint) prints `N passed` in green and exits
    non-zero, which is the one combination a CI log cannot be read through.

    A real `CollectReport` rather than a stand-in: `short_test_summary` renders
    whatever lands in `stats` under `-ra`, and a `str` longrepr is the shape it
    reads a message off.
    """
    terminalreporter.stats.setdefault('error', []).append(
        pytest.CollectReport(
            nodeid='pytest-given', outcome='failed', longrepr=summary, result=[]
        )
    )
