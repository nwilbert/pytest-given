"""The parametrize carriers capture, grouping and the plugin pass between
themselves.

None of it is serialized: `schema.py` is what reaches the JSON report, and the
reflective serializer walks only what is reachable from `ReportData`. Kept
apart so "does this end up in the report?" is answerable by which file a type
is declared in.
"""

import contextlib
import copy
from typing import NamedTuple

from .schema import NodeId

# A parametrize argument as pytest handed it over — an arbitrary object. Kept
# raw on ParamSpec so grouping can re-apply an interpolation's conversion and
# format spec to the value the t-string actually saw (see the rebound-parameter
# rule in the per-case-columns design).
type RawParamValue = object


class ParamSpec(NamedTuple):
    """Parameter names and raw values for a single parametrized test run.

    `group` carries `@scenario(group_parametrized=...)`: False declines the
    merge and emits this case as its own scenario.
    """

    names: list[str]
    values: list[RawParamValue]
    group: bool = True

    def mapping(self) -> dict[str, RawParamValue]:
        """This case's parameters by name — the pairing of the two lists."""
        return dict(zip(self.names, self.values, strict=True))


# Maps node IDs to their parameter specification.
type ParamInfo = dict[NodeId, ParamSpec]


def snapshot_param_value(value: RawParamValue) -> RawParamValue:
    """A shallow copy of a parametrize value, or the value itself when its type
    refuses to be copied or the copy would not render the way it does.

    These values are read again at session finish, so a body that mutates one
    in place would otherwise put the post-test state in the parameter table and
    make the rebound-parameter rule compare the narration against a value it
    never rendered.

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
