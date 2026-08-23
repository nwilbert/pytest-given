from .cli import add_report_parser, run_report
from .html_renderer import render_html, render_html_string
from .md_renderer import render_md
from .source_link import detect_commit_sha, resolve_template

__all__ = [
    'add_report_parser',
    'detect_commit_sha',
    'render_html',
    'render_html_string',
    'render_md',
    'resolve_template',
    'run_report',
]
