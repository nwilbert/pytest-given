"""The reader's inline Markdown spans as safe HTML: in scenario titles and step
text, and in glossary definitions, which also break lines. Rendering is a
report concern, so this lives in `report/` and never imports from `capture/`."""

# A run that renders no HTML never loads MarkupSafe.
__lazy_modules__ = ['markupsafe']

from collections.abc import Callable

from markupsafe import escape

from ..markdown import (
    DEFINITION_BREAK,
    CodeSpan,
    EmphasisSpan,
    InlineSpan,
    PlainSpan,
    read_spans,
)


def render_span(span: InlineSpan) -> str:
    """A span of a title or step, which never breaks a line."""
    return _span_html(span, _escaped)


type RefRenderer = Callable[[InlineSpan], str | None]


def render_definition(text: str, *, render_ref: RefRenderer | None = None) -> str:
    """A glossary definition: its spans, and an author's `<br>` or a newline
    as a break — except in a code span, which is how to show `<br>` as text.

    `render_ref` returns the HTML a span renders as instead, or None."""
    return ''.join(_definition_span_html(span, render_ref) for span in read_spans(text))


def _definition_span_html(span: InlineSpan, render_ref: RefRenderer | None) -> str:
    ref = render_ref(span) if render_ref is not None else None
    return ref if ref is not None else _span_html(span, _with_breaks)


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
    return '<br>'.join(_escaped(line) for line in DEFINITION_BREAK.split(text))
