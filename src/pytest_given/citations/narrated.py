"""Narrated citations in a document: a `<details>` block whose summary holds a
scenario citation written as HTML, with the spans `citations update` rewrites.
"""

import html
import re
from collections.abc import Collection
from dataclasses import dataclass
from html.entities import html5

from ..markdown import HtmlBlock, Span, html_blocks
from .markdown_links import VARIATION_SELECTOR, Glyph


@dataclass(frozen=True, kw_only=True)
class NarratedCitation:
    """`body` is the lines between the summary and the closing tag past
    `prefix`, a blank container line read as empty, joined by `\n`: a filled
    block reads `'\n' + narration + '\n'`, a freshly copied one `''`.
    `body_span` is those whole source lines, zero-width at the `</details>`
    line when the block holds its own."""

    line: int
    glyph: Glyph
    opening_tag: str
    opening_tag_span: Span
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
        for token in _REFERENCE_TOKEN.finditer(self.href):
            if _unescaped(token.group()) == '#':
                return (self.href_span[0] + token.end(), self.href_span[1])
        return None


@dataclass(frozen=True, kw_only=True)
class LooseDetails:
    """A `<details>` block that cites into the report in no shape a narrated
    citation takes."""

    line: int
    href: str
    reason: str


def scan_narrated(
    source: str, glyphs: Collection[str]
) -> list[NarratedCitation | LooseDetails]:
    longest_first = sorted(glyphs, key=len, reverse=True)
    glyph_pattern = '|'.join(map(re.escape, longest_first)) or '(?!)'
    shape = _shape(glyph_pattern)
    summary_glyph = re.compile(rf'<summary[^>]*>\s*(?:{glyph_pattern})', re.IGNORECASE)
    buried = re.compile(
        rf'\n<details(?:\s[^>]*)?>\s*<summary[^>]*>\s*(?:{glyph_pattern})',
        re.IGNORECASE,
    )
    blocks = html_blocks(source)
    found: list[NarratedCitation | LooseDetails] = []
    for index, block in enumerate(blocks):
        if _OPENS.match(block.run.text) and (
            read := _read(source, blocks, index, shape, summary_glyph)
        ):
            found.append(read)
        found.extend(_buried(block, buried))
    return found


_OPENS = re.compile(r'<details(?=[\s>])', re.IGNORECASE)
_CLOSES = re.compile(r'</details\s*>', re.IGNORECASE)
_SUMMARY_THEN_CLOSE = re.compile(r'</summary>[ \t]*</details\s*>', re.IGNORECASE)
_ANCHOR = re.compile(r'<a\b[^>]*>', re.IGNORECASE)
_PLAIN_ANCHOR = re.compile(r'<a href="[^"\n]*">', re.IGNORECASE)
_ANY_HREF = re.compile(
    r"""\bhref\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))""", re.IGNORECASE
)
_REFERENCE_TOKEN = re.compile(
    r'&(?:#[0-9]{1,7}|#[xX][0-9a-fA-F]{1,6}|[A-Za-z][A-Za-z0-9]{1,31});|.',
    re.DOTALL,
)
_LINE_BREAK = re.compile(r'\r\n|\r|\n')


def _shape(glyph_pattern: str) -> re.Pattern[str]:
    return re.compile(
        r'(?P<tag><details(?:\s[^>]*)?>)\s*<summary>'
        rf'\s*(?P<glyph>(?:{glyph_pattern}){VARIATION_SELECTOR}?)\s+'
        r'<a href="(?P<href>[^"\n]*)">(?P<text>(?:(?!</a>).)*)</a>'
        # A closing tag the block holds starts its own line, where an update
        # writes the body above it.
        r'\s*</summary>(?:[ \t]*(?:\r\n?|\n)\s*(?P<close></details\s*>))?\s*\Z',
        re.IGNORECASE | re.DOTALL,
    )


def _read(
    source: str,
    blocks: list[HtmlBlock],
    index: int,
    shape: re.Pattern[str],
    summary_glyph: re.Pattern[str],
) -> NarratedCitation | LooseDetails | None:
    block = blocks[index]
    parts = shape.match(block.run.text)
    if parts is None:
        return _loose(block, summary_glyph)
    closing = None if parts['close'] else _closing(blocks, index)
    if parts['close'] is None and closing is None:
        return LooseDetails(
            line=block.run.line_at(parts.start('href')),
            href=_resolve(parts['href']),
            reason='no </details> closes it',
        )
    return _citation(source, block, parts, closing)


def _buried(block: HtmlBlock, buried: re.Pattern[str]) -> list[LooseDetails]:
    """A citing `<details>` line past the block's first, which every reader
    takes for more of the block above it, not a block of its own."""
    text = block.run.text
    found: list[LooseDetails] = []
    for opening in buried.finditer(text):
        anchor = _ANCHOR.search(text, opening.end())
        href = _ANY_HREF.search(anchor.group()) if anchor else None
        if anchor and href:
            found.append(
                LooseDetails(
                    line=block.run.line_at(anchor.start()),
                    href=_href_value(href),
                    reason='a blank line must separate it from the HTML above it',
                )
            )
    return found


def _closing(blocks: list[HtmlBlock], opening: int) -> HtmlBlock | None:
    for block in blocks[opening + 1 :]:
        if block.container != blocks[opening].container:
            continue
        if _CLOSES.match(block.run.text):
            return block
        if _OPENS.match(block.run.text):
            return None
    return None


def _citation(
    source: str, block: HtmlBlock, parts: re.Match[str], closing: HtmlBlock | None
) -> NarratedCitation:
    run = block.run
    if closing is None:
        line_start = block.line_starts[run.line_at(parts.start('close')) - run.line]
        body, body_span = '', (line_start, line_start)
    else:
        body_span = (block.end, closing.line_starts[0])
        body = _body(source[slice(*body_span)], block.prefix)
    return NarratedCitation(
        line=run.line_at(parts.start('href')),
        glyph=Glyph(parts['glyph'], run.span(*parts.span('glyph'))),
        opening_tag=parts['tag'],
        opening_tag_span=run.span(*parts.span('tag')),
        href=parts['href'],
        href_span=run.span(*parts.span('href')),
        text=parts['text'],
        text_span=run.span(*parts.span('text')),
        body=body,
        body_span=body_span,
        prefix=block.prefix,
    )


def _body(region: str, prefix: str) -> str:
    lines = _LINE_BREAK.split(region)
    if not lines[-1]:
        lines.pop()
    return '\n'.join(_past_prefix(line, prefix) for line in lines)


def _past_prefix(line: str, prefix: str) -> str:
    if line.startswith(prefix):
        return line[len(prefix) :]
    return '' if line == prefix.rstrip() else line


def _loose(block: HtmlBlock, summary_glyph: re.Pattern[str]) -> LooseDetails | None:
    text = block.run.text
    cited = summary_glyph.search(text)
    anchor = _ANCHOR.search(text, cited.end()) if cited else None
    href = _ANY_HREF.search(anchor.group()) if anchor else None
    if anchor is None or href is None:
        return None
    if not _PLAIN_ANCHOR.fullmatch(anchor.group()):
        reason = 'its <a> takes attributes besides href'
    elif _after_anchor(text, anchor.end()).strip():
        reason = 'text follows </a>'
    elif _SUMMARY_THEN_CLOSE.search(text):
        reason = 'its </details> is not on a line of its own'
    else:
        reason = 'its summary is not the glyph, a space and the link alone'
    return LooseDetails(
        line=block.run.line_at(anchor.start()),
        href=_href_value(href),
        reason=reason,
    )


def _href_value(href: re.Match[str]) -> str:
    return _resolve(next(group for group in href.groups() if group is not None))


def _after_anchor(text: str, start: int) -> str:
    """What follows the anchor's closing tag, up to `</summary>`."""
    end = text.find('</a>', start)
    if end == -1:
        return ''
    return text[end + len('</a>') : text.find('</summary>', end)]


def _resolve(value: str) -> str:
    return ''.join(_unescaped(token) for token in _REFERENCE_TOKEN.findall(value))


def _unescaped(token: str) -> str:
    if token.startswith('&#'):
        return html.unescape(token)
    # Not `html.unescape`, which also reads `&notit;` as `¬it;`.
    return html5.get(token[1:], token) if token.startswith('&') else token
