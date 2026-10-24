"""The `pytest-given report` subcommand: re-render a saved JSON report."""

import argparse
import sys
from pathlib import Path

from ..model import PytestGivenError, ReportUrl, read_report_json, resolve_report_url
from ..report import (
    DEFAULT_HTML_PATH,
    DEFAULT_JSON_PATH,
    DEFAULT_THEME,
    MD_SUFFIXES,
    SOURCE_LINK_HELP,
    THEME_HELP,
    SinkConfig,
    emit_sinks,
    resolve_source_link_template,
    resolve_theme,
)


def add_report_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    report_parser = subparsers.add_parser(
        'report', help='Re-render a saved JSON report as HTML or Markdown'
    )
    report_parser.set_defaults(handler=run_report)
    report_parser.add_argument(
        'json_file',
        nargs='?',
        type=Path,
        default=DEFAULT_JSON_PATH,
        help=(
            f'Path to JSON report data (default: {DEFAULT_JSON_PATH.as_posix()}, '
            'where a bare --given-json writes it)'
        ),
    )
    report_parser.add_argument(
        '-o',
        '--output',
        type=Path,
        default=None,
        help=(
            f'Output file path (default: {DEFAULT_HTML_PATH.as_posix()} for '
            'HTML, stdout for Markdown)'
        ),
    )
    report_parser.add_argument(
        '--source-link',
        default='none',
        help=SOURCE_LINK_HELP,
    )
    report_parser.add_argument(
        '--theme',
        default=DEFAULT_THEME,
        help=THEME_HELP,
    )
    report_parser.add_argument(
        '--report-url',
        default='',
        help=(
            "The report's public URL, for the citations it copies (default: "
            'the one stored in the report)'
        ),
    )
    report_parser.add_argument(
        '--no-lines',
        dest='lines',
        action='store_false',
        help=(
            'Leave the line out of each Markdown scenario anchor, like '
            '--no-given-md-lines.'
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
    try:
        config = _sink_config(
            args.output,
            args.source_link,
            args.format,
            args.theme,
            args.lines,
            resolve_report_url(args.report_url, '--report-url'),
        )
        rendered = emit_sinks(read_report_json(json_file), config, json_file.as_posix())
    except (PytestGivenError, OSError) as error:
        print(f'Error: {error}', file=sys.stderr)
        return 1
    if rendered.md_stdout is not None:
        print(rendered.md_stdout)
    for rendered_file in rendered.files:
        print(f'Report generated: {rendered_file.path}')
    return 0


def _sink_config(
    output: Path | None,
    source_link: str,
    fmt: str | None,
    theme: str,
    lines: bool,
    report_url: ReportUrl | None,
) -> SinkConfig:
    """The one sink this invocation writes.

    Markdown with no `-o` goes to stdout; HTML always needs a file, so it falls
    back to the default path rather than to stdout.

    `--source-link` and `--theme` are resolved whichever format was asked for,
    so a bogus value is refused rather than silently ignored on a Markdown run
    that has nowhere to put it. Resolved here rather than by argparse
    `choices`, so the plugin and the CLI reject a typo with the same words.
    """
    source_link_template = resolve_source_link_template(source_link, '--source-link')
    resolved_theme = resolve_theme(theme, '--theme')
    if (fmt or _infer_format(output)) == 'md':
        return SinkConfig(md_path=output, md_to_stdout=output is None, md_lines=lines)
    return SinkConfig(
        html_path=output or DEFAULT_HTML_PATH,
        source_link_template=source_link_template,
        theme=resolved_theme,
        report_url=report_url,
    )


def _infer_format(output: Path | None) -> str:
    if output is not None and output.suffix.lower() in MD_SUFFIXES:
        return 'md'
    return 'html'
