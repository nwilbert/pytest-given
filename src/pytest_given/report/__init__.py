"""Rendering a report: the HTML, Markdown and JSON sinks, and the view models
the templates read.

Renderers only ever return text. Argv, exit codes and stderr belong to the
entry points in `cli/`, which is where the `pytest-given report` subcommand
lives — importing this package must not drag argparse in behind it.
"""

from .sinks import (
    DEFAULT_HTML_PATH,
    DEFAULT_JSON_PATH,
    RenderedFile,
    RenderedSinks,
    SinkConfig,
    discard_stale_sinks,
    emit_sinks,
)
from .source_link import detect_commit_sha, resolve_source_link_template

__all__ = [
    'DEFAULT_HTML_PATH',
    'DEFAULT_JSON_PATH',
    'RenderedFile',
    'RenderedSinks',
    'SinkConfig',
    'detect_commit_sha',
    'discard_stale_sinks',
    'emit_sinks',
    'resolve_source_link_template',
]
