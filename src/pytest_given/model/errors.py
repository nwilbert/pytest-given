from collections.abc import Sequence


class PytestGivenError(RuntimeError):
    """Raised when given/when/then/attach is called in an invalid lifecycle context."""


def placeholder_mismatch(
    name: str, param_names: Sequence[str], *, where: str = ''
) -> PytestGivenError:
    """The error for a `Template` placeholder naming no parametrize column.

    Three call sites reach this condition — a scenario name at collection, a
    scenario name at grouping, a step narration at grouping — and an author who
    hits one of them is looking at the same mistake each time, so they read the
    same sentence. `where` names the site when the caller knows it.
    """
    location = f' {where}' if where else ''
    return PytestGivenError(
        f"pytest_given.Template placeholder '{{{name}}}'{location} does not "
        f'match any parametrize column (have: {sorted(param_names)}).'
    )
