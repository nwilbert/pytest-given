from pytest_given.model import (
    Narration,
    NodeId,
    Scenario,
    SourceLocation,
    in_report_order,
)


def _scenario(
    node_id: str, line: int | None = 1, relpath: str | None = None
) -> Scenario:
    """A scenario whose source is `line` in `relpath`, the node id's own file
    unless given; `line=None` leaves it without a source."""
    source = (
        None
        if line is None
        else SourceLocation(relpath=relpath or node_id.split('::')[0], line=line)
    )
    return Scenario(
        id=NodeId(node_id), narration=Narration(text=node_id), module='m', source=source
    )


def _ordered_ids(scenarios: list[Scenario]) -> list[str]:
    index = {scenario.id: position for position, scenario in enumerate(scenarios)}
    return [scenario.id for scenario in in_report_order(scenarios, index)]


def test_files_sort_by_path_parts():
    scenarios = [
        _scenario('tests/b.py::t'),
        _scenario('tests/a.py::t'),
        _scenario('tests/a/z.py::t'),
    ]
    assert _ordered_ids(scenarios) == [
        'tests/a/z.py::t',
        'tests/a.py::t',
        'tests/b.py::t',
    ]


def test_paths_compare_case_sensitively():
    scenarios = [_scenario('a.py::t'), _scenario('B.py::t')]
    assert _ordered_ids(scenarios) == ['B.py::t', 'a.py::t']


def test_within_a_file_scenarios_sort_by_line():
    scenarios = [_scenario('t.py::late', line=20), _scenario('t.py::early', line=5)]
    assert _ordered_ids(scenarios) == ['t.py::early', 't.py::late']


def test_a_foreign_or_missing_source_sorts_after_the_file_own():
    scenarios = [
        _scenario('t.py::Sub::test_inherited', line=1, relpath='base.py'),
        _scenario('t.py::test_unlocated', line=None),
        _scenario('t.py::test_own', line=50),
    ]
    assert _ordered_ids(scenarios) == [
        't.py::test_own',
        't.py::Sub::test_inherited',
        't.py::test_unlocated',
    ]


def test_shared_lines_keep_collection_order():
    scenarios = [_scenario('t.py::f[10]', line=3), _scenario('t.py::f[2]', line=3)]
    assert _ordered_ids(scenarios) == ['t.py::f[10]', 't.py::f[2]']


def test_a_scenario_without_a_collection_index_sorts_last_among_ties():
    scenarios = [_scenario('a.py::t[added]'), _scenario('a.py::t[1]')]
    ordered = in_report_order(scenarios, {NodeId('a.py::t[1]'): 0})
    assert [scenario.id for scenario in ordered] == ['a.py::t[1]', 'a.py::t[added]']
