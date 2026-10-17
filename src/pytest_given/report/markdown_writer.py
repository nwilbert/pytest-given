"""The Markdown writer: text written so a Markdown viewer shows what the HTML
report shows."""

import re
from collections.abc import Callable

from ..markdown import LINE_BREAK, CodeSpan, EmphasisSpan, InlineSpan, PlainSpan
from ..model import (
    Narration,
    NarrationPiece,
    NarrationPlaceholder,
    NarrationTermRef,
    NarrationValue,
    placeholder_token,
    read_narration,
)

# What CommonMark or GFM give inline meaning: a link, emphasis,
# strikethrough, a code span, raw HTML, an entity, a table cell, GitHub math —
# and `_`, except between two letters or digits, where it never emphasizes.
_ESCAPED = re.compile(r'[\\\[\]*~`<&|$]|(?<![^\W_])_|_(?![^\W_])')
_ALNUM = re.compile(r'[^\W_]')


def narration_markdown(
    narration: Narration,
    *,
    in_table_row: bool = False,
    term_ref: Callable[[str], str] = lambda display: display,
) -> str:
    """A title or step on one line, its spans kept as markup and everything
    else literal. `term_ref` frames a term ref's written display."""
    pieces = read_narration(narration)
    edges = [_edge_text(piece) for piece in pieces]
    return ''.join(
        _piece_markdown(piece, before[-1:], after[:1], in_table_row, term_ref)
        for piece, before, after in zip(
            pieces, ['', *edges[:-1]], [*edges[1:], ''], strict=True
        )
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


def one_line(text: str) -> str:
    return LINE_BREAK.sub(' ', text)


def _edge_text(piece: NarrationPiece) -> str:
    """What a piece writes at its edges, as far as an `_` beside it can tell:
    a span's edge is its marker, and a term ref's may be framed."""
    match piece:
        case PlainSpan(text=text) | NarrationValue(rendered=text):
            return text
        case _:
            return ''


def _piece_markdown(
    part: NarrationPiece,
    before: str,
    after: str,
    in_table_row: bool,
    term_ref: Callable[[str], str],
) -> str:
    match part:
        case PlainSpan(text=text) | NarrationValue(rendered=text):
            return literal_markdown(one_line(text), before=before, after=after)
        case CodeSpan() | EmphasisSpan():
            return _span_markdown(part, in_table_row)
        case NarrationPlaceholder():
            return literal_markdown(placeholder_token(part))
        case NarrationTermRef(display=display):
            return term_ref(literal_markdown(one_line(display)))


def _span_markdown(span: InlineSpan, in_table_row: bool) -> str:
    match span:
        case PlainSpan(text=text):
            return literal_markdown(one_line(text))
        case CodeSpan(text=text):
            return code_span_markdown(one_line(text), in_table_row=in_table_row)
        case EmphasisSpan(strong=strong, content=content):
            marker = '**' if strong else '*'
            inner = ''.join(_span_markdown(part, in_table_row) for part in content)
            return f'{marker}{inner}{marker}'
