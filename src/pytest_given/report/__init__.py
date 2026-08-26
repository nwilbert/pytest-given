from .cli import add_report_parser, run_report
from .html_renderer import render_html_string
from .md_renderer import render_md
from .sinks import (
    RenderedSinks,
    SinkConfig,
    discard_stale_sinks,
    render_sinks,
    write_sinks,
)
from .source_link import detect_commit_sha, resolve_template

__all__ = [
    'RenderedSinks',
    'SinkConfig',
    'add_report_parser',
    'detect_commit_sha',
    'discard_stale_sinks',
    'render_html_string',
    'render_md',
    'render_sinks',
    'resolve_template',
    'run_report',
    'write_sinks',
]
