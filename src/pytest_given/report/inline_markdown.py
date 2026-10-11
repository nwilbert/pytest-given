"""The reader's inline Markdown spans as safe HTML: in scenario titles and step
text, and in glossary definitions, which also break lines. Rendering is a
report concern, so this lives in `report/` and never imports from `capture/`."""

import re
from collections.abc import Callable

from markupsafe import escape

from ..model import CodeSpan, EmphasisSpan, InlineSpan, PlainSpan, read_spans
from .text import NEWLINE

# Re-admit an author's escaped <br> / <br/> / <br /> (any case) as a real break.
_BR = re.compile(r'&lt;br\s*/?\s*&gt;', re.IGNORECASE)


def render_span(span: InlineSpan) -> str:
    """A span of a title or step, which never breaks a line."""
    return _span_html(span, _escaped)


def render_definition(text: str) -> str:
    """A glossary definition: its spans, and an author's `<br>` or a newline
    as a break — except in a code span, which is how to show `<br>` as text."""
    return ''.join(_span_html(span, _with_breaks) for span in read_spans(text))


def _span_html(span: InlineSpan, plain: Callable[[str], str]) -> str:
    match span:
        case PlainSpan(text=text):
            return plain(text)
        case CodeSpan(text=text):
            return f'<code>{escape(text)}</code>'
        case EmphasisSpan(strong=strong, content=content):
            tag = 'strong' if strong else 'em'
            inner = ''.join(_span_html(part, plain) for part in content)
            return f'<{tag}>{inner}</{tag}>'


def _escaped(text: str) -> str:
    return str(escape(text))


def _with_breaks(text: str) -> str:
    return NEWLINE.sub('<br>', _BR.sub('<br>', _escaped(text)))
