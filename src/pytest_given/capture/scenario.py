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
    ActivityId,
    PytestGivenError,
    Story,
)
from .steps import StepDescriptor, normalize_activity
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
        story: Story | None = None,
        activity_ids: tuple[ActivityId, ...] = (),
        group_parametrized: bool = True,
    ) -> None:
        self.name: ResolvedName = name
        self.tags = tags
        self.story = story
        self.activity_ids = activity_ids
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
    story: Story | None = None,
    activities: int | Sequence[int] | None = None,
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
    if story is not None and not isinstance(story, Story):
        raise PytestGivenError(
            f'@scenario(story=...) must be a Story instance; '
            f'got {type(story).__name__}: {story!r}'
        )
    activity_ids = normalize_activity(activities, 'activities')
    _validate_story_binding(story, activity_ids)
    return ScenarioDecorator(
        resolved_name,
        tags or [],
        story=story,
        activity_ids=activity_ids,
        group_parametrized=group_parametrized,
    )


def _validate_story_binding(
    story: Story | None, activity_ids: tuple[ActivityId, ...]
) -> None:
    """Reject activity ids that no story can resolve.

    Both arguments are `@scenario`'s own, fully known here, so this does not
    wait for collection the way the parametrize-dependent checks must — and
    the traceback points at the decorator that got it wrong rather than
    naming a node id.
    """
    if story is None:
        if activity_ids:
            raise PytestGivenError(
                '@scenario(activities=...) requires story=; activity ids are '
                'meaningless without a story to look them up in.'
            )
        return
    valid_ids = {activity.id for activity in story.activities}
    for activity_id in activity_ids:
        if activity_id not in valid_ids:
            raise PytestGivenError(
                f'@scenario(activities=...): activity id {activity_id} not in '
                f'story {story.title!r} (valid: {sorted(valid_ids)}).'
            )


def annotated_given_descriptors(func: object) -> dict[str, StepDescriptor]:
    """Map each parameter carrying ``Annotated[..., given(...)]`` to its
    descriptor.

    Reads type hints off the unwrapped function (past the ``@scenario``
    wrapper). Best-effort: if the annotations cannot be resolved, returns an
    empty mapping rather than failing the test. Rejects the forbidden forms —
    ``when(...)`` / ``then(...)``, a t-string label, or more than one
    descriptor on a single parameter.
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
        out[name] = desc
    return out
