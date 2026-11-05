"""The `pytest-given delta` subcommand: compare two JSON reports, or re-render a
delta JSON."""

# Only `pytest-given delta` builds a delta: no other command loads it. Each name
# from the shared packages resolves on first use, so parser setup reads only the
# ones it needs.
__lazy_modules__ = ['pytest_given.delta', 'pytest_given.model', 'pytest_given.report']

import argparse
import sys
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path

from ..delta import DeltaInputs, build_delta, check_reports, read_rename_log
from ..git import is_ancestor, is_shallow, resolve_revision, tags_pointing_at
from ..model import (
    Change,
    DeltaData,
    JsonObject,
    PytestGivenError,
    Side,
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
    """The config refuses an output that is an input before `emit_delta_sinks`
    discards anything."""
    rerender = args.second is None
    try:
        config = _sink_config(args, rerender)
        rendered = emit_delta_sinks(
            lambda: _rerender(args) if rerender else _compare(args), config
        )
    except (PytestGivenError, OSError) as error:
        print(f'Error: {error}', file=sys.stderr)
        return 2
    for rendered_file in rendered.files:
        print(f'Delta generated: {rendered_file.path}')
    print(_summary(rendered.delta))
    return 0


def _sink_config(args: argparse.Namespace, rerender: bool) -> DeltaSinkConfig:
    inputs: list[Path] = [args.first]
    if rerender:
        for flag, attribute in _COMPARE_ONLY_FLAGS.items():
            if getattr(args, attribute) is not None:
                raise PytestGivenError(
                    f'{flag} needs two reports to compare; one input only '
                    're-renders the HTML of a delta JSON'
                )
        json_path = None
        html_path = args.html or DEFAULT_DELTA_HTML_PATH
    else:
        inputs.append(args.second)
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


def _rerender(args: argparse.Namespace) -> tuple[JsonObject, str | None]:
    """`emit_delta_sinks` refuses a dict that is no delta."""
    path: Path = args.first
    return read_report_json(path), path.as_posix()


def _compare(args: argparse.Namespace) -> tuple[JsonObject, str | None]:
    before_path: Path = args.first
    after_path: Path = args.second
    before = report_from_dict(read_report_json(before_path), before_path.as_posix())
    after = report_from_dict(read_report_json(after_path), after_path.as_posix())
    warnings = list(
        check_reports(before, after, before_path.as_posix(), after_path.as_posix())
    )
    renames = read_rename_log(args.renames)
    repo = Path.cwd()
    before_sha, after_sha = before.metadata.commit_sha, after.metadata.commit_sha
    skipped_revs, rev_warnings = _skipped_revs(
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


def _skipped_revs(
    revs: frozenset[str], before_sha: str | None, after_sha: str | None, repo: Path
) -> tuple[frozenset[str], list[str]]:
    """The rename-log revs outside the range: an ancestor of the before commit,
    whose rename predates it, or a rev the after commit doesn't reach, whose
    rename postdates it. A rev git can't answer for applies."""
    if not revs:
        return frozenset(), []
    repo_reason = _no_repo_answer_reason(repo)
    reason = _no_ancestry_reason('before', before_sha, repo_reason, repo)
    if reason is not None:
        return frozenset(), [
            f'no ancestry answer ({reason}); rename-log entries with `rev` all apply'
        ]
    assert before_sha is not None
    skipped: set[str] = set()
    unknown: list[str] = []
    warnings: list[str] = []
    after_reason = _no_ancestry_reason('after', after_sha, repo_reason, repo)
    if after_reason is not None:
        warnings.append(
            f'no ancestry answer ({after_reason}); rename-log entries with a `rev` '
            'later than the after commit apply'
        )
    for rev in sorted(revs):
        if resolve_revision(rev, repo) is None:
            warnings.append(
                f'rename-log rev {rev!r} does not resolve; its entries apply'
            )
            continue
        predates = is_ancestor(rev, before_sha, repo)
        if predates == 'yes':
            skipped.add(rev)
            continue
        reached = 'yes'
        if after_reason is None:
            assert after_sha is not None
            reached = is_ancestor(rev, after_sha, repo)
        if reached == 'no':
            skipped.add(rev)
        elif 'unknown' in (predates, reached):
            unknown.append(rev)
    if unknown:
        warnings.append(
            f'no ancestry answer for {plural(len(unknown), "rename-log rev")}; '
            'their entries apply'
        )
    return frozenset(skipped), warnings


def _no_repo_answer_reason(repo: Path) -> str | None:
    match is_shallow(repo):
        case None:
            return 'git cannot read a repository here'
        case True:
            return 'a shallow clone'
        case False:
            return None


def _no_ancestry_reason(
    side: Side, sha: str | None, repo_reason: str | None, repo: Path
) -> str | None:
    if sha is None:
        return f'the {side} report has no commit SHA'
    if repo_reason is not None:
        return repo_reason
    if resolve_revision(sha, repo) is None:
        return f'git cannot resolve the {side} commit {sha}'
    return None


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
