"""The grouping pass: the N scenario records of a parametrized test collapsed
into one logical scenario carrying a parameter table.

Scenarios group when they share the same name and module. Everything else in
the run passes through untouched, and a group's own assembly — baseline,
comparable cases, cells, cases — happens here; the promoting is `templatize`'s.
"""

from ..model import (
    NodeId,
    ParameterCase,
    ParameterTable,
    ParamInfo,
    Scenario,
    Step,
    StepPath,
    node_base,
    walk_steps,
)
from .checks import (
    check_rebound_params,
    check_same_template,
    check_varying_str_narration,
)
from .columns import GroupContext, param_cell, param_cell_formats, step_narrations
from .percase import per_case_scenarios
from .templatize import reconcile_name_slots, templatize_narration, templatize_steps


def group_parametrized(
    scenarios: list[Scenario], param_info: ParamInfo
) -> list[Scenario]:
    """Group parametrized scenarios into single scenarios with parameter tables."""
    result: list[Scenario] = []
    groups: dict[tuple[str, str], list[Scenario]] = {}

    for scenario in scenarios:
        if scenario.id in param_info:
            key = (node_base(scenario.id), scenario.narration.text)
            groups.setdefault(key, []).append(scenario)
        else:
            result.append(scenario)

    for cases in groups.values():
        if param_info[cases[0].id].group:
            result.append(_grouped_scenario(cases, param_info))
        else:
            result.extend(per_case_scenarios(cases, param_info))

    return result


def _grouped_scenario(group: list[Scenario], param_info: ParamInfo) -> Scenario:
    first = group[0]
    param_names = list(param_info[first.id].names)
    baseline = _baseline(group)
    comparable = _comparable(group)
    indexed = _indexed(comparable)
    ctx = GroupContext(
        param_names=param_names,
        comparable=comparable,
        indexed=indexed,
        anchor=first,
        case_params={s.id: param_info[s.id].mapping() for s in group},
    )
    check_same_template(baseline, ctx)
    check_varying_str_narration(baseline, ctx)
    for scenario in group:
        if scenario.status == 'passed':
            check_rebound_params(scenario, param_info[scenario.id], ctx)
    # Before the walk, not with the other cells below: a `param` cell is what
    # its slots substitute, so the walk compares against it. The scenario name
    # is scanned alongside the steps — a `Template` name's spec is a slot's
    # spec, and often the only one in play.
    formats = param_cell_formats(
        [first.narration, *step_narrations(baseline.steps)], param_names
    )
    for scenario in group:
        spec = param_info[scenario.id]
        for name, value in zip(spec.names, spec.values, strict=True):
            ctx.set_cell(name, scenario.id, param_cell(value, formats.get(name)))
    template_steps = templatize_steps(baseline.steps, (), ctx)
    grouped_narration = reconcile_name_slots(
        templatize_narration(first.narration, param_names), ctx
    )

    cases: list[ParameterCase] = []
    total_duration = 0
    for scenario in group:
        cases.append(
            ParameterCase(
                values=[ctx.cells[c.id].get(scenario.id) for c in ctx.columns],
                status=scenario.status,
                error=scenario.error,
            )
        )
        total_duration += scenario.duration_ms

    return Scenario(
        id=first.id,
        narration=grouped_narration,
        module=first.module,
        tags=first.tags,
        status=_grouped_status(cases),
        duration_ms=total_duration,
        steps=template_steps,
        parameters=ParameterTable(columns=ctx.columns, cases=cases),
        source=first.source,
        story_id=first.story_id,
        activity_ids=first.activity_ids,
    )


def _baseline(group: list[Scenario]) -> Scenario:
    """The first passed case; failing that, the first case that recorded a
    tree; failing that, `group[0]`.

    A skipped case records no steps and a failed one may abort mid-tree, so
    neither can define the shared structure — with no passed case there is
    nothing to compare and the grouped tree is one case's rendering either way.
    Which one still matters: a skipped case has *no* steps, so preferring it
    over a failed one renders the scenario step-less and hides the failure a
    reader opened it for.
    """
    passed = next((s for s in group if s.status == 'passed'), None)
    if passed is not None:
        return passed
    return next((s for s in group if s.steps), group[0])


def _comparable(group: list[Scenario]) -> list[Scenario]:
    """The passed cases — every one of them.

    Rule 6 has already refused any group whose passed cases narrate different
    templates, so positional comparison is safe by construction here. A
    non-passed case still drops out: a skipped one records no steps and a
    failed one may abort mid-tree.
    """
    return [s for s in group if s.status == 'passed']


def _indexed(scenarios: list[Scenario]) -> dict[NodeId, dict[StepPath, Step]]:
    """Each case's tree keyed by position, so "the same position in every other
    case" is a lookup rather than a parallel descent through several trees."""
    return {s.id: dict(walk_steps(s.steps)) for s in scenarios}


def _grouped_status(cases: list[ParameterCase]) -> str:
    if any(c.status == 'failed' for c in cases):
        return 'failed'
    if all(c.status == 'skipped' for c in cases):
        return 'skipped'
    return 'passed'
