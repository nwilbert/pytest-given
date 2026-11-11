"""A title or step as Markdown source, so a Markdown viewer shows it as the
HTML report does."""

from collections.abc import Callable

from ..markdown import (
    CodeSpan,
    EmphasisSpan,
    PlainSpan,
    literal_markdown,
    one_line,
    span_markdown,
)
from ..model import (
    Narration,
    NarrationPiece,
    NarrationPlaceholder,
    NarrationTermRef,
    NarrationValue,
    placeholder_token,
    read_narration,
)


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
            return span_markdown(part, in_table_row=in_table_row)
        case NarrationPlaceholder():
            return literal_markdown(one_line(placeholder_token(part)))
        case NarrationTermRef(display=display):
            return term_ref(literal_markdown(one_line(display)))
