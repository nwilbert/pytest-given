"""The inline subset titles, steps and definitions are written in: plain text,
code spans, and bold or italic holding only those. It departs from CommonMark
on purpose — underscores never format — so it is read here, not by
markdown-it. One reader, so text reads alike wherever it is unwrapped,
rendered or written back."""

import re
from collections.abc import Iterator
from dataclasses import dataclass


@dataclass(frozen=True)
class PlainSpan:
    text: str


@dataclass(frozen=True)
class CodeSpan:
    text: str


@dataclass(frozen=True)
class EmphasisSpan:
    strong: bool
    content: tuple[PlainSpan | CodeSpan, ...]


type InlineSpan = PlainSpan | CodeSpan | EmphasisSpan


def read_spans(text: str, *, before: str = '', after: str = '') -> list[InlineSpan]:
    """`text` as plain text, code spans, and bold or italic holding only those.
    `before` and `after`, the neighbouring text, flank its edges unread."""
    return [span for span, _ in located_spans(text, before=before, after=after)]


def located_spans(
    text: str, *, before: str = '', after: str = ''
) -> Iterator[tuple[InlineSpan, range]]:
    """Each span `read_spans` reads, with the characters of `text` it spans."""
    if '*' not in text and '`' not in text:
        yield from _located_plain(text, 0, len(text))
        return
    # A marker before the text stays one, so no span opens to touch it.
    prefix = before[-1:] if before.endswith(('*', '`')) else _neighbour(before[-1:])
    padded = f'{prefix}{text}{_neighbour(after[:1])}'
    end = 0
    for match in _SPAN.finditer(padded, len(prefix)):
        start = match.start() - len(prefix)
        yield from _located_plain(text, end, start)
        end = match.end() - len(prefix)
        code, strong, italic = match.groups()
        if code is not None:
            yield CodeSpan(code[1:-1]), range(start, end)
        else:
            inner = strong if strong is not None else italic
            assert inner is not None
            span = EmphasisSpan(strong is not None, tuple(_code_spans(inner)))
            yield span, range(start, end)
    yield from _located_plain(text, end, len(text))


# A lone backtick, never one of a run, so no two code spans touch.
_CODE_SPAN = r'(?<!`)`[^`]+`(?!`)'
# A letter or digit; CommonMark counts `_` as punctuation.
_ALNUM = r'[^\W_]'


def _emphasis(marker: str, content: str) -> str:
    """Two `marker`s, each a whole run of `*`, flanked as CommonMark flanks
    them. Content holding no marker that could close keeps the reader linear."""
    escaped = re.escape(marker)
    opener = rf'(?<!\*)(?:(?<!{_ALNUM}){escaped}(?=[^\s*])|{escaped}(?={_ALNUM}))'
    closer = rf'(?:(?<={_ALNUM}){escaped}|(?<=[^\s*]){escaped}(?!{_ALNUM}))(?!\*)'
    # A code span binds tighter: it is taken whole, and no other backtick opens one.
    unmarked = rf'{_CODE_SPAN}|[^*`]|(?!{_CODE_SPAN})`'
    return rf'{opener}((?:{unmarked}|{content})+?){closer}'


# Bold content may hold a lone `*`; either may hold a marker between spaces,
# which opens and closes nothing. Underscores never format.
_SPAN = re.compile(
    f'({_CODE_SPAN})|'
    + _emphasis('**', r'(?<!\*)\*(?!\*)|(?<=\s)\*\*(?=\s)')
    + '|'
    + _emphasis('*', r'(?<=\s)\*(?=\s)'),
    re.DOTALL,
)
_CODE = re.compile(_CODE_SPAN)


def _neighbour(char: str) -> str:
    """A neighbouring character as one of its class no span can take:
    whitespace (or none), a letter or digit, or punctuation."""
    if not char or char.isspace():
        return ' '
    return 'a' if char.isalnum() else '.'


def _code_spans(text: str) -> list[PlainSpan | CodeSpan]:
    spans: list[PlainSpan | CodeSpan] = []
    end = 0
    for match in _CODE.finditer(text):
        spans.extend(_plain(text[end : match.start()]))
        spans.append(CodeSpan(match.group()[1:-1]))
        end = match.end()
    spans.extend(_plain(text[end:]))
    return spans


def _plain(text: str) -> list[PlainSpan]:
    return [PlainSpan(text)] if text else []


def _located_plain(
    text: str, start: int, end: int
) -> Iterator[tuple[InlineSpan, range]]:
    if start < end:
        yield PlainSpan(text[start:end]), range(start, end)
