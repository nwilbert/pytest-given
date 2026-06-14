"""Pure-function id derivation, shared by capture and report layers."""

import re

from .errors import PytestGivenError
from .schema import TermId

_NON_ALNUM = re.compile(r'[^a-z0-9]+')


def id_derive(name: str) -> TermId:
    slug = _NON_ALNUM.sub('-', name.lower()).strip('-')
    if not slug:
        raise PytestGivenError(
            f'derived id is empty for {name!r}; provide a name with at least '
            f'one ASCII alphanumeric character.'
        )
    return TermId(slug)
