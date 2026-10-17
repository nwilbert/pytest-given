"""Inline links in a Markdown document, with the source span of every part
`pytest-given citations update` may rewrite.

`markdown/` reads the block structure, placing each paragraph's, heading's and
table cell's text in the source. The inline links are read here, because no
Markdown parser reports where a link's text and destination, or the characters
around it, sit in the source — and an update must change those bytes and no
others.
"""

import html
import re
from collections.abc import Collection, Iterator
from dataclasses import dataclass
from html.entities import html5
from typing import NamedTuple

from ..markdown import (
    ASCII_PUNCTUATION,
    Span,
    TextRun,
    code_span_at,
    text_runs,
)

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
    trailing_run: TextRun
    in_table_row: bool
    glyph: Glyph | None

    @property
    def trailing(self) -> str:
        return self.trailing_run.text

    @property
    def end(self) -> int:
        """Just past the link's closing `)`."""
        return self.trailing_run.offsets[0]

    def trailing_span(self, start: int, end: int) -> Span:
        return self.trailing_run.span(start, end)

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
    longest_first = sorted(glyphs, key=len, reverse=True)
    return [
        link
        for run in text_runs(source)
        # A link's text always runs into its destination.
        if '](' in run.text
        for link in _links_in(run, longest_first)
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


def _links_in(run: TextRun, glyphs: list[str]) -> Iterator[MarkdownLink]:
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
                yield _link(run, opener.position, index, destination, glyphs)
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
    run: TextRun,
    open_index: int,
    close_index: int,
    destination: _Destination,
    glyphs: list[str],
) -> MarkdownLink:
    text = run.text
    after = destination.close + 1
    line_end = text.find('\n', after)
    next_line_end = -1 if line_end == -1 else text.find('\n', line_end + 1)
    trailing_end = len(text) if next_line_end == -1 else next_line_end
    return MarkdownLink(
        line=run.line_at(open_index),
        text=text[open_index + 1 : close_index],
        text_span=run.span(open_index + 1, close_index),
        url=text[destination.url_start : destination.url_end],
        url_span=run.span(destination.url_start, destination.url_end),
        trailing_run=run.slice(after, trailing_end),
        in_table_row=run.in_table_row,
        glyph=_glyph_before(run, open_index, glyphs),
    )


def _glyph_before(run: TextRun, open_index: int, glyphs: list[str]) -> Glyph | None:
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
