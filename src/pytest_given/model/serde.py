"""ReportData ↔ JSON-shaped dict (de)serialization.

`report_to_dict` is a thin wrapper around `dataclasses.asdict` — kept here
so callers go through a single named entry point and we have somewhere to
hang future serialization concerns (field filtering, format-version stamps,
schema validation). `report_from_dict` is the inverse; the renderer reads
the JSON, calls it once, and operates on typed dataclasses from there.

The only non-trivial part is `Narration.parts`, whose three subtypes share
the parent type but each carry a distinct key (`value` / `rendered` / `name`).
"""

import dataclasses
from typing import Any

from .errors import PytestGivenError
from .schema import (
    Attachment,
    ContentType,
    ErrorInfo,
    Metadata,
    Narration,
    NarrationLiteral,
    NarrationPart,
    NarrationPlaceholder,
    NarrationValue,
    NodeId,
    ParameterCase,
    ParameterTable,
    Phase,
    ReportData,
    Scenario,
    SourceLocation,
    Step,
)


def report_to_dict(report: ReportData) -> dict[str, Any]:
    """Serialize a `ReportData` to a JSON-shaped dict."""
    return dataclasses.asdict(report)


def report_from_dict(d: dict[str, Any]) -> ReportData:
    """Reconstruct a `ReportData` from a JSON-shaped dict."""
    return ReportData(
        metadata=_metadata_from_dict(d['metadata']),
        scenarios=[_scenario_from_dict(s) for s in d['scenarios']],
    )


def _metadata_from_dict(d: dict[str, Any]) -> Metadata:
    return Metadata(
        project=d['project'],
        timestamp=d['timestamp'],
        pytest_version=d['pytest_version'],
        plugin_version=d['plugin_version'],
        commit_sha=d.get('commit_sha'),
    )


def _scenario_from_dict(d: dict[str, Any]) -> Scenario:
    src = d.get('source')
    return Scenario(
        id=NodeId(d['id']),
        narration=_narration_from_dict(d['narration']),
        module=d['module'],
        tags=list(d.get('tags', [])),
        status=d.get('status', 'passed'),
        duration_ms=d.get('duration_ms', 0),
        steps=[_step_from_dict(s) for s in d.get('steps', [])],
        parameters=_param_table_from_dict(d.get('parameters')),
        error=_error_from_dict(d.get('error')),
        skip_reason=d.get('skip_reason'),
        source=SourceLocation(relpath=src['relpath'], line=src['line'])
        if src is not None
        else None,
    )


def _step_from_dict(d: dict[str, Any]) -> Step:
    phase: Phase = d['phase']
    return Step(
        phase=phase,
        narration=_narration_from_dict(d['narration']),
        status=d.get('status', 'passed'),
        children=[_step_from_dict(c) for c in d.get('children', [])],
        attachments=[_attachment_from_dict(a) for a in d.get('attachments', [])],
        error=_error_from_dict(d.get('error')),
    )


def _attachment_from_dict(d: dict[str, Any]) -> Attachment:
    content_type: ContentType = d.get('content_type', 'text')
    return Attachment(label=d['label'], content=d['content'], content_type=content_type)


def _error_from_dict(d: dict[str, Any] | None) -> ErrorInfo | None:
    if d is None:
        return None
    return ErrorInfo(message=d['message'], diff=d.get('diff'))


def _param_table_from_dict(d: dict[str, Any] | None) -> ParameterTable | None:
    if d is None:
        return None
    return ParameterTable(
        names=list(d['names']),
        cases=[_param_case_from_dict(c) for c in d.get('cases', [])],
    )


def _param_case_from_dict(d: dict[str, Any]) -> ParameterCase:
    return ParameterCase(
        values=list(d['values']),
        status=d.get('status', 'passed'),
        error=_error_from_dict(d.get('error')),
    )


def _narration_from_dict(d: dict[str, Any]) -> Narration:
    return Narration(
        text=d['text'],
        parts=[_narration_part_from_dict(p) for p in d.get('parts', [])],
    )


def _narration_part_from_dict(d: dict[str, Any]) -> NarrationPart:
    """Discriminate by unique key: `value` → Literal, `rendered` → Value,
    `name` → Placeholder. Unknown shapes are a serialization bug; raise."""
    if 'value' in d:
        return NarrationLiteral(value=d['value'])
    if 'rendered' in d:
        return NarrationValue(
            rendered=d['rendered'],
            expression=d['expression'],
            format_spec=d.get('format_spec', ''),
            conversion=d.get('conversion'),
        )
    if 'name' in d:
        return NarrationPlaceholder(
            name=d['name'],
            format_spec=d.get('format_spec', ''),
            conversion=d.get('conversion'),
        )
    raise PytestGivenError(
        f'Unknown narration part shape (keys: {sorted(d)!r}). Expected one of '
        '"value", "rendered", or "name".'
    )
