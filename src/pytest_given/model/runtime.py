"""The carriers capture, grouping and the plugin pass between themselves.

None of it is serialized: `schema.py` is what reaches the JSON report, and the
reflective serializer walks only what is reachable from `ReportData`. Kept
apart so "does this end up in the report?" is answerable by which file a type
is declared in.
"""

from dataclasses import dataclass, field
from typing import Literal, NamedTuple

from .schema import NodeId, Step

# Lifecycle state of the collector — determines where push_step/attach route.
type RecordingState = Literal['idle', 'test', 'fixture_setup', 'fixture_teardown']

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


@dataclass
class FixtureRecording:
    """A captured subtree of steps/attachments for one fixture instance.

    `root` is the labeled step from @given/@when/@then on the fixture; its
    `children` accumulate as the fixture body runs. `stack` mirrors the
    collector's step stack while the recording is active, so nested
    `with given(...)` inside the body works.
    """

    root: Step
    stack: list[Step] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.stack:
            self.stack.append(self.root)
