"""The fixture side: recording a decorated fixture's body, and grafting what
it recorded onto the test that requested it.
"""

import contextlib
import functools
import inspect
from collections.abc import Callable, Generator
from typing import cast

import pytest
from _pytest.fixtures import SubRequest

from ..capture import (
    Collector,
    StepDecorated,
    StepDescriptor,
    annotated_given_descriptors,
)
from ..model import (
    FixtureRecording,
    PytestGivenError,
    Step,
)
from .state import FixtureInstanceKey, session_collector, session_state


@pytest.hookimpl(hookwrapper=True)
def pytest_fixture_setup(
    fixturedef: pytest.FixtureDef[object],
    request: pytest.FixtureRequest,
) -> Generator[None]:
    desc = getattr(fixturedef.func, '_step_descriptor', None)
    if not isinstance(desc, StepDescriptor):
        yield
        return
    if desc.phase != 'given':
        raise PytestGivenError(
            f"Fixture '{fixturedef.argname}' is decorated with @{desc.phase}, "
            'but only @given is allowed on fixtures (fixtures are setup). '
            'Use @given(...) on the fixture, or move the step into the test body.'
        )
    if desc.is_deferred_template:
        raise PytestGivenError(
            f'@given(Template(...)) on fixture {fixturedef.argname!r} is not '
            'yet supported; use a plain string label, or move the step into a '
            'helper function.'
        )
    collector = session_collector(request.config)
    if collector.state == 'idle':
        # Fixture is being set up outside any tracked scenario (e.g. unannotated
        # test pulling in a step fixture). Don't record.
        yield
        return
    _ensure_teardown_wrapped(fixturedef, collector)
    recording = FixtureRecording(
        root=Step(
            phase=desc.phase,
            narration=desc.narration,
            fixture_name=fixturedef.argname,
        )
    )
    token = collector.enter_fixture_setup(recording, descriptor=desc)
    try:
        yield
    finally:
        collector.exit_fixture(token)
        key = _setup_instance_key(fixturedef, request)
        session_state(request.config).fixture_recordings[key] = recording


def _ensure_teardown_wrapped(
    fixturedef: pytest.FixtureDef[object], collector: Collector
) -> None:
    """Wrap a generator fixture's body once so post-yield code runs in
    fixture_teardown state. Idempotent.

    The closure captures the collector directly: fixturedefs live for exactly
    one session, and teardown can fire where no config is reachable (e.g. a
    session-scoped fixture finalized after the last item)."""
    func = fixturedef.func
    if getattr(func, '_pytest_given_teardown_wrapped', False):
        return
    if not inspect.isgeneratorfunction(func):
        return
    original = func
    desc = cast('StepDecorated', original)._step_descriptor
    original_typed = cast('Callable[..., Generator[object]]', original)

    @functools.wraps(original)
    def wrapped(*args: object, **kwargs: object) -> Generator[object]:
        gen = original_typed(*args, **kwargs)
        try:
            value = next(gen)
        except StopIteration:
            return
        yield value
        # Past the yield → teardown. Use the captured collector (not the
        # ContextVar): session-scoped fixtures tear down at session end, after
        # the per-test active collector is cleared.
        token = collector.enter_fixture_teardown()
        try:
            with contextlib.suppress(StopIteration):
                next(gen)
        finally:
            collector.exit_fixture(token)

    wrapped_typed = cast('StepDecorated', wrapped)
    wrapped_typed._pytest_given_teardown_wrapped = True  # type: ignore[attr-defined]
    wrapped_typed._step_descriptor = desc
    fixturedef.func = wrapped  # type: ignore[misc]


def _setup_instance_key(
    fixturedef: pytest.FixtureDef[object],
    request: pytest.FixtureRequest,
) -> FixtureInstanceKey:
    """The key at setup time, deriving the cache key from the live request."""
    return _fixture_instance_key(
        fixturedef, fixturedef.cache_key(cast(SubRequest, request))
    )


def _cached_instance_key(
    fixturedef: pytest.FixtureDef[object],
) -> FixtureInstanceKey:
    """The key at graft time, reading back the cache key pytest stored.

    `cached_result` is `(value, cache_key, exc)`; taking element 1 rather than
    re-deriving it is deliberate — the request that produced it is gone by now,
    and the stored value is by definition the one `_setup_instance_key` saw.
    """
    assert fixturedef.cached_result is not None
    return _fixture_instance_key(fixturedef, fixturedef.cached_result[1])


def _fixture_instance_key(
    fixturedef: pytest.FixtureDef[object],
    cache_key: object,
) -> FixtureInstanceKey:
    """Built here rather than at either end of the graft, so the two cannot
    drift into keys that no longer meet; a miss is silent, and costs the
    fixture's whole recorded subtree."""
    return (id(fixturedef), cache_key)


def graft_fixture_recordings(item: pytest.Item, collector: Collector) -> None:
    """Graft this item's fixture step-recordings and Annotated `given` labels."""
    func = getattr(item, 'function', None)
    descriptors = annotated_given_descriptors(func) if func is not None else {}
    grafted = _graft_recorded_fixtures(item, collector, descriptors)
    _graft_annotated_leaves(item, collector, descriptors, grafted)


def _graft_recorded_fixtures(
    item: pytest.Item,
    collector: Collector,
    descriptors: dict[str, StepDescriptor],
) -> set[str | None]:
    """Graft what this item's step fixtures recorded, in setup order, each with
    the Annotated override narration its parameter name carries. Returns the
    fixture names grafted — what `_graft_annotated_leaves` must leave alone.
    """
    recordings = session_state(item.config).fixture_recordings
    scopes = _recorded_fixture_scopes(item)
    grafted: set[str | None] = set()
    # Function-scoped recordings won't be re-consumed; drop after grafting so
    # the store doesn't grow unboundedly across the session.
    to_drop: list[FixtureInstanceKey] = []
    for key, recording in recordings.items():
        if key not in scopes:
            continue
        name = recording.root.fixture_name
        descriptor = descriptors.get(name) if name is not None else None
        collector.graft_recording(
            recording,
            override_narration=None if descriptor is None else descriptor.narration,
        )
        grafted.add(name)
        if scopes[key] == 'function':
            to_drop.append(key)
    for key in to_drop:
        del recordings[key]
    return grafted


def _recorded_fixture_scopes(item: pytest.Item) -> dict[FixtureInstanceKey, str]:
    """The instance key of every step fixture this item has cached, and its
    scope — which is what says whether its recording is still needed after."""
    assert hasattr(item, 'fixturenames'), f'expected fixturenames on {item!r}'
    scopes: dict[FixtureInstanceKey, str] = {}
    for name in item.fixturenames:
        fixturedef = _step_fixturedef(item, name)
        if fixturedef is None or fixturedef.cached_result is None:
            continue
        scopes[_cached_instance_key(fixturedef)] = fixturedef.scope
    return scopes


def _graft_annotated_leaves(
    item: pytest.Item,
    collector: Collector,
    descriptors: dict[str, StepDescriptor],
    grafted: set[str | None],
) -> None:
    """Graft the Annotated-only labels — parametrize values and built-in or
    undecorated fixtures — in test-signature order.

    A decorated fixture is phase-1 territory even when it recorded nothing, so
    its body is never replaced by a bodyless leaf.
    """
    for name, descriptor in descriptors.items():
        if name in grafted or _step_fixturedef(item, name) is not None:
            continue
        collector.graft_leaf_given(descriptor.narration)


def _step_fixturedef(item: pytest.Item, name: str) -> pytest.FixtureDef[object] | None:
    """The fixturedef `name` resolves to for this item, when it carries a step
    descriptor — else None. Both phases ask this, from opposite sides."""
    defs = item.session._fixturemanager.getfixturedefs(name, item)
    if not defs:
        return None
    fixturedef = defs[-1]
    if getattr(fixturedef.func, '_step_descriptor', None) is None:
        return None
    return fixturedef
