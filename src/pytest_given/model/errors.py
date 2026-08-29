from collections.abc import Sequence


class PytestGivenWarning(UserWarning):
    """Anything pytest-given wants to say without refusing to continue.

    Its own type rather than `pytest.PytestWarning`: that spelling was the only
    reason `capture/` imported pytest at all. A `UserWarning` subclass still
    lands in pytest's warnings summary, and being our own type is what lets a
    suite filter it by name.
    """


class PytestGivenError(RuntimeError):
    """Anything pytest-given refuses to do, raised from any layer.

    One type on purpose: every one of these is an authoring mistake carrying
    its own fix in the message, and session finish catches the lot in order to
    discard a run's sinks rather than let a traceback escape `console_main`.
    """


def placeholder_mismatch(
    name: str, param_names: Sequence[str], *, where: str = ''
) -> PytestGivenError:
    """The error for a `Template` placeholder naming no parametrize column.

    Collection and grouping both reach this condition and say the same
    sentence. `where` names the site when the caller knows it.
    """
    location = f' {where}' if where else ''
    return PytestGivenError(
        f"pytest_given.Template placeholder '{{{name}}}'{location} does not "
        f'match any parametrize column (have: {sorted(param_names)}).'
    )
