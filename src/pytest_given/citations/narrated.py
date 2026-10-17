"""Narrated citations in a document: a `<details>` block whose summary holds a
scenario citation written as HTML, with the spans `citations update` rewrites.
"""

import functools
import itertools
import re
from collections.abc import Collection, Iterator
from dataclasses import dataclass
from typing import NamedTuple

from ..markdown import LINE_BREAK, HtmlBlock, Span, TextRun, html_blocks
from .markdown_links import (
    ATTRIBUTE_TOKEN,
    VARIATION_SELECTOR,
    Glyph,
    fragment_offset,
    resolved,
)


@dataclass(frozen=True, kw_only=True)
class NarratedCitation:
    """`body` is the lines between the summary and the closing tag past
    `prefix`, a blank container line read as empty, joined by `\n`: a filled
    block reads `'\n' + narration + '\n'`, a freshly copied one `''`.
    `body_span` is those whole source lines, zero-width at the `</details>`
    line when the block holds its own. `markdown` is the opening tag's
    attribute value, `''` bare and None without it; `markdown_attribute` its
    span in the tag, leading whitespace included, or zero-width past
    `<details`."""

    line: int
    glyph: Glyph
    opening_tag: str
    opening_tag_span: Span
    markdown: str | None
    markdown_attribute: Span
    href: str
    href_span: Span
    text: str
    text_span: Span
    body: str
    body_span: Span
    prefix: str

    @property
    def destination(self) -> str:
        """`href` with its character references resolved."""
        return _resolve(self.href)

    @property
    def fragment_span(self) -> Span | None:
        """Past the first `#` that `destination` reads, however written."""
        offset = fragment_offset(self.href, ATTRIBUTE_TOKEN)
        return (
            None if offset is None else (self.href_span[0] + offset, self.href_span[1])
        )

    def written_body(self, body: str, line_break: str) -> str:
        """The source lines `body` reads back from."""
        return ''.join(
            f'{self.prefix + line if line else self.prefix.rstrip()}{line_break}'
            for line in body.split('\n')
        )


@dataclass(frozen=True, kw_only=True)
class LooseDetails:
    """A `<details>` block that cites into the report in no shape a narrated
    citation takes. `offset` places its `<a>` in the source."""

    line: int
    offset: int
    href: str
    reason: str


def scan_narrated(
    source: str, glyphs: Collection[str]
) -> list[NarratedCitation | LooseDetails]:
    """In document order. A `<details>` line inside a larger HTML block is
    read as a block of its own, so its citation is never missed."""
    patterns = _patterns(tuple(sorted(glyphs, key=len, reverse=True)))
    blocks = html_blocks(source)
    found: list[NarratedCitation | LooseDetails] = []
    for index, block in enumerate(blocks):
        first, *buried = _pieces(block.run)
        if _OPENS.match(first.text):
            read = _read(source, blocks, index, first, patterns, bool(buried))
        elif _SUMMARY_OPENS.match(first.text):
            read = _loose(first, patterns, _CUT_OFF)
        else:
            read = None
        if read:
            found.append(read)
        found.extend(
            loose for piece in buried if (loose := _loose(piece, patterns, _BURIED))
        )
    return found


_OPENS = re.compile(r'<details(?=[\s>])', re.IGNORECASE)
_DETAILS_LINE = re.compile(r'\n(?=<details[\s>])', re.IGNORECASE)
_SUMMARY_OPENS = re.compile(r'<summary(?=[\s>])', re.IGNORECASE)
_CLOSES = re.compile(r'</details\s*>', re.IGNORECASE)
_ANCHOR = re.compile(r'<a\b[^>]*>', re.IGNORECASE)
_ANCHOR_CLOSES = re.compile(r'</a\s*>', re.IGNORECASE)
_SUMMARY_CLOSES = re.compile(r'</summary\s*>', re.IGNORECASE)
# One attribute, read in sequence from a tag's name on, so a quoted value is
# never read as attributes.
_ATTRIBUTE = re.compile(
    r"""\s+(?P<name>[A-Za-z_:][\w.:-]*)"""
    r"""(?:\s*=\s*(?P<value>"[^"]*"|'[^']*'|[^\s"'=<>`]+))?"""
)

_BURIED = 'a blank line must separate it from the HTML above it'
_CUT_OFF = (
    "its <summary> is separated from <details> by a blank line or a list item's "
    "or quote's edge"
)
_NOT_THE_SHAPE = 'its summary is not the glyph, a space and the link alone'


class _Patterns(NamedTuple):
    shape: re.Pattern[str]
    # A citation's opening up to its `<a>`, as the shape takes it.
    head: re.Pattern[str]
    summary_glyph: re.Pattern[str]


@functools.cache
def _patterns(longest_first: tuple[str, ...]) -> _Patterns:
    glyph = '|'.join(map(re.escape, longest_first)) or '(?!)'
    head = (
        r'(?P<tag><details(?:\s[^>]*)?>)\s*<summary>'
        rf'\s*(?P<glyph>(?:{glyph}){VARIATION_SELECTOR}?)\s+'
    )
    shape = re.compile(
        head + r'<a href="(?P<href>[^"\n]*)">(?P<text>(?:(?!</a>).)*)</a>'
        # A closing tag the block holds starts its own line, where an update
        # writes the body above it.
        r'\s*</summary>(?:[ \t]*(?:\r\n?|\n)\s*(?P<close></details\s*>))?\s*\Z',
        re.IGNORECASE | re.DOTALL,
    )
    return _Patterns(
        shape,
        re.compile(head + r'\Z', re.IGNORECASE),
        re.compile(rf'<summary[^>]*>\s*(?:{glyph})', re.IGNORECASE),
    )


def _pieces(run: TextRun) -> list[TextRun]:
    """The run split before each line past its first that opens a `<details>`."""
    starts = [0, *(line.end() for line in _DETAILS_LINE.finditer(run.text))]
    if len(starts) == 1:
        return [run]
    ends = [start - 1 for start in starts[1:]] + [len(run.text)]
    return [run.slice(start, end) for start, end in zip(starts, ends, strict=True)]


def _read(
    source: str,
    blocks: list[HtmlBlock],
    index: int,
    run: TextRun,
    patterns: _Patterns,
    holds_more: bool,
) -> NarratedCitation | LooseDetails | None:
    """`run` is the block's first piece; `holds_more`, whether others follow."""
    parts = patterns.shape.match(run.text)
    if parts is None:
        return _loose(run, patterns)

    def loose(reason: str) -> LooseDetails:
        return LooseDetails(
            line=run.line_at(parts.start('href')),
            offset=run.offsets[parts.start('href')],
            href=_resolve(parts['href']),
            reason=reason,
        )

    block = blocks[index]
    if parts['close']:
        return _citation(source, block, run, parts, None)
    if holds_more:
        return loose('a blank line must follow its </summary>')
    closing = _closing(blocks, index)
    if closing is None:
        return loose('no </details> closes it')
    if not _closing_line(closing.run.text):
        return loose('text follows its </details>')
    return _citation(source, block, run, parts, closing)


def _closing(blocks: list[HtmlBlock], opening: int) -> HtmlBlock | None:
    for block in itertools.islice(blocks, opening + 1, None):
        if block.container != blocks[opening].container:
            continue
        if _CLOSES.match(block.run.text):
            return block
        if _OPENS.match(block.run.text):
            return None
    return None


def _closing_line(text: str) -> bool:
    """Whether `text` starts with a `</details>` line holding nothing else."""
    closes = _CLOSES.match(text)
    return closes is not None and not text[closes.end() :].split('\n', 1)[0].strip()


def _citation(
    source: str,
    block: HtmlBlock,
    run: TextRun,
    parts: re.Match[str],
    closing: HtmlBlock | None,
) -> NarratedCitation:
    if closing is None:
        line_start = block.line_starts[run.line_at(parts.start('close')) - run.line]
        body, body_span = '', (line_start, line_start)
    else:
        body_span = (block.end, closing.line_starts[0])
        body = _body(source[slice(*body_span)], block.prefix)
    tag = parts['tag']
    markdown = next(
        (
            attribute
            for attribute in _attributes(tag, len('<details'))
            if attribute['name'].lower() == 'markdown'
        ),
        None,
    )
    return NarratedCitation(
        line=run.line_at(parts.start('href')),
        glyph=Glyph(parts['glyph'], run.span(*parts.span('glyph'))),
        opening_tag=tag,
        opening_tag_span=run.span(*parts.span('tag')),
        markdown=None if markdown is None else _unquoted(markdown['value'] or ''),
        markdown_attribute=(
            (len('<details'), len('<details')) if markdown is None else markdown.span()
        ),
        href=parts['href'],
        href_span=run.span(*parts.span('href')),
        text=parts['text'],
        text_span=run.span(*parts.span('text')),
        body=body,
        body_span=body_span,
        prefix=block.prefix,
    )


def _body(region: str, prefix: str) -> str:
    lines = LINE_BREAK.split(region)
    if not lines[-1]:
        lines.pop()
    return '\n'.join(_past_prefix(line, prefix) for line in lines)


def _past_prefix(line: str, prefix: str) -> str:
    if line.startswith(prefix):
        return line[len(prefix) :]
    return '' if line == prefix.rstrip() else line


def _loose(
    run: TextRun, patterns: _Patterns, reason: str | None = None
) -> LooseDetails | None:
    """The run's citing summary, if it has one, as loose: for `reason`, or
    for what keeps it from a narrated citation's shape."""
    text = run.text
    summary = patterns.summary_glyph.search(text)
    anchor = _ANCHOR.search(text, summary.end()) if summary else None
    href = _href(anchor.group()) if anchor else None
    if anchor is None or href is None:
        return None
    return LooseDetails(
        line=run.line_at(anchor.start()),
        offset=run.offsets[anchor.start()],
        href=_resolve(_unquoted(href['value'])),
        reason=reason or _mistyped(text, anchor, patterns.head),
    )


def _href(anchor: str) -> re.Match[str] | None:
    return next(
        (
            attribute
            for attribute in _attributes(anchor, len('<a'))
            if attribute['name'].lower() == 'href' and attribute['value']
        ),
        None,
    )


def _mistyped(text: str, anchor: re.Match[str], head: re.Pattern[str]) -> str:
    """The first part, in reading order, where a block that starts as a
    narrated citation leaves its shape."""
    if not head.match(text[: anchor.start()]):
        return _NOT_THE_SHAPE
    names = [attribute['name'].lower() for attribute in _attributes(anchor.group(), 2)]
    if names != ['href']:
        return 'its <a> takes attributes besides href'
    href = _href(anchor.group())
    if href is None or not href['value'].startswith('"'):
        return 'its href is not in double quotes'
    anchor_closes = _ANCHOR_CLOSES.search(text, anchor.end())
    if anchor_closes is None:
        return _NOT_THE_SHAPE
    summary_closes = _SUMMARY_CLOSES.search(text, anchor_closes.end())
    in_summary_end = len(text) if summary_closes is None else summary_closes.start()
    if text[anchor_closes.end() : in_summary_end].strip():
        return 'text follows </a>'
    if summary_closes is None:
        return _NOT_THE_SHAPE
    summary_line, _, below = text[summary_closes.end() :].partition('\n')
    if _CLOSES.match(summary_line.strip()):
        return 'its </details> is not on a line of its own'
    if not below.strip() or summary_line.strip():
        return _NOT_THE_SHAPE
    if not _CLOSES.match(below):
        return 'a blank line must follow its </summary>'
    if not _closing_line(below):
        return 'text follows its </details>'
    return 'a blank line must follow its </details>'


def _attributes(tag: str, start: int) -> Iterator[re.Match[str]]:
    """The tag's attributes, from `start` just past its name."""
    position = start
    while attribute := _ATTRIBUTE.match(tag, position):
        yield attribute
        position = attribute.end()


def _unquoted(value: str) -> str:
    return value[1:-1] if value[:1] in ('"', "'") else value


def _resolve(value: str) -> str:
    return resolved(value, ATTRIBUTE_TOKEN)
