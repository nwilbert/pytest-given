"""Text written as Markdown source, so a Markdown viewer shows it as the HTML
report does: the inline subset's spans kept as markup, everything else
escaped to show as written."""

import re
from collections.abc import Callable

from .plain_text import DEFINITION_BREAK, one_line
from .spans import CodeSpan, EmphasisSpan, InlineSpan, PlainSpan, read_spans

# What CommonMark or GFM give inline meaning: a link, emphasis,
# strikethrough, a code span, raw HTML, an entity, a table cell, GitHub math —
# and `_`, except between two letters or digits, where it never emphasizes.
_ESCAPED = re.compile(r'[\\\[\]*~`<&|$]|(?<![^\W_])_|_(?![^\W_])')
_ALNUM = re.compile(r'[^\W_]')


def span_markdown(span: InlineSpan, *, in_table_row: bool = False) -> str:
    """A span of a title or step, on one line."""
    return _span_markdown(span, in_table_row, _literal_line)


def definition_markdown(text: str) -> str:
    """A glossary definition on one line, as the report shows it: its spans kept
    as markup, everything else literal, an author's `<br>` or a newline as `<br>`."""
    return ''.join(
        _span_markdown(span, in_table_row=False, plain=_literal_with_breaks)
        for span in read_spans(text)
    )


def literal_markdown(text: str, *, before: str = '', after: str = '') -> str:
    """`text` with every character of inline meaning backslash-escaped, so it
    shows as written. A letter or digit written `before` or `after` it makes
    an `_` at its edge intraword."""
    lead, trail = (char if _ALNUM.fullmatch(char) else '' for char in (before, after))
    escaped = _ESCAPED.sub(r'\\\g<0>', f'{lead}{text}{trail}')
    return escaped[len(lead) : len(escaped) - len(trail)]


def code_span_markdown(text: str, *, in_table_row: bool = False) -> str:
    """`text` as a code span. Nothing inside is escaped — a backslash there
    would show — except a table row's `|`, which GFM lets an escape keep from
    splitting the cell."""
    if in_table_row:
        text = text.replace('|', '\\|')
    # CommonMark strips one space off each end of such a span.
    if text.startswith(' ') and text.endswith(' ') and text.strip(' '):
        text = f' {text} '
    return f'`{text}`'


def _span_markdown(
    span: InlineSpan, in_table_row: bool, plain: Callable[[str], str]
) -> str:
    match span:
        case PlainSpan(text=text):
            return plain(text)
        case CodeSpan(text=text):
            return code_span_markdown(one_line(text), in_table_row=in_table_row)
        case EmphasisSpan(strong=strong, content=content):
            marker = '**' if strong else '*'
            inner = ''.join(
                _span_markdown(part, in_table_row, plain) for part in content
            )
            return f'{marker}{inner}{marker}'


def _literal_line(text: str) -> str:
    return literal_markdown(one_line(text))


def _literal_with_breaks(text: str) -> str:
    return '<br>'.join(literal_markdown(line) for line in DEFINITION_BREAK.split(text))
