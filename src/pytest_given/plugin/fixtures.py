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
    FixtureInstanceKey,
    StepDecorated,
    StepDescriptor,
    annotated_given_descriptors,
)
from ..model import (
    FixtureRecording,
    PytestGivenError,
    Step,
)
from .state import session_collector


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
        collector.store_recording(key, recording)


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
    """One fixture *instance*: the def it came from, plus its cache key.

    Both ends of the graft build this key, and they reach the cache key two
    ways — at setup from the request, at graft from what pytest cached. The
    shape lives here rather than at either end so the two cannot drift into
    keys that no longer meet; a miss is silent, and costs the fixture's whole
    recorded subtree.
    """
    return (id(fixturedef), cache_key)


def _graft_fixture_recordings(item: pytest.Item, collector: Collector) -> None:
    """Graft this item's fixture step-recordings and Annotated `given` labels.

    Phase 1 takes the fixture recordings in setup order — `_recordings` is
    insertion-ordered by setup time, so this stays correct even though
    `item.fixturenames` can list a dependent before its dependency — each with
    an optional Annotated override narration matched by parameter name. Phase 2
    takes the Annotated-only leaves in test-signature order.
    """
    assert hasattr(item, 'fixturenames'), f'expected fixturenames on {item!r}'
    func = getattr(item, 'function', None)
    descriptors = annotated_given_descriptors(func) if func is not None else {}

    fm = item.session._fixturemanager
    expected: dict[FixtureInstanceKey, str] = {}
    for name in item.fixturenames:
        defs = fm.getfixturedefs(name, item)
        if not defs:
            continue
        fixturedef = defs[-1]
        if getattr(fixturedef.func, '_step_descriptor', None) is None:
            continue
        if fixturedef.cached_result is None:
            continue
        key = _cached_instance_key(fixturedef)
        expected[key] = fixturedef.scope

    # Function-scoped recordings won't be re-consumed; drop after grafting so
    # the recordings dict doesn't grow unboundedly across the session.
    grafted_names: set[str | None] = set()
    to_drop: list[FixtureInstanceKey] = []
    for key, recording in collector.recordings():
        if key not in expected:
            continue
        name = recording.root.fixture_name
        descriptor = descriptors.get(name) if name is not None else None
        override = descriptor.narration if descriptor is not None else None
        collector.graft_recording(recording, override_narration=override)
        grafted_names.add(name)
        if expected[key] == 'function':
            to_drop.append(key)
    for key in to_drop:
        collector.drop_recording(key)

    # Parametrize values and built-in / undecorated fixtures.
    for name, descriptor in descriptors.items():
        if name in grafted_names:
            continue
        defs = fm.getfixturedefs(name, item)
        fdef = defs[-1] if defs else None
        # A decorated fixture is phase-1 territory; skip it here so its
        # recorded body is never replaced by a bodyless leaf.
        if (
            fdef is not None
            and getattr(fdef.func, '_step_descriptor', None) is not None
        ):
            continue
        collector.graft_leaf_given(descriptor.narration)
