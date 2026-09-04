"""Text rules shared across packages that may not import each other.

`capture/`, `lint/` and `report/` each depend on `model/` and never on one
another, so a rule two of them have to agree on lives here in the leaf.

`EMPHASIS` — `capture/markdown_glossary.py` *strips* this markup from a
glossary term cell while `report/inline_markdown.py` *renders* it in a
definition cell: a term written ``**Guest**`` has to canonicalize to the same
word its definition renders bold, so the two must recognize exactly the same
spans. Only the pattern is shared: what a match *becomes* differs by caller, so
each keeps its own substitution function.

`id_derive` — capture, lint and report all derive ids with it. It returns a
bare `str`, not a `TermId`: a story id, a term id and a coverage instance id
are derived the same way, so the callers that do want a typed id wrap it
themselves and the ones that don't have no NewType to discard.

`plural` — `report/` and `lint/` both count things into a sentence.
"""

import re

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


def id_derive(name: str) -> str:
    """`name` as a slug: lowercased, every non-ASCII-alphanumeric run folded to
    a single `-`."""
    slug = _NON_ALNUM.sub('-', name.lower()).strip('-')
    if not slug:
        raise PytestGivenError(
            f'derived id is empty for {name!r}; provide a name with at least '
            f'one ASCII alphanumeric character.'
        )
    return slug


def plural(count: int, singular: str, plural_form: str | None = None) -> str:
    """`'1 scenario'` / `'3 scenarios'` — the noun agreeing with its count."""
    if count == 1:
        return f'{count} {singular}'
    return f'{count} {plural_form or singular + "s"}'
