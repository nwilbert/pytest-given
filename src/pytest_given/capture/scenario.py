"""The scenario marker: `@scenario`, and the `Annotated` labels it reads.

What marks a test for the report, as opposed to what records inside one —
that is `steps.py`, which this module imports for the descriptor an
`Annotated[..., given(...)]` parameter carries.
"""

import inspect
from collections.abc import Callable, Sequence
from string import templatelib
from typing import cast, get_type_hints

from ..model import (
    Pin,
    PytestGivenError,
    Story,
)
from .steps import StepDescriptor
from .story import Pins, sentence_handles
from .template import (
    ResolvedName,
    StepText,
    narration_from,
    reject_baked_values,
)


class ScenarioDecorator:
    """Decorator that marks a test for inclusion in the report."""

    def __init__(
        self,
        name: ResolvedName,
        tags: list[str],
        *,
        stories: tuple[Story, ...] = (),
        pins: tuple[Pin, ...] = (),
        group_parametrized: bool = True,
    ) -> None:
        self.name: ResolvedName = name
        self.tags = tags
        self.stories = stories
        self.pins = pins
        self.group_parametrized = group_parametrized

    def __call__(self, func: Callable[..., object]) -> Callable[..., object]:
        """Mark `func` and hand back the same object.

        No pass-through wrapper: a `*args, **kwargs` shim would hide the real
        function — its signature, and so its fixture requests — behind
        `functools.wraps`.
        """
        func._scenario = self  # type: ignore[attr-defined]
        return func


def scenario_marker(func: object) -> ScenarioDecorator | None:
    """The marker `@scenario` hung on `func`, or None for anything else.

    Reading the attribute is this module's job, so its name stays spelled in
    the one file that writes it.
    """
    marker = getattr(func, '_scenario', None)
    return marker if isinstance(marker, ScenarioDecorator) else None


def scenario(
    name: StepText,
    tags: list[str] | None = None,
    *,
    stories: Story | Sequence[Story] | None = None,
    pins: Pins | None = None,
    group_parametrized: bool = True,
) -> ScenarioDecorator:
    """Mark a test for inclusion in the report."""
    resolved_name: ResolvedName
    if isinstance(name, templatelib.Template):
        # Glossary handles are in scope at import time and render eagerly to
        # term refs; a parametrize value is not, so it would be baked in.
        resolved_name = narration_from(name)
        reject_baked_values(
            resolved_name,
            '@scenario',
            'module import',
            'a plain string for a static name',
        )
    else:
        resolved_name = name
    matched = _matched_stories(stories)
    handles = sentence_handles(pins)
    pinned = {handle.story.id: handle.story for handle in handles}
    for story in matched:
        if story.id in pinned:
            raise PytestGivenError(
                f'@scenario names story {story.title!r} in both stories= and '
                f'pins=: stories= matches narration against it, pins= replaces '
                f'that matching. Keep one.'
            )
    return ScenarioDecorator(
        resolved_name,
        tags or [],
        stories=matched + tuple(pinned.values()),
        pins=tuple(handle.pin for handle in handles),
        group_parametrized=group_parametrized,
    )


def _matched_stories(stories: Story | Sequence[Story] | None) -> tuple[Story, ...]:
    if stories is None:
        return ()
    items = (stories,) if isinstance(stories, Story) else stories
    if (
        isinstance(items, Sequence)
        and not isinstance(items, str)
        and all(isinstance(item, Story) for item in items)
    ):
        return tuple({story.id: story for story in items}.values())
    raise PytestGivenError(
        f'@scenario(stories=...) takes a Story or a sequence of them; '
        f'got {type(stories).__name__}: {stories!r}'
    )


def annotated_given_descriptors(func: object) -> dict[str, StepDescriptor]:
    """Map each parameter carrying ``Annotated[..., given(...)]`` to its
    descriptor.

    Reads type hints off the unwrapped function (past the ``@scenario``
    wrapper). Best-effort: if the annotations cannot be resolved, returns an
    empty mapping rather than failing the test. Rejects the forbidden forms —
    ``when(...)`` / ``then(...)``, a t-string label, a pin, or more than
    one descriptor on a single parameter.
    """
    target = inspect.unwrap(cast('Callable[..., object]', func))
    try:
        hints = get_type_hints(target, include_extras=True)
    except Exception:  # noqa: BLE001 — annotations are arbitrary user code; see the docstring
        return {}
    out: dict[str, StepDescriptor] = {}
    for name, hint in hints.items():
        if name in ('self', 'cls', 'return'):
            continue
        metadata = getattr(hint, '__metadata__', None)
        if metadata is None:
            continue
        descriptors = [m for m in metadata if isinstance(m, StepDescriptor)]
        if not descriptors:
            continue
        if len(descriptors) > 1:
            raise PytestGivenError(
                f'multiple given()/when()/then() in Annotated metadata for '
                f'parameter {name!r} — use exactly one.'
            )
        desc = descriptors[0]
        if desc.phase != 'given':
            raise PytestGivenError(
                f'only given() is supported inside Annotated; parameter '
                f"{name!r} carries {desc.phase}(). Use 'with when(...)' / "
                f"'with then(...)' in the test body for the action and outcome."
            )
        if desc.is_tstring:
            raise PytestGivenError(
                f'Annotated given(t"...") on parameter {name!r} is not '
                f'supported: a t-string evaluates at function-definition time, '
                f'where the parameter value is not in scope. Use '
                f'given(Template("... {{{name}}} ...")) for a per-case '
                f'placeholder, or a plain string label.'
            )
        if desc.pins:
            raise PytestGivenError(
                f'Annotated given(..., pins=...) on parameter {name!r} is not '
                f'supported: the label only renames the fixture step, so the pin '
                f'would be dropped. Pin a step inside the fixture body, or in the '
                f'test body.'
            )
        out[name] = desc
    return out
