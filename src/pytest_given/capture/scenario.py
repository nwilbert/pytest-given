"""The scenario marker: `@scenario`, and the `Annotated` labels it reads.

What marks a test for the report, as opposed to what records inside one —
that is `steps.py`, which this module imports for the descriptor an
`Annotated[..., given(...)]` parameter carries.
"""

import inspect
from collections.abc import Callable, Sequence
from string import templatelib
from typing import Any, cast, get_type_hints

from ..model import (
    ActivityId,
    Narration,
    NarrationValue,
    PytestGivenError,
    Story,
)
from .steps import StepDescriptor, normalize_activity
from .template import Template, narration_from


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

    def __call__(self, func: Callable[..., object]) -> Callable[..., object]:
        """Mark `func` and hand back the same object.

        No pass-through wrapper: a `*args, **kwargs` shim would hide the real
        function — its signature, and so its fixture requests — behind
        `functools.wraps`.
        """
        func._scenario = self  # type: ignore[attr-defined]
        return func


def scenario(
    name: str | templatelib.Template | Template,
    tags: list[str] | None = None,
    *,
    story: Story | None = None,
    activities: int | Sequence[int] | None = None,
    group_parametrized: bool = True,
) -> ScenarioDecorator:
    """Mark a test for inclusion in the report."""
    resolved_name: str | Template | Narration
    if isinstance(name, templatelib.Template):
        # @scenario runs at module-import time. Glossary handles are in scope
        # then and render eagerly to term refs; a parametrize value is not,
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
                    f'(g.actor/g.work_object/g.verb) for a term ref, or a '
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
    activity_ids = normalize_activity(activities, 'activities')
    return ScenarioDecorator(
        resolved_name,
        tags or [],
        story=story,
        activity_ids=activity_ids,
        group_parametrized=group_parametrized,
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
    target = inspect.unwrap(cast(Any, func))
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
