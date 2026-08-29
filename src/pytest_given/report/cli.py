import argparse
import json
import sys
from pathlib import Path
from typing import Any

from ..model import PytestGivenError, ReportData, report_from_dict
from .sinks import SinkConfig, render_sinks, write_sinks
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


def _load_report(json_file: Path) -> tuple[ReportData, dict[str, Any]]:
    """Deserialize the input file, mapping a shape mismatch to a
    `PytestGivenError`.

    Returns the model *and* the dict it was built from, because the file is
    already the serialized report: re-deriving it with `report_to_dict` would
    hand the JSON sink a round-tripped copy rather than what was read.

    `report_from_dict` indexes whatever it is handed, so a file that parses as
    JSON but is not a pytest-given report surfaces as a builtin from deep inside
    serde. Converting here rather than widening the handler in `run_report`
    keeps the same builtins raised by a *renderer* visible as the bugs they
    would be.
    """
    report_dict = json.loads(json_file.read_text(encoding='utf-8'))
    try:
        return report_from_dict(report_dict), report_dict
    except (AttributeError, KeyError, TypeError) as error:
        raise PytestGivenError(
            f'{json_file} is not a pytest-given report, or was written by an '
            f'incompatible version ({type(error).__name__}: {error}).'
        ) from error


def _render_report(args: argparse.Namespace) -> int:
    """Render the requested sink through the same render-then-write path the
    plugin uses.

    Going through `SinkConfig` rather than calling a renderer and writing the
    result here is what keeps the two entry points honest with each other: a
    render that raises leaves no half-written file, and the rules about which
    sink a flag selects live in one place. Only one sink is ever configured —
    this command renders one format per invocation.
    """
    report, report_dict = _load_report(args.json_file)
    rendered = render_sinks(report, report_dict, _sink_config(args))
    write_sinks(rendered)
    if rendered.md_stdout is not None:
        print(rendered.md_stdout)
    for path, _text in rendered.files:
        print(f'Report generated: {path}')
    return 0


def _sink_config(args: argparse.Namespace) -> SinkConfig:
    """The one sink this invocation writes.

    Markdown with no `-o` goes to stdout; HTML always needs a file, so it falls
    back to the default path rather than to stdout.
    """
    if (args.format or _infer_format(args.output)) == 'md':
        return SinkConfig(md_path=args.output, md_to_stdout=args.output is None)
    return SinkConfig(
        html_path=args.output or Path('given-report/report.html'),
        source_link_template=resolve_template(args.source_link),
    )


def _infer_format(output: Path | None) -> str:
    if output is not None and output.suffix.lower() == '.md':
        return 'md'
    return 'html'
