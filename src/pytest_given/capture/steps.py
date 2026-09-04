"""The step front doors: `given` / `when` / `then` / `when_then` / `attach`.

The dual context-manager/decorator descriptor, the paired `when_then`, and the
attachment call that binds to whatever step is open. They share
`collector.recording_collector`, which decides whether a call records, no-ops with a
warning, or refuses. The scenario marker is `scenario.py`'s.
"""

import functools
import inspect
import json
import types
from collections.abc import Callable, Mapping, Sequence
from string import templatelib
from typing import (
    Protocol,
    Self,
    cast,
    runtime_checkable,
)

from ..model import (
    ActivityId,
    Narration,
    Phase,
    PytestGivenError,
    SourceLocation,
    narration_of,
)
from .collector import Collector, get_active_collector, recording_collector
from .source import capture_caller_source, code_source
from .template import (
    StepText,
    Template,
    narration_from,
    reject_baked_values,
    resolve_template_parts,
)


@runtime_checkable
class StepDecorated(Protocol):
    """A function carrying a pytest-given step descriptor.

    Not a return type — the decorator is signature-preserving — but the shape
    the two read sites in `plugin.fixtures` narrow with, so the marker contract
    is written down once and checked where it is read.
    """

    _step_descriptor: StepDescriptor


_TEMPLATE_PARAM_KINDS = frozenset(
    {
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
        inspect.Parameter.KEYWORD_ONLY,
        inspect.Parameter.POSITIONAL_ONLY,
    }
)


class StepDescriptor:
    """Dual context-manager / decorator for Given/When/Then steps.

    As a context manager:
        with given("a coffee machine"):
            ...

    As a decorator:
        @given("a coffee machine")
        def coffee_machine():
            ...
    """

    def __init__(
        self,
        phase: Phase,
        text: StepText,
        *,
        activity_ids: tuple[ActivityId, ...] = (),
    ) -> None:
        self.phase = phase
        self._source: StepText = text
        self.narration: Narration = narration_from(text)
        self.activity_ids: tuple[ActivityId, ...] = activity_ids

    @property
    def is_deferred_template(self) -> bool:
        """Whether the label was written as `pytest_given.Template(...)`."""
        return isinstance(self._source, Template)

    @property
    def is_tstring(self) -> bool:
        """Whether the label was written as a t-string (`t"…"`)."""
        return isinstance(self._source, templatelib.Template)

    def __enter__(self) -> Self:
        if self.is_deferred_template:
            raise PytestGivenError(
                f'{self.phase}(Template(...)) is not supported in a test body; '
                f'use a t-string for dynamic values, or a plain string for '
                f'static labels. Template is for @scenario(...) and helper-'
                f'function decorators, where deferred substitution is the only '
                f'sensible option.'
            )
        return self._open()

    def _open(self, pinned_source: SourceLocation | None = None) -> Self:
        """Open this step, optionally against an anchor its caller already has.

        `when_then` drives both halves from its own frames, so the `then` half
        can no longer be anchored by walking out to user code — it is entered
        from `__exit__`, where the user's line has moved on. It passes the
        pair's `with` line instead.
        """
        collector = recording_collector(self.phase, self.narration.text)
        if collector is None:
            return self
        source: SourceLocation | None = pinned_source
        if source is None and collector.capture_step_source:
            source = capture_caller_source()
        collector.push_step(
            self.phase, self.narration, activity_ids=self.activity_ids, source=source
        )
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> None:
        collector = get_active_collector()
        if collector is None or not collector.recording:
            return
        collector.pop_step()

    def __call__[F: Callable[..., object]](self, func: F) -> F:
        """Decorate `func`: reject the forms this label cannot take, then wrap
        it in whatever its own flavor needs.

        Signature-preserving on purpose. Returning a Protocol here — one
        carrying `_step_descriptor` and no `__call__` — left every decorated
        helper uncallable to a type checker, which the in-repo mypy run could
        not see because it checks `src` only. `@scenario` makes the same
        promise by returning the function unwrapped.

        The signature crosses between the two halves only for a `Template`
        label, whose per-call substitution needs what validation inspected.
        """
        return self._wrapped(func, self._validated(func))

    def _validated(self, func: Callable[..., object]) -> inspect.Signature | None:
        """Reject the label forms `func` cannot carry, returning the signature
        a `Template` label binds against (None for every other label)."""
        # pytest>=9 is the floor, so `_fixture_function_marker` is the only
        # spelling; the pre-8.4 `_pytestfixturefunction` cannot appear.
        if getattr(func, '_fixture_function_marker', None) is not None:
            raise PytestGivenError(
                f'@{self.phase}(...) is above @pytest.fixture on '
                f'{func.__name__!r}, which leaves pytest with a plain '
                f'function and no fixture by that name. Put @pytest.fixture '
                f'outermost:\n\n'
                f'    @pytest.fixture\n'
                f'    @{self.phase}(...)\n'
                f'    def {func.__name__}(): ...'
            )
        if self.is_tstring:
            self._check_tstring_decorator_safety()
        if self.is_deferred_template:
            return self._validate_template_against_signature(func)
        return None

    def _wrapped[F: Callable[..., object]](
        self, func: F, sig: inspect.Signature | None
    ) -> F:
        """`func` behind the wrapper its flavor needs, carrying this descriptor.

        Four flavors, and the branch order matters: an async generator is
        neither `isgeneratorfunction` nor `iscoroutinefunction`, so it has to be
        asked about before the call-time wrappers can claim it.
        """
        # A generator function is a fixture body: `pytest_fixture_setup` has
        # already made the recording's root from this descriptor, so there is
        # nothing to do at call time and nothing to wrap — marking it in place
        # keeps the real function, the way `@scenario` does.
        if inspect.isgeneratorfunction(func) or inspect.isasyncgenfunction(func):
            return self._marked(func)

        # A coroutine function needs its own wrapper: the sync one would call
        # `func(...)`, get back an un-awaited coroutine, and pop in `finally`
        # — closing the step before a line of the body had run.
        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: object, **kwargs: object) -> object:
                collector = self._push_call_step(func, sig, args, kwargs)
                if collector is None:
                    return await func(*args, **kwargs)
                try:
                    return await func(*args, **kwargs)
                finally:
                    collector.pop_step()

            return self._marked(cast('F', async_wrapper))

        @functools.wraps(func)
        def wrapper(*args: object, **kwargs: object) -> object:
            collector = self._push_call_step(func, sig, args, kwargs)
            if collector is None:
                return func(*args, **kwargs)
            try:
                return func(*args, **kwargs)
            finally:
                collector.pop_step()

        return self._marked(cast('F', wrapper))

    def _marked[F: Callable[..., object]](self, func: F) -> F:
        """Hang this descriptor on `func`, where the read sites find it."""
        func._step_descriptor = self  # type: ignore[attr-defined]
        return func

    def _push_call_step(
        self,
        func: Callable[..., object],
        sig: inspect.Signature | None,
        args: tuple[object, ...],
        kwargs: Mapping[str, object],
    ) -> Collector | None:
        """Open this step for one helper call, returning the collector to pop
        it with — or None when the call passes straight through.

        Nothing recording is a pass-through rather than an error here: a
        decorated helper is an ordinary function its module may call outside
        any test. The least obvious transparent case is pytest invoking this
        very descriptor as a fixture body, whose root the fixture hook has
        already recorded from the same narration.
        """
        collector = get_active_collector()
        if (
            collector is None
            or not collector.recording
            or collector.active_fixture_descriptor is self
        ):
            return None
        narration = (
            self._narration_for_call(sig, args, kwargs)
            if sig is not None
            else self.narration
        )
        # The helper's FunctionDef *is* the step body — anchor there, no frame
        # walk needed.
        source = code_source(func.__code__) if collector.capture_step_source else None
        collector.push_step(
            self.phase, narration, activity_ids=self.activity_ids, source=source
        )
        return collector

    def _check_tstring_decorator_safety(self) -> None:
        reject_baked_values(
            self.narration,
            f'@{self.phase}',
            'module load',
            'move the text into the test body (with given/when/then(t"...")) '
            'where the value is in scope',
        )

    def _validate_template_against_signature(
        self, func: Callable[..., object]
    ) -> inspect.Signature:
        assert isinstance(self._source, Template)
        sig = inspect.signature(func)
        for name in self._source.get_identifiers():
            param = sig.parameters.get(name)
            if param is None or param.kind not in _TEMPLATE_PARAM_KINDS:
                available = sorted(
                    n
                    for n, p in sig.parameters.items()
                    if p.kind in _TEMPLATE_PARAM_KINDS
                )
                raise PytestGivenError(
                    f'@{self.phase}(Template({self._source.template!r})) '
                    f'references placeholder {{{name}}} which is not a '
                    f'named parameter of {func.__name__}. '
                    f'Available parameters: {available}. Rename the '
                    f'placeholder, or add the parameter.'
                )
        return sig

    def _narration_for_call(
        self,
        sig: inspect.Signature,
        args: tuple[object, ...],
        kwargs: Mapping[str, object],
    ) -> Narration:
        assert isinstance(self._source, Template)
        bound = sig.bind(*args, **kwargs)
        bound.apply_defaults()
        parts = resolve_template_parts(self.narration.parts, bound.arguments)
        return narration_of(parts)


def normalize_activity(
    activity: int | Sequence[int] | None,
    kwarg: str = 'activity',
) -> tuple[ActivityId, ...]:
    """Normalize an ``activity=`` / ``activities=`` kwarg to ActivityId values.

    `kwarg` names the argument the author actually wrote, so the step form and
    the scenario form each report their own.
    """
    if activity is None:
        return ()
    # Each accepting branch excludes the type that would otherwise slip into
    # it: a bool is an `int` and a str is a `Sequence[int]` to nobody but
    # `isinstance`. Without the guards `activities='13'` would yield ids 1
    # and 3 rather than the TypeError it deserves.
    if isinstance(activity, int) and not isinstance(activity, bool):
        return (ActivityId(activity),)
    if isinstance(activity, Sequence) and not isinstance(activity, str):
        result: list[ActivityId] = []
        for item in activity:
            if not isinstance(item, int) or isinstance(item, bool):
                raise TypeError(
                    f'{kwarg} sequence must contain int values, got {type(item)!r}'
                )
            result.append(ActivityId(item))
        return tuple(result)
    raise TypeError(
        f'{kwarg} must be an int or a Sequence[int], got {type(activity)!r}'
    )


def given(
    text: StepText,
    *,
    activity: int | Sequence[int] | None = None,
) -> StepDescriptor:
    """Create a Given step (context manager or decorator)."""
    return StepDescriptor('given', text, activity_ids=normalize_activity(activity))


def when(
    text: StepText,
    *,
    activity: int | Sequence[int] | None = None,
) -> StepDescriptor:
    """Create a When step (context manager or decorator)."""
    return StepDescriptor('when', text, activity_ids=normalize_activity(activity))


def then(
    text: StepText,
    *,
    activity: int | Sequence[int] | None = None,
) -> StepDescriptor:
    """Create a Then step (context manager or decorator)."""
    return StepDescriptor('then', text, activity_ids=normalize_activity(activity))


class WhenThen:
    """Narrate an action and its outcome as two sibling steps in one ``with``.

    Reach for it when a single expression is both the action under test and
    the thing you assert about — most often an expected raise, where forcing
    one ``then`` step to carry both reads awkwardly. The body runs inside the
    ``when``; the ``then`` sibling is emitted once the body exits cleanly, so
    pair it with a vanilla ``pytest.raises`` *inside* the same ``with`` (the
    inner context manager swallows the error before this one's ``__exit__``
    runs)::

        with when_then('the parser reads a table-less document',
                       'no pipe table is reported'), \\
             pytest.raises(PytestGivenError, match=r'no .*table'):
            parse_glossary_tables(text, term_column=0, ...)

    If the body raises and nothing catches it, the outcome never held: the
    ``when`` is recorded, the ``then`` is skipped, and the exception
    propagates.
    """

    def __init__(
        self,
        when_text: StepText,
        then_text: StepText,
    ) -> None:
        self._when = StepDescriptor('when', when_text)
        self._then = StepDescriptor('then', then_text)
        self._source: SourceLocation | None = None

    def __enter__(self) -> Self:
        collector = get_active_collector()
        if collector is not None and collector.capture_step_source:
            # Both steps share the pair's `with` statement as their anchor —
            # captured here because the `then` half opens from `__exit__`,
            # where the user's current line is the end of the body.
            self._source = capture_caller_source()
        self._when._open(self._source)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> None:
        self._when.__exit__(exc_type, exc_val, exc_tb)
        if exc_type is None:
            self._then._open(self._source)
            self._then.__exit__(None, None, None)


def when_then(
    when_text: StepText,
    then_text: StepText,
) -> WhenThen:
    """Pair a When action with its Then outcome as two sibling steps."""
    return WhenThen(when_text, then_text)


def attach(label: str, content: object) -> None:
    """Attach data to the current step.

    *label* is plain text — an f-string is the way to vary it. If *content* is a
    ``str`` it is stored verbatim; any other type is serialized as indented JSON.
    """
    if not isinstance(label, str):
        raise PytestGivenError(
            'attachment labels are plain text; f-strings are fine — '
            'attach(f"{kind} log", …). In a parametrized scenario keep the '
            'label the same in every case and let the content vary.'
        )
    collector = recording_collector('attach', label)
    if collector is None:
        return
    if isinstance(content, str):
        collector.attach(label, content, content_type='text')
    else:
        collector.attach(
            label,
            json.dumps(content, indent=2, default=str),
            content_type='json',
        )
