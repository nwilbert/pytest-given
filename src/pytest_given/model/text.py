"""Text rules two packages that cannot import each other have to agree on.

`EMPHASIS` is matched by `capture/markdown_glossary.py`, which *strips* the
markup, and by `report/inline_markdown.py`, which *renders* it — a term written
``**Guest**`` has to canonicalize to the word its definition renders bold, so
both must recognize exactly the same spans. Only the pattern is shared; what a
match becomes differs by caller.

`id_derive` returns a bare `str`, not a `TermId`: story ids, term ids and
coverage instance ids all derive the same way.
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
