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

    Four checks:
    1. A Template-named scenario must be parametrized (its substitution source
       is `callspec.params`).
    2. Every Template placeholder must match a parametrize column name —
       catches typos at `pytest --collect-only` rather than at session-finish
       grouping, where the error would escape `pytest_sessionfinish` opaquely.
    3. Any activity_ids on the scenario must be valid ids within the story.
    4. `group_parametrized=False` must have a parametrization to decline —
       otherwise the flag would silently do nothing, since an unparametrized
       scenario never reaches the grouping pass at all.

    Deferred to collection time (rather than decoration time) because
    @scenario and @pytest.mark.parametrize can appear in either order, and
    decoration-time inspection only sees markers from earlier (bottom-up)
    decorators.

    Reported as a `pytest.UsageError`, the way `pytest_configure` reports a bad
    lint config: an exception raised from a collection hook renders as an
    INTERNALERROR stack dump with the message buried under forty lines of
    pluggy frames, which is not what an author who mistyped a placeholder needs
    to read.
    """
    try:
        for item in items:
            _validate_scenario_marker(item)
    except PytestGivenError as error:
        raise pytest.UsageError(str(error)) from error


def _validate_scenario_marker(item: pytest.Item) -> None:
    """The four collection-time checks for one item, or nothing when it carries
    no `@scenario`."""
    marker = _get_scenario_marker(item)
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


def _get_scenario_marker(item: pytest.Item) -> ScenarioDecorator | None:
    """Get the _scenario attribute from a test function, if present.

    Returns None for items without a `.function` (e.g. DoctestItem) — those
    can't carry @scenario, so they're never load-bearing here.
    """
    func = getattr(item, 'function', None)
    if func is None:
        return None
    marker = getattr(func, '_scenario', None)
    return marker if isinstance(marker, ScenarioDecorator) else None
