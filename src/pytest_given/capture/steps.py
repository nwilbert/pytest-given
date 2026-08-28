"""The step front doors: `given` / `when` / `then` / `when_then` / `attach`.

One module for the whole of what a step *is* from user code — the dual
context-manager/decorator descriptor, the paired `when_then`, and the
attachment call that binds to whatever step is open. They share
`_recording_collector`, which is the one place that decides whether a call
records, no-ops with a warning, or refuses.

Split out of the former `decorators.py` for the reason the `plugin` package
was split: that module held the step descriptor, the scenario marker and the
`Annotated` reader in one 600-line file while every other module in the tree
holds one thing. The scenario marker is `scenario.py`'s.

`capture.traceback` names this module in `_INTERNAL_SUFFIXES`: the wrappers and
`__enter__` / `__exit__` below are pytest-given frames a reader never wants in
a failure traceback. Moving a wrapper out of here means updating that tuple.
"""

import functools
import inspect
import json
import types
import warnings
from collections.abc import Callable, Mapping, Sequence
from string import templatelib
from typing import (
    Any,
    Protocol,
    Self,
    assert_never,
    cast,
    runtime_checkable,
)

from ..model import (
    ActivityId,
    Narration,
    NarrationLiteral,
    NarrationPart,
    NarrationPlaceholder,
    NarrationTermRef,
    NarrationValue,
    Phase,
    PytestGivenError,
    PytestGivenWarning,
    SourceLocation,
    narration_text,
)
from .collector import Collector, get_active_collector, no_scenario_error
from .source import capture_caller_source, code_source
from .template import Template, narration_from, resolved_placeholder_part


@runtime_checkable
class StepDecorated(Protocol):
    """A function carrying a pytest-given step descriptor.

    `StepDescriptor.__call__` stashes `self` as ``_step_descriptor`` on the
    wrapped function; `_ensure_teardown_wrapped` does the same for the
    generator-fixture wrapper. Read sites (`pytest_fixture_setup`,
    `_graft_fixture_recordings`) cast to this Protocol instead of probing an
    untyped attribute.
    """

    _step_descriptor: StepDescriptor


def _recording_collector(action: str, warning: str) -> Collector | None:
    """The collector to record into, or None when the caller should do nothing.

    None means an unannotated test, where `with given(...)` and `attach(...)`
    are both legal and both no-ops: a test without `@scenario` is not a
    mistake, it simply has no report to appear in, so it warns once instead of
    raising. With nothing recording anywhere else there is no such reading, and
    the call raises.

    `stacklevel=3` reaches past this helper and its caller to the user's own
    line — the two front doors are called directly from user code.
    """
    collector = get_active_collector()
    if collector is not None and collector.state != 'idle':
        return collector
    if collector is not None and collector.inside_unannotated_test:
        warnings.warn(warning, PytestGivenWarning, stacklevel=3)
        return None
    raise no_scenario_error(action)


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
        text: str | templatelib.Template | Template,
        *,
        activity_ids: tuple[ActivityId, ...] = (),
    ) -> None:
        self.phase = phase
        self._source: str | templatelib.Template | Template = text
        self.narration: Narration = narration_from(text)
        self.activity_ids: tuple[ActivityId, ...] = activity_ids
        # Lint anchor of the step's `with` statement. A descriptor normally
        # captures its own caller frame on __enter__; when_then composes two
        # descriptors behind an extra frame, so it captures once itself and
        # pins the shared location here (_captures_own_source False).
        self._pinned_source: SourceLocation | None = None
        self._captures_own_source: bool = True

    @property
    def is_deferred_template(self) -> bool:
        """Whether the label was written as `pytest_given.Template(...)`.

        A property rather than an `isinstance` at each read site: the question
        is asked from four places here and one in `plugin/fixtures.py`, and
        that last one is the only thing in the package that would otherwise
        reach across a package boundary into a private attribute. What the
        label was *written* as is the descriptor's business to answer.
        """
        return isinstance(self._source, Template)

    @property
    def is_tstring(self) -> bool:
        """Whether the label was written as a t-string (`t"…"`).

        The counterpart to `is_deferred_template`, for the same reason: the
        two rejection sites — a decorator label and an `Annotated` one — ask
        exactly this and nothing else about `_source`.
        """
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
        collector = _recording_collector(
            f"enter '{self.phase}: {self.narration.text}'",
            f"'{self.phase}: {self.narration.text}' recorded in a test without "
            '@scenario — step will not appear in the report.',
        )
        if collector is None:
            return self
        source: SourceLocation | None = None
        if collector.capture_step_source:
            source = (
                capture_caller_source(skip=2)
                if self._captures_own_source
                else self._pinned_source
            )
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
        if collector is None or collector.inside_unannotated_test:
            return
        collector.pop_step()

    def __call__(self, func: Callable[..., object]) -> StepDecorated:
        """Decorate `func`: reject the forms this label cannot take, then wrap
        it in whatever its own flavor needs.

        The two halves are separated because they answer different questions —
        whether this *label* is legal on this function at all, and which of
        four wrappers the *function* calls for. Only `sig` crosses between
        them, and only for a `Template` label, whose per-call substitution
        needs the signature the validation already had to inspect.
        """
        return self._wrapped(func, self._validated(func))

    def _validated(self, func: Callable[..., object]) -> inspect.Signature | None:
        """Reject the label forms `func` cannot carry, returning the signature
        a `Template` label binds against (None for every other label)."""
        is_fixture = (
            getattr(func, '_fixture_function_marker', None) is not None
            or getattr(func, '_pytestfixturefunction', None) is not None
        )
        if self.is_deferred_template and is_fixture:
            raise PytestGivenError(
                f'@{self.phase}(Template(...)) on a fixture is not yet '
                'supported; use a plain string label, or move the step into a '
                'helper function.'
            )
        if self.is_tstring:
            self._check_tstring_decorator_safety()
        if self.is_deferred_template:
            return self._validate_template_against_signature(func)
        return None

    def _wrapped(
        self, func: Callable[..., object], sig: inspect.Signature | None
    ) -> StepDecorated:
        """`func` behind the wrapper its flavor needs, carrying this descriptor.

        Four flavors, and the branch order matters: an async generator is
        neither `isgeneratorfunction` nor `iscoroutinefunction`, so it has to be
        asked about before the call-time wrappers can claim it.
        """
        # A generator function is a fixture body: `pytest_fixture_setup` has
        # already made the recording's root from this descriptor, so the
        # wrapper only carries the marker.
        if inspect.isgeneratorfunction(func):

            @functools.wraps(func)
            def gen_wrapper(*args: Any, **kwargs: Any) -> Any:
                yield from func(*args, **kwargs)

            return self._marked(gen_wrapper)

        if inspect.isasyncgenfunction(func):

            @functools.wraps(func)
            async def async_gen_wrapper(*args: Any, **kwargs: Any) -> Any:
                async for value in func(*args, **kwargs):
                    yield value

            return self._marked(async_gen_wrapper)

        # A coroutine function needs its own wrapper: the sync one would call
        # `func(...)`, get back an un-awaited coroutine, and pop in `finally`
        # — closing the step before a line of the body had run.
        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                collector = self._push_call_step(func, sig, args, kwargs)
                if collector is None:
                    return await func(*args, **kwargs)
                try:
                    return await func(*args, **kwargs)
                finally:
                    collector.pop_step()

            return self._marked(async_wrapper)

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            collector = self._push_call_step(func, sig, args, kwargs)
            if collector is None:
                return func(*args, **kwargs)
            try:
                return func(*args, **kwargs)
            finally:
                collector.pop_step()

        return self._marked(wrapper)

    def _marked(self, wrapper: Callable[..., object]) -> StepDecorated:
        """Hang this descriptor on the wrapper, where the read sites find it."""
        wrapper._step_descriptor = self  # type: ignore[attr-defined]
        return cast('StepDecorated', wrapper)

    def _push_call_step(
        self,
        func: Callable[..., object],
        sig: inspect.Signature | None,
        args: tuple[Any, ...],
        kwargs: Mapping[str, Any],
    ) -> Collector | None:
        """Open this step for one helper call, returning the collector to pop
        it with — or None when the call passes straight through.

        None covers the three transparent cases: no collector, an idle one,
        and pytest invoking this very descriptor as a fixture body (where
        `pytest_fixture_setup` already created the root from its narration and
        a second push would duplicate it).
        """
        collector = get_active_collector()
        if (
            collector is None
            or collector.state == 'idle'
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
        """A t-string passed to a decorator is evaluated once at module load;
        any non-glossary interpolation captures its value frozen there.

        Glossary handles render as `NarrationTermRef` and are safe to bake in
        (they identify a concept, not a per-call datum). Anything else surfaces
        as `NarrationValue`, which means the author probably expected per-call
        substitution and won't get it — point them at the right form.
        """
        for part in self.narration.parts:
            if not isinstance(part, NarrationValue):
                continue
            raise PytestGivenError(
                f'@{self.phase}(t"...") interpolates non-glossary value '
                f'{{{part.expression}}} (rendered as {part.rendered!r}); '
                f't-strings on a decorator evaluate once at module load, '
                f'so the value is baked into every recorded step. '
                f'Use a glossary handle (g.actor/g.work_object/g.verb) for a '
                f'term reference; pytest_given.Template('
                f"'...{{{part.expression}}}...') for a helper arg bound "
                f'per call; or move the step into the test body (with '
                f'given/when/then(t"...")) where the value is in scope.'
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
                    f'positional-or-keyword parameter of {func.__name__}. '
                    f'Available parameters: {available}. Rename the '
                    f'placeholder, or add the parameter.'
                )
        return sig

    def _narration_for_call(
        self,
        sig: inspect.Signature,
        args: tuple[Any, ...],
        kwargs: Mapping[str, Any],
    ) -> Narration:
        assert isinstance(self._source, Template)
        bound = sig.bind(*args, **kwargs)
        bound.apply_defaults()
        parts = _resolve_template_parts(self.narration.parts, bound.arguments)
        return Narration(text=narration_text(parts), parts=parts)


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
    # `isinstance`, so both guards carry a `not isinstance(...)` and both
    # values fall through to the TypeError at the end. Without them
    # `activities='13'` would yield ids 1 and 3 and fail later against a story
    # that visibly lists them as valid.
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
    text: str | templatelib.Template | Template,
    *,
    activity: int | Sequence[int] | None = None,
) -> StepDescriptor:
    """Create a Given step (context manager or decorator)."""
    return StepDescriptor('given', text, activity_ids=normalize_activity(activity))


def when(
    text: str | templatelib.Template | Template,
    *,
    activity: int | Sequence[int] | None = None,
) -> StepDescriptor:
    """Create a When step (context manager or decorator)."""
    return StepDescriptor('when', text, activity_ids=normalize_activity(activity))


def then(
    text: str | templatelib.Template | Template,
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
    propagates. It composes two `StepDescriptor` instances, so every guard
    (Template rejection, idle/unannotated handling, t-string narration) is
    inherited by construction.
    """

    def __init__(
        self,
        when_text: str | templatelib.Template | Template,
        then_text: str | templatelib.Template | Template,
    ) -> None:
        self._when = StepDescriptor('when', when_text)
        self._then = StepDescriptor('then', then_text)
        self._when._captures_own_source = False
        self._then._captures_own_source = False

    def __enter__(self) -> Self:
        collector = get_active_collector()
        if collector is not None and collector.capture_step_source:
            # Both steps share the pair's `with` statement as their anchor —
            # captured here because the composed descriptors' own caller frame
            # would be this method, not user code.
            source = capture_caller_source(skip=2)
            self._when._pinned_source = source
            self._then._pinned_source = source
        self._when.__enter__()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> None:
        self._when.__exit__(exc_type, exc_val, exc_tb)
        if exc_type is None:
            self._then.__enter__()
            self._then.__exit__(None, None, None)


def when_then(
    when_text: str | templatelib.Template | Template,
    then_text: str | templatelib.Template | Template,
) -> WhenThen:
    """Pair a When action with its Then outcome as two sibling steps."""
    return WhenThen(when_text, then_text)


def _resolve_template_parts(
    parts: list[NarrationPart],
    mapping: Mapping[str, Any],
) -> list[NarrationPart]:
    out: list[NarrationPart] = []
    for part in parts:
        assert not isinstance(part, NarrationValue), (
            'pytest_given.Template never yields NarrationValue'
        )
        match part:
            case NarrationLiteral():
                out.append(part)
            case NarrationPlaceholder(name=name):
                out.append(resolved_placeholder_part(part, mapping[name]))
            case NarrationTermRef():
                # Not reachable while `Template` parses only literals and
                # placeholders, but a term ref carries its own display and has
                # nothing to resolve — passing it through is what keeps the
                # word in the narration if `Template` ever learns to hold one.
                out.append(part)
            case _:
                assert_never(part)
    return out


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
    collector = _recording_collector(
        f"attach '{label}'",
        f"attach('{label}') called in a test without @scenario — "
        'attachment will not appear in the report.',
    )
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
