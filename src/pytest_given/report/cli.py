"""The `pytest-given report` subcommand: re-render a saved JSON report."""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from ..model import PytestGivenError, report_from_dict
from .sinks import SinkConfig, emit_sinks
from .source_link import resolve_source_link_template

DEFAULT_HTML_OUTPUT = Path('given-report/report.html')


def add_report_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    report_parser = subparsers.add_parser(
        'report', help='Generate HTML report from JSON data'
    )
    report_parser.set_defaults(handler=run_report)
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

    Goes through `emit_sinks` rather than calling a renderer directly, so this
    entry point gets exactly the guarantee the plugin has: a render or write
    that fails leaves no half-written report behind, and takes the stale
    previous one with it. Input and output problems are reported as CLI errors
    rather than tracebacks.
    """
    json_file: Path = args.json_file
    if not json_file.exists():
        print(f'Error: {json_file} not found', file=sys.stderr)
        return 1
    try:
        config = _sink_config(args.output, args.source_link, args.format)
        rendered = emit_sinks(_load_report(json_file), config)
    except json.JSONDecodeError as error:
        print(f'Error: {json_file} is not valid JSON — {error}', file=sys.stderr)
        return 1
    except (PytestGivenError, OSError) as error:
        print(f'Error: {error}', file=sys.stderr)
        return 1
    if rendered.md_stdout is not None:
        print(rendered.md_stdout)
    for rendered_file in rendered.files:
        print(f'Report generated: {rendered_file.path}')
    return 0


def _load_report(json_file: Path) -> dict[str, Any]:
    """Read the input file and check that it really is a report.

    The rendering path deserializes the dict itself, so the copy built here is
    discarded — it is a shape check, not a conversion. Doing it as its own step
    keeps the check tight around serde: the same builtins raised later by a
    *renderer* stay visible as the bugs they would be, rather than being
    reported as a malformed input file.

    An `OSError` here is the caller's problem too, not a bug: `exists()` is
    true for a directory, and both the bundled assets and the Jinja templates
    are read during render.
    """
    report_dict: dict[str, Any] = json.loads(json_file.read_text(encoding='utf-8'))
    try:
        report_from_dict(report_dict)
    except (AttributeError, KeyError, TypeError) as error:
        raise PytestGivenError(
            f'{json_file} is not a pytest-given report, or was written by an '
            f'incompatible version ({type(error).__name__}: {error}).'
        ) from error
    return report_dict


def _sink_config(output: Path | None, source_link: str, fmt: str | None) -> SinkConfig:
    """The one sink this invocation writes.

    Markdown with no `-o` goes to stdout; HTML always needs a file, so it falls
    back to the default path rather than to stdout.

    `--source-link` is resolved whichever format was asked for, so a bogus
    preset is refused rather than silently ignored on a Markdown run that has
    nowhere to put the links.
    """
    source_link_template = resolve_source_link_template(source_link, '--source-link')
    if (fmt or _infer_format(output)) == 'md':
        return SinkConfig(md_path=output, md_to_stdout=output is None)
    return SinkConfig(
        html_path=output or DEFAULT_HTML_OUTPUT,
        source_link_template=source_link_template,
    )


def _infer_format(output: Path | None) -> str:
    if output is not None and output.suffix.lower() == '.md':
        return 'md'
    return 'html'
