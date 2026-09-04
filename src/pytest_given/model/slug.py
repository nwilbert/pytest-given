"""The slug rule every derived id shares.

Lives in `model/` because capture, lint and report all derive ids with it and
none of them may import the others.

`id_derive` returns a bare `str`, not a `TermId`: a story id, a term id and a
coverage instance id are derived the same way, so the callers that do want a
typed id wrap it themselves and the ones that don't have no NewType to discard.
"""

import re

from .errors import PytestGivenError

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
