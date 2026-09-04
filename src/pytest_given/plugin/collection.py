"""Collection-time validation of what `@scenario` declared.

Only the checks that need the item's `callspec`: `@scenario` and
`@pytest.mark.parametrize` can appear in either order, and decoration-time
inspection only sees markers from earlier (bottom-up) decorators. Anything
decidable from `@scenario`'s own arguments is rejected in `capture.scenario`
instead, where the traceback points at the decorator.
"""

import pytest

from ..capture import (
    Template,
)
from ..model import (
    PytestGivenError,
    placeholder_mismatch,
)
from .state import scenario_marker


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Validate Template-named scenarios eagerly at collection.

    `trylast`, so `items` is what the run will actually execute. Plain hook
    impls are called LIFO and entry-point plugins register after core, so
    without it this ran *before* `_pytest.mark` deselected anything and a
    `-k`-narrowed run died on a bad scenario it had already dropped — while
    selecting the same test by file, where the bad one is never collected,
    passed. The hook's own rationale is that such a scenario does not reach
    grouping; a deselected one does not either.

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
