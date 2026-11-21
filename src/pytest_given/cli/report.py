"""The `pytest-given report` subcommand: re-render a saved JSON report."""

import argparse
import sys
from pathlib import Path

from ..model import (
    JsonObject,
    PytestGivenError,
    ReportUrl,
    read_report_json,
    report_from_dict,
    resolve_report_url,
)
from ..report import (
    DEFAULT_DIAGRAMS_PATH,
    DEFAULT_HTML_PATH,
    DEFAULT_THEME,
    MD_SUFFIXES,
    SOURCE_LINK_HELP,
    THEME_HELP,
    SinkConfig,
    emit_sinks,
    refuse_writing_over_an_input,
    require_glossary_terms,
    resolve_source_link_template,
    resolve_theme,
)
from .arguments import add_json_report_argument


def add_report_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    report_parser = subparsers.add_parser(
        'report', help='Re-render a saved JSON report as HTML or Markdown'
    )
    report_parser.set_defaults(handler=run_report)
    add_json_report_argument(report_parser)
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
        '--glossary-only',
        action='store_true',
        help=(
            'Render only the Glossary tab, leaving out scenarios and stories '
            '(HTML only).'
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
        const=DEFAULT_DIAGRAMS_PATH,
        default=None,
        help=(
            'Also write the story diagrams page (bare: '
            f'{DEFAULT_DIAGRAMS_PATH.as_posix()}). The HTML report then links '
            'each story to its diagram.'
        ),
    )


def run_report(args: argparse.Namespace) -> int:
    """Render a saved JSON report to HTML or Markdown.

    Goes through `emit_sinks` rather than calling a renderer directly, so this
    entry point gets exactly the guarantee the plugin has: a run that fails,
    reading its input included, leaves no half-written report behind, and
    takes the stale previous one with it. Input and output problems are
    reported as CLI errors rather than tracebacks.
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
            args.glossary_only,
            args.diagrams,
        )
        refuse_writing_over_an_input(
            {
                'report HTML': config.html_path,
                'report Markdown': config.md_path,
                'diagrams page': config.diagrams_path,
            },
            [json_file],
        )
        report_dict = (
            _refuse_a_report_without_glossary_terms(json_file)
            if args.glossary_only
            else None
        )
        rendered = emit_sinks(
            lambda: read_report_json(json_file) if report_dict is None else report_dict,
            config,
            json_file.as_posix(),
        )
    except (PytestGivenError, OSError) as error:
        print(f'Error: {error}', file=sys.stderr)
        return 2
    # Markdown on stdout is the payload, so the status lines keep out of it.
    status = sys.stdout
    if rendered.md_stdout is not None:
        print(rendered.md_stdout)
        status = sys.stderr
    for rendered_file in rendered.files:
        print(f'Report generated: {rendered_file.path}', file=status)
    return 0


def _refuse_a_report_without_glossary_terms(json_file: Path) -> JsonObject | None:
    """The report dict read, for `emit_sinks` to render. A refusal keeps the
    previous report, so it comes before `emit_sinks`. An unreadable input is no
    refusal: `emit_sinks` reads it again, fails and discards."""
    try:
        report_dict = read_report_json(json_file)
        report = report_from_dict(report_dict, json_file.as_posix())
    except PytestGivenError, OSError:
        return None
    require_glossary_terms(report)
    return report_dict


def _sink_config(
    output: Path | None,
    source_link: str,
    fmt: str | None,
    theme: str,
    lines: bool,
    report_url: ReportUrl | None,
    glossary_only: bool,
    diagrams: Path | None,
) -> SinkConfig:
    """The one report sink this invocation writes, and the diagrams page
    beside it when asked for.

    Markdown with no `-o` goes to stdout; HTML always needs a file, so it falls
    back to the default path rather than to stdout.

    `--source-link` and `--theme` are resolved whichever format was asked for,
    so a bogus value is refused rather than silently ignored on a Markdown run
    that has nowhere to put it. Resolved here rather than by argparse
    `choices`, so the plugin and the CLI reject a typo with the same words.
    """
    source_link_template = resolve_source_link_template(source_link, '--source-link')
    resolved_theme = resolve_theme(theme, '--theme')
    is_md = (fmt or _infer_format(output)) == 'md'
    if glossary_only and is_md:
        raise PytestGivenError('--glossary-only renders HTML only, not Markdown.')
    if glossary_only and report_url is not None:
        raise PytestGivenError(
            '--glossary-only leaves citations out, so --report-url has nothing to set.'
        )
    if is_md:
        return SinkConfig(
            md_path=output,
            md_to_stdout=output is None,
            md_lines=lines,
            diagrams_path=diagrams,
            theme=resolved_theme,
        )
    return SinkConfig(
        html_path=output or DEFAULT_HTML_PATH,
        diagrams_path=diagrams,
        source_link_template=source_link_template,
        theme=resolved_theme,
        report_url=report_url,
        html_glossary_only=glossary_only,
    )


def _infer_format(output: Path | None) -> str:
    if output is not None and output.suffix.lower() in MD_SUFFIXES:
        return 'md'
    return 'html'
