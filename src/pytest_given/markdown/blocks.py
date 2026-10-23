"""The block structure of a Markdown document, placed in its source.

markdown-it-py reads which text is a paragraph, heading or table cell, and
which is code or HTML, with its block rules wrapped to record where each line
of that text starts: its tokens say which lines a block takes, but not where
on them, past a container prefix, its text begins.
"""

# Reading no document never loads markdown-it.
__lazy_modules__ = ['markdown_it']

import functools
import itertools
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import TYPE_CHECKING

from markdown_it import MarkdownIt

from .plain_text import LINE_BREAK

if TYPE_CHECKING:
    from markdown_it.rules_block import StateBlock
    from markdown_it.token import Token

type Span = tuple[int, int]


@dataclass(frozen=True)
class TextRun:
    """Inline content: a paragraph's lines joined by `\\n` without their
    container prefixes, a heading, or a table cell."""

    # 1-based, the source's. A run's lines are consecutive source lines.
    line: int
    lines: tuple[SourceLine, ...]
    in_table_row: bool = False

    @functools.cached_property
    def text(self) -> str:
        return '\n'.join(line.content for line in self.lines)

    @functools.cached_property
    def offsets(self) -> list[int]:
        """`offsets[i]` is where `text[i]` sits in the source; one more entry
        marks the end. Built on first use: most runs hold nothing a caller
        places."""
        offsets: list[int] = []
        for number, line in enumerate(self.lines):
            if number:
                offsets.append(self.lines[number - 1].end)
            offsets.extend(range(line.start, line.start + len(line.content)))
        last = self.lines[-1]
        offsets.append(last.start + len(last.content))
        return offsets

    def span(self, start: int, end: int) -> Span:
        if end == start:
            return (self.offsets[start], self.offsets[start])
        last = end - 1
        if self.text[last] == '\n':
            # A joining newline stands for the whole break, CRLF included.
            join = self.text.count('\n', 0, last)
            return (self.offsets[start], self.lines[join].break_end)
        return (self.offsets[start], self.offsets[last] + 1)

    def line_at(self, index: int) -> int:
        return self.line + self.text.count('\n', 0, index)

    def slice(self, start: int, end: int) -> TextRun:
        """`text[start:end]` as a run of its own, still placed in the source."""
        lines: list[SourceLine] = []
        position = 0
        for line in self.lines:
            line_end = position + len(line.content)
            if start <= line_end and position <= end:
                low, high = (
                    max(start, position) - position,
                    min(end, line_end) - position,
                )
                lines.append(
                    SourceLine(
                        line.start + low,
                        line.content[low:high],
                        line.end,
                        line.break_end,
                    )
                )
            position = line_end + 1
        return TextRun(self.line_at(start), tuple(lines), self.in_table_row)


@dataclass(frozen=True)
class HtmlBlock:
    # Its lines, each past its container prefix and indent.
    run: TextRun
    # Equal for blocks in one document, list item or blockquote.
    container: int
    # The first line's continuation prefix: `>` and tabs kept, the rest spaces.
    prefix: str
    # Each source line's start offset, prefix included.
    line_starts: tuple[int, ...]
    # Past the last line's line break, or `len(source)`.
    end: int


@dataclass(frozen=True)
class TableCell:
    # Source offsets. A cell GFM supplies to a short row is empty, at its end.
    start: int
    # As written, the container prefix left out.
    text: str

    @property
    def end(self) -> int:
        return self.start + len(self.text)

    @property
    def content(self) -> str:
        """What a renderer reads: stripped, `\\|` as `|`, NUL as U+FFFD."""
        return self.text.replace('\\|', '|').replace('\0', '\ufffd').strip()


@dataclass(frozen=True)
class TableRow:
    # 1-based, the source's.
    line: int
    # Exactly as many as the header has, as GFM fits a row.
    cells: tuple[TableCell, ...]

    @property
    def contents(self) -> list[str]:
        return [cell.content for cell in self.cells]


@dataclass(frozen=True)
class Table:
    header: TableRow
    rows: tuple[TableRow, ...]


def text_runs(source: str) -> Iterator[TextRun]:
    """Every paragraph's, heading's and table cell's text, in document order.
    Code and HTML blocks hold none."""
    for block in _blocks(source):
        if isinstance(block, TextRun):
            yield block
        elif isinstance(block, Table):
            for row in (block.header, *block.rows):
                for cell in row.cells:
                    # A cell holds one line, and a one-line run's spans never
                    # cross a break.
                    cell_line = SourceLine(cell.start, cell.text, cell.end, cell.end)
                    yield TextRun(row.line, (cell_line,), in_table_row=True)


def html_blocks(source: str) -> list[HtmlBlock]:
    """The HTML blocks a renderer reads, fences and code left out."""
    return [block for block in _blocks(source) if isinstance(block, HtmlBlock)]


def tables(source: str) -> list[Table]:
    """The GFM pipe tables a renderer shows."""
    return [block for block in _blocks(source) if isinstance(block, Table)]


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


@dataclass(frozen=True)
class SourceLine:
    """A source line, or the part of one a block's inline text takes up."""

    start: int
    content: str
    # Where the source line ends, before its line break.
    end: int
    # Past the line break: the next line's start, or `len(source)`.
    break_end: int

    def after(self, column: int) -> SourceLine:
        # Stripping the container prefix moves the text, not the break.
        return SourceLine(
            self.start + column, self.content[column:], self.end, self.break_end
        )


# The citation readers each walk the document they read.
@functools.lru_cache(maxsize=1)
def _blocks(source: str) -> tuple[TextRun | Table | HtmlBlock, ...]:
    return tuple(_walk(source))


def _walk(source: str) -> Iterator[TextRun | Table | HtmlBlock]:
    lines = _source_lines(source)
    tokens = _block_parser().parse(source)
    rows: list[TableRow] = []
    containers: list[int] = []
    for index, token in enumerate(tokens):
        if token.nesting == -1:
            containers.pop()
        elif token.nesting == 1:
            containers.append(index)
        match token.type:
            case 'html_block':
                assert token.map is not None
                first, last = token.map
                yield HtmlBlock(
                    TextRun(first + 1, tuple(_text_lines(token, lines))),
                    containers[-1] if containers else -1,
                    token.meta['prefix'],
                    tuple(line.start for line in lines[first:last]),
                    lines[last].start if last < len(lines) else len(source),
                )
            case 'tr_open':
                # markdown-it does not say where a cell sits in its row, so
                # the row is split again, as its table rule splits one.
                row = _text_lines(tokens[index + 2], lines)[0]
                assert token.map is not None
                width = len(rows[0].cells) if rows else None
                rows.append(TableRow(token.map[0] + 1, _cells(row, width)))
            case 'table_close':
                header, *body = rows
                yield Table(header, tuple(body))
                rows = []
            case 'inline' if tokens[index - 1].type in (
                'paragraph_open',
                'heading_open',
            ):
                yield _prose_run(token, tokens[index - 1], lines)


def _cells(row: SourceLine, width: int | None) -> tuple[TableCell, ...]:
    """The row's cells, fitted to `width`: a cell past it is dropped, a
    missing one supplied empty. The header's, given no width, as written."""
    cells = [
        TableCell(row.start + start, row.content[start:end])
        for start, end in table_cell_spans(row.content)
    ]
    if width is None:
        return tuple(cells)
    missing = TableCell(row.end, '')
    return (*cells[:width], *(missing,) * (width - len(cells)))


def _prose_run(token: Token, opener: Token, lines: list[SourceLine]) -> TextRun:
    text = _text_lines(token, lines)
    if opener.type == 'heading_open' and opener.markup.startswith('#'):
        text[0] = _past_hashes(text[0], opener.markup)
    assert token.map is not None
    return TextRun(token.map[0] + 1, tuple(text))


def _text_lines(token: Token, lines: list[SourceLine]) -> list[SourceLine]:
    assert token.map is not None
    return [
        line.after(column)
        for line, column in zip(
            lines[slice(*token.map)], token.meta['columns'], strict=True
        )
    ]


def _past_hashes(line: SourceLine, hashes: str) -> SourceLine:
    """An ATX heading's text, past its opening hashes and the space after."""
    rest = line.content[len(hashes) :]
    return line.after(len(hashes) + len(rest) - len(rest.lstrip(' \t')))


type _BlockRule = Callable[[StateBlock, int, int, bool], bool]


def _recording(rule: _BlockRule) -> _BlockRule:
    """`rule`, recording on each inline or HTML block token it makes the column
    each line's text starts at, past the line's container prefix and indent:
    markdown-it knows it while the rule runs, but its tokens do not say."""

    def recorded(state: StateBlock, start: int, end: int, silent: bool) -> bool:
        made = len(state.tokens)
        matched = rule(state, start, end, silent)
        if matched and not silent:
            for token in state.tokens[made:]:
                if token.type not in ('inline', 'html_block'):
                    continue
                assert token.map is not None
                token.meta['columns'] = [
                    _column(state, line) for line in range(*token.map)
                ]
                if token.type == 'html_block':
                    token.meta['prefix'] = _prefix(state, token.map[0])
        return matched

    return recorded


def _column(state: StateBlock, line: int) -> int:
    # Normalizing the source rewrites line breaks, and NULs one for one, so
    # a column within a line of it is one in the source line too.
    text_start = state.bMarks[line] + state.tShift[line]
    return text_start - (state.src.rfind('\n', 0, text_start) + 1)


def _prefix(state: StateBlock, line: int) -> str:
    """The line's characters before the block's text, as a continuation line
    would write them."""
    end = state.bMarks[line] + min(state.tShift[line], state.blkIndent)
    before = state.src[state.src.rfind('\n', 0, end) + 1 : end]
    return ''.join(char if char in '>\t' else ' ' for char in before)


@functools.cache
def _block_parser() -> MarkdownIt:
    # The preset stops reading blocks nested 20 deep; a renderer does not.
    parser = MarkdownIt('commonmark', {'maxNesting': 100})
    parser.enable('table').disable('inline')
    ruler = parser.block.ruler
    for rule in list(ruler.__rules__):
        if rule.name in ('paragraph', 'heading', 'lheading', 'table', 'html_block'):
            # Given no options, `at` drops the blocks the rule may interrupt.
            ruler.at(rule.name, _recording(rule.fn), {'alt': rule.alt})
    return parser


def _source_lines(source: str) -> list[SourceLine]:
    lines: list[SourceLine] = []
    start = 0
    # Every line break markdown-it reads, so its line numbers are the source's.
    for line_break in LINE_BREAK.finditer(source):
        lines.append(
            SourceLine(
                start,
                source[start : line_break.start()],
                line_break.start(),
                line_break.end(),
            )
        )
        start = line_break.end()
    if start < len(source):
        lines.append(SourceLine(start, source[start:], len(source), len(source)))
    return lines
