"""ReportData ↔ JSON-shaped dict (de)serialization.

`report_to_dict` serializes a `ReportData` to a JSON-shaped dict, filtering
out underscore-prefixed fields (e.g. `_by_id` on `Story`/`Glossary`).
`report_from_dict` is the inverse; the renderer reads the JSON, calls it
once, and operates on typed dataclasses from there.

The only non-trivial part is `Narration.parts`, whose three subtypes share
the parent type but each carry a distinct key (`value` / `rendered` / `name`).
"""

import dataclasses
from typing import Any

from .errors import PytestGivenError
from .schema import (
    Activity,
    ActivityId,
    ActivityPart,
    ActivityPath,
    ActivityPlaceholder,
    ActivityTermRef,
    ActivityWord,
    Attachment,
    ContentType,
    ErrorInfo,
    Glossary,
    GlossaryTerm,
    Metadata,
    Narration,
    NarrationLiteral,
    NarrationPart,
    NarrationPlaceholder,
    NarrationTermRef,
    NarrationValue,
    NodeId,
    ParameterCase,
    ParameterTable,
    Phase,
    ReportData,
    Scenario,
    SourceLocation,
    Step,
    Story,
    StoryId,
    TermId,
    TracebackFrame,
)


def report_to_dict(report: ReportData) -> dict[str, Any]:
    """Serialize a `ReportData` to a JSON-shaped dict, skipping _ fields."""
    result = _asdict_filtered(report)
    assert isinstance(result, dict)
    return result


def _asdict_filtered(obj: Any) -> Any:
    """Recursively convert dataclasses to dicts, skipping underscore fields."""
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {
            f.name: _asdict_filtered(getattr(obj, f.name))
            for f in dataclasses.fields(obj)
            if not f.name.startswith('_')
        }
    if isinstance(obj, (list, tuple)):
        return [_asdict_filtered(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _asdict_filtered(v) for k, v in obj.items()}
    return obj


def report_from_dict(d: dict[str, Any]) -> ReportData:
    """Reconstruct a `ReportData` from a JSON-shaped dict."""
    return ReportData(
        metadata=_metadata_from_dict(d['metadata']),
        scenarios=[_scenario_from_dict(s) for s in d['scenarios']],
        stories=[_story_from_dict(s) for s in d.get('stories', [])],
        glossary=_glossary_from_dict(d.get('glossary')),
    )


def _metadata_from_dict(d: dict[str, Any]) -> Metadata:
    return Metadata(
        project=d['project'],
        timestamp=d['timestamp'],
        pytest_version=d['pytest_version'],
        plugin_version=d['plugin_version'],
        commit_sha=d.get('commit_sha'),
    )


def _glossary_from_dict(d: dict[str, Any] | None) -> Glossary | None:
    if d is None:
        return None
    return Glossary(
        terms=[_glossary_term_from_dict(t) for t in d.get('terms', [])],
    )


def _glossary_term_from_dict(d: dict[str, Any]) -> GlossaryTerm:
    src = d.get('source')
    return GlossaryTerm(
        id=TermId(d['id']),
        kind=d['kind'],
        canonical=d['canonical'],
        definition=d.get('definition', ''),
        source=SourceLocation(relpath=src['relpath'], line=src['line'])
        if src is not None
        else None,
    )


def _story_from_dict(d: dict[str, Any]) -> Story:
    src = d.get('source')
    return Story(
        id=StoryId(d['id']),
        title=d['title'],
        activities=tuple(_activity_from_dict(a) for a in d.get('activities', [])),
        source=SourceLocation(relpath=src['relpath'], line=src['line'])
        if src is not None
        else None,
    )


def _activity_from_dict(d: dict[str, Any]) -> Activity:
    return Activity(
        id=ActivityId(d['id']),
        paths=tuple(_activity_path_from_dict(p) for p in d.get('paths', [])),
    )


def _activity_path_from_dict(d: dict[str, Any]) -> ActivityPath:
    return ActivityPath(
        parts=tuple(_activity_part_from_dict(p) for p in d.get('parts', [])),
    )


def _activity_part_from_dict(d: dict[str, Any]) -> ActivityPart:
    if 'term_id' in d:
        return ActivityTermRef(term_id=TermId(d['term_id']), display=d['display'])
    if 'kind' in d:
        return ActivityPlaceholder(kind=d['kind'], text=d['text'])
    if 'text' in d:
        return ActivityWord(text=d['text'])
    raise PytestGivenError(
        f'unknown ActivityPart shape (keys: {sorted(d)!r}). Expected one of '
        '"term_id", "kind", "text".'
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
        story_id=StoryId(d['story_id']) if d.get('story_id') else None,
        activity_ids=tuple(ActivityId(i) for i in d.get('activity_ids') or ()),
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
        activity_ids=tuple(ActivityId(i) for i in d.get('activity_ids') or ()),
        fixture_name=d.get('fixture_name'),
    )


def _attachment_from_dict(d: dict[str, Any]) -> Attachment:
    content_type: ContentType = d.get('content_type', 'text')
    return Attachment(label=d['label'], content=d['content'], content_type=content_type)


def _error_from_dict(d: dict[str, Any] | None) -> ErrorInfo | None:
    if d is None:
        return None
    return ErrorInfo(
        message=d['message'],
        frames=[_frame_from_dict(f) for f in d.get('frames', [])],
        error_tail=d.get('error_tail'),
    )


def _frame_from_dict(d: dict[str, Any]) -> TracebackFrame:
    return TracebackFrame(
        path=d['path'],
        lineno=d['lineno'],
        func=d['func'],
        code=d['code'],
        is_internal=d['is_internal'],
    )


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
    """Discriminate by unique key: `value` → Literal, `term_id` → TermRef,
    `rendered` → Value, `name` → Placeholder. Unknown shapes are a
    serialization bug; raise."""
    if 'value' in d:
        return NarrationLiteral(value=d['value'])
    if 'term_id' in d:
        return NarrationTermRef(
            term_id=TermId(d['term_id']),
            display=d['display'],
            expression=d.get('expression', ''),
            param_column=d.get('param_column'),
        )
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
        '"value", "rendered", "name", or "term_id".'
    )
