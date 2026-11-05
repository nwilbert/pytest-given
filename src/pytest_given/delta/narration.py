"""Two narrations compared as they read, and diffed by word.

A narration is read into tokens: words, the spaces between them, and the
pieces a diff keeps whole — inline Markdown spans, links, placeholders and term
refs. Two tokens compare by what a reader sees, not by how the part was
authored.
"""

import re
from collections import Counter
from collections.abc import Callable, Iterable, Iterator, Sequence
from dataclasses import dataclass, field, replace
from functools import lru_cache
from itertools import groupby
from typing import Literal

from ..markdown import CodeSpan, EmphasisSpan, PlainSpan, located_spans
from ..model import (
    DiffSegment,
    Glossary,
    GlossaryTerm,
    Mark,
    Narration,
    NarrationLiteral,
    NarrationPart,
    NarrationPlaceholder,
    NarrationTermRef,
    NarrationValue,
    TermId,
    l_form,
    merged_literals,
    parts_in_context,
    s_form,
)
from .lcs import lcs_gaps, lcs_pairs


@dataclass(frozen=True)
class Reading:
    """How one side's narration is read for comparison."""

    glossary: Glossary | None
    term_id: Callable[[TermId], TermId]  # the before side's goes through renames
    column: Callable[[NarrationPlaceholder], str]  # the key a placeholder compares by


def same_term_id(term_id: TermId) -> TermId:
    """The after side's `Reading.term_id`: its refs need no rename."""
    return term_id


def placeholder_name(placeholder: NarrationPlaceholder) -> str:
    return placeholder.name


type TokenKind = Literal[
    'word', 'space', 'code', 'emphasis', 'link', 'placeholder', 'term'
]
type WordKey = tuple[TokenKind, str]
type TokenBucket = tuple[tuple[TokenKind, str], ...]


@dataclass(frozen=True)
class Token:
    kind: TokenKind
    key: str  # word / span source / column key / rewritten term id
    forms: frozenset[str] = frozenset()  # a term ref's; none: `display` compares
    display: str = ''
    parts: tuple[NarrationPart, ...] = field(default=(), compare=False)


def tokens(narration: Narration, reading: Reading) -> list[Token]:
    """Each literal is read with its neighbouring parts' text as context, as
    `model.read_narration` reads it, so a span never crosses into a value."""
    read: list[Token] = []
    for part, before, after in parts_in_context(narration):
        if isinstance(part, NarrationLiteral):
            read.extend(_literal_tokens(part.value, before, after))
        elif isinstance(part, NarrationValue):
            read.extend(_value_tokens(part))
        else:
            read.append(_interpolated_token(part, reading))
    return read


def tokens_equal(a: Token, b: Token) -> bool:
    if a.kind != b.kind:
        return False
    if a.kind == 'space':
        return True
    if a.key != b.key:
        return False
    if a.kind == 'term':
        if a.forms or b.forms:
            return bool(a.forms & b.forms)
        return a.display == b.display
    return True


def narrations_equal(a: Narration, ra: Reading, b: Narration, rb: Reading) -> bool:
    return token_lists_equal(tokens(a, ra), tokens(b, rb))


def token_lists_equal(tokens_a: Sequence[Token], tokens_b: Sequence[Token]) -> bool:
    return len(tokens_a) == len(tokens_b) and all(
        map(tokens_equal, tokens_a, tokens_b, strict=True)
    )


def token_bucket(read: Sequence[Token]) -> TokenBucket:
    """A hashable key that two equal token lists always share; equal keys can
    still differ in a space's width or a term ref's form."""
    return tuple(
        (token.kind, '' if token.kind == 'space' else token.key) for token in read
    )


def similarity(words_a: Sequence[Token], words_b: Sequence[Token]) -> float:
    """The share of `reading_words` the two have in common: 1.0 for the same
    words, 0.0 for none shared."""
    if not words_a and not words_b:
        return 1.0
    shared = len(lcs_pairs(words_a, words_b, tokens_equal))
    return 2 * shared / (len(words_a) + len(words_b))


def reading_words(narration: Narration, reading: Reading) -> list[Token]:
    return words_of(tokens(narration, reading))


def words_of(read: Iterable[Token]) -> list[Token]:
    return [token for token in read if token.kind != 'space']


def word_counts(words: Iterable[Token]) -> Counter[WordKey]:
    """Two words can be equal only with the same kind and key."""
    return Counter((word.kind, word.key) for word in words)


def word_diff(
    a: Narration, ra: Reading, b: Narration, rb: Reading
) -> tuple[DiffSegment, ...]:
    """Runs of equal, removed and added tokens; a replaced stretch reads
    removed, then added. Each run holds each side's own tokens, so either
    side reads back whole."""
    return token_diff(tokens(a, ra), tokens(b, rb))


def token_diff(
    tokens_a: Sequence[Token], tokens_b: Sequence[Token]
) -> tuple[DiffSegment, ...]:
    return tuple(
        _segment(mark, [pair for _, pair in ops])
        for mark, ops in groupby(_ops(tokens_a, tokens_b), key=lambda op: op[0])
    )


def term_forms(display: str, term: GlossaryTerm | None) -> frozenset[str]:
    """The handle forms of `term` that read as `display`: none for an instance,
    an inflection, or a term the glossary lacks."""
    if term is None:
        return frozenset()
    canonical = term.canonical
    spelled = {
        'bare': canonical,
        'l': l_form(canonical),
        's': s_form(canonical),
        'l.s': s_form(l_form(canonical)),
    }
    return frozenset(form for form, text in spelled.items() if text == display)


# A Markdown link, read whole inside plain text.
_LINK = re.compile(r'\[[^\[\]]+\]\([^()\s]+\)')
_SPACES = re.compile(r'(\s+)')


def _value_tokens(value: NarrationValue) -> Iterator[Token]:
    """Read by word, as a literal reading the same is: each word keeps the
    value it is a piece of."""
    for kind, piece in _pieces(value.rendered):
        yield Token(kind, piece, parts=(replace(value, rendered=piece),))


def _interpolated_token(
    part: NarrationPlaceholder | NarrationTermRef, reading: Reading
) -> Token:
    match part:
        case NarrationPlaceholder():
            return Token('placeholder', reading.column(part), parts=(part,))
        case NarrationTermRef(term_id=term_id, display=display):
            glossary = reading.glossary
            term = glossary.get(term_id) if glossary is not None else None
            return Token(
                'term',
                reading.term_id(term_id),
                forms=term_forms(display, term),
                display=display,
                parts=(part,),
            )


@lru_cache(maxsize=8192)
def _literal_tokens(text: str, before: str, after: str) -> tuple[Token, ...]:
    """Cached: an unchanged literal is read on both sides, and many recur across
    a suite's scenarios."""
    read: list[Token] = []
    for span, chars in located_spans(text, before=before, after=after):
        source = text[chars.start : chars.stop]
        match span:
            case CodeSpan():
                read.append(_literal('code', source))
            case EmphasisSpan():
                read.append(_literal('emphasis', source))
            case PlainSpan():
                read.extend(_plain_tokens(source))
    return tuple(read)


def _plain_tokens(text: str) -> Iterator[Token]:
    end = 0
    for link in _LINK.finditer(text):
        yield from _word_tokens(text[end : link.start()])
        yield _literal('link', link.group())
        end = link.end()
    yield from _word_tokens(text[end:])


def _word_tokens(text: str) -> Iterator[Token]:
    for kind, piece in _pieces(text):
        yield _literal(kind, piece)


def _pieces(text: str) -> Iterator[tuple[TokenKind, str]]:
    for piece in _SPACES.split(text):
        if piece:
            yield ('space' if piece.isspace() else 'word'), piece


def _literal(kind: TokenKind, source: str) -> Token:
    return Token(kind, source, parts=(NarrationLiteral(value=source),))


type _Op = tuple[Mark, _Pair]


@dataclass(frozen=True)
class _Pair:
    """A token of the diff, with its before and after reading when equal."""

    before: Token | None
    after: Token | None


def _ops(tokens_a: Sequence[Token], tokens_b: Sequence[Token]) -> Iterator[_Op]:
    """Each token marked, every gap between matches read removed-then-added."""
    for gap_a, gap_b, anchor in lcs_gaps(tokens_a, tokens_b, tokens_equal):
        for index in gap_a:
            yield 'removed', _Pair(tokens_a[index], None)
        for index in gap_b:
            yield 'added', _Pair(None, tokens_b[index])
        if anchor is not None:
            yield 'equal', _Pair(tokens_a[anchor[0]], tokens_b[anchor[1]])


def _segment(mark: Mark, pairs: list[_Pair]) -> DiffSegment:
    return DiffSegment(
        mark=mark,
        before=_parts([pair.before for pair in pairs if pair.before]),
        after=_parts([pair.after for pair in pairs if pair.after]),
    )


def _parts(shown: list[Token]) -> tuple[NarrationPart, ...]:
    """A value's adjacent words joined back into one value."""
    joined: list[NarrationPart] = []
    for part in merged_literals(part for token in shown for part in token.parts):
        last = joined[-1] if joined else None
        if (
            isinstance(part, NarrationValue)
            and isinstance(last, NarrationValue)
            and replace(last, rendered=part.rendered) == part
        ):
            joined[-1] = replace(last, rendered=last.rendered + part.rendered)
        else:
            joined.append(part)
    return tuple(joined)
