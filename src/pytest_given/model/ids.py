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


def node_base(node_id: str) -> str:
    """A node id (or a bare function segment) without its parametrize tail:
    ``'f.py::t[1-2]' -> 'f.py::t'``, ``'t[1-2]' -> 't'``. Two cases of one
    parametrized function share this; two different functions never do."""
    return node_id.split('[', 1)[0]


def case_suffix(node_id: str) -> str:
    """The parametrize tail of a node id, brackets included, or ``''`` when it
    has none: ``'f.py::t[1-2]' -> '[1-2]'``, ``'f.py::t' -> ''``."""
    _, bracket, rest = node_id.partition('[')
    return f'{bracket}{rest}'
