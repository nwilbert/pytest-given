"""DeltaData ↔ JSON-shaped dict (de)serialization.

The writer is `serde`'s reflective walk. The reader checks no schema version:
rendering a delta computes nothing, so a field it lacks cannot read as a change.
What rendering looks up it does check: the sides a change shows, and each step
path, column and case a scenario's pairing names.
"""

from typing import Any

from .delta import (
    CASE_PAIRINGS,
    CHANGES,
    COLUMN_PAIRINGS,
    MARKS,
    SCENARIO_PAIRINGS,
    STEP_CHANGES,
    SUGGESTION_OFS,
    TERM_PAIRINGS,
    CasePair,
    Change,
    ColumnPair,
    DeltaData,
    DeltaMetadata,
    DeltaSide,
    DiffSegment,
    GlossaryDelta,
    IdentityPair,
    ParameterDelta,
    ScenarioDelta,
    StepDelta,
    Suggestion,
    TermDelta,
    TermFacts,
)
from .errors import PytestGivenError
from .schema import ColumnId, NodeId, ParameterTable, Scenario
from .serde import (
    JsonObject,
    asdict_filtered,
    glossary_from_dict,
    glossary_term_from_dict,
    is_delta_dict,
    literal,
    metadata_from_dict,
    narration_part_from_dict,
    scenario_from_dict,
)
from .steps import StepPath, walk_steps


def delta_to_dict(delta: DeltaData) -> JsonObject:
    result = asdict_filtered(delta)
    assert isinstance(result, dict)
    return result


def delta_from_dict(d: dict[str, Any], source: str | None = None) -> DeltaData:
    """Rebuild a delta from its serialized form.

    Anything that is not one raises `PytestGivenError`, as `report_from_dict`
    does, and a report is refused with the command that compares two of them.
    """
    if not is_delta_dict(d):
        if isinstance(d.get('metadata'), dict) and 'scenarios' in d:
            raise PytestGivenError(
                f'{source or "input"} is a report, not a delta; compare it with '
                'a second report: `pytest-given delta BEFORE.json AFTER.json`.'
            )
        raise PytestGivenError(f'{source or "input"} is not a delta report.')
    try:
        return DeltaData(
            metadata=_delta_metadata_from_dict(d['metadata'], source),
            scenarios=tuple(_scenario_delta_from_dict(s) for s in d['scenarios']),
            unchanged=_identity_pairs(d['unchanged']),
            suggestions=tuple(_suggestion_from_dict(s) for s in d['suggestions']),
            glossary=_glossary_delta_from_dict(d['glossary']),
        )
    except (AttributeError, KeyError, TypeError, ValueError) as error:
        raise PytestGivenError(
            f'{source + " is" if source else "input is"} not a pytest-given '
            f'delta, or was written by an incompatible version '
            f'({type(error).__name__}: {error}).'
        ) from error


def _delta_metadata_from_dict(d: dict[str, Any], source: str | None) -> DeltaMetadata:
    return DeltaMetadata(
        before=_side_from_dict(d['before'], source),
        after=_side_from_dict(d['after'], source),
        plugin_version=d['plugin_version'],
        timestamp=d['timestamp'],
        title=d.get('title'),
        schema_version=d['schema_version'],
    )


def _side_from_dict(d: dict[str, Any], source: str | None) -> DeltaSide:
    return DeltaSide(
        metadata=metadata_from_dict(d['metadata'], source),
        label=d.get('label'),
        modules=tuple(d.get('modules', ())),
    )


def _scenario_delta_from_dict(d: dict[str, Any]) -> ScenarioDelta:
    scenario_delta = _read_scenario_delta(d)
    _check_sides(scenario_delta.change, scenario_delta.before, scenario_delta.after)
    _check_lookups(scenario_delta)
    return scenario_delta


def _read_scenario_delta(d: dict[str, Any]) -> ScenarioDelta:
    before, after = d.get('before'), d.get('after')
    paired_by = d.get('paired_by')
    return ScenarioDelta(
        change=literal(d['change'], CHANGES, 'scenario change'),
        before=None if before is None else scenario_from_dict(before),
        after=None if after is None else scenario_from_dict(after),
        paired_by=None
        if paired_by is None
        else literal(paired_by, SCENARIO_PAIRINGS, 'scenario pairing'),
        title_changed=d.get('title_changed', False),
        steps=tuple(_step_delta_from_dict(s) for s in d.get('steps', ())),
        parameters=_parameter_delta_from_dict(d.get('parameters')),
    )


def _step_delta_from_dict(d: dict[str, Any]) -> StepDelta:
    return StepDelta(
        change=literal(d['change'], STEP_CHANGES, 'step change'),
        before=_step_path(d.get('before')),
        after=_step_path(d.get('after')),
        words=_segments_from_list(d.get('words', ())),
        children=tuple(_step_delta_from_dict(c) for c in d.get('children', ())),
    )


def _step_path(path: list[int] | None) -> StepPath | None:
    return None if path is None else tuple(path)


def _segments_from_list(items: list[dict[str, Any]]) -> tuple[DiffSegment, ...]:
    return tuple(
        DiffSegment(
            mark=literal(item['mark'], MARKS, 'diff mark'),
            before=tuple(narration_part_from_dict(p) for p in item.get('before', ())),
            after=tuple(narration_part_from_dict(p) for p in item.get('after', ())),
        )
        for item in items
    )


def _parameter_delta_from_dict(d: dict[str, Any] | None) -> ParameterDelta | None:
    if d is None:
        return None
    return ParameterDelta(
        columns=tuple(_column_pair_from_dict(c) for c in d['columns']),
        cases=tuple(_case_pair_from_dict(c) for c in d['cases']),
    )


def _column_pair_from_dict(d: dict[str, Any]) -> ColumnPair:
    before, after, paired_by = d.get('before'), d.get('after'), d.get('paired_by')
    return ColumnPair(
        before=None if before is None else ColumnId(before),
        after=None if after is None else ColumnId(after),
        paired_by=None
        if paired_by is None
        else literal(paired_by, COLUMN_PAIRINGS, 'column pairing'),
    )


def _case_pair_from_dict(d: dict[str, Any]) -> CasePair:
    before, after, paired_by = d.get('before'), d.get('after'), d.get('paired_by')
    return CasePair(
        before=None if before is None else NodeId(before),
        after=None if after is None else NodeId(after),
        paired_by=None
        if paired_by is None
        else literal(paired_by, CASE_PAIRINGS, 'case pairing'),
        changed_cells=tuple(ColumnId(c) for c in d.get('changed_cells', ())),
        id_changed=d.get('id_changed', False),
        status_changed=d.get('status_changed', False),
    )


def _identity_pairs(items: list[dict[str, Any]]) -> tuple[IdentityPair, ...]:
    return tuple(_identity_pair_from_dict(item) for item in items)


def _identity_pair_from_dict(d: dict[str, Any]) -> IdentityPair:
    return IdentityPair(before=d['before'], after=d['after'])


def _suggestion_from_dict(d: dict[str, Any]) -> Suggestion:
    scenario = d.get('scenario')
    return Suggestion(
        of=literal(d['of'], SUGGESTION_OFS, 'suggestion kind'),
        before=d['before'],
        after=d['after'],
        scenario=None if scenario is None else _identity_pair_from_dict(scenario),
    )


def _glossary_delta_from_dict(d: dict[str, Any]) -> GlossaryDelta:
    return GlossaryDelta(
        before=glossary_from_dict(d.get('before')),
        after=glossary_from_dict(d.get('after')),
        terms=tuple(_term_delta_from_dict(t) for t in d.get('terms', ())),
        unchanged=_identity_pairs(d.get('unchanged', ())),
    )


def _term_delta_from_dict(d: dict[str, Any]) -> TermDelta:
    term_delta = _read_term_delta(d)
    _check_sides(term_delta.change, term_delta.before, term_delta.after)
    return term_delta


def _read_term_delta(d: dict[str, Any]) -> TermDelta:
    before, after, paired_by = d.get('before'), d.get('after'), d.get('paired_by')
    return TermDelta(
        change=literal(d['change'], CHANGES, 'term change'),
        before=None if before is None else glossary_term_from_dict(before),
        after=None if after is None else glossary_term_from_dict(after),
        paired_by=None
        if paired_by is None
        else literal(paired_by, TERM_PAIRINGS, 'term pairing'),
        before_facts=_facts_from_dict(d.get('before_facts')),
        after_facts=_facts_from_dict(d.get('after_facts')),
        definition=_segments_from_list(d.get('definition', ())),
    )


def _facts_from_dict(d: dict[str, Any] | None) -> TermFacts | None:
    if d is None:
        return None
    return TermFacts(
        other_forms=tuple(d.get('other_forms', ())),
        scenario_count=d.get('scenario_count', 0),
    )


def _check_sides(change: Change, before: object, after: object) -> None:
    """An added entry has its after side alone, a removed one its before side
    alone, a changed one both."""
    if (before is not None, after is not None) != _SIDES_SHOWN[change]:
        raise ValueError(f'a {change} entry in the delta lacks a side.')


_SIDES_SHOWN: dict[Change, tuple[bool, bool]] = {
    'added': (False, True),
    'removed': (True, False),
    'changed': (True, True),
}


def _check_lookups(scenario_delta: ScenarioDelta) -> None:
    before, after = scenario_delta.before, scenario_delta.after
    if before is None or after is None:
        return
    paths = (_step_paths(before), _step_paths(after))
    for step_delta in scenario_delta.steps:
        _check_step_paths(step_delta, *paths)
    parameters = scenario_delta.parameters
    if parameters is None:
        return
    if before.parameters is None or after.parameters is None:
        raise ValueError('a table pairing in the delta lacks a table.')
    before_columns, before_cases = _table_ids(before.parameters)
    after_columns, after_cases = _table_ids(after.parameters)
    named: list[tuple[str | None, set[str]]] = []
    for column in parameters.columns:
        named += [(column.before, before_columns), (column.after, after_columns)]
    for case in parameters.cases:
        named += [(case.before, before_cases), (case.after, after_cases)]
        named += [(cell, after_columns) for cell in case.changed_cells]
    if any(name is not None and name not in ids for name, ids in named):
        raise ValueError(
            'a table pairing in the delta names a column or case its table lacks.'
        )


def _step_paths(scenario: Scenario) -> set[StepPath]:
    return {path for path, _step in walk_steps(scenario.steps)}


def _check_step_paths(
    step_delta: StepDelta, before: set[StepPath], after: set[StepPath]
) -> None:
    if (step_delta.before is not None and step_delta.before not in before) or (
        step_delta.after is not None and step_delta.after not in after
    ):
        raise ValueError('a step in the delta names a step its scenario lacks.')
    for child in step_delta.children:
        _check_step_paths(child, before, after)


def _table_ids(table: ParameterTable) -> tuple[set[str], set[str]]:
    return {column.id for column in table.columns}, {case.id for case in table.cases}
