"""The URL-fragment slug each scenario is addressed by."""

from pytest_given.model import Metadata, Narration, NodeId, ReportData, Scenario
from pytest_given.report.slugs import build_scenario_slug_index


def _meta() -> Metadata:
    return Metadata(project='p', timestamp='t', pytest_version='8', plugin_version='0')


def _scn(node_id: str) -> Scenario:
    return Scenario(
        id=NodeId(node_id),
        narration=Narration(text='s'),
        module='m',
    )


def test_scenario_slug_strips_test_prefix_and_py_and_dir() -> None:
    rd = ReportData(
        metadata=_meta(),
        scenarios=[
            _scn('examples/hotel-booking/test_hotel_booking.py::test_complete_booking')
        ],
    )
    index = build_scenario_slug_index(rd)
    assert index == {
        NodeId(
            'examples/hotel-booking/test_hotel_booking.py::test_complete_booking'
        ): 'hotel_booking/complete_booking',
    }


def test_scenario_slug_drops_parametrization_tail_when_unique() -> None:
    rd = ReportData(
        metadata=_meta(), scenarios=[_scn('pkg/test_pour.py::test_pour[water]')]
    )
    index = build_scenario_slug_index(rd)
    assert index[NodeId('pkg/test_pour.py::test_pour[water]')] == 'pour/pour'


def test_scenario_slug_keeps_tail_only_for_colliding_scenarios() -> None:
    # Two scenarios from the same parametrized function (narration varies per
    # case, so they don't merge) would share a slug — both keep their tails.
    rd = ReportData(
        metadata=_meta(),
        scenarios=[
            _scn('pkg/test_pour.py::test_pour[water]'),
            _scn('pkg/test_pour.py::test_pour[fire]'),
            _scn('pkg/test_pour.py::test_drain[once]'),  # unique base → no tail
        ],
    )
    index = build_scenario_slug_index(rd)
    assert index[NodeId('pkg/test_pour.py::test_pour[water]')] == 'pour/pour[water]'
    assert index[NodeId('pkg/test_pour.py::test_pour[fire]')] == 'pour/pour[fire]'
    assert index[NodeId('pkg/test_pour.py::test_drain[once]')] == 'pour/drain'


def test_scenario_slug_file_without_test_prefix_kept_verbatim() -> None:
    rd = ReportData(metadata=_meta(), scenarios=[_scn('checks.py::test_run')])
    index = build_scenario_slug_index(rd)
    assert index[NodeId('checks.py::test_run')] == 'checks/run'


def test_scenario_slug_empty_report_is_empty() -> None:
    rd = ReportData(metadata=_meta())
    assert build_scenario_slug_index(rd) == {}


def test_scenario_slug_duplicate_basename_gains_its_directory() -> None:
    """Two test files sharing a basename is an ordinary layout, not an error."""
    rd = ReportData(
        metadata=_meta(),
        scenarios=[
            _scn('a/test_booking.py::test_make'),
            _scn('b/test_booking.py::test_make'),
        ],
    )
    index = build_scenario_slug_index(rd)
    assert index[NodeId('a/test_booking.py::test_make')] == 'a/booking/make'
    assert index[NodeId('b/test_booking.py::test_make')] == 'b/booking/make'


def test_scenario_slug_escalates_only_as_far_as_it_must() -> None:
    """Directories come back one level at a time, and only for the colliding
    scenarios — a scenario that is already unique keeps its short slug."""
    rd = ReportData(
        metadata=_meta(),
        scenarios=[
            _scn('t/u/a/test_x.py::test_y'),
            _scn('t/v/a/test_x.py::test_y'),
            _scn('other/test_z.py::test_w'),
        ],
    )
    index = build_scenario_slug_index(rd)
    assert index[NodeId('t/u/a/test_x.py::test_y')] == 'u/a/x/y'
    assert index[NodeId('t/v/a/test_x.py::test_y')] == 'v/a/x/y'
    assert index[NodeId('other/test_z.py::test_w')] == 'z/w'


def test_scenario_slug_fallback_stays_fragment_safe() -> None:
    """The fallback is still addressed as `#scenario=<slug>`, so it may not
    hand back characters `_fragment_safe` exists to remove — a `+` there
    decodes to a space and the deep link silently misses."""
    rd = ReportData(
        metadata=_meta(),
        scenarios=[_scn('test_x.py::test_y[a+b]'), _scn('test_x.py::test_y[a-b]')],
    )
    index = build_scenario_slug_index(rd)
    for slug in index.values():
        assert not set(slug) & set('+&=# ')


def test_scenario_slug_fallback_separates_ids_that_fold_together() -> None:
    """Two node ids differing only in a character the fold removes are still
    told apart, and which one gets which slug does not depend on the order the
    report lists them in."""
    ids = ['test_x.py::test_y[a+b]', 'test_x.py::test_y[a-b]']
    forward = build_scenario_slug_index(
        ReportData(metadata=_meta(), scenarios=[_scn(i) for i in ids])
    )
    reverse = build_scenario_slug_index(
        ReportData(metadata=_meta(), scenarios=[_scn(i) for i in reversed(ids)])
    )
    assert len(set(forward.values())) == 2
    assert forward == reverse


def test_scenario_slug_falls_back_to_the_node_id_when_paths_cannot_separate() -> None:
    """`test_x.py` beside `x.py` in one directory reads the same at every
    depth; the node id is the only thing left that is unique."""
    rd = ReportData(
        metadata=_meta(),
        scenarios=[_scn('a/test_x.py::test_y'), _scn('a/x.py::test_y')],
    )
    index = build_scenario_slug_index(rd)
    assert index[NodeId('a/test_x.py::test_y')] == 'a/test_x.py::test_y'
    assert index[NodeId('a/x.py::test_y')] == 'a/x.py::test_y'
