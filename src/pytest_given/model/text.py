"""Text rules two packages that cannot import each other have to agree on.

`read_spans` is the one reader of inline Markdown: `capture/markdown_glossary.py`
unwraps its spans, and `report/` renders them to HTML and writes them back as
Markdown — a term written ``**Guest**`` has to canonicalize to the word its
definition renders bold, and the Markdown report has to show what the HTML
shows.

`s_form` is shared so that what a handle's `.s` spells, the report recognizes
as the same term; `plural` so the lint summary and the report count alike.

`id_derive` returns a bare `str`, not a `TermId`: story ids, term ids and
coverage instance ids all derive the same way.

`table_cell_spans` is how `capture` reads a glossary file's table and
`citations` a cited document's: one GFM row rule, not two.
"""

import itertools
import re
from dataclasses import dataclass

from .errors import PytestGivenError

# Code span first, so nothing inside `code` is treated as markup — neither a
# `*` nor, on the render side, an escaped `<br>`. Callers get that only by
# routing every other substitution through this one pass; `render_inline_markdown`
# says what happens when they don't. The group order is part of the contract
# every substitution function reads: code span, **bold**, __bold__, *italic*.
# Only paired markers match, so a lone underscore inside an identifier
# (`work_object`) is left untouched — a paired dunder (`__init__`) is strong
# emphasis, which is what CommonMark makes it too.
EMPHASIS = re.compile(r'`(.+?)`|\*\*(.+?)\*\*|__(.+?)__|\*(.+?)\*')


_NON_ALNUM = re.compile(r'[^a-z0-9]+')
_SIBILANT_ENDINGS = ('s', 'x', 'z', 'ch', 'sh')
_CONSONANT_Y = re.compile(r'[b-df-hj-np-tv-z]y$')


def derived_id(name: str) -> str | None:
    """`name` as a slug — lowercased, every non-ASCII-alphanumeric run folded to
    a single `-` — or None if nothing survives the fold.

    The fold runs after `str.lower`, so whether a name has a slug is not the
    same question as whether its characters are ASCII: `'\u212a'` lowercases
    into `'k'`. Callers that need the predicate ask this rather than
    reimplementing it.
    """
    return _NON_ALNUM.sub('-', name.lower()).strip('-') or None


def id_derive(name: str) -> str:
    """`derived_id`, raising instead of returning None."""
    slug = derived_id(name)
    if slug is None:
        raise PytestGivenError(
            f'derived id is empty for {name!r}; provide a name with at least '
            f'one ASCII alphanumeric character.'
        )
    return slug


def plural(count: int, singular: str) -> str:
    """`'1 scenario'` / `'3 stories'` — the noun agreeing with its count."""
    if count == 1:
        return f'{count} {singular}'
    return f'{count} {s_form(singular)}'


def s_form(text: str) -> str:
    """`text` with the regular English -s ending: a plural noun, or a verb's
    third person singular. Only a lowercase ending takes -es or -ies, so an
    acronym takes a plain -s (``APIs``); irregular words are the caller's."""
    if text.endswith(_SIBILANT_ENDINGS):
        return f'{text}es'
    if _CONSONANT_Y.search(text):
        return f'{text[:-1]}ies'
    return f'{text}s'


def table_cell_spans(row: str) -> list[tuple[int, int]]:
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

_CODE_SPAN = r'`([^`]+)`'
# A marker touching whitespace or another `*` on its inner side opens or closes
# nothing, so `2 * 3 * 4` stays literal; the lazy body lets the first span to
# close win. Underscores never format.
_SPAN = re.compile(
    _CODE_SPAN
    + r'|\*\*(?=[^\s*])(.+?)(?<=[^\s*])\*\*'
    + r'|\*(?=[^\s*])(.+?)(?<=[^\s*])\*',
    re.DOTALL,
)
_CODE = re.compile(_CODE_SPAN)


def read_spans(text: str) -> list[InlineSpan]:
    """`text` as plain text, code spans, and bold or italic holding nothing but
    plain text and code spans. Everything a span does not take is plain, an
    unmatched marker and a backslash included."""
    spans: list[InlineSpan] = []
    end = 0
    for match in _SPAN.finditer(text):
        spans.extend(_plain(text[end : match.start()]))
        code, strong, italic = match.groups()
        if code is not None:
            spans.append(CodeSpan(code))
        else:
            inner = strong if strong is not None else italic
            assert inner is not None
            spans.append(EmphasisSpan(strong is not None, tuple(_code_spans(inner))))
        end = match.end()
    spans.extend(_plain(text[end:]))
    return spans


def _code_spans(text: str) -> list[PlainSpan | CodeSpan]:
    spans: list[PlainSpan | CodeSpan] = []
    end = 0
    for match in _CODE.finditer(text):
        spans.extend(_plain(text[end : match.start()]))
        spans.append(CodeSpan(match.group(1)))
        end = match.end()
    spans.extend(_plain(text[end:]))
    return spans


def _plain(text: str) -> list[PlainSpan]:
    return [PlainSpan(text)] if text else []
