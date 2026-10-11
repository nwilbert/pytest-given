"""The `pytest-given citations` subcommand: `check` reports every finding and
writes nothing; `update` rewrites what it can and reports what remains. The
verb, not a flag, says whether a command line writes files."""

import argparse
import sys
from pathlib import Path

from ..citations import CitationsResult, check_citations, markdown_documents
from ..model import PytestGivenError, plural, report_from_dict, resolve_report_url
from .report import load_report_json


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
        verb_parser.set_defaults(handler=run_citations, update=verb == 'update')
        verb_parser.add_argument(
            'documents',
            nargs='+',
            type=Path,
            help='Markdown files, and directories searched recursively for *.md',
        )
        verb_parser.add_argument(
            '--report',
            type=Path,
            required=True,
            help='The JSON report of a run of every scenario',
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


def run_citations(args: argparse.Namespace) -> int:
    report_file: Path = args.report
    try:
        result = check_citations(
            report_from_dict(load_report_json(report_file), report_file.as_posix()),
            markdown_documents(args.documents),
            report_url=resolve_report_url(args.report_url, '--report-url'),
            report_path=args.report_path,
            update=args.update,
        )
    except (PytestGivenError, OSError) as error:
        print(f'Error: {error}', file=sys.stderr)
        return 2
    return _report_update(result) if args.update else _report_check(result)


def _report_check(result: CitationsResult) -> int:
    for finding in result.findings:
        print('\n'.join(finding.lines()))
    if not result.findings:
        print('citations: every report link is current')
        return 0
    fixable = len(result.findings) - len(result.remaining)
    print(
        f'citations: {plural(len(result.findings), "finding")}; '
        f'`citations update` fixes {fixable}'
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
