from collections.abc import Sequence


class PytestGivenWarning(UserWarning):
    """Anything pytest-given wants to say without refusing to continue.

    Lives here beside `PytestGivenError` rather than being spelled
    `pytest.PytestWarning` at the one site that raises it: that spelling was
    the only reason `capture/` imported pytest at all, and `capture/` is meant
    to record without one (`capture.discovery` is built to be unit-testable
    against plain module objects for the same reason). A `UserWarning`
    subclass still lands in pytest's warnings summary, and being our own type
    is what lets a suite filter it by name.
    """


class PytestGivenError(RuntimeError):
    """Anything pytest-given refuses to do, raised from any layer.

    One type on purpose. Every one of these is an authoring mistake carrying
    its own fix in the message, and `plugin.pytest_sessionfinish` catches the
    lot in order to discard a run's sinks rather than let a traceback escape
    `console_main`. What raises it spans the package: a step recorded outside
    a scenario, a grouped tree that would lie about its cases, an activity
    path that is not a sentence, a glossary reaching two definitions of one
    term, a saved report too old to render, an unknown source-link preset.
    """


def placeholder_mismatch(
    name: str, param_names: Sequence[str], *, where: str = ''
) -> PytestGivenError:
    """The error for a `Template` placeholder naming no parametrize column.

    Collection and grouping both reach this condition, and an author who hits
    it is looking at the same mistake each time, so they read the same
    sentence. `where` names the site when the caller knows it.
    """
    location = f' {where}' if where else ''
    return PytestGivenError(
        f"pytest_given.Template placeholder '{{{name}}}'{location} does not "
        f'match any parametrize column (have: {sorted(param_names)}).'
    )
