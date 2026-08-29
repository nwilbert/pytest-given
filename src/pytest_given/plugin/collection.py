"""Collection-time validation of what `@scenario` declared.

Deferred to collection rather than decoration because `@scenario` and
`@pytest.mark.parametrize` can appear in either order, and decoration-time
inspection only sees markers from earlier (bottom-up) decorators.
"""

import pytest

from ..capture import (
    ScenarioDecorator,
    Template,
)
from ..model import (
    PytestGivenError,
    placeholder_mismatch,
)


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Validate Template-named scenarios and story bindings eagerly at collection.

    Eagerly, because the alternative is late or never: a mistyped `Template`
    placeholder surfaces opaquely at session-finish grouping, and
    `group_parametrized=False` on an unparametrized test is never noticed at
    all — such a scenario does not reach grouping.

    Reported as a `pytest.UsageError` because an exception raised from a
    collection hook renders as an INTERNALERROR stack dump with the message
    buried under forty lines of pluggy frames.
    """
    try:
        for item in items:
            _validate_scenario_marker(item)
    except PytestGivenError as error:
        raise pytest.UsageError(str(error)) from error


def _validate_scenario_marker(item: pytest.Item) -> None:
    """The collection-time checks for one item, or nothing when it carries no
    `@scenario`."""
    marker = scenario_marker(item)
    if marker is None:
        return
    _validate_scenario_story_binding(item, marker)
    callspec = getattr(item, 'callspec', None)
    if not marker.group_parametrized and callspec is None:
        raise PytestGivenError(
            f'@scenario(group_parametrized=False) on {item.nodeid!r} has '
            f'nothing to opt out of; the test is not parametrized. Drop '
            f'the argument, or add @pytest.mark.parametrize.'
        )
    if not isinstance(marker.name, Template):
        return
    if callspec is None:
        raise PytestGivenError(
            f'@scenario(Template(...)) on {item.nodeid!r} requires '
            f'@pytest.mark.parametrize; the substitution source is '
            f'callspec.params only. Use a plain string for static '
            f'scenario names, or add @pytest.mark.parametrize.'
        )
    param_names = list(callspec.params.keys())
    for placeholder in marker.name.get_identifiers():
        if placeholder not in param_names:
            raise placeholder_mismatch(
                placeholder,
                param_names,
                where=f'in @scenario(...) on {item.nodeid!r}',
            )


def _validate_scenario_story_binding(
    item: pytest.Item, marker: ScenarioDecorator
) -> None:
    """Check scenario.activity_ids against the story; runtime covers step scope."""
    if marker.story is None and marker.activity_ids:
        raise PytestGivenError(
            f'@scenario(activities=...) on {item.nodeid!r} requires story=; '
            f'activity ids are meaningless without a story to look them up in.'
        )
    if marker.story is None:
        return
    valid_ids = {a.id for a in marker.story.activities}
    for aid in marker.activity_ids:
        if aid not in valid_ids:
            raise PytestGivenError(
                f'@scenario(activities=...) on {item.nodeid!r}: activity id '
                f'{aid} not in story {marker.story.title!r} '
                f'(valid: {sorted(valid_ids)}).'
            )


def scenario_marker(item: pytest.Item) -> ScenarioDecorator | None:
    """Get the _scenario attribute from a test function, if present.

    Returns None for items without a `.function` (e.g. DoctestItem) — those
    can't carry @scenario, so they're never load-bearing here.
    """
    func = getattr(item, 'function', None)
    if func is None:
        return None
    marker = getattr(func, '_scenario', None)
    return marker if isinstance(marker, ScenarioDecorator) else None
