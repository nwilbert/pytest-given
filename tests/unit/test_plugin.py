"""Unit tests for plugin internals reached only via pytester subprocesses
in integration tests; tested here directly so coverage hits 100%."""

import inspect
import tomllib
from importlib.metadata import version
from pathlib import Path
from types import SimpleNamespace
from typing import Annotated, Any, cast

import pytest

from pytest_given import Template, given, then, when
from pytest_given.capture.collector import (
    Collector,
    get_active_collector,
    set_active_collector,
)
from pytest_given.capture.decorators import (
    ScenarioDecorator,
    StepDescriptor,
    annotated_given_descriptors,
)
from pytest_given.capture.params import snapshot_param_value
from pytest_given.capture.source import file_source
from pytest_given.capture.story import (
    clear_story_registry,
)
from pytest_given.capture.story import (
    story as story_fn,
)
from pytest_given.model import (
    ActivityId,
    FixtureRecording,
    Narration,
    NodeId,
    PytestGivenError,
    Step,
)
from pytest_given.plugin import collection, fixtures, runtest, session, state


@pytest.fixture
def fake_config() -> Any:
    """A config double carrying a real Stash with a session collector and its
    hook bookkeeping, as `pytest_sessionstart` leaves it."""
    config = SimpleNamespace(stash=pytest.Stash())
    config.stash[state._collector_key] = Collector()
    config.stash[state._session_state] = state._SessionState()
    return config


@pytest.fixture
def fresh_collector(fake_config: Any) -> Collector:
    """The collector owned by `fake_config`'s session."""
    return fake_config.stash[state._collector_key]


@pytest.fixture
def fresh_state(fake_config: Any) -> state._SessionState:
    """The hook bookkeeping owned by `fake_config`'s session."""
    return fake_config.stash[state._session_state]


def _drive_fixture_setup(fixturedef: Any, request: Any) -> None:
    """Step the pytest_fixture_setup hookwrapper generator as pluggy would."""
    gen = fixtures.pytest_fixture_setup(fixturedef, request)
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
    fake_config: Any,
    fresh_collector: Collector,
) -> None:
    fixturedef = SimpleNamespace(func=_fake_func(StepDescriptor('given', 'a thing')))
    assert fresh_collector.state == 'idle'
    _drive_fixture_setup(fixturedef, SimpleNamespace(config=fake_config))
    assert list(fresh_collector.recordings()) == []


def test_ensure_teardown_wrapped_is_idempotent() -> None:
    desc = StepDescriptor('given', 'a thing')

    def gen_fixture() -> Any:
        yield 'value'

    gen_fixture._step_descriptor = desc  # type: ignore[attr-defined]
    fixturedef = SimpleNamespace(func=gen_fixture)
    fixtures._ensure_teardown_wrapped(fixturedef, Collector())
    first_wrap = fixturedef.func
    assert first_wrap is not gen_fixture
    fixtures._ensure_teardown_wrapped(fixturedef, Collector())
    assert fixturedef.func is first_wrap


def test_ensure_teardown_wrapped_skips_non_generator() -> None:
    plain = _fake_func(StepDescriptor('given', 'a thing'))
    fixturedef = SimpleNamespace(func=plain)
    fixtures._ensure_teardown_wrapped(fixturedef, Collector())
    assert fixturedef.func is plain


def test_wrapped_generator_handles_no_yield() -> None:
    desc = StepDescriptor('given', 'empty')

    def degenerate() -> Any:
        if False:
            yield None
        return

    degenerate._step_descriptor = desc  # type: ignore[attr-defined]
    fixturedef = SimpleNamespace(func=degenerate)
    fixtures._ensure_teardown_wrapped(fixturedef, Collector())
    wrapped = fixturedef.func
    assert inspect.isgeneratorfunction(wrapped)
    assert list(wrapped()) == []


def test_graft_fixture_recordings_skips_plain_fixtures(
    fresh_collector: Collector,
) -> None:
    fixturedef = SimpleNamespace(func=lambda: None, cached_result=('v', None, None))
    item = _fake_item({'plain': [fixturedef]})
    fresh_collector.start_scenario(NodeId('t::x'), 'x', 'mod', [])
    fixtures._graft_fixture_recordings(item, fresh_collector)
    assert fresh_collector._current_scenario is not None
    assert fresh_collector._current_scenario.steps == []


def test_graft_fixture_recordings_skips_uncached_fixtures(
    fresh_collector: Collector,
) -> None:
    deco = _fake_func(StepDescriptor('given', 'a thing'))
    fixturedef = SimpleNamespace(func=deco, cached_result=None)
    item = _fake_item({'deco': [fixturedef]})
    fresh_collector.start_scenario(NodeId('t::x'), 'x', 'mod', [])
    fixtures._graft_fixture_recordings(item, fresh_collector)
    assert fresh_collector._current_scenario is not None
    assert fresh_collector._current_scenario.steps == []


def test_graft_fixture_recordings_skips_unknown_fixturename(
    fresh_collector: Collector,
) -> None:
    item = _fake_item({'missing': None})
    fresh_collector.start_scenario(NodeId('t::x'), 'x', 'mod', [])
    fixtures._graft_fixture_recordings(item, fresh_collector)
    assert fresh_collector._current_scenario is not None
    assert fresh_collector._current_scenario.steps == []


def test_pytest_runtest_teardown_ignores_mismatched_item(
    fake_config: Any,
    fresh_collector: Collector,
    fresh_state: state._SessionState,
) -> None:
    fresh_state.published_for = NodeId('t::a')
    set_active_collector(fresh_collector)
    item = cast(pytest.Item, SimpleNamespace(nodeid='t::b', config=fake_config))
    runtest.pytest_runtest_teardown(item)
    assert get_active_collector() is fresh_collector
    set_active_collector(None)


def test_pytest_runtest_teardown_clears_collector_when_matched(
    fake_config: Any,
    fresh_collector: Collector,
    fresh_state: state._SessionState,
) -> None:
    fresh_state.published_for = NodeId('t::a')
    set_active_collector(fresh_collector)
    item = cast(pytest.Item, SimpleNamespace(nodeid='t::a', config=fake_config))
    runtest.pytest_runtest_teardown(item)
    assert get_active_collector() is None


def test_pytest_runtest_teardown_clears_a_finished_scenario(
    fake_config: Any,
    fresh_collector: Collector,
    fresh_state: state._SessionState,
) -> None:
    """The call report runs `finish_scenario` before teardown, so
    `active_scenario_id` is already None here. Teardown keys on
    `published_for` instead, which still names the item."""
    fresh_state.published_for = NodeId('t::a')
    fresh_collector.start_scenario(NodeId('t::a'), 'a', 'mod', [])
    fresh_collector.finish_scenario(status='passed')
    set_active_collector(fresh_collector)
    assert fresh_collector.active_scenario_id is None
    item = cast(pytest.Item, SimpleNamespace(nodeid='t::a', config=fake_config))
    runtest.pytest_runtest_teardown(item)
    assert get_active_collector() is None


def test_pytest_runtest_teardown_clears_unannotated_flag(
    fake_config: Any,
    fresh_collector: Collector,
    fresh_state: state._SessionState,
) -> None:
    fresh_collector.inside_unannotated_test = True
    fresh_state.published_for = NodeId('t::x')
    set_active_collector(fresh_collector)
    item = cast(pytest.Item, SimpleNamespace(nodeid='t::x', config=fake_config))
    runtest.pytest_runtest_teardown(item)
    assert fresh_collector.inside_unannotated_test is False
    assert get_active_collector() is None


def test_reported_plugin_version_matches_pyproject() -> None:
    """The version in every report's metadata comes from the installed
    distribution, so it cannot drift from `pyproject.toml` the way a literal
    did — `docs/releasing.md` bumps one file, and nothing used to notice."""
    pyproject = Path(__file__).resolve().parents[2] / 'pyproject.toml'
    declared = tomllib.loads(pyproject.read_text(encoding='utf-8'))['project']
    assert version('pytest-given') == declared['version']


def test_makereport_ignores_a_failure_outside_the_active_scenario(
    fake_config: Any,
    fresh_collector: Collector,
) -> None:
    """An unannotated test failing beside a tracked scenario must not fail it.

    Only the teardown phase reaches the collector without an active scenario
    (the call report finished it already); every other phase still has to match
    the node id it is reporting on.
    """
    fresh_collector.start_scenario(NodeId('t::a'), 'a', 'mod', [])
    call = SimpleNamespace(when='call', excinfo=SimpleNamespace())
    item = cast(pytest.Item, SimpleNamespace(nodeid='t::b', config=fake_config))
    runtest.pytest_runtest_makereport(item, cast(Any, call))
    recorded = fresh_collector.finish_scenario(status='passed')
    assert recorded.status == 'passed'
    assert recorded.error is None


def _fake_session() -> Any:
    """A session double with just enough config for `pytest_sessionstart`.

    The stash carries a `_GivenConfig` because the real lifecycle always runs
    `pytest_configure` first — that is where every option is resolved, and
    `pytest_sessionstart` reads the result rather than re-deriving it.
    """
    config = SimpleNamespace(stash=pytest.Stash())
    config.stash[state._given_config] = state._GivenConfig(
        rule_levels={},
        ignore_entries=[],
        source_link_template=None,
        title=None,
        lint_enabled=False,
    )
    return SimpleNamespace(config=config)


def test_sessionstart_gives_each_session_its_own_collector() -> None:
    """The collector lives in `config.stash`, not a module global: starting a
    second in-process session (pytester, nested pytest.main) must hand out a
    fresh collector without disturbing the outer session's."""
    outer = _fake_session()
    inner = _fake_session()
    session.pytest_sessionstart(cast(pytest.Session, outer))
    outer_collector = state._collector(outer.config)
    outer_collector.start_scenario(NodeId('t::x'), 'x', 'mod', [])
    session.pytest_sessionstart(cast(pytest.Session, inner))
    assert state._collector(outer.config) is outer_collector
    assert state._collector(inner.config) is not outer_collector
    assert outer_collector.active_scenario_id == NodeId('t::x')


def _lifecycle_config(rootpath: Path) -> Any:
    """A config double carrying what the config lifecycle touches: a stash, a
    rootpath, and the cleanup stack pytest drains on shutdown."""
    cleanups: list[Any] = []
    return SimpleNamespace(
        stash=pytest.Stash(),
        rootpath=rootpath,
        add_cleanup=cleanups.append,
        cleanups=cleanups,
    )


def _drain_cleanups(config: Any) -> None:
    """What `Config._ensure_unconfigure` does with the cleanup stack — run
    whether or not the config ever reached `pytest_configure`."""
    while config.cleanups:
        config.cleanups.pop()()


@pytest.mark.usefixtures('_reset_story_registry_plugin')
def test_nested_session_restores_the_outer_story_registry(tmp_path: Any) -> None:
    """The story registry is displaced at `load_initial_conftests` time (before
    conftests import), so each session starts clean, but a nested in-process
    session must put the outer session's registrations back when its config is
    cleaned up — otherwise the outer session silently loses
    duplicate-declaration detection."""
    outer = _lifecycle_config(tmp_path / 'outer')
    inner = _lifecycle_config(tmp_path / 'inner')
    session.pytest_load_initial_conftests(cast(pytest.Config, outer))
    try:
        story_fn('Shared Title')
        session.pytest_load_initial_conftests(cast(pytest.Config, inner))
        story_fn('Shared Title')  # fresh registry per session: no duplicate error
        _drain_cleanups(inner)
        with pytest.raises(PytestGivenError, match='already declared'):
            story_fn('Shared Title')  # the outer registration is back
    finally:
        # Puts back whatever rootdir the real surrounding session had.
        _drain_cleanups(outer)


def test_nested_config_lifecycle_restores_the_outer_rootdir(tmp_path: Any) -> None:
    """`pytest_load_initial_conftests` re-points the capture rootdir for a
    nested in-process run; the cleanup it registers must point it back so the
    outer session's path resolution keeps working after the nested run."""
    outer_config = _lifecycle_config(tmp_path / 'outer')
    nested_config = _lifecycle_config(tmp_path / 'nested')
    target = tmp_path / 'outer' / 'f.py'
    session.pytest_load_initial_conftests(cast(pytest.Config, outer_config))
    try:
        assert file_source(target, 1) is not None
        session.pytest_load_initial_conftests(cast(pytest.Config, nested_config))
        assert file_source(target, 1) is None  # re-pointed at the nested root
        _drain_cleanups(nested_config)
        assert file_source(target, 1) is not None  # outer resolution restored
    finally:
        # Puts back whatever rootdir the real surrounding session had.
        _drain_cleanups(outer_config)


def test_get_scenario_marker_returns_none_for_item_without_function() -> None:
    """DoctestItem and other non-Function items lack `.function`; the marker
    lookup must tolerate that rather than asserting."""
    item = cast(pytest.Item, SimpleNamespace(nodeid='t::doctest'))
    assert collection._get_scenario_marker(item) is None


def test_extract_skip_reason_parses_canonical_tuple() -> None:
    assert runtest._extract_skip_reason(('t.py', 12, 'Skipped: because')) == 'because'


def test_extract_skip_reason_strips_prefix_when_present() -> None:
    assert runtest._extract_skip_reason(('t.py', 12, 'Skipped: mid-test')) == 'mid-test'


def test_extract_skip_reason_handles_no_prefix() -> None:
    assert runtest._extract_skip_reason(('t.py', 12, 'mid-test')) == 'mid-test'


def test_extract_skip_reason_returns_none_for_placeholder() -> None:
    assert (
        runtest._extract_skip_reason(('t.py', 12, 'Skipped: <Skipped instance>'))
        is None
    )
    # pytest 9+: @pytest.mark.skip with no reason emits 'unconditional skip'
    assert (
        runtest._extract_skip_reason(('t.py', 12, 'Skipped: unconditional skip'))
        is None
    )


def test_extract_skip_reason_returns_none_for_empty_message() -> None:
    assert runtest._extract_skip_reason(('t.py', 12, 'Skipped: ')) is None
    assert runtest._extract_skip_reason(('t.py', 12, '')) is None


def test_extract_skip_reason_returns_none_for_unrecognized_shapes() -> None:
    assert runtest._extract_skip_reason(None) is None
    assert runtest._extract_skip_reason('just a string') is None
    assert runtest._extract_skip_reason(('only', 'two')) is None
    assert runtest._extract_skip_reason(('t.py', 12, 42)) is None


# --- Task 7.2 / 7.4 unit coverage ---


@pytest.fixture
def _reset_story_registry_plugin() -> Any:
    clear_story_registry()
    yield
    clear_story_registry()


@pytest.mark.usefixtures('_reset_story_registry_plugin')
def test_validate_scenario_story_binding_activities_without_story_raises() -> None:
    """_validate_scenario_story_binding must raise when activities= is given
    without story= (plugin.py line 141)."""
    marker = ScenarioDecorator('x', [], activity_ids=(ActivityId(1),))
    item = cast(pytest.Item, SimpleNamespace(nodeid='test_mod.py::test_x'))
    with pytest.raises(PytestGivenError, match='requires story='):
        collection._validate_scenario_story_binding(item, marker)


def test_extract_given_descriptor_from_parametrize_param() -> None:
    def f(text: Annotated[str, given(Template('the name {text}'))]) -> None: ...

    descs = annotated_given_descriptors(f)
    assert set(descs) == {'text'}
    assert descs['text'].phase == 'given'


def test_extract_ignores_unannotated_and_plain_annotated_params() -> None:
    def f(a: int, b: Annotated[str, 'just a string'], c: str) -> None: ...

    assert annotated_given_descriptors(f) == {}


def test_extract_skips_self() -> None:
    class T:
        def m(self, text: Annotated[str, given('a name')]) -> None: ...

    descs = annotated_given_descriptors(T.m)
    assert set(descs) == {'text'}


def test_extract_rejects_when_in_annotated() -> None:
    def f(x: Annotated[int, when('an action')]) -> None: ...

    with pytest.raises(PytestGivenError, match='only given'):
        annotated_given_descriptors(f)


def test_extract_rejects_then_in_annotated() -> None:
    def f(x: Annotated[int, then('an outcome')]) -> None: ...

    with pytest.raises(PytestGivenError, match='only given'):
        annotated_given_descriptors(f)


def test_extract_rejects_tstring_label() -> None:
    name = 'frozen'

    def f(x: Annotated[int, given(t'a {name} label')]) -> None: ...

    with pytest.raises(PytestGivenError, match='t-string'):
        annotated_given_descriptors(f)


def test_extract_rejects_multiple_descriptors_on_one_param() -> None:
    def f(x: Annotated[int, given('one'), given('two')]) -> None: ...

    with pytest.raises(PytestGivenError, match='multiple'):
        annotated_given_descriptors(f)


def test_extract_returns_empty_on_unresolvable_annotations() -> None:
    def f(
        x: 'DefinitelyNotAType',  # noqa: UP037, F821
        y: Annotated[str, given('a name')],
    ) -> None: ...

    # Best-effort: an unresolvable sibling annotation must not raise.
    assert annotated_given_descriptors(f) == {}


def test_graft_skips_recording_not_belonging_to_item(
    fresh_collector: Collector,
) -> None:
    """A recording left in the collector by another item (its key isn't in
    this item's `expected` set) is skipped, not grafted."""
    fresh_collector.start_scenario(NodeId('t::x'), 'x', 'mod', [])
    stale = FixtureRecording(
        root=Step(phase='given', narration=Narration(text='stale'), fixture_name='o')
    )
    fresh_collector.store_recording((object(), None), stale)
    item = _fake_item({})
    fixtures._graft_fixture_recordings(item, fresh_collector)
    assert fresh_collector._current_scenario is not None
    assert fresh_collector._current_scenario.steps == []


def test_graft_phase2_skips_decorated_fixture_without_recording(
    fresh_collector: Collector,
) -> None:
    """An Annotated given() on a decorated fixture that recorded nothing (no
    cached_result) is phase-1 territory — phase 2 must not synthesize a leaf
    for it and drop the body."""

    def testfn(machine: Annotated[object, given('override')]) -> None: ...

    deco = _fake_func(StepDescriptor('given', 'a machine'))
    fixturedef = SimpleNamespace(func=deco, cached_result=None, scope='function')
    fm = SimpleNamespace(
        getfixturedefs=lambda name, _i: {'machine': [fixturedef]}.get(name)
    )
    session = SimpleNamespace(_fixturemanager=fm)
    item = cast(
        pytest.Item,
        SimpleNamespace(fixturenames=['machine'], session=session, function=testfn),
    )
    fresh_collector.start_scenario(NodeId('t::x'), 'x', 'mod', [])
    fixtures._graft_fixture_recordings(item, fresh_collector)
    assert fresh_collector._current_scenario is not None
    assert fresh_collector._current_scenario.steps == []


class _Uncopyable:
    """A parametrize value whose type refuses `copy.copy` — a lock, a live
    connection, anything holding a resource."""

    def __copy__(self) -> _Uncopyable:
        raise TypeError('cannot copy this')


def test_an_uncopyable_parametrize_value_is_kept_as_it_is() -> None:
    """Snapshotting is best effort: a value that cannot be copied is one whose
    mutation could not have been guarded against anyway, and refusing to copy
    it must not take the run down with it."""
    value = _Uncopyable()
    assert snapshot_param_value(value) is value


def test_a_copyable_parametrize_value_is_snapshotted() -> None:
    """The copy is what keeps a later in-place mutation out of the table."""
    value = ['latte']
    snapshot = snapshot_param_value(value)
    value.append('cup')
    assert snapshot == ['latte']


class _IdentityRepr:
    """A parametrize value inheriting `object.__repr__`, which renders the
    object's own address — the shape a `MagicMock` shares."""


def test_a_value_rendering_by_identity_is_kept_as_it_is() -> None:
    """A copy renders as a different address than the object the test narrated,
    which would put a value in the cell that no case ever narrated and read to
    the rebound-parameter rule as a rebinding that never happened. Mutation
    cannot change such a rendering, so the copy protects nothing."""
    value = _IdentityRepr()
    assert snapshot_param_value(value) is value


class _StrByValueReprByIdentity:
    """`__str__` defined by value, `__repr__` inherited — so a copy renders
    alike under `{x}` but not under `{x!r}`."""

    def __str__(self) -> str:
        return 'a mug'


def test_a_value_rendering_by_identity_under_repr_only_is_kept_as_it_is() -> None:
    """Both renderings are checked: an interpolation may ask for either."""
    value = _StrByValueReprByIdentity()
    assert snapshot_param_value(value) is value
