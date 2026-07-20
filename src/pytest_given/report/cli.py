import argparse
import json
import sys
from pathlib import Path

from ..model import report_from_dict
from .diagram import render_diagrams
from .html_renderer import diagrams_href, render_html
from .md_renderer import render_md
from .source_link import resolve_template


def add_report_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    report_parser = subparsers.add_parser(
        'report', help='Generate HTML report from JSON data'
    )
    report_parser.add_argument('json_file', type=Path, help='Path to JSON report data')
    report_parser.add_argument(
        '-o',
        '--output',
        type=Path,
        default=None,
        help='Output file path (default: given-report/report.html)',
    )
    report_parser.add_argument(
        '--source-link',
        default='none',
        help=(
            'Source-link template or preset (vscode, cursor, zed, pycharm, '
            'github, none). See README for variables.'
        ),
    )
    report_parser.add_argument(
        '--format',
        choices=['html', 'md'],
        default=None,
        help='Output format. Inferred from -o extension when omitted (default: html).',
    )
    report_parser.add_argument(
        '--diagrams',
        type=Path,
        nargs='?',
        const=Path('given-report/diagrams.html'),
        default=None,
        help=(
            'Also write the story diagrams HTML. Bare uses the default path; '
            'a value overrides.'
        ),
    )


def run_report(args: argparse.Namespace) -> int:
    if not args.json_file.exists():
        print(f'Error: {args.json_file} not found', file=sys.stderr)
        return 1
    report_dict = json.loads(args.json_file.read_text(encoding='utf-8'))
    report = report_from_dict(report_dict)
    fmt = args.format or _infer_format(args.output)
    if fmt == 'md':
        md = render_md(report)
        if args.output is None:
            print(md)
        else:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(md, encoding='utf-8')
            print(f'Report generated: {args.output}')
    else:
        template = resolve_template(args.source_link)
        output = args.output or Path('given-report/report.html')
        diagrams_href_value = None
        if args.diagrams is not None:
            diagrams_href_value = diagrams_href(output, args.diagrams)
        render_html(
            report,
            output,
            source_link_template=template,
            diagrams_href=diagrams_href_value,
        )
        print(f'Report generated: {output}')

    if args.diagrams is not None:
        render_diagrams(report, args.diagrams)
        diagrams_message = f'Diagrams generated: {args.diagrams}'
        if fmt == 'md' and args.output is None:
            print(diagrams_message, file=sys.stderr)
        else:
            print(diagrams_message)
    return 0


def _infer_format(output: Path | None) -> str:
    if output is not None and output.suffix.lower() == '.md':
        return 'md'
    return 'html'
