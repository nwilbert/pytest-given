"""Unit tests for plugin internals reached only via pytester subprocesses
in integration tests; tested here directly so coverage hits 100%."""

import inspect
from types import SimpleNamespace
from typing import Any, cast

import pytest

from pytest_given import plugin
from pytest_given.collector import Collector, get_active_collector, set_active_collector
from pytest_given.decorators import StepDescriptor
from pytest_given.model import NodeId, ParamSpec, PytestGivenError, Scenario
from pytest_given.template import Narration, NarrationPlaceholder


@pytest.fixture(autouse=True)
def fresh_collector() -> Any:
    """Swap plugin.collector for an isolated one per test."""
    original = plugin.collector
    plugin.collector = Collector()
    try:
        yield plugin.collector
    finally:
        plugin.collector = original


def _drive_fixture_setup(fixturedef: Any, request: Any) -> None:
    """Step the pytest_fixture_setup hookwrapper generator as pluggy would."""
    gen = plugin.pytest_fixture_setup(fixturedef, request)
    next(gen)
    with pytest.raises(StopIteration):
        next(gen)


def _fake_func(desc: StepDescriptor | None = None) -> Any:
    def f() -> None:
        pass

    if desc is not None:
        f._step_descriptor = desc  # type: ignore[attr-defined]
    return f


def _fake_item(fixturedefs: dict[str, Any]) -> pytest.Item:
    fm = SimpleNamespace(getfixturedefs=lambda name, _item: fixturedefs.get(name))
    session = SimpleNamespace(_fixturemanager=fm)
    return cast(
        pytest.Item,
        SimpleNamespace(fixturenames=list(fixturedefs.keys()), session=session),
    )


def test_pytest_fixture_setup_skips_plain_fixture(
    fresh_collector: Collector,
) -> None:
    fixturedef = SimpleNamespace(func=lambda: None)
    _drive_fixture_setup(fixturedef, SimpleNamespace())
    assert list(fresh_collector.recordings()) == []


def test_pytest_fixture_setup_skips_when_collector_idle(
    fresh_collector: Collector,
) -> None:
    fixturedef = SimpleNamespace(func=_fake_func(StepDescriptor('given', 'a thing')))
    assert fresh_collector.state == 'idle'
    _drive_fixture_setup(fixturedef, SimpleNamespace())
    assert list(fresh_collector.recordings()) == []


def test_ensure_teardown_wrapped_is_idempotent() -> None:
    desc = StepDescriptor('given', 'a thing')

    def gen_fixture() -> Any:
        yield 'value'

    gen_fixture._step_descriptor = desc  # type: ignore[attr-defined]
    fixturedef = SimpleNamespace(func=gen_fixture)
    plugin._ensure_teardown_wrapped(fixturedef)
    first_wrap = fixturedef.func
    assert first_wrap is not gen_fixture
    plugin._ensure_teardown_wrapped(fixturedef)
    assert fixturedef.func is first_wrap


def test_ensure_teardown_wrapped_skips_non_generator() -> None:
    plain = _fake_func(StepDescriptor('given', 'a thing'))
    fixturedef = SimpleNamespace(func=plain)
    plugin._ensure_teardown_wrapped(fixturedef)
    assert fixturedef.func is plain


def test_wrapped_generator_handles_no_yield() -> None:
    desc = StepDescriptor('given', 'empty')

    def degenerate() -> Any:
        if False:
            yield None
        return

    degenerate._step_descriptor = desc  # type: ignore[attr-defined]
    fixturedef = SimpleNamespace(func=degenerate)
    plugin._ensure_teardown_wrapped(fixturedef)
    wrapped = fixturedef.func
    assert inspect.isgeneratorfunction(wrapped)
    assert list(wrapped()) == []


def test_graft_fixture_recordings_skips_plain_fixtures(
    fresh_collector: Collector,
) -> None:
    fixturedef = SimpleNamespace(func=lambda: None, cached_result=('v', None, None))
    item = _fake_item({'plain': [fixturedef]})
    fresh_collector.start_scenario(NodeId('t::x'), 'x', 'mod', [])
    plugin._graft_fixture_recordings(item)
    assert fresh_collector._current_scenario is not None
    assert fresh_collector._current_scenario.steps == []


def test_graft_fixture_recordings_skips_uncached_fixtures(
    fresh_collector: Collector,
) -> None:
    deco = _fake_func(StepDescriptor('given', 'a thing'))
    fixturedef = SimpleNamespace(func=deco, cached_result=None)
    item = _fake_item({'deco': [fixturedef]})
    fresh_collector.start_scenario(NodeId('t::x'), 'x', 'mod', [])
    plugin._graft_fixture_recordings(item)
    assert fresh_collector._current_scenario is not None
    assert fresh_collector._current_scenario.steps == []


def test_graft_fixture_recordings_skips_unknown_fixturename(
    fresh_collector: Collector,
) -> None:
    item = _fake_item({'missing': None})
    fresh_collector.start_scenario(NodeId('t::x'), 'x', 'mod', [])
    plugin._graft_fixture_recordings(item)
    assert fresh_collector._current_scenario is not None
    assert fresh_collector._current_scenario.steps == []


def test_pytest_runtest_teardown_ignores_mismatched_item(
    fresh_collector: Collector,
) -> None:
    fresh_collector.start_scenario(NodeId('t::a'), 'a', 'mod', [])
    set_active_collector(fresh_collector)
    item = cast(pytest.Item, SimpleNamespace(nodeid='t::b'))
    plugin.pytest_runtest_teardown(item)
    assert get_active_collector() is fresh_collector
    set_active_collector(None)


def test_pytest_runtest_teardown_clears_collector_when_matched(
    fresh_collector: Collector,
) -> None:
    fresh_collector.start_scenario(NodeId('t::a'), 'a', 'mod', [])
    set_active_collector(fresh_collector)
    item = cast(pytest.Item, SimpleNamespace(nodeid='t::a'))
    plugin.pytest_runtest_teardown(item)
    assert get_active_collector() is None


def test_pytest_runtest_teardown_clears_unannotated_flag(
    fresh_collector: Collector,
) -> None:
    fresh_collector.inside_unannotated_test = True
    set_active_collector(fresh_collector)
    item = cast(pytest.Item, SimpleNamespace(nodeid='t::x'))
    plugin.pytest_runtest_teardown(item)
    assert fresh_collector.inside_unannotated_test is False
    assert get_active_collector() is None


def test_get_scenario_marker_returns_none_for_item_without_function() -> None:
    """DoctestItem and other non-Function items lack `.function`; the marker
    lookup must tolerate that rather than asserting."""
    item = cast(pytest.Item, SimpleNamespace(nodeid='t::doctest'))
    assert plugin._get_scenario_marker(item) is None


def test_templatize_narration_rejects_unknown_placeholder() -> None:
    """Safety-net guard: a NarrationPlaceholder whose name isn't a parametrize
    column raises. Defense in depth on top of the collection-time hook, which
    catches Template placeholders in scenario names (and step text from
    Template can't happen since given/when/then reject Template). The runtime
    guard covers any future code path that might construct parts directly."""
    narration = Narration(text='', parts=[NarrationPlaceholder(name='cup_zize')])
    with pytest.raises(PytestGivenError, match='cup_zize'):
        plugin._templatize_narration(narration, ['cup_size'])


def test_extract_skip_reason_parses_canonical_tuple() -> None:
    assert plugin._extract_skip_reason(('t.py', 12, 'Skipped: because')) == 'because'


def test_extract_skip_reason_strips_prefix_when_present() -> None:
    assert plugin._extract_skip_reason(('t.py', 12, 'Skipped: mid-test')) == 'mid-test'


def test_extract_skip_reason_handles_no_prefix() -> None:
    assert plugin._extract_skip_reason(('t.py', 12, 'mid-test')) == 'mid-test'


def test_extract_skip_reason_returns_none_for_placeholder() -> None:
    assert (
        plugin._extract_skip_reason(('t.py', 12, 'Skipped: <Skipped instance>')) is None
    )
    # pytest 9+: @pytest.mark.skip with no reason emits 'unconditional skip'
    assert (
        plugin._extract_skip_reason(('t.py', 12, 'Skipped: unconditional skip')) is None
    )


def test_extract_skip_reason_returns_none_for_empty_message() -> None:
    assert plugin._extract_skip_reason(('t.py', 12, 'Skipped: ')) is None
    assert plugin._extract_skip_reason(('t.py', 12, '')) is None


def test_extract_skip_reason_returns_none_for_unrecognized_shapes() -> None:
    assert plugin._extract_skip_reason(None) is None
    assert plugin._extract_skip_reason('just a string') is None
    assert plugin._extract_skip_reason(('only', 'two')) is None
    assert plugin._extract_skip_reason(('t.py', 12, 42)) is None


def test_group_parameterized_all_skipped_merges_as_skipped() -> None:
    nid1, nid2 = NodeId('t::x[1]'), NodeId('t::x[2]')
    scenarios = [
        Scenario(id=nid1, narration=Narration(text='x'), module='m', status='skipped'),
        Scenario(id=nid2, narration=Narration(text='x'), module='m', status='skipped'),
    ]
    param_info = {
        nid1: ParamSpec(names=['n'], values=[1]),
        nid2: ParamSpec(names=['n'], values=[2]),
    }
    merged = plugin._group_parameterized(scenarios, param_info)
    assert len(merged) == 1
    assert merged[0].status == 'skipped'


def test_group_parameterized_mixed_pass_skip_merges_as_passed() -> None:
    nid1, nid2 = NodeId('t::x[1]'), NodeId('t::x[2]')
    scenarios = [
        Scenario(id=nid1, narration=Narration(text='x'), module='m', status='passed'),
        Scenario(id=nid2, narration=Narration(text='x'), module='m', status='skipped'),
    ]
    param_info = {
        nid1: ParamSpec(names=['n'], values=[1]),
        nid2: ParamSpec(names=['n'], values=[2]),
    }
    merged = plugin._group_parameterized(scenarios, param_info)
    assert merged[0].status == 'passed'


def test_group_parameterized_any_failed_merges_as_failed() -> None:
    nid1, nid2, nid3 = NodeId('t::x[1]'), NodeId('t::x[2]'), NodeId('t::x[3]')
    scenarios = [
        Scenario(id=nid1, narration=Narration(text='x'), module='m', status='passed'),
        Scenario(id=nid2, narration=Narration(text='x'), module='m', status='failed'),
        Scenario(id=nid3, narration=Narration(text='x'), module='m', status='skipped'),
    ]
    param_info = {
        nid1: ParamSpec(names=['n'], values=[1]),
        nid2: ParamSpec(names=['n'], values=[2]),
        nid3: ParamSpec(names=['n'], values=[3]),
    }
    merged = plugin._group_parameterized(scenarios, param_info)
    assert merged[0].status == 'failed'
