"""The `pytest-given citations` subcommand: `check` reports every finding and
writes nothing; `update` rewrites what it can and reports what remains. The
verb, not a flag, says whether a command line writes files."""

import argparse
import sys
from pathlib import Path

from ..citations import CitationsResult, check_citations, markdown_documents
from ..model import (
    PytestGivenError,
    plural,
    read_report_json,
    report_from_dict,
    resolve_report_url,
)
from ..report import DEFAULT_JSON_PATH


def add_citations_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    citations_parser = subparsers.add_parser(
        'citations', help='Check or update the report links in Markdown documents'
    )
    verbs = citations_parser.add_subparsers(required=True)
    for verb, help_text in (
        ('check', 'Report every finding and write nothing'),
        ('update', 'Rewrite stale citations, then report what remains'),
    ):
        verb_parser = verbs.add_parser(verb, help=help_text)
        verb_parser.set_defaults(
            handler=run_citations,
            update=verb == 'update',
            list_links=False,
            covering=None,
        )
        verb_parser.add_argument(
            'documents',
            nargs='+',
            type=Path,
            help='Markdown files, and directories searched recursively for *.md',
        )
        verb_parser.add_argument(
            '--report',
            type=Path,
            default=DEFAULT_JSON_PATH,
            help=(
                'The JSON report of a run of every scenario (default: '
                f'{DEFAULT_JSON_PATH.as_posix()}, where a bare --given-json writes it)'
            ),
        )
        verb_parser.add_argument(
            '--report-url',
            default='',
            help="The report's public URL (default: the one stored in the report)",
        )
        verb_parser.add_argument(
            '--report-path',
            type=Path,
            default=None,
            help=(
                'Where the HTML report sits once the docs build has placed it, '
                'so relative links to it are read too'
            ),
        )
        if verb == 'check':
            _add_listing_options(verb_parser)


def _add_listing_options(check_parser: argparse.ArgumentParser) -> None:
    check_parser.add_argument(
        '--list',
        dest='list_links',
        action='store_true',
        help='Print every report link, each with its findings under it',
    )
    check_parser.add_argument(
        '--covering',
        action='append',
        metavar='NODE_ID',
        help=(
            'List only the links that may cite this scenario (implies --list); '
            'repeatable'
        ),
    )


def run_citations(args: argparse.Namespace) -> int:
    report_file: Path = args.report
    covering: list[str] = args.covering or []
    try:
        result = check_citations(
            report_from_dict(read_report_json(report_file), report_file.as_posix()),
            markdown_documents(args.documents),
            report_url=resolve_report_url(args.report_url, '--report-url'),
            report_path=args.report_path,
            update=args.update,
            covering=covering,
        )
    except (PytestGivenError, OSError) as error:
        print(f'Error: {error}', file=sys.stderr)
        return 2
    if args.update:
        return _report_update(result)
    return _report_check(result, listed=args.list_links or bool(covering))


def _report_check(result: CitationsResult, *, listed: bool) -> int:
    """The summary and exit code are the same listed or not: a finding on a
    link `--covering` leaves out still counts."""
    if listed:
        for link in result.listed:
            print('\n'.join(link.lines()))
    else:
        for finding in result.findings:
            print('\n'.join(finding.lines()))
    if not result.findings:
        print('citations: every report link is current')
        return 0
    fixable = len(result.findings) - len(result.remaining)
    print(
        f'citations: {plural(len(result.findings), "finding")}'
        + (
            f', {result.left_out} of them left out by --covering'
            if result.left_out
            else ''
        )
        + f'; `citations update` fixes {fixable}'
    )
    return 1


def _report_update(result: CitationsResult) -> int:
    for finding in result.remaining:
        print('\n'.join(finding.lines()))
    summary = f'citations: updated {plural(len(result.updated), "document")}'
    if result.remaining:
        print(f'{summary}; {plural(len(result.remaining), "finding")} remain')
        return 1
    print(summary)
    return 0
