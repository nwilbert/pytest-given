"""The grouping pass: the N scenario records of a parametrized test collapsed
into one logical scenario carrying a parameter table.

Cases group on `(node_base(id), narration.text)` — one test function, one name.
Everything else in the run passes through untouched. A group's own assembly —
baseline, comparable cases, cells, cases — happens here; the promoting is
`templatize`'s.
"""

from dataclasses import replace

from ..model import (
    ParameterCase,
    ParamInfo,
    Scenario,
    Status,
    iter_steps,
    node_base,
)
from .checks import check_rebound_params, check_same_template
from .columns import ColumnBuilder, param_cell_formats
from .context import build_group
from .percase import per_case_scenarios
from .templatize import templatize_scenario_name, templatize_steps

# What cases group on: one test function, one name.
type GroupKey = tuple[str, str]


def group_parametrized(
    scenarios: list[Scenario], param_info: ParamInfo
) -> list[Scenario]:
    """Group parametrized scenarios into single scenarios with parameter tables.

    A group takes the place of its *first* case, so the report keeps listing
    scenarios in the order the file declares them. Collecting the groups and
    appending them afterwards would sort every parametrized scenario to the end.
    """
    groups: dict[GroupKey, list[Scenario]] = {}
    order: list[Scenario | GroupKey] = []
    for scenario in scenarios:
        if scenario.id not in param_info:
            order.append(scenario)
            continue
        key = (node_base(scenario.id), scenario.narration.text)
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(scenario)

    result: list[Scenario] = []
    for entry in order:
        if isinstance(entry, Scenario):
            result.append(entry)
            continue
        cases = groups[entry]
        if param_info[cases[0].id].group:
            result.append(_grouped_scenario(cases, param_info))
        else:
            result.extend(per_case_scenarios(cases, param_info))
    return result


def _grouped_scenario(cases: list[Scenario], param_info: ParamInfo) -> Scenario:
    group = build_group(cases, param_info)
    check_same_template(group)
    check_rebound_params(group)
    anchor, baseline = group.anchor, group.baseline
    # The scenario name is scanned alongside the steps — a `Template` name's
    # spec is a slot's spec, and often the only one in play.
    formats = param_cell_formats(
        [anchor.narration, *(s.narration for s in iter_steps(baseline.steps))],
        group.param_names,
    )
    builder = ColumnBuilder.for_params(group, formats)
    template_steps = templatize_steps(baseline.steps, (), builder)
    grouped_narration = templatize_scenario_name(anchor.narration, builder)

    table = builder.table(group.cases)
    # `replace` rather than a field-by-field rebuild: the two fields a group
    # does *not* inherit are then the only two spelled out, and a field added
    # to `Scenario` later cannot go missing here by omission. `error` is
    # dropped because a grouped scenario carries none of its own — each case's
    # sits in the table; `skip_reason` is the anchor's, which is the reason
    # every case shares when they all skipped.
    return replace(
        anchor,
        narration=grouped_narration,
        status=_grouped_status(table.cases),
        duration_ms=sum(case.duration_ms for case in group.cases),
        steps=template_steps,
        parameters=table,
        error=None,
    )


def _grouped_status(cases: list[ParameterCase]) -> Status:
    if any(c.status == 'failed' for c in cases):
        return 'failed'
    if all(c.status == 'skipped' for c in cases):
        return 'skipped'
    return 'passed'
