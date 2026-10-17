"""A citation's link text, written so it renders as the title it stands for."""

from ..markdown import PlainSpan
from ..model import (
    Narration,
    NarrationPiece,
    NarrationPlaceholder,
    NarrationTermRef,
    NarrationValue,
    placeholder_token,
    read_narration,
)
from .inline_markdown import render_span
from .markdown_writer import literal_markdown, narration_markdown, one_line


def link_text(title: Narration | str, *, in_table_row: bool = False) -> str:
    """A citation's link text: a scenario title as the Markdown report writes
    it, a tag or story title literal."""
    if isinstance(title, str):
        return literal_markdown(one_line(title))
    return narration_markdown(title, in_table_row=in_table_row)


def html_link_text(title: Narration) -> str:
    """A scenario title as the HTML report's inline Markdown renders it, for a
    narrated citation's `<summary>`: one line, everything but its spans escaped."""
    return ''.join(_piece_html(piece) for piece in read_narration(title))


def _piece_html(piece: NarrationPiece) -> str:
    match piece:
        case NarrationValue(rendered=text) | NarrationTermRef(display=text):
            return render_span(PlainSpan(text=one_line(text)))
        case NarrationPlaceholder():
            return render_span(PlainSpan(text=placeholder_token(piece)))
        case _:
            return one_line(render_span(piece))
