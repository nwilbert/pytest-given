"""The plugin's options: declaration, and the one place they are resolved.

`pytest_configure` parses every option into a single `_GivenConfig` before the
suite runs, so a typo in a rule name or a source-link preset is a `UsageError`
up front rather than a surprise after the last test.
"""

from typing import cast

import pytest

from ..lint import (
    parse_ignore_entries,
    parse_rule_levels,
)
from ..model import (
    PytestGivenError,
)
from ..report import (
    resolve_template,
)
from .state import _given_config, _GivenConfig, _session_outcome, _SessionOutcome

_LINT_CHOICES = ('true', 'false')


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup('given', 'pytest-given report generation')
    group.addoption(
        '--given-json',
        nargs='?',
        const='given-report/report-data.json',
        default=None,
        help=(
            'Write JSON report data. Bare uses the default path; =PATH '
            'overrides. Off when absent.'
        ),
    )
    group.addoption(
        '--given-html',
        nargs='?',
        const='given-report/report.html',
        default=None,
        help=(
            'Write the HTML report. Bare uses the default path; =PATH '
            'overrides. Off when absent.'
        ),
    )
    group.addoption(
        '--given-md',
        nargs='?',
        const='-',
        default=None,
        help=(
            'Write the Markdown report. Bare renders to stdout (fenced); '
            '=PATH writes a file. Off when absent.'
        ),
    )
    group.addoption(
        '--given-all-frames',
        action='store_true',
        default=False,
        help=(
            'Store internal pluggy/_pytest/pytest-given frames in the JSON '
            'report. Slower on large failing suites — only set when debugging '
            'the plugin or pytest itself.'
        ),
    )
    group.addoption(
        '--given-source-link',
        default=None,
        help=(
            'Source-link template or preset (vscode, cursor, zed, pycharm, '
            'github, none). See README for available variables.'
        ),
    )
    group.addoption(
        '--given-title',
        default=None,
        help=(
            'Name the report. Defaults to the rootdir name. Overrides the '
            'given_title ini for one run.'
        ),
    )
    group.addoption(
        '--given-lint',
        default=None,
        choices=_LINT_CHOICES,
        help=(
            'Run the narration lint: true | false. Overrides the given_lint '
            'ini for one run.'
        ),
    )
    parser.addini(
        'given_source_link',
        type='string',
        default='none',
        help='Source-link template or preset name (CLI flag overrides this).',
    )
    parser.addini(
        'given_title',
        type='string',
        default='',
        help='Name the report (CLI flag overrides this).',
    )
    parser.addini(
        'given_lint',
        type='bool',
        default=False,
        help='Run the narration lint (CLI flag overrides this).',
    )
    parser.addini(
        'given_lint_rules',
        type='linelist',
        default=[],
        help='Per-rule severity overrides: rule-id=level (off | warn | error).',
    )
    parser.addini(
        'given_lint_ignore',
        type='linelist',
        default=[],
        help=(
            'Subject globs exempt from lint findings, optionally rule-scoped '
            "with a 'rule-id:' prefix. Entries that suppress nothing fail the "
            'run.'
        ),
    )


def _resolve_title(config: pytest.Config) -> str | None:
    """The report title: CLI flag (when given) wins over the ini value.

    None when neither is set, which leaves renderers on the rootdir name.
    """
    cli = config.getoption('given_title')
    if cli is not None:
        return cast('str', cli)
    return cast('str', config.getini('given_title')) or None


def _resolve_lint_enabled(config: pytest.Config) -> bool:
    """The lint switch: CLI flag (when given) wins over the ini value."""
    cli = config.getoption('given_lint')
    if cli is not None:
        return cast('str', cli) == 'true'
    return bool(config.getini('given_lint'))


def _resolve_source_link(config: pytest.Config) -> str:
    """The source-link template: CLI flag (when given) wins over the ini value.

    Tested with `is not None` like the other two rather than for truthiness, so
    an explicit `--given-source-link=` means what it says — no links — instead
    of falling through to whatever the ini declares.
    """
    cli = config.getoption('given_source_link')
    if cli is not None:
        return cast('str', cli)
    return cast('str', config.getini('given_source_link'))


def pytest_configure(config: pytest.Config) -> None:
    # Parsed eagerly (fail fast), even when the lint itself is disabled for
    # this run, so session finish reuses the parse.
    try:
        rule_levels = parse_rule_levels(config.getini('given_lint_rules'))
        ignore_entries = parse_ignore_entries(config.getini('given_lint_ignore'))
    except ValueError as error:
        raise pytest.UsageError(str(error)) from error
    # Same reason, for the source-link config: an unknown preset is a typo in a
    # flag, and learning about it only once the suite has finished is the worst
    # moment to learn it. Only an HTML run resolves one — `github` would
    # otherwise run its org/repo detection for a run that never asks.
    source_link_template = None
    if config.getoption('given_html') is not None:
        try:
            source_link_template = resolve_template(_resolve_source_link(config))
        except PytestGivenError as error:
            raise pytest.UsageError(str(error)) from error
    config.stash[_given_config] = _GivenConfig(
        rule_levels=rule_levels,
        ignore_entries=ignore_entries,
        source_link_template=source_link_template,
        title=_resolve_title(config),
        lint_enabled=_resolve_lint_enabled(config),
    )
    config.stash[_session_outcome] = _SessionOutcome()
