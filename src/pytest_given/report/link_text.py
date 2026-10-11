"""A citation's link text, written so it renders as the title it stands for,
and read back as the title it renders."""

from ..model import Narration
from .markdown_writer import literal_markdown, narration_markdown, one_line

# What a backslash escapes in CommonMark.
ASCII_PUNCTUATION = frozenset('!"#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~')


def link_text(title: Narration | str, *, in_table_row: bool = False) -> str:
    """A citation's link text: a scenario title as the Markdown report writes
    it, a tag or story title literal."""
    if isinstance(title, str):
        return literal_markdown(one_line(title))
    return narration_markdown(title, in_table_row=in_table_row)


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


def _backtick_run_end(text: str, start: int) -> int:
    end = start
    while end < len(text) and text[end] == '`':
        end += 1
    return end
