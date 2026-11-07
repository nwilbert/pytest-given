"""The `pytest-given delta` subcommand: compare two JSON reports, or re-render a
delta JSON."""

# Each name from the shared packages resolves on first use, so parser setup and
# the other commands load none of the delta code.
__lazy_modules__ = ['pytest_given.delta', 'pytest_given.model', 'pytest_given.report']

import argparse
import sys
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path

from ..delta import (
    DeltaInputs,
    build_delta,
    check_schema_versions,
    read_rename_log,
    revs_outside_range,
    version_warnings,
)
from ..git import tags_pointing_at
from ..model import (
    Change,
    DeltaData,
    JsonObject,
    PytestGivenError,
    change_counts,
    delta_to_dict,
    plural,
    read_report_json,
    report_from_dict,
)
from ..report import (
    DEFAULT_DELTA_HTML_PATH,
    DEFAULT_DELTA_JSON_PATH,
    DEFAULT_THEME,
    SOURCE_LINK_HELP,
    THEME_HELP,
    DeltaSinkConfig,
    emit_delta_sinks,
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
    _refuse_overwriting_an_input(config, inputs)
    return config


def _refuse_overwriting_an_input(config: DeltaSinkConfig, inputs: list[Path]) -> None:
    """A failed delta discards its outputs, so an output that is an input
    would delete it."""
    for sink, output in (('JSON', config.json_path), ('HTML', config.html_path)):
        if output is None:
            continue
        for input_path in inputs:
            if output.resolve() == input_path.resolve():
                raise PytestGivenError(
                    f'the delta {sink} {output.as_posix()} is the input '
                    f'{input_path.as_posix()}; write it elsewhere'
                )


def _compare(
    args: argparse.Namespace, before_dict: JsonObject, after_dict: JsonObject
) -> tuple[JsonObject, str | None]:
    before_source, after_source = args.first.as_posix(), args.second.as_posix()
    check_schema_versions(before_dict, after_dict, before_source, after_source)
    before = report_from_dict(before_dict, before_source)
    after = report_from_dict(after_dict, after_source)
    warnings = list(version_warnings(before, after, before_source, after_source))
    renames = read_rename_log(args.renames)
    repo = Path.cwd()
    before_sha, after_sha = before.metadata.commit_sha, after.metadata.commit_sha
    skipped_revs, rev_warnings = revs_outside_range(
        renames.revs(), before_sha, after_sha, repo
    )
    result = build_delta(
        DeltaInputs(
            before=before,
            after=after,
            renames=renames,
            skipped_revs=skipped_revs,
            before_label=args.before_label or _tag_label(before_sha, repo),
            after_label=args.after_label or _tag_label(after_sha, repo),
            title=args.title or None,
            plugin_version=version('pytest-given'),
            timestamp=datetime.now(tz=UTC).isoformat(),
        )
    )
    for warning in [*warnings, *rev_warnings, *result.warnings]:
        print(f'Warning: {warning}', file=sys.stderr)
    return delta_to_dict(result.delta), None


def _tag_label(sha: str | None, repo: Path) -> str | None:
    if sha is None:
        return None
    tags = tags_pointing_at(sha, repo)
    return tags[0] if tags else None


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
