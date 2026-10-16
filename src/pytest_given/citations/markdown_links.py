"""Inline links in a Markdown document, with the source span of every part
`pytest-given citations update` may rewrite.

markdown-it-py reads the block structure — which text is a paragraph, heading
or table cell, and which is code or HTML — with its block rules wrapped to
record where each line of that text starts. The inline links are read here,
because no Markdown parser reports where a link's text and destination, or the
characters around it, sit in the source — and an update must change those
bytes and no others.
"""

# A CLI command that checks no citations never loads markdown-it.
__lazy_modules__ = ['markdown_it']

import bisect
import functools
import html
import itertools
import re
from collections.abc import Callable, Collection, Iterator, Sequence
from dataclasses import dataclass
from html.entities import html5
from typing import TYPE_CHECKING, NamedTuple

from markdown_it import MarkdownIt

from ..report import ASCII_PUNCTUATION, code_span_at

if TYPE_CHECKING:
    from markdown_it.rules_block import StateBlock
    from markdown_it.token import Token

type Span = tuple[int, int]

VARIATION_SELECTOR = '\ufe0f'


class Glyph(NamedTuple):
    """A citation glyph as written, variation selector and all."""

    text: str
    span: Span

    @property
    def bare(self) -> str:
        return self.text.removesuffix(VARIATION_SELECTOR)


@dataclass(frozen=True, kw_only=True)
class MarkdownLink:
    """One inline link; spans are offsets into the document's source.

    `text` leaves out the container prefixes (`> `) of the lines it wraps
    over, while `text_span` covers them, so replacing the span writes the text
    on one line. `trailing` runs from `end` through the paragraph's next line,
    where a hard wrap may have put a summary, or to the end of the table cell,
    leaving out prefixes the same way; `trailing_span` places a slice of it.
    """

    line: int
    text: str
    text_span: Span
    url: str
    url_span: Span
    trailing: str
    trailing_offsets: tuple[int, ...]
    in_table_row: bool
    glyph: Glyph | None

    @property
    def end(self) -> int:
        """Just past the link's closing `)`."""
        return self.trailing_offsets[0]

    def trailing_span(self, start: int, end: int) -> Span:
        return _span(self.trailing_offsets, start, end)

    @property
    def destination(self) -> str:
        """`url` as a renderer reads it: backslash escapes and entity
        references resolved, percent-encoding left alone."""
        return ''.join(
            _unescaped(token) for token in _DESTINATION_TOKEN.findall(self.url)
        )

    @property
    def fragment_span(self) -> Span | None:
        """Where the fragment sits in the source: past the first `#` that
        `destination` reads, written as `#`, `\\#` or `&#35;`."""
        for token in _DESTINATION_TOKEN.finditer(self.url):
            if _unescaped(token.group()) == '#':
                return (self.url_span[0] + token.end(), self.url_span[1])
        return None


def scan_links(source: str, glyphs: Collection[str] = ()) -> list[MarkdownLink]:
    """Every inline link outside code and HTML blocks, in document order. A
    reference-style link is none, and neither is an image."""
    lines = _source_lines(source)
    line_starts = [line.start for line in lines]
    longest_first = sorted(glyphs, key=len, reverse=True)
    return [
        link
        for run in _inline_runs(source, lines)
        for link in _links_in(run, line_starts, longest_first)
    ]


# One character of a destination as written, or the escape or entity
# reference that reads as one.
_DESTINATION_TOKEN = re.compile(
    r'\\[!-/:-@\[-`{-~]|&(?:#[0-9]{1,7}|#[xX][0-9a-fA-F]{1,6}|[A-Za-z][A-Za-z0-9]{1,31});|.',
    re.DOTALL,
)


def _unescaped(token: str) -> str:
    if token.startswith('\\') and len(token) == 2:
        return token[1]
    if token.startswith('&#'):
        return html.unescape(token)
    # Not `html.unescape`, which also reads `&notit;` as `¬it;`: CommonMark
    # resolves only a whole entity name.
    return html5.get(token[1:], token) if token.startswith('&') else token


# --- Block structure ---


@dataclass(frozen=True)
class _Line:
    """A source line, or the part of one a block's inline text takes up."""

    start: int
    content: str
    # Where the source line ends, before its line break.
    end: int

    def after(self, column: int) -> _Line:
        return _Line(self.start + column, self.content[column:], self.end)


@dataclass(frozen=True)
class _Run:
    """Inline content: a paragraph's lines joined by `\\n` without their
    container prefixes, a heading, or a table cell. `offsets[i]` is where
    `text[i]` sits in the source; one more entry marks the end."""

    text: str
    offsets: list[int]
    in_table_row: bool = False

    @classmethod
    def of_lines(cls, lines: list[_Line], *, in_table_row: bool = False) -> _Run:
        parts: list[str] = []
        offsets: list[int] = []
        for number, line in enumerate(lines):
            if number:
                parts.append('\n')
                offsets.append(lines[number - 1].end)
            parts.append(line.content)
            offsets.extend(range(line.start, line.start + len(line.content)))
        offsets.append(lines[-1].start + len(lines[-1].content))
        return cls(''.join(parts), offsets, in_table_row)

    def span(self, start: int, end: int) -> Span:
        return _span(self.offsets, start, end)


def _span(offsets: Sequence[int], start: int, end: int) -> Span:
    if end == start:
        return (offsets[start], offsets[start])
    return (offsets[start], offsets[end - 1] + 1)


def _inline_runs(source: str, lines: list[_Line]) -> Iterator[_Run]:
    tokens = _block_parser().parse(source)
    cells: Iterator[_Line] = iter(())
    for index, token in enumerate(tokens):
        if token.type != 'inline':
            continue
        opener = tokens[index - 1]
        if opener.type in ('th_open', 'td_open'):
            # markdown-it does not say where a cell sits in its row, so the
            # row is split again at its first cell, and each cell markdown-it
            # reads takes the next: a cell past the header's is dropped.
            if tokens[index - 2].type == 'tr_open':
                cells = _cells(_text_lines(token, lines)[0])
            cell = next(cells, None)
            if cell is not None and '](' in cell.content:
                yield _Run.of_lines([cell], in_table_row=True)
        # A link's text always runs into its destination.
        elif '](' in token.content:
            text = _text_lines(token, lines)
            if opener.type == 'heading_open' and opener.markup.startswith('#'):
                text[0] = _past_hashes(text[0], opener.markup)
            yield _Run.of_lines(text)


def _text_lines(token: Token, lines: list[_Line]) -> list[_Line]:
    assert token.map is not None
    return [
        line.after(column)
        for line, column in zip(
            lines[slice(*token.map)], token.meta['columns'], strict=True
        )
    ]


def _cells(row: _Line) -> Iterator[_Line]:
    for start, end in table_cell_spans(row.content):
        yield _Line(row.start + start, row.content[start:end], row.start + end)


def table_cell_spans(row: str) -> list[Span]:
    """Each cell's span in a GFM table row, its outer pipes left out. A pipe
    right after a backslash is the cell's, escaped backslash or code span
    around it or not: GFM splits the row before it reads any inline syntax."""
    pipes = [
        index
        for index, char in enumerate(row)
        if char == '|' and row[index - 1 : index] != '\\'
    ]
    edges = [-1, *pipes, len(row)]
    spans = [(left + 1, right) for left, right in itertools.pairwise(edges)]
    if spans and not row[: spans[0][1]].strip():
        spans = spans[1:]
    if spans and not row[spans[-1][0] :].strip():
        spans = spans[:-1]
    return spans


def _past_hashes(line: _Line, hashes: str) -> _Line:
    """An ATX heading's text, past its opening hashes and the space after."""
    rest = line.content[len(hashes) :]
    return line.after(len(hashes) + len(rest) - len(rest.lstrip(' \t')))


type _BlockRule = Callable[[StateBlock, int, int, bool], bool]


def _recording(rule: _BlockRule) -> _BlockRule:
    """`rule`, recording on each inline token it makes the column each line's
    text starts at, past the line's container prefix and indent: markdown-it
    knows it while the rule runs, but its tokens do not say."""

    def recorded(state: StateBlock, start: int, end: int, silent: bool) -> bool:
        made = len(state.tokens)
        matched = rule(state, start, end, silent)
        if matched and not silent:
            for token in state.tokens[made:]:
                if token.type == 'inline':
                    assert token.map is not None
                    token.meta['columns'] = [
                        _column(state, line) for line in range(*token.map)
                    ]
        return matched

    return recorded


def _column(state: StateBlock, line: int) -> int:
    # Normalizing the source rewrites line breaks, and NULs one for one, so
    # a column within a line of it is one in the source line too.
    text_start = state.bMarks[line] + state.tShift[line]
    return text_start - (state.src.rfind('\n', 0, text_start) + 1)


@functools.cache
def _block_parser() -> MarkdownIt:
    # The preset stops reading blocks nested 20 deep; a renderer does not.
    parser = MarkdownIt('commonmark', {'maxNesting': 100})
    parser.enable('table').disable('inline')
    ruler = parser.block.ruler
    for rule in list(ruler.__rules__):
        if rule.name in ('paragraph', 'heading', 'lheading', 'table'):
            # Given no options, `at` drops the blocks the rule may interrupt.
            ruler.at(rule.name, _recording(rule.fn), {'alt': rule.alt})
    return parser


# Every line break markdown-it reads, so its line numbers are the source's.
_LINE_BREAK = re.compile(r'\r\n|\r|\n')


def _source_lines(source: str) -> list[_Line]:
    lines: list[_Line] = []
    start = 0
    for line_break in _LINE_BREAK.finditer(source):
        lines.append(
            _Line(start, source[start : line_break.start()], line_break.start())
        )
        start = line_break.end()
    if start < len(source):
        lines.append(_Line(start, source[start:], len(source)))
    return lines


# --- Inline structure ---


@dataclass
class _Opener:
    position: int
    image: bool
    active: bool = True


@dataclass(frozen=True)
class _Destination:
    url_start: int
    url_end: int
    close: int


_AUTOLINK = re.compile(
    r'<[A-Za-z][A-Za-z0-9+.-]{1,31}:[^\s<>]*>'
    r'|<[A-Za-z0-9.!#$%&\'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?'
    r'(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)*>'
)
_INLINE_HTML = re.compile(
    r'</?[A-Za-z][A-Za-z0-9-]*'
    r'(?:\s+[A-Za-z_:][\w.:-]*(?:\s*=\s*(?:[^\s"\'=<>`]+|\'[^\']*\'|"[^"]*"))?)*'
    r'\s*/?>|<!--.*?-->',
    re.DOTALL,
)


def _links_in(
    run: _Run, line_starts: list[int], glyphs: list[str]
) -> Iterator[MarkdownLink]:
    text = run.text
    openers: list[_Opener] = []
    index = 0
    while index < len(text):
        char = text[index]
        if char == '\\' and text[index + 1 : index + 2] in ASCII_PUNCTUATION:
            index += 2
        elif char == '`':
            index, _ = code_span_at(text, index)
        elif char == '<' and (
            tag := _AUTOLINK.match(text, index) or _INLINE_HTML.match(text, index)
        ):
            index = tag.end()
        elif char == '[' or (char == '!' and text.startswith('[', index + 1)):
            image = char == '!'
            openers.append(_Opener(index + image, image))
            index += 1 + image
        elif char == ']' and openers:
            opener = openers.pop()
            destination = _destination(text, index + 1) if opener.active else None
            if destination is None:
                index += 1
                continue
            if not opener.image:
                yield _link(
                    run, opener.position, index, destination, line_starts, glyphs
                )
                # Links do not nest: no earlier bracket can open one now.
                for earlier in openers:
                    earlier.active = earlier.image and earlier.active
            index = destination.close + 1
        else:
            index += 1


def _destination(text: str, start: int) -> _Destination | None:
    """The inline destination `(url "title")` opening at `start`, if any."""
    if text[start : start + 1] != '(':
        return None
    position = _skip_space(text, start + 1)
    if text[position : position + 1] == '<':
        end = position + 1
        while end < len(text) and text[end] not in '<>\n':
            end += 2 if text[end] == '\\' else 1
        if text[end : end + 1] != '>':
            return None
        url_start, url_end, position = position + 1, end, end + 1
    else:
        url_start = position
        depth = 0
        while position < len(text):
            char = text[position]
            if char == '\\' and text[position + 1 : position + 2] in ASCII_PUNCTUATION:
                position += 2
                continue
            if char.isspace() or ord(char) < 0x20:
                break
            if char == '(':
                depth += 1
            elif char == ')':
                if depth == 0:
                    break
                depth -= 1
            position += 1
        if depth:
            return None
        url_end = position
    after = _skip_space(text, position)
    if after > position and text[after : after + 1] in ('"', "'", '('):
        closer = ')' if text[after] == '(' else text[after]
        title_end = after + 1
        while title_end < len(text) and text[title_end] != closer:
            title_end += 2 if text[title_end] == '\\' else 1
        if title_end >= len(text):
            return None
        after = _skip_space(text, title_end + 1)
    if text[after : after + 1] != ')':
        return None
    return _Destination(url_start, url_end, after)


def _skip_space(text: str, position: int) -> int:
    while position < len(text) and text[position] in ' \t\n':
        position += 1
    return position


def _link(
    run: _Run,
    open_index: int,
    close_index: int,
    destination: _Destination,
    line_starts: list[int],
    glyphs: list[str],
) -> MarkdownLink:
    text = run.text
    after = destination.close + 1
    line_end = text.find('\n', after)
    next_line_end = -1 if line_end == -1 else text.find('\n', line_end + 1)
    trailing_end = len(text) if next_line_end == -1 else next_line_end
    return MarkdownLink(
        line=bisect.bisect_right(line_starts, run.offsets[open_index]),
        text=text[open_index + 1 : close_index],
        text_span=run.span(open_index + 1, close_index),
        url=text[destination.url_start : destination.url_end],
        url_span=run.span(destination.url_start, destination.url_end),
        trailing=text[after:trailing_end],
        trailing_offsets=tuple(run.offsets[after : trailing_end + 1]),
        in_table_row=run.in_table_row,
        glyph=_glyph_before(run, open_index, glyphs),
    )


def _glyph_before(run: _Run, open_index: int, glyphs: list[str]) -> Glyph | None:
    """The glyph leading the link at `open_index`: across any whitespace, and
    itself at the start of the content or after whitespace or `(` — so a
    question mark ending a sentence is never read as one."""
    text = run.text
    end = open_index
    while end > 0 and text[end - 1] in ' \t\n':
        end -= 1
    stop = end - 1 if end > 0 and text[end - 1] == VARIATION_SELECTOR else end
    for glyph in glyphs:
        start = stop - len(glyph)
        if (
            start >= 0
            and text[start:stop] == glyph
            and (start == 0 or text[start - 1] in ' \t\n(')
        ):
            return Glyph(text[start:end], run.span(start, end))
    return None
