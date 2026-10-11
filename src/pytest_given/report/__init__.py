"""Rendering a report: the HTML, Markdown and JSON sinks, and the view models
the templates read.

Renderers only ever return text. Argv, exit codes and stderr belong to the
entry points in `cli/`, which is where the `pytest-given report` subcommand
lives — importing this package must not drag argparse in behind it.
"""

from .citation_index import CitationIndex, Target, parse_fragment, report_fragment
from .link_text import fold_whitespace, link_text, plain_link_text
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
from .text import CITATION_GLYPH, CITATION_GLYPH_PLACEHOLDERS
from .theme import DEFAULT_THEME, THEME_HELP, Theme, resolve_theme

__all__ = [
    'CITATION_GLYPH',
    'CITATION_GLYPH_PLACEHOLDERS',
    'DEFAULT_HTML_PATH',
    'DEFAULT_JSON_PATH',
    'DEFAULT_THEME',
    'MD_SUFFIXES',
    'SOURCE_LINK_HELP',
    'THEME_HELP',
    'CitationIndex',
    'RenderedFile',
    'RenderedSinks',
    'SinkConfig',
    'Target',
    'Theme',
    'detect_commit_sha',
    'emit_sinks',
    'fold_whitespace',
    'link_text',
    'parse_fragment',
    'plain_link_text',
    'report_fragment',
    'resolve_source_link_template',
    'resolve_theme',
    'sink_failure',
]
