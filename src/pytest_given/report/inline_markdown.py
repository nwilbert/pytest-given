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


def render_spans(text: str) -> str:
    """A title's or step's plain-text piece: its spans as HTML, the rest
    escaped. A title or step never breaks a line."""
    return _render(text, _escaped)


def render_definition(text: str) -> str:
    """A glossary definition: its spans, and an author's `<br>` or a newline
    as a break — except in a code span, which is how to show `<br>` as text."""
    return _render(text, _with_breaks)


def _render(text: str, plain: Callable[[str], str]) -> str:
    return ''.join(_span_html(span, plain) for span in read_spans(text))


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
