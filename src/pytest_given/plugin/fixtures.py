"""The fixture side: recording a decorated fixture's body, and grafting what
it recorded onto the test that requested it.

Where the plugin's coupling to pytest internals concentrates, so a pytest
upgrade's blast radius is greppable: `fixturedef.func` is reassigned to wrap a
generator body, `fixturedef.cached_result` says whether a test holds an
instance, and `item.session._fixturemanager.getfixturedefs` resolves what a
test requested. Each is unavoidable and none is public API.
"""

import contextlib
import functools
import inspect
from collections.abc import Callable, Generator
from typing import cast

import pytest

from ..capture import (
    Collector,
    FixtureRecording,
    StepDescriptor,
    annotated_given_descriptors,
    step_descriptor,
)
from ..model import (
    NarrationPlaceholder,
    PytestGivenError,
    Step,
    placeholder_mismatch,
)
from .state import session_collector, session_state


@pytest.hookimpl(hookwrapper=True)
def pytest_fixture_setup(
    fixturedef: pytest.FixtureDef[object],
    request: pytest.FixtureRequest,
) -> Generator[None]:
    desc = step_descriptor(fixturedef.func)
    if desc is None:
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
    if not collector.recording and fixturedef.scope == 'function':
        # Set up outside any tracked scenario — an unannotated test pulling in
        # a step fixture. A function-scoped one is set up again for the next
        # test that wants it, so skipping costs nothing. A wider scope is set
        # up *once* and served from cache to every later scenario, so it is
        # recorded regardless.
        yield
        return
    _ensure_teardown_wrapped(fixturedef, collector)
    recording = FixtureRecording(
        root=Step(
            phase=desc.phase,
            narration=desc.narration,
            pins=desc.pins,
            fixture_name=fixturedef.argname,
        )
    )
    try:
        with collector.fixture_setup(recording, desc):
            yield
    finally:
        recordings = session_state(request.config).fixture_recordings
        # Popped first, so a re-setup moves to the end: the graft reads the
        # store in setup order.
        recordings.pop(fixturedef, None)
        recordings[fixturedef] = recording


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
    original_typed = cast('Callable[..., Generator[object]]', func)

    @functools.wraps(func)
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
        with collector.fixture_teardown(), contextlib.suppress(StopIteration):
            next(gen)

    # `functools.wraps` copies `__dict__`, so the wrapper already carries the
    # original's `_step_descriptor`; only the idempotence flag is new.
    wrapped._pytest_given_teardown_wrapped = True  # type: ignore[attr-defined]
    fixturedef.func = wrapped  # type: ignore[misc]


def graft_fixture_recordings(item: pytest.Item, collector: Collector) -> None:
    func = getattr(item, 'function', None)
    descriptors = annotated_given_descriptors(func) if func is not None else {}
    _check_template_labels(item, descriptors)
    grafted = _graft_recorded_fixtures(item, collector, descriptors)
    _graft_annotated_leaves(item, collector, descriptors, grafted)


def _check_template_labels(
    item: pytest.Item, descriptors: dict[str, StepDescriptor]
) -> None:
    """Refuse a `Template` label whose placeholder names no parametrize column.

    Nothing downstream can fill such a slot: an unparametrized scenario never
    reaches grouping, so the placeholder would reach the renderers unresolved.
    """
    callspec = getattr(item, 'callspec', None)
    param_names = list(callspec.params) if callspec is not None else []
    for parameter, descriptor in descriptors.items():
        for part in descriptor.narration.parts:
            if not isinstance(part, NarrationPlaceholder):
                continue
            if callspec is None:
                raise PytestGivenError(
                    f'the Annotated given(Template(...)) label on parameter '
                    f'{parameter!r} of {item.nodeid!r} needs '
                    f'@pytest.mark.parametrize: its placeholders name '
                    f'parametrize columns. Use a plain string label instead.'
                )
            if part.name not in param_names:
                raise placeholder_mismatch(
                    part.name,
                    param_names,
                    where=f'in the Annotated label on parameter {parameter!r}',
                )


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
    cached = _cached_step_fixturedefs(item)
    grafted: set[str | None] = set()
    for fixturedef, recording in list(recordings.items()):
        if fixturedef not in cached:
            continue
        name = recording.root.fixture_name
        label = descriptors.get(name) if name is not None else None
        collector.graft_recording(recording.root, label=label)
        grafted.add(name)
        if fixturedef.scope == 'function':
            # Never re-consumed; dropped so the store doesn't grow
            # unboundedly across the session.
            del recordings[fixturedef]
    return grafted


def _cached_step_fixturedefs(item: pytest.Item) -> set[pytest.FixtureDef[object]]:
    """Every step fixture this item holds an instance of."""
    assert hasattr(item, 'fixturenames'), f'expected fixturenames on {item!r}'
    return {
        fixturedef
        for name in item.fixturenames
        if (fixturedef := _step_fixturedef(item, name)) is not None
        and fixturedef.cached_result is not None
    }


def _graft_annotated_leaves(
    item: pytest.Item,
    collector: Collector,
    descriptors: dict[str, StepDescriptor],
    grafted: set[str | None],
) -> None:
    """Graft the Annotated-only labels — parametrize values and built-in or
    undecorated fixtures — in test-signature order.

    A step fixture is grafted from its recording, even an empty one, and never
    as a bodyless leaf.
    """
    for name, descriptor in descriptors.items():
        if name in grafted or _step_fixturedef(item, name) is not None:
            continue
        collector.graft_leaf_given(descriptor.narration, pins=descriptor.pins)


def _step_fixturedef(item: pytest.Item, name: str) -> pytest.FixtureDef[object] | None:
    """The fixturedef `name` resolves to for this item, when it carries a step
    descriptor — else None. Both phases ask this, from opposite sides."""
    defs = item.session._fixturemanager.getfixturedefs(name, item)
    if not defs:
        return None
    fixturedef = defs[-1]
    if step_descriptor(fixturedef.func) is None:
        return None
    return fixturedef
