"""The delta's JSON document, apart from `serde` so that only reading or
writing a delta builds its model.

Its validators also check what rendering looks up: the sides a change shows,
and the step paths, columns and cases the step and table pairings name. An
attachment diff's indices and a changed attachment cell's column go unchecked.
"""

# No `__lazy_modules__`: the `BaseModel` subclass below imports Pydantic as
# this module loads.

import dataclasses
from typing import Annotated, ClassVar

from pydantic import AfterValidator, Field

from ..model import (
    Document,
    ParameterTable,
    Scenario,
    ScenarioIdentity,
    StepPath,
    walk_steps,
    with_resolved_report_url,
)
from .schema import (
    DELTA_SCHEMA_URL,
    DELTA_SCHEMA_VERSION,
    Change,
    DeltaMetadata,
    GlossaryDelta,
    IdentityPair,
    ScenarioDelta,
    Suggestion,
    walk_step_deltas,
)


def _with_citable_report_urls(metadata: DeltaMetadata) -> DeltaMetadata:
    return dataclasses.replace(
        metadata,
        before=dataclasses.replace(
            metadata.before,
            metadata=with_resolved_report_url(
                metadata.before.metadata, 'before.metadata.report_url'
            ),
        ),
        after=dataclasses.replace(
            metadata.after,
            metadata=with_resolved_report_url(
                metadata.after.metadata, 'after.metadata.report_url'
            ),
        ),
    )


def _checked_scenario(scenario_delta: ScenarioDelta) -> ScenarioDelta:
    _check_sides(scenario_delta.change, scenario_delta.before, scenario_delta.after)
    _check_lookups(scenario_delta)
    return scenario_delta


def _checked_terms(glossary: GlossaryDelta) -> GlossaryDelta:
    for term_delta in glossary.terms:
        _check_sides(term_delta.change, term_delta.before, term_delta.after)
    return glossary


class DeltaDocument(Document):
    current_version: ClassVar[int | None] = DELTA_SCHEMA_VERSION
    stale_remedy: ClassVar[str] = 'Build it again from its two reports.'
    schema_url: str = Field(default=DELTA_SCHEMA_URL, alias='$schema')
    metadata: Annotated[DeltaMetadata, AfterValidator(_with_citable_report_urls)]
    scenarios: tuple[
        Annotated[ScenarioDelta, AfterValidator(_checked_scenario)], ...
    ] = ()
    unchanged: tuple[IdentityPair[ScenarioIdentity], ...] = ()
    suggestions: tuple[Suggestion, ...] = ()
    glossary: Annotated[GlossaryDelta, AfterValidator(_checked_terms)] = GlossaryDelta()


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
