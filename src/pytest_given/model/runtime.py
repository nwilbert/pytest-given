"""The parametrize carriers capture, grouping and the plugin pass between
themselves.

None of it is serialized: `schema.py` is what reaches the JSON report, and the
reflective serializer walks only what is reachable from `ReportData`. Kept
apart so "does this end up in the report?" is answerable by which file a type
is declared in.
"""

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
