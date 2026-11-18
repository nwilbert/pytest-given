"""The `pytest-given delta` subcommand: compare two JSON reports, or re-render a
delta JSON."""

# Each name from the shared packages resolves on first use, so parser setup and
# the other commands load none of the delta code.
__lazy_modules__ = ['pytest_given.delta', 'pytest_given.model', 'pytest_given.report']

import argparse
import sys
from pathlib import Path

from ..delta import Change, DeltaData, change_counts, compare_reports, delta_to_dict
from ..model import JsonObject, PytestGivenError, plural, read_report_json
from ..report import (
    DEFAULT_DELTA_HTML_PATH,
    DEFAULT_DELTA_JSON_PATH,
    DEFAULT_THEME,
    SOURCE_LINK_HELP,
    THEME_HELP,
    DeltaSinkConfig,
    emit_delta_sinks,
    refuse_writing_over_an_input,
    resolve_source_link_template,
    resolve_theme,
)


def add_delta_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    delta_parser = subparsers.add_parser(
        'delta',
        help=(
            'Compare two JSON reports as a delta report, or re-render the HTML '
            'of a delta JSON'
        ),
    )
    delta_parser.set_defaults(handler=run_delta)
    delta_parser.add_argument(
        'first',
        type=Path,
        metavar='INPUT',
        help='The before report, or a delta JSON to re-render',
    )
    delta_parser.add_argument(
        'second',
        type=Path,
        nargs='?',
        default=None,
        metavar='INPUT',
        help='The after report',
    )
    delta_parser.add_argument(
        '--json',
        type=Path,
        default=None,
        help=(
            f'Delta JSON path (default: {DEFAULT_DELTA_JSON_PATH.as_posix()} '
            'when neither --json nor --html is given)'
        ),
    )
    delta_parser.add_argument(
        '--html',
        type=Path,
        default=None,
        help=(
            f'Delta HTML path (default: {DEFAULT_DELTA_HTML_PATH.as_posix()} '
            'when neither --json nor --html is given)'
        ),
    )
    delta_parser.add_argument(
        '--renames',
        type=Path,
        default=None,
        help='Rename log (default: given-renames.toml, when it exists)',
    )
    delta_parser.add_argument('--source-link', default='none', help=SOURCE_LINK_HELP)
    delta_parser.add_argument('--theme', default=DEFAULT_THEME, help=THEME_HELP)
    delta_parser.add_argument(
        '--before-label',
        default=None,
        help='Version label of the before side (default: the tag on its commit)',
    )
    delta_parser.add_argument(
        '--after-label',
        default=None,
        help='Version label of the after side (default: the tag on its commit)',
    )
    delta_parser.add_argument(
        '--title',
        default=None,
        help="The delta's title (default: the after report's title)",
    )


# What only a comparison uses, as `--flag`: Namespace attribute.
_COMPARE_ONLY_FLAGS = {
    '--json': 'json',
    '--renames': 'renames',
    '--before-label': 'before_label',
    '--after-label': 'after_label',
    '--title': 'title',
}


def run_delta(args: argparse.Namespace) -> int:
    """Inputs are read inside `emit_delta_sinks`, so one that can't be read
    takes the previous delta with it, as `pytest-given report` does; the
    config refuses an output that is an input before anything is discarded."""
    paths: list[Path] = (
        [args.first] if args.second is None else [args.first, args.second]
    )
    try:
        config = _sink_config(args, paths)
        rendered = emit_delta_sinks(
            lambda: (
                (read_report_json(args.first), args.first.as_posix())
                if args.second is None
                else _compare(
                    args, read_report_json(args.first), read_report_json(args.second)
                )
            ),
            config,
        )
    except (PytestGivenError, OSError) as error:
        print(f'Error: {error}', file=sys.stderr)
        return 2
    for rendered_file in rendered.files:
        print(f'Delta generated: {rendered_file.path}')
    print(_summary(rendered.delta))
    return 0


def _sink_config(args: argparse.Namespace, inputs: list[Path]) -> DeltaSinkConfig:
    if len(inputs) == 1:
        for flag, attribute in _COMPARE_ONLY_FLAGS.items():
            if getattr(args, attribute) is not None:
                raise PytestGivenError(
                    f'{flag} needs two reports to compare; one input only '
                    're-renders the HTML of a delta JSON'
                )
        json_path = None
        html_path = args.html or DEFAULT_DELTA_HTML_PATH
    else:
        both_default = args.json is None and args.html is None
        json_path = DEFAULT_DELTA_JSON_PATH if both_default else args.json
        html_path = DEFAULT_DELTA_HTML_PATH if both_default else args.html
    config = DeltaSinkConfig(
        json_path=json_path,
        html_path=html_path,
        source_link_template=resolve_source_link_template(
            args.source_link, '--source-link'
        ),
        theme=resolve_theme(args.theme, '--theme'),
    )
    refuse_writing_over_an_input(
        {'delta JSON': config.json_path, 'delta HTML': config.html_path}, inputs
    )
    return config


def _compare(
    args: argparse.Namespace, before_dict: JsonObject, after_dict: JsonObject
) -> tuple[JsonObject, str | None]:
    result = compare_reports(
        before_dict,
        after_dict,
        before_source=args.first.as_posix(),
        after_source=args.second.as_posix(),
        before_label=args.before_label,
        after_label=args.after_label,
        title=args.title or None,
        rename_log=args.renames,
        repo=Path.cwd(),
    )
    for warning in result.warnings:
        print(f'Warning: {warning}', file=sys.stderr)
    return delta_to_dict(result.delta), None


def _summary(delta: DeltaData) -> str:
    """`delta: 1 added, 2 changed, 1 removed scenarios; 3 unchanged`, with a
    terms clause and the suggested matches when there are any."""
    changes = [scenario.change for scenario in delta.scenarios]
    clauses = [
        f'{_counts(changes)} scenarios',
        f'{len(delta.unchanged)} unchanged',
    ]
    term_changes = [term.change for term in delta.glossary.terms]
    if term_changes:
        clauses.append(f'{_counts(term_changes)} terms')
    if delta.suggestions:
        clauses.append(plural(len(delta.suggestions), 'suggested match'))
    return 'delta: ' + '; '.join(clauses)


def _counts(changes: list[Change]) -> str:
    return ', '.join(
        f'{count} {change}' for change, count in change_counts(changes).items()
    )
