import functools
import inspect
import json
import types
import warnings
from collections.abc import Callable, Mapping, Sequence
from string import templatelib
from typing import Any, Protocol, Self, cast, runtime_checkable

import pytest

from ..model import (
    ActivityId,
    Narration,
    NarrationLiteral,
    NarrationPart,
    NarrationPlaceholder,
    NarrationValue,
    Phase,
    PytestGivenError,
    SourceLocation,
    Story,
)
from .collector import get_active_collector
from .source import capture_caller_source, code_source
from .template import Template, narration_from, placeholder_value


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


@runtime_checkable
class ScenarioMarked(Protocol):
    """A test function carrying a `ScenarioDecorator` marker.

    `ScenarioDecorator.__call__` stashes `self` as ``_scenario`` on the
    wrapper; `_get_scenario_marker` reads it via this Protocol.
    """

    _scenario: ScenarioDecorator


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

    def __enter__(self) -> Self:
        if isinstance(self._source, Template):
            raise PytestGivenError(
                f'{self.phase}(Template(...)) is not supported in a test body; '
                f'use a t-string for dynamic values, or a plain string for '
                f'static labels. Template is for @scenario(...) and helper-'
                f'function decorators, where deferred substitution is the only '
                f'sensible option.'
            )
        collector = get_active_collector()
        if collector is None or collector.state == 'idle':
            if collector is not None and collector.inside_unannotated_test:
                warnings.warn(
                    f"'{self.phase}: {self.narration.text}' recorded in a test "
                    'without @scenario — step will not appear in the report.',
                    pytest.PytestWarning,
                    stacklevel=2,
                )
                return self
            raise PytestGivenError(
                f"Cannot enter '{self.phase}: {self.narration.text}' — "
                'no active scenario or fixture.'
            )
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
        is_fixture = (
            getattr(func, '_fixture_function_marker', None) is not None
            or getattr(func, '_pytestfixturefunction', None) is not None
        )
        if isinstance(self._source, Template) and is_fixture:
            raise PytestGivenError(
                f'@{self.phase}(Template(...)) on a fixture is not yet '
                'supported; use a plain string label, or move the step into a '
                'helper function.'
            )
        if isinstance(self._source, templatelib.Template):
            self._check_tstring_decorator_safety()
        sig = (
            self._validate_template_against_signature(func)
            if isinstance(self._source, Template)
            else None
        )
        if inspect.isgeneratorfunction(func):

            @functools.wraps(func)
            def gen_wrapper(*args: Any, **kwargs: Any) -> Any:
                yield from func(*args, **kwargs)

            gen_wrapper._step_descriptor = self  # type: ignore[attr-defined]
            return cast('StepDecorated', gen_wrapper)

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            collector = get_active_collector()
            if (
                collector is None
                or collector.state == 'idle'
                or collector.active_fixture_descriptor is self
            ):
                return func(*args, **kwargs)
            narration = (
                self._narration_for_call(sig, args, kwargs)
                if sig is not None
                else self.narration
            )
            # The helper's FunctionDef *is* the step body — anchor there, no
            # frame walk needed.
            source = (
                code_source(func.__code__) if collector.capture_step_source else None
            )
            collector.push_step(
                self.phase, narration, activity_ids=self.activity_ids, source=source
            )
            try:
                return func(*args, **kwargs)
            finally:
                collector.pop_step()

        wrapper._step_descriptor = self  # type: ignore[attr-defined]
        return cast('StepDecorated', wrapper)

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
        return Narration(text=self._source.substitute(bound.arguments), parts=parts)


class ScenarioDecorator:
    """Decorator that marks a test for inclusion in the report."""

    def __init__(
        self,
        name: str | Template | Narration,
        tags: list[str],
        *,
        story: Story | None = None,
        activity_ids: tuple[ActivityId, ...] = (),
        group_parametrized: bool = True,
    ) -> None:
        self.name: str | Template | Narration = name
        self.tags = tags
        self.story = story
        self.activity_ids = activity_ids
        self.group_parametrized = group_parametrized

    def __call__(self, func: Callable[..., object]) -> ScenarioMarked:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return func(*args, **kwargs)

        wrapper._scenario = self  # type: ignore[attr-defined]
        return cast('ScenarioMarked', wrapper)


def _normalize_activity(
    activity: int | Sequence[int] | None,
) -> tuple[ActivityId, ...]:
    """Normalize the ``activity=`` kwarg to a tuple of ActivityId values."""
    if activity is None:
        return ()
    if isinstance(activity, bool | str):
        raise TypeError(
            f'activity must be an int or a Sequence[int], got {type(activity)!r}'
        )
    if isinstance(activity, int):
        return (ActivityId(activity),)
    if isinstance(activity, Sequence):
        result: list[ActivityId] = []
        for item in activity:
            if not isinstance(item, int):
                raise TypeError(
                    f'activity sequence must contain int values, got {type(item)!r}'
                )
            result.append(ActivityId(item))
        return tuple(result)
    raise TypeError(
        f'activity must be an int or a Sequence[int], got {type(activity)!r}'
    )


def given(
    text: str | templatelib.Template | Template,
    *,
    activity: int | Sequence[int] | None = None,
) -> StepDescriptor:
    """Create a Given step (context manager or decorator)."""
    return StepDescriptor('given', text, activity_ids=_normalize_activity(activity))


def when(
    text: str | templatelib.Template | Template,
    *,
    activity: int | Sequence[int] | None = None,
) -> StepDescriptor:
    """Create a When step (context manager or decorator)."""
    return StepDescriptor('when', text, activity_ids=_normalize_activity(activity))


def then(
    text: str | templatelib.Template | Template,
    *,
    activity: int | Sequence[int] | None = None,
) -> StepDescriptor:
    """Create a Then step (context manager or decorator)."""
    return StepDescriptor('then', text, activity_ids=_normalize_activity(activity))


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
                out.append(placeholder_value(part, mapping[name]))
    return out


def attach(label: str, content: object) -> None:
    """Attach data to the current step.

    *label* is plain text — an f-string is the way to vary it. If *content* is a
    ``str`` it is stored verbatim; any other type is serialised as indented JSON.
    """
    if not isinstance(label, str):
        raise PytestGivenError(
            'attachment labels are plain text; f-strings are fine — '
            'attach(f"{kind} log", …). In a parametrized scenario keep the '
            'label the same in every case and let the content vary.'
        )
    collector = get_active_collector()
    if collector is None or collector.state == 'idle':
        if collector is not None and collector.inside_unannotated_test:
            warnings.warn(
                f"attach('{label}') called in a test without @scenario — "
                'attachment will not appear in the report.',
                pytest.PytestWarning,
                stacklevel=2,
            )
            return
        raise PytestGivenError(
            f"Cannot attach '{label}' — no active scenario or fixture."
        )
    if isinstance(content, str):
        collector.attach(label, content, content_type='text')
    else:
        collector.attach(
            label,
            json.dumps(content, indent=2, default=str),
            content_type='json',
        )


def scenario(
    name: str | templatelib.Template | Template,
    tags: list[str] | None = None,
    *,
    story: Story | None = None,
    activities: Sequence[int] | None = None,
    group_parametrized: bool = True,
) -> ScenarioDecorator:
    """Mark a test for inclusion in the report."""
    resolved_name: str | Template | Narration
    if isinstance(name, templatelib.Template):
        # @scenario runs at module-import time. Glossary handles are in scope
        # then and render eagerly to term pills; a parametrize value is not,
        # so it would be baked into the name frozen. Accept the first, reject
        # the second — mirrors the step-decorator rule.
        narration = narration_from(name)
        for part in narration.parts:
            if isinstance(part, NarrationValue):
                raise PytestGivenError(
                    f'@scenario(t"...") interpolates non-glossary value '
                    f'{{{part.expression}}} (rendered as {part.rendered!r}); '
                    f'@scenario runs at module-import time, so parametrize '
                    f'values are not in scope. Use pytest_given.Template(...) '
                    f'for a parametrized name, a glossary handle '
                    f'(g.actor/g.work_object/g.verb) for a term pill, or a '
                    f'plain string for a static name.'
                )
        resolved_name = narration
    else:
        resolved_name = name
    if story is not None and not isinstance(story, Story):
        raise PytestGivenError(
            f'@scenario(story=...) must be a Story instance; '
            f'got {type(story).__name__}: {story!r}'
        )
    activity_ids: tuple[ActivityId, ...] = (
        tuple(ActivityId(i) for i in activities) if activities else ()
    )
    return ScenarioDecorator(
        resolved_name,
        tags or [],
        story=story,
        activity_ids=activity_ids,
        group_parametrized=group_parametrized,
    )
