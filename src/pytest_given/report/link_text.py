"""A citation's link text, written so it renders as the title it stands for,
and read back as the title it renders."""

from .text import NEWLINE

# What a backslash escapes in CommonMark.
ASCII_PUNCTUATION = frozenset('!"#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~')

# Outside a code span, what CommonMark or GFM give inline meaning, beside `_`,
# which has a rule of its own: closing the link early, emphasis,
# strikethrough, opening a code span, raw HTML, an entity, a table cell,
# GitHub math.
_ALWAYS_ESCAPED = frozenset('\\[]*~`<&|$')


def link_text(title: str, *, in_table_row: bool = False) -> str:
    """`title` as link text that renders as it, character for character.

    Code spans are meant as code, as the Markdown sink renders them, so
    nothing inside one is escaped — a backslash there would render — except a
    table row's `|`, which GFM lets an escape keep from splitting the cell.
    """
    text = NEWLINE.sub(' ', title)
    out: list[str] = []
    index = 0
    while index < len(text):
        char = text[index]
        if char == '`':
            end, closed = code_span_at(text, index)
            run = text[index:end]
            if not closed:
                # Literal, so escaped, or it would pair with a run later on
                # the line and swallow the link.
                run = run.replace('`', '\\`')
            elif in_table_row:
                run = run.replace('|', '\\|')
            out.append(run)
            index = end
            continue
        if char in _ALWAYS_ESCAPED or (char == '_' and not _intraword(text, index)):
            out.append('\\')
        out.append(char)
        index += 1
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


def _intraword(text: str, index: int) -> bool:
    """An `_` between two letters or digits never emphasizes."""
    return (
        0 < index < len(text) - 1
        and text[index - 1].isalnum()
        and text[index + 1].isalnum()
    )
