"""Rendering a report: the HTML, Markdown and JSON sinks, and the view models
the templates read.

Renderers only ever return text. Argv, exit codes and stderr belong to the
entry points in `cli/`, which is where the `pytest-given report` subcommand
lives — importing this package must not drag argparse in behind it.
"""

from .citations import (
    CitationFinding,
    CitationsResult,
    check_citations,
    markdown_documents,
)
from .report_url import REPORT_URL_HELP, resolve_report_url
from .sinks import (
    DEFAULT_HTML_PATH,
    DEFAULT_JSON_PATH,
    MD_SUFFIXES,
    RenderedFile,
    RenderedSinks,
    SinkConfig,
    emit_sinks,
    sink_failure,
)
from .source_link import (
    SOURCE_LINK_HELP,
    detect_commit_sha,
    resolve_source_link_template,
)
from .theme import DEFAULT_THEME, THEME_HELP, Theme, resolve_theme

__all__ = [
    'DEFAULT_HTML_PATH',
    'DEFAULT_JSON_PATH',
    'DEFAULT_THEME',
    'MD_SUFFIXES',
    'REPORT_URL_HELP',
    'SOURCE_LINK_HELP',
    'THEME_HELP',
    'CitationFinding',
    'CitationsResult',
    'RenderedFile',
    'RenderedSinks',
    'SinkConfig',
    'Theme',
    'check_citations',
    'detect_commit_sha',
    'emit_sinks',
    'markdown_documents',
    'resolve_report_url',
    'resolve_source_link_template',
    'resolve_theme',
    'sink_failure',
]
