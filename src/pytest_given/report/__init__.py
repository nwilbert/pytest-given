"""Rendering a report: the HTML, Markdown and JSON sinks, and the view models
the templates read.

Renderers only ever return text. Argv, exit codes and stderr belong to the
entry points in `cli/`, which is where the `pytest-given report` subcommand
lives — importing this package must not drag argparse in behind it.
"""

from .citation_index import (
    NO_SCENARIOS_SUMMARY,
    SUMMARY_SEPARATOR,
    Citation,
    CitationIndex,
    Target,
    report_fragment,
)
from .link_text import html_link_text, link_text
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
from .slugs import build_scenario_slug_index
from .source_link import (
    SOURCE_LINK_HELP,
    detect_commit_sha,
    resolve_source_link_template,
)
from .staged_write import write_all_or_none
from .text import CITATION_GLYPH, STATUS_GLYPH
from .theme import DEFAULT_THEME, THEME_HELP, Theme, resolve_theme

__all__ = [
    'CITATION_GLYPH',
    'DEFAULT_HTML_PATH',
    'DEFAULT_JSON_PATH',
    'DEFAULT_THEME',
    'MD_SUFFIXES',
    'NO_SCENARIOS_SUMMARY',
    'SOURCE_LINK_HELP',
    'STATUS_GLYPH',
    'SUMMARY_SEPARATOR',
    'THEME_HELP',
    'Citation',
    'CitationIndex',
    'RenderedFile',
    'RenderedSinks',
    'SinkConfig',
    'Target',
    'Theme',
    'build_scenario_slug_index',
    'detect_commit_sha',
    'emit_sinks',
    'html_link_text',
    'link_text',
    'report_fragment',
    'resolve_source_link_template',
    'resolve_theme',
    'sink_failure',
    'write_all_or_none',
]
