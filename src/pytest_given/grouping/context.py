"""What one group *is*, before anything is promoted out of it.

Immutable and derived once, so the checks and the templatize walk cannot
disagree about which cases are in play or what each case bound. The columns
they build up are `columns.ColumnBuilder`'s, kept apart so a module that only
inspects a group — `checks` — does not also carry the ability to add one.
"""

from dataclasses import dataclass

from ..model import (
    NodeId,
    ParamInfo,
    RawParamValue,
    Scenario,
    Step,
    StepPath,
    walk_steps,
)


@dataclass(frozen=True, kw_only=True)
class Group:
    """One parametrized test's cases, and everything derived from them."""

    cases: list[Scenario]
    param_names: list[str]
    # The case a grouped scenario takes its identity from: the first, so the
    # report keeps the file's declaration order.
    anchor: Scenario
    # The case whose tree defines the shared structure the walk templatizes.
    baseline: Scenario
    # The passed cases — every one of them. Rule 6 has already refused a group
    # whose passed cases narrate different templates, so positional comparison
    # is safe by construction. A non-passed case drops out: a skipped one
    # records no steps and a failed one may abort mid-tree.
    comparable: list[Scenario]
    # Each case's raw parametrize arguments by name. A `Template` slot — in a
    # step or in the scenario name — records no per-case rendering to compare
    # against, so what it renders has to be recomputed from these; see
    # `templatize._reconciled_slot`.
    case_params: dict[NodeId, dict[str, RawParamValue]]
    # Each comparable case's tree keyed by position, so "the same position in
    # every other case" is a lookup rather than a parallel descent through
    # several trees.
    indexed: dict[NodeId, dict[StepPath, Step]]


def build_group(cases: list[Scenario], param_info: ParamInfo) -> Group:
    comparable = [case for case in cases if case.status == 'passed']
    return Group(
        cases=cases,
        param_names=list(param_info[cases[0].id].names),
        anchor=cases[0],
        baseline=_baseline(cases, comparable),
        comparable=comparable,
        case_params={case.id: param_info[case.id].mapping() for case in cases},
        indexed={case.id: dict(walk_steps(case.steps)) for case in comparable},
    )


def _baseline(cases: list[Scenario], comparable: list[Scenario]) -> Scenario:
    """The first passed case; failing that, the first case that recorded a
    tree; failing that, `cases[0]`.

    Which fallback matters: a skipped case has *no* steps, so preferring it
    over a failed one renders the scenario step-less and hides the failure a
    reader opened it for.
    """
    if comparable:
        return comparable[0]
    return next((case for case in cases if case.steps), cases[0])
