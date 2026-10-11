"""Inline links in a Markdown document, with the source span of every part
`pytest-given citations update` may rewrite.

Hand-written because no Markdown parser reports where a link's text and
destination, or the characters around it, sit in the source — and an update
must change those bytes and no others. It follows CommonMark plus GFM tables
closely enough for documentation; `test_markdown_links_oracle.py` holds it to
markdown-it-py over every Markdown file the repository tracks.
"""

import bisect
import itertools
import re
from collections.abc import Collection, Iterator, Sequence
from dataclasses import dataclass
from typing import NamedTuple

type Span = tuple[int, int]

ASCII_PUNCTUATION = frozenset('!"#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~')
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
    end: int
    trailing: str
    trailing_offsets: tuple[int, ...]
    in_table_row: bool
    glyph: Glyph | None = None

    def trailing_span(self, start: int, end: int) -> Span:
        return _span(self.trailing_offsets, start, end)


def scan_links(source: str, glyphs: Collection[str] = ()) -> list[MarkdownLink]:
    """Every inline link outside code and HTML blocks, in document order. A
    reference-style link is none, and neither is an image."""
    line_starts = [0, *(match.end() for match in re.finditer('\n', source))]
    longest_first = sorted(glyphs, key=len, reverse=True)
    return [
        link
        for run in _inline_runs(source)
        for link in _links_in(run, line_starts, longest_first)
    ]


def code_span_end(text: str, start: int) -> int | None:
    """Where the code span opening at `start` ends, or None when no backtick
    run of exactly its width closes it."""
    width = backtick_run_end(text, start) - start
    position = start + width
    while (found := text.find('`', position)) != -1:
        run_end = backtick_run_end(text, found)
        if run_end - found == width:
            return run_end
        position = run_end
    return None


def backtick_run_end(text: str, start: int) -> int:
    end = start
    while end < len(text) and text[end] == '`':
        end += 1
    return end


# --- Block structure ---


@dataclass(frozen=True)
class _Line:
    start: int
    content: str
    end: int


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


@dataclass(frozen=True)
class _Fence:
    char: str
    width: int
    base: int
    quote_depth: int


class _ListItem(NamedTuple):
    quote_depth: int
    column: int


_BLOCKQUOTE_MARKER = re.compile(r' {0,3}> ?')
_FENCE_OPEN = re.compile(r'`{3,}(?=[^`]*$)|~{3,}')
_ATX_HEADING = re.compile(r'#{1,6}(?:[ \t]|$)')
_SETEXT_UNDERLINE = re.compile(r'(?:=+|-+)[ \t]*$')
_THEMATIC_BREAK = re.compile(r'(?:(?:\*[ \t]*){3,}|(?:-[ \t]*){3,}|(?:_[ \t]*){3,})$')
_LIST_ITEM = re.compile(r'([-+*]|\d{1,9}[.)])([ \t]+|$)')
_DELIMITER_ROW = re.compile(
    r' {0,3}\|?[ \t]*:?-+:?[ \t]*(?:\|[ \t]*:?-+:?[ \t]*)*\|?[ \t]*$'
)
_BLOCK_TAGS = (
    'address|article|aside|base|basefont|blockquote|body|caption|center|col|'
    'colgroup|dd|details|dialog|dir|div|dl|dt|fieldset|figcaption|figure|'
    'footer|form|frame|frameset|h[1-6]|head|header|hr|html|iframe|legend|li|'
    'link|main|menu|menuitem|nav|noframes|ol|optgroup|option|p|param|search|'
    'section|summary|table|tbody|td|tfoot|th|thead|title|tr|track|ul'
)
_HTML_BLOCK_START = re.compile(rf'</?(?:{_BLOCK_TAGS})(?:[ \t>]|/>|$)', re.IGNORECASE)
_HTML_TAG_LINE = re.compile(
    r'(?:<[A-Za-z][A-Za-z0-9-]*(?:\s[^<>]*)?/?>|</[A-Za-z][A-Za-z0-9-]*\s*>)[ \t]*$'
)


def _inline_runs(source: str) -> Iterator[_Run]:
    raw_lines = list(_raw_lines(source))
    paragraph: list[_Line] = []
    paragraph_depth = 0
    fence: _Fence | None = None
    # '-->' while inside an HTML comment, '' inside an HTML block that a blank
    # line ends.
    html_end: str | None = None
    in_table = False
    skip_delimiter = False
    list_items: list[_ListItem] = []
    # An item whose marker line held nothing else, until the line after it.
    empty_item: _ListItem | None = None
    for index, (line_start, raw) in enumerate(raw_lines):
        if skip_delimiter:
            skip_delimiter = False
            continue
        if fence is not None:
            fenced = _fence_content(fence, raw)
            if fenced is not None:
                if _closes(fence, fenced):
                    fence = None
                continue
            fence = None
        depth, prefix = _quote_prefix(raw, None)
        content = raw[prefix:]
        line = _Line(line_start + prefix, content, line_start + len(raw))
        if html_end == '-->':
            if '-->' in content:
                html_end = None
            continue
        if html_end == '' and content.strip():
            continue
        html_end = None
        # A line ends the list items it is not indented into, or whose quote
        # it leaves — unless it continues a paragraph lazily, which keeps them.
        # A quote marker outside an item it ends opens a new quote instead.
        open_items = list_items
        list_items = [o for o in open_items if _holds(o, raw, depth)]
        if not content.strip():
            # An item can begin with at most one blank line: its marker line.
            list_items = [o for o in list_items if o is not empty_item]
            empty_item = None
            yield from _paragraph_run(paragraph)
            paragraph = []
            in_table = False
            continue
        empty_item = None
        chars, columns = _leading(content)
        ended = [o for o in open_items if o not in list_items]
        may_be_lazy = all(o.quote_depth >= depth for o in ended)
        base = max((o.column for o in list_items if o.quote_depth == depth), default=0)
        relative = columns - base
        rest = content[chars:]
        if paragraph and depth > paragraph_depth:
            yield from _paragraph_run(paragraph)
            paragraph = []
        block_start = relative <= 3
        # A line outside the paragraph's item or quote continues it only
        # lazily: it is no setext underline, starts no table, and any list
        # item may interrupt it.
        lazy = bool(ended) or depth < paragraph_depth
        # A list item, or a blockquote opened inside one, holds blocks of its
        # own: open each container, then read what follows it as a line.
        opened_item: _ListItem | None = None
        while block_start:
            interrupts = bool(paragraph) and not lazy
            if item := _list_item(rest, interrupts_paragraph=interrupts):
                gap = len(item.group(2))
                taken = gap if gap <= 4 else 1
                width = len(item.group(1)) + taken
                base = columns + len(item.group(1)) + (taken or 1)
                opened_item = _ListItem(depth, base)
                list_items = [
                    *(
                        o
                        for o in list_items
                        if o.quote_depth < depth or o.column <= columns
                    ),
                    opened_item,
                ]
            elif quote := _BLOCKQUOTE_MARKER.match(rest):
                width, base, depth = quote.end(), 0, depth + 1
                lazy = bool(ended) or depth < paragraph_depth
                opened_item = None
            else:
                break
            # A quote marker under a list item continues that quote's paragraph.
            if item or depth > paragraph_depth or not paragraph:
                yield from _paragraph_run(paragraph)
                paragraph, paragraph_depth, in_table = [], depth, False
            offset = line.start + len(line.content) - len(rest) + width
            line = _Line(offset, rest[width:], line.end)
            content = line.content
            chars, relative = _leading(content)
            columns = base + relative
            rest = content[chars:]
            block_start = relative <= 3
        if not rest:
            empty_item = opened_item
            continue
        if relative >= 4 and not paragraph and not in_table:
            continue
        if block_start and (opening := _FENCE_OPEN.match(rest)):
            yield from _paragraph_run(paragraph)
            paragraph, in_table = [], False
            fence = _Fence(opening.group()[0], len(opening.group()), base, depth)
            continue
        if block_start and rest.startswith('<!--'):
            yield from _paragraph_run(paragraph)
            paragraph = []
            html_end = None if '-->' in rest[4:] else '-->'
            continue
        if block_start and (
            _HTML_BLOCK_START.match(rest)
            or (not paragraph and _HTML_TAG_LINE.match(rest))
        ):
            yield from _paragraph_run(paragraph)
            paragraph, html_end = [], ''
            continue
        if block_start and _ATX_HEADING.match(rest):
            yield from _paragraph_run(paragraph)
            paragraph, in_table = [], False
            yield _Run.of_lines([line])
            continue
        if block_start and paragraph and not lazy and _SETEXT_UNDERLINE.match(rest):
            yield from _paragraph_run(paragraph)
            paragraph = []
            continue
        if block_start and _THEMATIC_BREAK.match(rest):
            yield from _paragraph_run(paragraph)
            paragraph, in_table = [], False
            continue
        if in_table:
            yield from _cell_runs(line)
            continue
        if (
            block_start
            and not (paragraph and lazy)
            and _starts_table(content, raw_lines, index)
        ):
            yield from _paragraph_run(paragraph)
            paragraph, in_table, skip_delimiter = [], True, True
            yield from _cell_runs(line)
            continue
        if paragraph and not may_be_lazy:
            yield from _paragraph_run(paragraph)
            paragraph = []
        if paragraph:
            list_items = open_items
        else:
            paragraph_depth = depth
        paragraph.append(line)
    yield from _paragraph_run(paragraph)


def _list_item(rest: str, *, interrupts_paragraph: bool) -> re.Match[str] | None:
    """A list marker opening `rest`, unless the line is a thematic break or a
    setext underline, which win over it. Only an item that holds text, and an
    ordered one only from 1, interrupts a paragraph."""
    item = _LIST_ITEM.match(rest)
    if item is None or _THEMATIC_BREAK.match(rest):
        return None
    number = item.group(1)[:-1]
    if interrupts_paragraph and (
        _SETEXT_UNDERLINE.match(rest)
        or not rest[item.end() :].strip()
        or (number and int(number) != 1)
    ):
        return None
    return item


def _holds(item: _ListItem, raw: str, depth: int) -> bool:
    """Whether the line stays in the list item: inside the item's quote, and
    blank or indented into it there — a quote opened in the item counts as
    indent, so a bare `>` outside the item ends it."""
    if item.quote_depth > depth:
        return False
    _, prefix = _quote_prefix(raw, item.quote_depth)
    inside = raw[prefix:]
    return not inside.strip() or _leading(inside)[1] >= item.column


def _raw_lines(source: str) -> Iterator[tuple[int, str]]:
    """Each line's start offset and text, without its `\\n` or `\\r\\n`."""
    start = 0
    while start < len(source):
        newline = source.find('\n', start)
        stop = len(source) if newline == -1 else newline + 1
        yield start, source[start:stop].removesuffix('\n').removesuffix('\r')
        start = stop


def _quote_prefix(raw: str, limit: int | None) -> tuple[int, int]:
    """How many blockquote markers open the line, and where its content
    starts. Inside a fence, only the fence's own markers are containers."""
    depth = position = 0
    while (limit is None or depth < limit) and (
        marker := _BLOCKQUOTE_MARKER.match(raw, position)
    ):
        depth, position = depth + 1, marker.end()
    return depth, position


def _leading(content: str) -> tuple[int, int]:
    """The leading whitespace as characters, and as columns (a tab reaches the
    next multiple of 4)."""
    columns = chars = 0
    for char in content:
        if char == ' ':
            columns += 1
        elif char == '\t':
            columns += 4 - columns % 4
        else:
            break
        chars += 1
    return chars, columns


def _fence_content(fence: _Fence, raw: str) -> str | None:
    """The line inside the fence's containers, or None when the line ends one
    of them, and the fence with it: a quote it leaves out, or a list item it
    is not indented into."""
    depth, prefix = _quote_prefix(raw, fence.quote_depth)
    content = raw[prefix:]
    if depth < fence.quote_depth or (
        content.strip() and _leading(content)[1] < fence.base
    ):
        return None
    return content


def _closes(fence: _Fence, content: str) -> bool:
    chars, columns = _leading(content)
    rest = content[chars:]
    run = len(rest) - len(rest.lstrip(fence.char))
    return columns - fence.base <= 3 and run >= fence.width and not rest[run:].strip()


def _starts_table(content: str, raw_lines: list[tuple[int, str]], index: int) -> bool:
    if '|' not in content or index + 1 >= len(raw_lines):
        return False
    _, next_raw = raw_lines[index + 1]
    _, prefix = _quote_prefix(next_raw, None)
    delimiter = next_raw[prefix:]
    return bool(_DELIMITER_ROW.match(delimiter)) and len(_cell_bounds(content)) == len(
        _cell_bounds(delimiter)
    )


def _paragraph_run(lines: list[_Line]) -> Iterator[_Run]:
    if lines:
        yield _Run.of_lines(lines)


def _cell_runs(line: _Line) -> Iterator[_Run]:
    for start, end in _cell_bounds(line.content):
        cell = _Line(line.start + start, line.content[start:end], line.start + end)
        yield _Run.of_lines([cell], in_table_row=True)


def _cell_bounds(content: str) -> list[Span]:
    """Each cell's span in a table row: split on the pipes no backslash
    escapes — GFM applies that inside code spans too — with the row's outer
    pipes left out."""
    pipes = [
        index
        for index, char in enumerate(content)
        if char == '|' and _backslashes_before(content, index) % 2 == 0
    ]
    edges = [-1, *pipes, len(content)]
    bounds = [(left + 1, right) for left, right in itertools.pairwise(edges)]
    if bounds and not content[: bounds[0][1]].strip():
        bounds = bounds[1:]
    if bounds and not content[bounds[-1][0] :].strip():
        bounds = bounds[:-1]
    return bounds


def _backslashes_before(text: str, index: int) -> int:
    count = 0
    while index - count > 0 and text[index - count - 1] == '\\':
        count += 1
    return count


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
            index = code_span_end(text, index) or backtick_run_end(text, index)
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
        end=run.offsets[destination.close] + 1,
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
