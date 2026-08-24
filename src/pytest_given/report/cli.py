import argparse
import json
import sys
from pathlib import Path

from ..model import PytestGivenError, ReportData, report_from_dict
from .html_renderer import render_html
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


def run_report(args: argparse.Namespace) -> int:
    """Render a saved JSON report to HTML or Markdown.

    Input problems are reported as CLI errors rather than tracebacks.
    """
    if not args.json_file.exists():
        print(f'Error: {args.json_file} not found', file=sys.stderr)
        return 1
    try:
        return _render_report(args)
    except json.JSONDecodeError as error:
        print(f'Error: {args.json_file} is not valid JSON — {error}', file=sys.stderr)
        return 1
    except PytestGivenError as error:
        print(f'Error: {error}', file=sys.stderr)
        return 1


def _load_report(json_file: Path) -> ReportData:
    """Deserialize the input file, mapping a shape mismatch to a
    `PytestGivenError`.

    `report_from_dict` indexes whatever it is handed, so a file that parses as
    JSON but is not a pytest-given report surfaces as a builtin from deep inside
    serde. Converting here rather than widening the handler in `run_report`
    keeps the same builtins raised by a *renderer* visible as the bugs they
    would be.
    """
    report_dict = json.loads(json_file.read_text(encoding='utf-8'))
    try:
        return report_from_dict(report_dict)
    except (AttributeError, KeyError, TypeError) as error:
        raise PytestGivenError(
            f'{json_file} is not a pytest-given report, or was written by an '
            f'incompatible version ({type(error).__name__}: {error}).'
        ) from error


def _render_report(args: argparse.Namespace) -> int:
    report = _load_report(args.json_file)
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
        render_html(report, output, source_link_template=template)
        print(f'Report generated: {output}')
    return 0


def _infer_format(output: Path | None) -> str:
    if output is not None and output.suffix.lower() == '.md':
        return 'md'
    return 'html'
