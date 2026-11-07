"""The inline subset's spans as safe HTML: in scenario titles and step text,
and in glossary definitions, which also break lines."""

# A run that renders no HTML never loads MarkupSafe.
__lazy_modules__ = ['markupsafe']

from collections.abc import Callable

from markupsafe import escape

from .plain_text import DEFINITION_BREAK
from .spans import CodeSpan, EmphasisSpan, InlineSpan, PlainSpan, read_spans


def span_html(span: InlineSpan) -> str:
    """A span of a title or step, which never breaks a line."""
    return _span_html(span, _escaped)


def definition_html(text: str, *, before: str = '', after: str = '') -> str:
    """A glossary definition: its spans, and an author's `<br>` or a newline
    as a break — except in a code span, which is how to show `<br>` as text.
    `before` and `after` flank a stretch of a longer one."""
    return ''.join(
        definition_span_html(span)
        for span in read_spans(text, before=before, after=after)
    )


def definition_span_html(span: InlineSpan) -> str:
    """A span of a glossary definition, which may break a line."""
    return _span_html(span, _with_breaks)


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
