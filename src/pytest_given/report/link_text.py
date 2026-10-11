"""The Markdown writer — text written so a Markdown viewer shows what the HTML
report shows — and a citation's link text read back as the title it renders."""

from collections.abc import Callable

from ..model import (
    CodeSpan,
    EmphasisSpan,
    InlineSpan,
    Narration,
    NarrationLiteral,
    NarrationPart,
    NarrationPlaceholder,
    NarrationTermRef,
    NarrationValue,
    PlainSpan,
    placeholder_token,
    read_spans,
)
from .text import NEWLINE

# What a backslash escapes in CommonMark.
ASCII_PUNCTUATION = frozenset('!"#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~')

# What CommonMark or GFM give inline meaning, beside `_`, which has a rule of
# its own: a link, emphasis, strikethrough, a code span, raw HTML, an entity,
# a table cell, GitHub math.
_ALWAYS_ESCAPED = frozenset('\\[]*~`<&|$')


def link_text(title: Narration | str, *, in_table_row: bool = False) -> str:
    """A citation's link text: a scenario title as the Markdown report writes
    it, a tag or story title literal."""
    if isinstance(title, str):
        return literal_markdown(_one_line(title))
    return narration_markdown(title, in_table_row=in_table_row)


def narration_markdown(
    narration: Narration,
    *,
    in_table_row: bool = False,
    term_ref: Callable[[str], str] = lambda display: display,
) -> str:
    """A title or step on one line, piece by piece: each plain-text piece keeps
    the reader's spans, every other piece is literal — so a span never crosses
    a term ref or a value. `term_ref` frames a term ref's written display."""
    if not narration.parts:
        return spans_markdown(_one_line(narration.text), in_table_row=in_table_row)
    return ''.join(
        _piece_markdown(part, in_table_row, term_ref) for part in narration.parts
    )


def spans_markdown(text: str, *, in_table_row: bool = False) -> str:
    """`text` with the reader's spans kept as markup and everything else
    literal. Nothing inside a code span is escaped — a backslash there would
    show — except a table row's `|`, which GFM lets an escape keep from
    splitting the cell."""
    return ''.join(_span_markdown(span, in_table_row) for span in read_spans(text))


def literal_markdown(text: str) -> str:
    """`text` with every character of inline meaning backslash-escaped, so it
    shows as written."""
    return ''.join(
        f'\\{char}'
        if char in _ALWAYS_ESCAPED or (char == '_' and not _intraword(text, index))
        else char
        for index, char in enumerate(text)
    )


def plain_link_text(written: str, *, in_table_row: bool = False) -> str:
    """The text a link renders, escapes resolved and whitespace folded: what a
    citation's text is compared as. Code spans keep their backticks, as a
    scenario title spells them."""
    out: list[str] = []
    index = 0
    while index < len(written):
        char = written[index]
        if char == '\\' and written[index + 1 : index + 2] in ASCII_PUNCTUATION:
            out.append(written[index + 1])
            index += 2
        elif char == '`':
            end, closed = code_span_at(written, index)
            span = written[index:end]
            out.append(span.replace('\\|', '|') if closed and in_table_row else span)
            index = end
        else:
            out.append(char)
            index += 1
    return fold_whitespace(''.join(out))


def fold_whitespace(text: str) -> str:
    return ' '.join(text.split())


def code_span_at(text: str, start: int) -> tuple[int, bool]:
    """Where the backticks opening at `start` stop counting, and whether they
    open a code span: its end if a run of exactly their width closes it, else
    the end of their own run, which is literal."""
    width = _backtick_run_end(text, start) - start
    position = start + width
    while (found := text.find('`', position)) != -1:
        run_end = _backtick_run_end(text, found)
        if run_end - found == width:
            return run_end, True
        position = run_end
    return start + width, False


def _piece_markdown(
    part: NarrationPart, in_table_row: bool, term_ref: Callable[[str], str]
) -> str:
    match part:
        case NarrationLiteral(value=value):
            return spans_markdown(_one_line(value), in_table_row=in_table_row)
        case NarrationValue(rendered=rendered):
            return literal_markdown(_one_line(rendered))
        case NarrationPlaceholder():
            return literal_markdown(placeholder_token(part))
        case NarrationTermRef(display=display):
            return term_ref(literal_markdown(_one_line(display)))


def _span_markdown(span: InlineSpan, in_table_row: bool) -> str:
    match span:
        case PlainSpan(text=text):
            return literal_markdown(text)
        case CodeSpan(text=text):
            if in_table_row:
                text = text.replace('|', '\\|')
            # CommonMark strips one space off each end of such a span.
            if text.startswith(' ') and text.endswith(' ') and text.strip(' '):
                text = f' {text} '
            return f'`{text}`'
        case EmphasisSpan(strong=strong, content=content):
            marker = '**' if strong else '*'
            inner = ''.join(_span_markdown(part, in_table_row) for part in content)
            return f'{marker}{inner}{marker}'


def _one_line(text: str) -> str:
    return NEWLINE.sub(' ', text)


def _backtick_run_end(text: str, start: int) -> int:
    end = start
    while end < len(text) and text[end] == '`':
        end += 1
    return end


def _intraword(text: str, index: int) -> bool:
    """An `_` between two letters or digits never emphasizes."""
    return (
        0 < index < len(text) - 1
        and text[index - 1].isalnum()
        and text[index + 1].isalnum()
    )
