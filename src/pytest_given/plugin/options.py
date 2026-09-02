"""The plugin's options: declaration, and the one place they are resolved.

`pytest_configure` parses every option into a single `GivenConfig` before the
suite runs, so a typo in a rule name or a source-link preset is a `UsageError`
up front rather than a surprise after the last test.
"""

from pathlib import Path
from typing import cast

import pytest

from ..lint import parse_lint_config
from ..model import PytestGivenError
from ..report import SinkConfig, resolve_template
from .state import GivenConfig, SessionOutcome, given_config_key, session_outcome_key

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


def _cli_over_ini(config: pytest.Config, name: str) -> str | bool:
    """The precedence rule for every option carrying both a flag and an ini,
    stated once: the flag when it was given at all, otherwise the ini.

    Presence is `is not None`, never truthiness: the flags all default to None,
    so an explicitly empty one still wins over the ini — `--given-source-link=`
    disables links rather than falling through. Each option's argparse `dest`
    is its ini name, so one lookup name serves both. The ini value comes back
    as pytest typed it, so each caller converts its own.
    """
    cli = config.getoption(name)
    if cli is not None:
        return cast('str', cli)
    return cast('str | bool', config.getini(name))


def _resolve_title(config: pytest.Config) -> str | None:
    """The report title, or None when it is empty from whichever source won.

    None leaves the renderers on the rootdir name, which is what an empty title
    would display anyway — so the two spellings of "no title" resolve alike
    rather than reaching `metadata.title` as `null` from one and `""` from the
    other. Coalescing here rather than in `_cli_over_ini` keeps it this
    option's own rule: `--given-source-link=` means the opposite.
    """
    return cast('str', _cli_over_ini(config, 'given_title')) or None


def _resolve_lint_enabled(config: pytest.Config) -> bool:
    """The lint switch. The flag spells it `'true'` / `'false'`; the ini is
    already a bool."""
    value = _cli_over_ini(config, 'given_lint')
    return value == 'true' if isinstance(value, str) else bool(value)


def _resolve_source_link(config: pytest.Config) -> str:
    """The source-link template or preset name."""
    return cast('str', _cli_over_ini(config, 'given_source_link'))


def _resolve_sinks(
    config: pytest.Config, source_link_template: str | None
) -> SinkConfig:
    """The three sink flags, resolved into the pytest-free shape `report/`
    reads. CLI-only, so there is no ini precedence to settle here."""
    md_opt = config.getoption('given_md')
    json_opt = config.getoption('given_json')
    html_opt = config.getoption('given_html')
    return SinkConfig(
        json_path=Path(json_opt) if json_opt is not None else None,
        html_path=Path(html_opt) if html_opt is not None else None,
        md_path=Path(md_opt) if md_opt is not None and md_opt != '-' else None,
        md_to_stdout=md_opt == '-',
        source_link_template=source_link_template,
    )


def pytest_configure(config: pytest.Config) -> None:
    # Everything is parsed eagerly (fail fast), even when the lint itself is
    # disabled for this run: a typo in a rule name or a source-link preset is a
    # UsageError up front rather than a surprise after the last test. Only an
    # HTML run resolves a source link — `github` would otherwise run its
    # org/repo detection for a run that never asks.
    try:
        lint = parse_lint_config(
            config.getini('given_lint_rules'), config.getini('given_lint_ignore')
        )
        source_link_template = (
            resolve_template(_resolve_source_link(config))
            if config.getoption('given_html') is not None
            else None
        )
    except PytestGivenError as error:
        raise pytest.UsageError(str(error)) from error
    config.stash[given_config_key] = GivenConfig(
        lint=lint,
        lint_enabled=_resolve_lint_enabled(config),
        sinks=_resolve_sinks(config, source_link_template),
        title=_resolve_title(config),
    )
    config.stash[session_outcome_key] = SessionOutcome()
