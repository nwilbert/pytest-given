import functools
import inspect
import json
import types
import warnings
from collections.abc import Mapping, Sequence
from string import Formatter, templatelib
from typing import Any, Self

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
    Story,
)
from .collector import get_active_collector
from .template import Template, narration_from

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
        collector.push_step(self.phase, self.narration, activity_ids=self.activity_ids)
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

    def __call__(self, func: Any) -> Any:
        is_fixture = (
            getattr(func, '_fixture_function_marker', None) is not None
            or getattr(func, '_pytestfixturefunction', None) is not None
        )
        if isinstance(self._source, templatelib.Template):
            raise PytestGivenError(
                f"@{self.phase}(t'...') is not allowed on a fixture or helper; "
                "the function's argument values aren't in scope at decoration "
                'time. Use a plain string label, pytest_given.Template for '
                'deferred substitution from bound args, or move the step into '
                'the test body.'
            )
        if isinstance(self._source, Template) and is_fixture:
            raise PytestGivenError(
                f'@{self.phase}(Template(...)) on a fixture is not yet '
                'supported; use a plain string label, or move the step into a '
                'helper function.'
            )
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
            return gen_wrapper

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
            collector.push_step(self.phase, narration, activity_ids=self.activity_ids)
            try:
                return func(*args, **kwargs)
            finally:
                collector.pop_step()

        wrapper._step_descriptor = self  # type: ignore[attr-defined]
        return wrapper

    def _validate_template_against_signature(self, func: Any) -> inspect.Signature:
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
        name: str | Template,
        tags: list[str],
        *,
        story: Story | None = None,
        activity_ids: tuple[ActivityId, ...] = (),
    ) -> None:
        self.name: str | Template = name
        self.tags = tags
        self.story = story
        self.activity_ids = activity_ids

    def __call__(self, func: Any) -> Any:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return func(*args, **kwargs)

        wrapper._scenario = self  # type: ignore[attr-defined]
        return wrapper


def _normalize_activity(
    activity: int | Sequence[int] | None,
) -> tuple[ActivityId, ...]:
    """Normalize the ``activity=`` kwarg to a tuple of ActivityId values."""
    if activity is None:
        return ()
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


_FORMATTER = Formatter()


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
            case NarrationPlaceholder(name=name, format_spec=spec, conversion=conv):
                resolved = _FORMATTER.convert_field(mapping[name], conv)
                out.append(
                    NarrationValue(
                        rendered=format(resolved, spec),
                        expression=name,
                        format_spec=spec,
                        conversion=conv,
                    )
                )
    return out


def attach(label: str | templatelib.Template, content: object) -> None:
    """Attach data to the current step.

    If *content* is a ``str`` it is stored verbatim.  Any other type is
    serialised as indented JSON.
    """
    if isinstance(label, Template):
        raise PytestGivenError(
            'attach(Template(...)) is not supported; use a t-string (eager) '
            'or a plain string.'
        )
    if isinstance(label, templatelib.Template):
        label = narration_from(label).text
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
    name: str | Template,
    tags: list[str] | None = None,
    *,
    story: Story | None = None,
    activities: Sequence[int] | None = None,
) -> ScenarioDecorator:
    """Mark a test for inclusion in the report."""
    if isinstance(name, templatelib.Template):
        raise PytestGivenError(
            't-string in @scenario(...) is not supported; @scenario runs at '
            'module-import time, so the parametrize parameters are not yet in '
            'scope. Use pytest_given.Template(...) for parametrized scenario '
            'names, or a plain string for static names.'
        )
    if story is not None and not isinstance(story, Story):
        raise PytestGivenError(
            f'@scenario(story=...) must be a Story instance; '
            f'got {type(story).__name__}: {story!r}'
        )
    activity_ids: tuple[ActivityId, ...] = (
        tuple(ActivityId(i) for i in activities) if activities else ()
    )
    return ScenarioDecorator(name, tags or [], story=story, activity_ids=activity_ids)
