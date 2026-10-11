"""Whether a parametrize case's id was written by hand.

pytest keeps only the finished id parts, so this rereads the `parametrize`
marks they came from. Parametrization that never became a mark —
`metafunc.parametrize`, fixture `params=` — reads as generated.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import cast

import pytest

# `pytest.param`'s return type, which pytest does not export by name.
_PARAMETER_SET = type(pytest.param())

# A case's arguments by identity: pytest passes each argvalue through to
# `callspec.params` as is, so identity finds the case's position in its mark.
# `callspec.indices` cannot, as pytest renumbers a direct argument's index to
# the case's place among all cases.
type _ArgIdentities = tuple[int, ...]


@dataclass(frozen=True)
class MarkIds:
    """Which of one mark's cases were named by hand, indexed once for all of
    them. Holding `mark` keeps the identities in `named` from being reused."""

    mark: pytest.Mark
    names: list[str]
    named: dict[_ArgIdentities, bool]

    @classmethod
    def of(cls, mark: pytest.Mark) -> MarkIds:
        argnames = _mark_arg(mark, 0, 'argnames')
        values = cast('Sequence[object]', _mark_arg(mark, 1, 'argvalues'))
        ids = _mark_arg(mark, 3, 'ids')
        if isinstance(argnames, str):
            names = [name.strip() for name in argnames.split(',') if name.strip()]
            # As in pytest: a lone name takes each value whole, unless `'a,'`.
            whole = len(names) == 1 and not argnames.rstrip().endswith(',')
        else:
            names, whole = list(cast('Sequence[str]', argnames)), False
        named: dict[_ArgIdentities, bool] = {}
        for index, value in enumerate(values):
            key = tuple(id(part) for part in _parts(value, whole=whole))
            # One object at several positions: any of them named counts, as the
            # table shows its ids for that position's own case anyway.
            named[key] = named.get(key, False) or _explicit_at(value, ids, index)
        return cls(mark=mark, names=names, named=named)

    def names_case(self, params: Mapping[str, object]) -> bool:
        return self.named.get(tuple(id(params[name]) for name in self.names), False)


# Keyed by the mark's identity: every case of a function shares its marks.
type MarkIdsCache = dict[int, MarkIds]


def explicit_case_id(
    item: pytest.Item, params: Mapping[str, object], cache: MarkIdsCache
) -> bool:
    """Whether any part of the case's id was written by hand."""
    return any(
        _mark_ids(mark, cache).names_case(params)
        for mark in item.iter_markers('parametrize')
    )


def _mark_ids(mark: pytest.Mark, cache: MarkIdsCache) -> MarkIds:
    if id(mark) not in cache:
        cache[id(mark)] = MarkIds.of(mark)
    return cache[id(mark)]


def _mark_arg(mark: pytest.Mark, position: int, keyword: str) -> object:
    return (
        mark.args[position] if len(mark.args) > position else mark.kwargs.get(keyword)
    )


def _parts(value: object, *, whole: bool) -> Sequence[object]:
    if isinstance(value, _PARAMETER_SET):
        return value.values
    if whole:
        return (value,)
    return cast('Sequence[object]', value)


def _explicit_at(value: object, ids: object, index: int) -> bool:
    """A `pytest.param` id wins over `ids=`, as in pytest. An `ids=` callable
    or iterator counts even where it gave `None`: it cannot be asked again."""
    if isinstance(value, _PARAMETER_SET) and value.id is not None:
        return value.id is not pytest.HIDDEN_PARAM
    if ids is None:
        return False
    if not isinstance(ids, Sequence):
        return True
    return index < len(ids) and ids[index] not in (None, pytest.HIDDEN_PARAM)
