"""Two narrations compared as they read, and diffed by word.

A narration is read into tokens: words, the spaces between them, and the
pieces a diff keeps whole — inline Markdown spans, links, placeholders and term
refs. Two tokens compare by what a reader sees, not by how the part was
authored.
"""

import re
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, field
from itertools import groupby
from typing import Literal

from ..markdown import CodeSpan, EmphasisSpan, PlainSpan, located_spans
from ..model import (
    DiffSegment,
    Glossary,
    GlossaryTerm,
    InterpolatedPart,
    Mark,
    Narration,
    NarrationLiteral,
    NarrationPart,
    NarrationPlaceholder,
    NarrationTermRef,
    NarrationValue,
    TermId,
    l_form,
    narration_text,
    s_form,
)
from .lcs import lcs_pairs


@dataclass(frozen=True)
class Reading:
    """How one side's narration is read for comparison."""

    glossary: Glossary | None
    term_id: Callable[[TermId], TermId]  # the before side's goes through renames
    column: Callable[[NarrationPlaceholder], str]  # the key a placeholder compares by


type TokenKind = Literal[
    'word', 'space', 'code', 'emphasis', 'link', 'placeholder', 'term'
]


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
    parts = narration.parts or (NarrationLiteral(value=narration.text),)
    texts = [narration_text((part,)) for part in parts]
    whole = ''.join(texts)
    read: list[Token] = []
    end = 0
    for part, text in zip(parts, texts, strict=True):
        start, end = end, end + len(text)
        if isinstance(part, NarrationLiteral):
            before, after = whole[max(start - 1, 0) : start], whole[end : end + 1]
            read.extend(_literal_tokens(part.value, before, after))
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


def token_bucket(read: Sequence[Token]) -> tuple[tuple[TokenKind, str], ...]:
    """A hashable key that two equal token lists always share; equal keys can
    still differ in a space's width or a term ref's form."""
    return tuple(
        (token.kind, '' if token.kind == 'space' else token.key) for token in read
    )


def similarity(a: Narration, ra: Reading, b: Narration, rb: Reading) -> float:
    """The share of tokens the two have in common, spaces left out: 1.0 for
    the same words, 0.0 for none shared."""
    words_a, words_b = reading_words(a, ra), reading_words(b, rb)
    if not words_a and not words_b:
        return 1.0
    shared = len(lcs_pairs(words_a, words_b, tokens_equal))
    return 2 * shared / (len(words_a) + len(words_b))


def reading_words(narration: Narration, reading: Reading) -> list[Token]:
    return [token for token in tokens(narration, reading) if token.kind != 'space']


def word_diff(
    a: Narration, ra: Reading, b: Narration, rb: Reading
) -> tuple[DiffSegment, ...]:
    """Runs of equal, removed and added tokens; a replaced stretch reads
    removed, then added. Equal runs show the after side's tokens."""
    tokens_a, tokens_b = tokens(a, ra), tokens(b, rb)
    runs = _joined_spaces(
        [
            _Run(mark, [pair for _, pair in ops])
            for mark, ops in groupby(_ops(tokens_a, tokens_b), key=lambda op: op[0])
        ]
    )
    return tuple(
        DiffSegment(mark=run.mark, parts=_merged_literals(run.tokens)) for run in runs
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


def _interpolated_token(part: InterpolatedPart, reading: Reading) -> Token:
    match part:
        case NarrationValue(rendered=rendered):
            return Token('word', rendered, parts=(part,))
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


def _literal_tokens(text: str, before: str, after: str) -> Iterator[Token]:
    for span, chars in located_spans(text, before=before, after=after):
        source = text[chars.start : chars.stop]
        match span:
            case CodeSpan():
                yield _literal('code', source)
            case EmphasisSpan():
                yield _literal('emphasis', source)
            case PlainSpan():
                yield from _plain_tokens(source)


def _plain_tokens(text: str) -> Iterator[Token]:
    end = 0
    for link in _LINK.finditer(text):
        yield from _word_tokens(text[end : link.start()])
        yield _literal('link', link.group())
        end = link.end()
    yield from _word_tokens(text[end:])


def _word_tokens(text: str) -> Iterator[Token]:
    for piece in _SPACES.split(text):
        if piece:
            yield _literal('space' if piece.isspace() else 'word', piece)


def _literal(kind: TokenKind, source: str) -> Token:
    return Token(kind, source, parts=(NarrationLiteral(value=source),))


type _Op = tuple[Mark, _Pair]


@dataclass(frozen=True)
class _Pair:
    """A token of the diff, with its before and after reading when equal."""

    before: Token | None
    after: Token | None

    def shown(self, mark: Mark) -> Token:
        token = self.before if mark == 'removed' else self.after
        assert token is not None
        return token


@dataclass
class _Run:
    mark: Mark
    pairs: list[_Pair]

    @property
    def tokens(self) -> list[Token]:
        return [pair.shown(self.mark) for pair in self.pairs]


def _ops(tokens_a: list[Token], tokens_b: list[Token]) -> Iterator[_Op]:
    """Each token marked, every gap between matches read removed-then-added."""
    end_a = end_b = 0
    for index_a, index_b in [
        *lcs_pairs(tokens_a, tokens_b, tokens_equal),
        (len(tokens_a), len(tokens_b)),
    ]:
        for token in tokens_a[end_a:index_a]:
            yield 'removed', _Pair(token, None)
        for token in tokens_b[end_b:index_b]:
            yield 'added', _Pair(None, token)
        if index_a < len(tokens_a):
            yield 'equal', _Pair(tokens_a[index_a], tokens_b[index_b])
        end_a, end_b = index_a + 1, index_b + 1


def _joined_spaces(runs: list[_Run]) -> list[_Run]:
    """An equal run of only spaces between two runs of one changed mark takes
    that mark, so a changed stretch never splits around a lone space. The other
    side's spaces there go unshown."""
    joined: list[_Run] = []
    for index, run in enumerate(runs):
        mark = run.mark
        if (
            mark == 'equal'
            and 0 < index < len(runs) - 1
            and runs[index - 1].mark == runs[index + 1].mark
            and all(pair.after and pair.after.kind == 'space' for pair in run.pairs)
        ):
            mark = runs[index - 1].mark
        if joined and joined[-1].mark == mark:
            joined[-1].pairs.extend(run.pairs)
        else:
            joined.append(_Run(mark, list(run.pairs)))
    return joined


def _merged_literals(shown: list[Token]) -> tuple[NarrationPart, ...]:
    merged: list[NarrationPart] = []
    for part in (part for token in shown for part in token.parts):
        last = merged[-1] if merged else None
        if isinstance(part, NarrationLiteral) and isinstance(last, NarrationLiteral):
            merged[-1] = NarrationLiteral(value=last.value + part.value)
        else:
            merged.append(part)
    return tuple(merged)
