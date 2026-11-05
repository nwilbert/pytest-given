"""DeltaData ↔ JSON-shaped dict (de)serialization.

The writer is `serde`'s reflective walk. The reader checks no schema version:
rendering a delta computes nothing, so a field it lacks cannot read as a change.
What rendering looks up it does check: the sides a change shows, and each step
path, column and case a scenario's pairing names.
"""

from collections.abc import Callable, Sequence
from typing import NotRequired, TypedDict, cast

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
    walk_step_deltas,
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
    unreadable,
)
from .steps import StepPath, walk_steps


def delta_to_dict(delta: DeltaData) -> JsonObject:
    result = asdict_filtered(delta)
    assert isinstance(result, dict)
    return result


def delta_from_dict(d: JsonObject, source: str | None = None) -> DeltaData:
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
    delta = cast(_DeltaJson, d)
    try:
        return DeltaData(
            metadata=_delta_metadata_from_dict(delta['metadata'], source),
            scenarios=tuple(_scenario_delta_from_dict(s) for s in delta['scenarios']),
            unchanged=_identity_pairs(delta['unchanged']),
            suggestions=tuple(_suggestion_from_dict(s) for s in delta['suggestions']),
            glossary=_glossary_delta_from_dict(delta['glossary']),
        )
    except (AttributeError, KeyError, TypeError, ValueError) as error:
        raise unreadable('delta', source, error) from error


def _delta_metadata_from_dict(d: _MetadataJson, source: str | None) -> DeltaMetadata:
    return DeltaMetadata(
        before=_side_from_dict(d['before'], source),
        after=_side_from_dict(d['after'], source),
        plugin_version=d['plugin_version'],
        timestamp=d['timestamp'],
        title=d['title'],
        schema_version=d['schema_version'],
    )


def _side_from_dict(d: _SideJson, source: str | None) -> DeltaSide:
    return DeltaSide(
        metadata=metadata_from_dict(d['metadata'], source),
        label=d.get('label'),
        modules=tuple(d.get('modules', ())),
    )


def _scenario_delta_from_dict(d: _ScenarioDeltaJson) -> ScenarioDelta:
    scenario_delta = _read_scenario_delta(d)
    _check_sides(scenario_delta.change, scenario_delta.before, scenario_delta.after)
    _check_lookups(scenario_delta)
    return scenario_delta


def _read_scenario_delta(d: _ScenarioDeltaJson) -> ScenarioDelta:
    return ScenarioDelta(
        change=literal(d['change'], CHANGES, 'scenario change'),
        before=_optional(scenario_from_dict, d.get('before')),
        after=_optional(scenario_from_dict, d.get('after')),
        paired_by=_optional(
            lambda value: literal(value, SCENARIO_PAIRINGS, 'scenario pairing'),
            d.get('paired_by'),
        ),
        title_changed=d.get('title_changed', False),
        steps=tuple(_step_delta_from_dict(s) for s in d.get('steps', ())),
        parameters=_parameter_delta_from_dict(d.get('parameters')),
    )


def _step_delta_from_dict(d: _StepDeltaJson) -> StepDelta:
    return StepDelta(
        change=literal(d['change'], STEP_CHANGES, 'step change'),
        before=_step_path(d.get('before')),
        after=_step_path(d.get('after')),
        words=_segments_from_list(d.get('words', ())),
        children=tuple(_step_delta_from_dict(c) for c in d.get('children', ())),
    )


def _optional[Raw, Read](read: Callable[[Raw], Read], value: Raw | None) -> Read | None:
    return None if value is None else read(value)


def _step_path(path: Sequence[int] | None) -> StepPath | None:
    return None if path is None else tuple(path)


def _segments_from_list(items: Sequence[_SegmentJson]) -> tuple[DiffSegment, ...]:
    return tuple(
        DiffSegment(
            mark=literal(item['mark'], MARKS, 'diff mark'),
            before=tuple(narration_part_from_dict(p) for p in item.get('before', ())),
            after=tuple(narration_part_from_dict(p) for p in item.get('after', ())),
        )
        for item in items
    )


def _parameter_delta_from_dict(
    d: _ParameterDeltaJson | None,
) -> ParameterDelta | None:
    if d is None:
        return None
    return ParameterDelta(
        columns=tuple(_column_pair_from_dict(c) for c in d['columns']),
        cases=tuple(_case_pair_from_dict(c) for c in d['cases']),
    )


def _column_pair_from_dict(d: _ColumnPairJson) -> ColumnPair:
    return ColumnPair(
        before=_optional(ColumnId, d.get('before')),
        after=_optional(ColumnId, d.get('after')),
        paired_by=_optional(
            lambda value: literal(value, COLUMN_PAIRINGS, 'column pairing'),
            d.get('paired_by'),
        ),
    )


def _case_pair_from_dict(d: _CasePairJson) -> CasePair:
    return CasePair(
        before=_optional(NodeId, d.get('before')),
        after=_optional(NodeId, d.get('after')),
        paired_by=_optional(
            lambda value: literal(value, CASE_PAIRINGS, 'case pairing'),
            d.get('paired_by'),
        ),
        changed_cells=tuple(ColumnId(c) for c in d.get('changed_cells', ())),
        id_changed=d.get('id_changed', False),
        status_changed=d.get('status_changed', False),
    )


def _identity_pairs(items: Sequence[_IdentityPairJson]) -> tuple[IdentityPair, ...]:
    return tuple(_identity_pair_from_dict(item) for item in items)


def _identity_pair_from_dict(d: _IdentityPairJson) -> IdentityPair:
    return IdentityPair(before=d['before'], after=d['after'])


def _suggestion_from_dict(d: _SuggestionJson) -> Suggestion:
    return Suggestion(
        of=literal(d['of'], SUGGESTION_OFS, 'suggestion kind'),
        before=d['before'],
        after=d['after'],
        scenario=_optional(_identity_pair_from_dict, d.get('scenario')),
    )


def _glossary_delta_from_dict(d: _GlossaryDeltaJson) -> GlossaryDelta:
    return GlossaryDelta(
        before=glossary_from_dict(d.get('before')),
        after=glossary_from_dict(d.get('after')),
        terms=tuple(_term_delta_from_dict(t) for t in d.get('terms', ())),
        unchanged=_identity_pairs(d.get('unchanged', ())),
    )


def _term_delta_from_dict(d: _TermDeltaJson) -> TermDelta:
    term_delta = _read_term_delta(d)
    _check_sides(term_delta.change, term_delta.before, term_delta.after)
    return term_delta


def _read_term_delta(d: _TermDeltaJson) -> TermDelta:
    return TermDelta(
        change=literal(d['change'], CHANGES, 'term change'),
        before=_optional(glossary_term_from_dict, d.get('before')),
        after=_optional(glossary_term_from_dict, d.get('after')),
        paired_by=_optional(
            lambda value: literal(value, TERM_PAIRINGS, 'term pairing'),
            d.get('paired_by'),
        ),
        before_facts=_facts_from_dict(d.get('before_facts')),
        after_facts=_facts_from_dict(d.get('after_facts')),
        definition=_segments_from_list(d.get('definition', ())),
    )


def _facts_from_dict(d: _TermFactsJson | None) -> TermFacts | None:
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
    before_paths, after_paths = _step_paths(before), _step_paths(after)
    for step_delta in walk_step_deltas(scenario_delta.steps):
        if (
            step_delta.before is not None and step_delta.before not in before_paths
        ) or (step_delta.after is not None and step_delta.after not in after_paths):
            raise ValueError('a step in the delta names a step its scenario lacks.')
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


def _table_ids(table: ParameterTable) -> tuple[set[str], set[str]]:
    return {column.id for column in table.columns}, {case.id for case in table.cases}


# The delta's JSON shapes, as `delta_to_dict` writes them. A report's scenario,
# term and metadata stay `JsonObject`: `serde` reads those.


class _SideJson(TypedDict):
    metadata: JsonObject
    label: NotRequired[str | None]
    modules: NotRequired[list[str]]


class _MetadataJson(TypedDict):
    before: _SideJson
    after: _SideJson
    plugin_version: str
    timestamp: str
    title: str | None
    schema_version: int


class _SegmentJson(TypedDict):
    mark: str
    before: NotRequired[list[JsonObject]]
    after: NotRequired[list[JsonObject]]


class _StepDeltaJson(TypedDict):
    change: str
    before: NotRequired[list[int] | None]
    after: NotRequired[list[int] | None]
    words: NotRequired[list[_SegmentJson]]
    children: NotRequired[list[_StepDeltaJson]]


class _ColumnPairJson(TypedDict):
    before: NotRequired[str | None]
    after: NotRequired[str | None]
    paired_by: NotRequired[str | None]


class _CasePairJson(TypedDict):
    before: NotRequired[str | None]
    after: NotRequired[str | None]
    paired_by: NotRequired[str | None]
    changed_cells: NotRequired[list[str]]
    id_changed: NotRequired[bool]
    status_changed: NotRequired[bool]


class _ParameterDeltaJson(TypedDict):
    columns: list[_ColumnPairJson]
    cases: list[_CasePairJson]


class _ScenarioDeltaJson(TypedDict):
    change: str
    before: NotRequired[JsonObject | None]
    after: NotRequired[JsonObject | None]
    paired_by: NotRequired[str | None]
    title_changed: NotRequired[bool]
    steps: NotRequired[list[_StepDeltaJson]]
    parameters: NotRequired[_ParameterDeltaJson | None]


class _IdentityPairJson(TypedDict):
    before: str
    after: str


class _SuggestionJson(TypedDict):
    of: str
    before: str
    after: str
    scenario: NotRequired[_IdentityPairJson | None]


class _TermFactsJson(TypedDict):
    other_forms: NotRequired[list[str]]
    scenario_count: NotRequired[int]


class _TermDeltaJson(TypedDict):
    change: str
    before: NotRequired[JsonObject | None]
    after: NotRequired[JsonObject | None]
    paired_by: NotRequired[str | None]
    before_facts: NotRequired[_TermFactsJson | None]
    after_facts: NotRequired[_TermFactsJson | None]
    definition: NotRequired[list[_SegmentJson]]


class _GlossaryDeltaJson(TypedDict):
    before: NotRequired[JsonObject | None]
    after: NotRequired[JsonObject | None]
    terms: NotRequired[list[_TermDeltaJson]]
    unchanged: NotRequired[list[_IdentityPairJson]]


class _DeltaJson(TypedDict):
    metadata: _MetadataJson
    scenarios: list[_ScenarioDeltaJson]
    unchanged: list[_IdentityPairJson]
    suggestions: list[_SuggestionJson]
    glossary: _GlossaryDeltaJson
