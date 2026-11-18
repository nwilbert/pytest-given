"""The order a report lists its scenarios in: by file, then by line, so that
neither the run order nor how pytest-xdist spread the tests changes it."""

from collections.abc import Iterable, Mapping
from pathlib import PurePosixPath

from .schema import NodeId, Scenario, Step

type _SortKey = tuple[tuple[str, ...], bool, int, int]


def in_report_order[S: Step](
    scenarios: Iterable[Scenario[S]], collection_index: Mapping[NodeId, int]
) -> list[Scenario[S]]:
    """`collection_index` breaks the ties file and line leave: the cases of an
    ungrouped parametrize share a line, and a scenario with no source in its
    own file — inherited from a base class elsewhere — has no line to compare.
    A scenario it lacks, from an item a plugin added after collection, sorts
    after the rest of its ties.
    """

    def sort_key(scenario: Scenario[S]) -> _SortKey:
        node_file = scenario.id.split('::', 1)[0]
        source = scenario.source
        foreign = source is None or source.relpath != node_file
        return (
            PurePosixPath(node_file).parts,
            foreign,
            0 if source is None or foreign else source.line,
            collection_index.get(scenario.id, len(collection_index)),
        )

    return sorted(scenarios, key=sort_key)
