"""Terse builders for the reports and scenarios the delta tests compare."""

import dataclasses
from collections.abc import Sequence

from pytest_given.delta import DeltaInputs, build_delta
from pytest_given.model import (
    CellValue,
    ColumnId,
    ColumnKind,
    Definition,
    DeltaData,
    Glossary,
    GlossaryTerm,
    Metadata,
    Narration,
    NarrationLiteral,
    NarrationPart,
    NarrationPlaceholder,
    NarrationTermRef,
    NodeId,
    ParameterCase,
    ParameterColumn,
    ParameterTable,
    Phase,
    ReportData,
    Scenario,
    Status,
    Step,
    TermId,
    TermKind,
    narration_of,
)

type CaseSpec = tuple[str, list[CellValue]] | tuple[str, list[CellValue], Status]


def meta(sha: str | None = None, **overrides: object) -> Metadata:
    base = Metadata(
        project='project',
        timestamp='2026-01-01T00:00:00+00:00',
        pytest_version='9.0.0',
        plugin_version='0.1.0',
        commit_sha=sha,
    )
    return dataclasses.replace(base, **overrides)


def report(
    *scenarios: Scenario, glossary: Glossary | None = None, sha: str | None = None
) -> ReportData:
    return ReportData(metadata=meta(sha), scenarios=list(scenarios), glossary=glossary)


def scn(
    node_id: str,
    title: str | Narration,
    *steps: Step,
    tags: Sequence[str] = (),
    status: Status = 'passed',
    parameters: ParameterTable | None = None,
    module: str | None = None,
) -> Scenario:
    return Scenario(
        id=NodeId(node_id),
        narration=_narration(title),
        module=module or node_id.split('::')[0].removesuffix('.py').replace('/', '.'),
        tags=list(tags),
        status=status,
        steps=list(steps),
        parameters=parameters,
    )


def step(phase: Phase, text: str | Narration, *children: Step) -> Step:
    return Step(phase=phase, narration=_narration(text), children=list(children))


def term(
    term_id: str,
    canonical: str,
    kind: TermKind | None = 'object',
    definition: str | None = None,
) -> GlossaryTerm:
    return GlossaryTerm(
        id=TermId(term_id),
        kind=kind,
        canonical=canonical,
        definition=None if definition is None else Definition.literal(definition),
    )


def ref(term_id: str, display: str) -> NarrationTermRef:
    return NarrationTermRef(term_id=TermId(term_id), display=display)


def lit(text: str) -> NarrationLiteral:
    return NarrationLiteral(value=text)


def ph(name: str, column_id: str | None = None) -> NarrationPlaceholder:
    return NarrationPlaceholder(name=name, column_id=ColumnId(column_id or name))


def narr(*parts: NarrationPart) -> Narration:
    return narration_of(parts)


def table(
    columns: list[tuple[str, ColumnKind]],
    *cases: CaseSpec,
    custom: bool = False,
    status: Status = 'passed',
) -> ParameterTable:
    """Columns as (name, kind); a case as (node ID, cells[, status]).

    A `param` column's ID is its name, as in a real report. The other kinds get
    the generated `derived:N` / `attachment:N` IDs, counted per kind.
    """
    seen: dict[ColumnKind, int] = {}
    built_columns: list[ParameterColumn] = []
    for name, kind in columns:
        if kind == 'param':
            column_id = name
        else:
            column_id = f'{kind}:{seen.get(kind, 0)}'
            seen[kind] = seen.get(kind, 0) + 1
        built_columns.append(
            ParameterColumn(id=ColumnId(column_id), name=name, kind=kind)
        )
    return ParameterTable(
        columns=built_columns,
        cases=[
            ParameterCase(
                id=NodeId(case[0]),
                values=case[1],
                status=case[2] if len(case) == 3 else status,
                custom_id=custom,
            )
            for case in cases
        ],
    )


def _narration(text: str | Narration) -> Narration:
    return text if isinstance(text, Narration) else narr(lit(text))


def glossary_of(*terms: GlossaryTerm) -> Glossary:
    return Glossary(list(terms))


def built_delta(
    before: ReportData,
    after: ReportData,
    *,
    before_label: str | None = None,
    after_label: str | None = None,
) -> DeltaData:
    return build_delta(
        DeltaInputs(
            before=before,
            after=after,
            before_label=before_label,
            after_label=after_label,
            plugin_version='0.1.0',
            timestamp='2026-01-02T00:00:00+00:00',
        )
    ).delta
