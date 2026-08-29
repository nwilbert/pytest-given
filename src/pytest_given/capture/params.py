"""Snapshotting a raw parametrize value at the moment it is recorded."""

import contextlib
import copy

from ..model import RawParamValue


def snapshot_param_value(value: RawParamValue) -> RawParamValue:
    """A shallow copy of a parametrize value, or the value itself when its type
    refuses to be copied or the copy would not render the way it does.

    Best effort by nature: a value that cannot be copied is one whose mutation
    cannot be guarded against either.

    A copy that renders differently is worse than no copy at all. An object
    inheriting the default `__repr__` — or a `MagicMock` — renders its own
    address, so the copy would put a value in the cell that no case narrated.
    Mutation cannot change such a rendering anyway.
    """
    with contextlib.suppress(Exception):
        snapshot = copy.copy(value)
        # Both renderings, since an interpolation may ask for either: `!r`
        # takes `repr` and a bare `{x}` takes `str`, and a type can define one
        # by value and inherit the other from `object`.
        if (str(snapshot), repr(snapshot)) == (str(value), repr(value)):
            return snapshot
    return value
