"""A citation's link text, written so it renders as the title it stands for,
and read back as the title it renders."""

import re

from ..model import ASCII_PUNCTUATION, backtick_run_end, code_span_end

# Outside a code span, what CommonMark or GFM give inline meaning, beside `_`,
# which has a rule of its own: closing the link early, emphasis,
# strikethrough, opening a code span, raw HTML, an entity, a table cell,
# GitHub math.
_ALWAYS_ESCAPED = frozenset('\\[]*~`<&|$')
_NEWLINE = re.compile(r'\r\n|\r|\n')


def link_text(title: str, *, in_table_row: bool = False) -> str:
    """`title` as link text that renders as it, character for character.

    Code spans are meant as code, as the Markdown sink renders them, so
    nothing inside one is escaped — a backslash there would render — except a
    table row's `|`, which GFM lets an escape keep from splitting the cell.
    """
    text = _NEWLINE.sub(' ', title)
    in_code = _code_span_mask(text)
    out: list[str] = []
    for index, char in enumerate(text):
        if in_code[index]:
            out.append('\\|' if in_table_row and char == '|' else char)
        elif char in _ALWAYS_ESCAPED or (char == '_' and not _intraword(text, index)):
            out.append('\\' + char)
        else:
            out.append(char)
    return ''.join(out)


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
            end = code_span_end(written, index)
            if end is None:
                end = backtick_run_end(written, index)
                out.append(written[index:end])
            else:
                span = written[index:end]
                out.append(span.replace('\\|', '|') if in_table_row else span)
            index = end
        else:
            out.append(char)
            index += 1
    return fold_whitespace(''.join(out))


def fold_whitespace(text: str) -> str:
    return ' '.join(text.split())


def _code_span_mask(text: str) -> list[bool]:
    """Which characters a code span holds, backticks included. A backtick run
    nothing closes is literal, and `link_text` escapes it, or it would pair
    with one later on the line and swallow the link."""
    mask = [False] * len(text)
    index = 0
    while index < len(text):
        if text[index] != '`':
            index += 1
            continue
        end = code_span_end(text, index)
        if end is None:
            index = backtick_run_end(text, index)
        else:
            mask[index:end] = [True] * (end - index)
            index = end
    return mask


def _intraword(text: str, index: int) -> bool:
    """An `_` between two letters or digits never emphasizes."""
    return (
        0 < index < len(text) - 1
        and text[index - 1].isalnum()
        and text[index + 1].isalnum()
    )
