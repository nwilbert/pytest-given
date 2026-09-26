"""ReportData ↔ JSON-shaped dict (de)serialization.

`report_to_dict` serializes a `ReportData` to a JSON-shaped dict, filtering
out the two kinds of field that stay out of the report: underscore-prefixed
ones (e.g. `_by_id` on `Glossary`, `_glossaries` on the story tree) and any
field marked `metadata={'serde_exclude': True}` — which is how `Step.source`
opts out while keeping a name the lint call sites can read.
`report_from_dict` is the inverse; the renderer reads the JSON, calls it
once, and operates on typed dataclasses from there.

The non-trivial parts are the unions — narration parts, a case cell, a step
attachment — each discriminated on read by the keys its variants do not share.
"""

import dataclasses
from typing import Any, cast

from .errors import PytestGivenError
from .schema import (
    CONTENT_TYPES,
    PHASES,
    Attachment,
    AttachmentLabel,
    AttachmentRef,
    CellValue,
    Clause,
    ClausePart,
    ClauseTermRef,
    ClauseWord,
    ColumnId,
    ColumnKind,
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
    ParameterColumn,
    ParameterTable,
    Pin,
    ReportData,
    Scenario,
    Sentence,
    SentenceId,
    SentenceName,
    SourceLocation,
    Status,
    Step,
    StepAttachment,
    Story,
    StoryId,
    TermId,
    TermKind,
    TracebackFrame,
)


def report_to_dict(report: ReportData) -> dict[str, Any]:
    result = _asdict_filtered(report)
    assert isinstance(result, dict)
    return result


def _asdict_filtered(obj: Any) -> Any:
    """Recursively convert dataclasses to dicts, skipping underscore fields
    and fields marked ``metadata={'serde_exclude': True}``."""
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {
            f.name: _asdict_filtered(getattr(obj, f.name))
            for f in dataclasses.fields(obj)
            if not f.name.startswith('_') and not f.metadata.get('serde_exclude')
        }
    if isinstance(obj, (list, tuple)):
        return [_asdict_filtered(x) for x in obj]
    return obj


def report_from_dict(d: dict[str, Any], source: str | None = None) -> ReportData:
    """Rebuild a report from its serialized form.

    A dict that is not one raises `PytestGivenError`, not the bare `KeyError`
    or `TypeError` that reaching for a missing field produces. `source` names
    where the dict came from, for the caller that read it from somewhere the
    user can point at.
    """
    try:
        return ReportData(
            metadata=_metadata_from_dict(d['metadata']),
            scenarios=[_scenario_from_dict(s) for s in d['scenarios']],
            stories=[_story_from_dict(s) for s in d.get('stories', [])],
            glossary=_glossary_from_dict(d.get('glossary')),
        )
    except (AttributeError, KeyError, TypeError) as error:
        raise PytestGivenError(
            f'{source + " is" if source else "input is"} not a pytest-given '
            f'report, or was written by an incompatible version '
            f'({type(error).__name__}: {error}).'
        ) from error


def _metadata_from_dict(d: dict[str, Any]) -> Metadata:
    return Metadata(
        project=d['project'],
        timestamp=d['timestamp'],
        pytest_version=d['pytest_version'],
        plugin_version=d['plugin_version'],
        commit_sha=d.get('commit_sha'),
        title=d.get('title'),
    )


def _glossary_from_dict(d: dict[str, Any] | None) -> Glossary | None:
    if d is None:
        return None
    return Glossary(
        terms=[_glossary_term_from_dict(t) for t in d.get('terms', [])],
    )


def _glossary_term_from_dict(d: dict[str, Any]) -> GlossaryTerm:
    return GlossaryTerm(
        id=TermId(d['id']),
        kind=_term_kind(d['kind']),
        canonical=d['canonical'],
        definition=d.get('definition'),
        source=_source_from_dict(d.get('source')),
    )


def _source_from_dict(d: dict[str, Any] | None) -> SourceLocation | None:
    """The optional `source` a term, story, or scenario carries."""
    if d is None:
        return None
    return SourceLocation(relpath=d['relpath'], line=d['line'])


def _story_from_dict(d: dict[str, Any]) -> Story:
    return Story(
        id=StoryId(d['id']),
        title=d['title'],
        sentences=tuple(
            _sentence_from_dict(sentence) for sentence in d.get('sentences', [])
        ),
        source=_source_from_dict(d.get('source')),
    )


def _sentence_from_dict(d: dict[str, Any]) -> Sentence:
    return Sentence(
        id=SentenceId(d['id']),
        clauses=tuple(_clause_from_dict(p) for p in d.get('clauses', [])),
        name=SentenceName(d['name']) if d.get('name') is not None else None,
    )


def _clause_from_dict(d: dict[str, Any]) -> Clause:
    return Clause(
        parts=tuple(_clause_part_from_dict(p) for p in d.get('parts', [])),
    )


def _clause_part_from_dict(d: dict[str, Any]) -> ClausePart:
    if 'term_id' in d:
        return ClauseTermRef(term_id=TermId(d['term_id']), display=d['display'])
    if 'text' in d:
        return ClauseWord(text=d['text'])
    raise PytestGivenError(
        f'unknown ClausePart shape (keys: {sorted(d)!r}). Expected one of '
        '"term_id", "text".'
    )


def _scenario_from_dict(d: dict[str, Any]) -> Scenario:
    status = _literal(d.get('status', 'passed'), _STATUSES, 'scenario status')
    return Scenario(
        id=NodeId(d['id']),
        narration=_narration_from_dict(d['narration']),
        module=d['module'],
        tags=list(d.get('tags', [])),
        status=status,
        duration_ms=d.get('duration_ms', 0),
        steps=[_step_from_dict(s) for s in d.get('steps', [])],
        parameters=_param_table_from_dict(d.get('parameters')),
        error=_error_from_dict(d.get('error')),
        skip_reason=d.get('skip_reason'),
        source=_source_from_dict(d.get('source')),
        story_ids=tuple(StoryId(story_id) for story_id in d.get('story_ids') or ()),
        pins=_pins_from_list(d.get('pins')),
    )


def _step_from_dict(d: dict[str, Any]) -> Step:
    """A step, dropping any `status` / `error` an older report carries.

    Failure lives on the scenario and — for a parametrized run — on the case.
    An old report's `"status": "passed"` is noise to discard, not data to
    migrate.
    """
    phase = _literal(d['phase'], PHASES, 'step phase')
    return Step(
        phase=phase,
        narration=_narration_from_dict(d['narration']),
        children=[_step_from_dict(c) for c in d.get('children', [])],
        attachments=[_step_attachment_from_dict(a) for a in d.get('attachments', [])],
        pins=_pins_from_list(d.get('pins')),
        fixture_name=d.get('fixture_name'),
    )


def _pins_from_list(items: list[dict[str, Any]] | None) -> tuple[Pin, ...]:
    return tuple(
        Pin(
            story_id=StoryId(item['story_id']),
            sentence_id=SentenceId(item['sentence_id']),
        )
        for item in items or ()
    )


def _step_attachment_from_dict(d: dict[str, Any]) -> StepAttachment:
    """A promoted attachment carries no `content` — only a pointer to its column."""
    if 'content' in d:
        return _attachment_from_dict(d)
    content_type = _literal(
        d.get('content_type', 'text'), CONTENT_TYPES, 'attachment content type'
    )
    return AttachmentRef(
        label=d['label'],
        content_type=content_type,
        column_id=ColumnId(d['column_id']),
    )


def _attachment_from_dict(d: dict[str, Any]) -> Attachment:
    content_type = _literal(
        d.get('content_type', 'text'), CONTENT_TYPES, 'attachment content type'
    )
    return Attachment(
        label=AttachmentLabel(d['label']),
        content=d['content'],
        content_type=content_type,
    )


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
        columns=[_param_column_from_dict(c) for c in d['columns']],
        cases=[_param_case_from_dict(c) for c in d.get('cases', [])],
    )


def _literal[T: str](value: object, allowed: tuple[T, ...], field: str) -> T:
    """`value` as one of `allowed`, or a `PytestGivenError` naming the field.

    The `Status` / `Phase` / `TermKind` / `ColumnKind` annotations are erased at
    runtime, so this is the only thing standing between a hand-edited report
    and a renderer indexing a lookup table with an unknown string — which used
    to surface as a bare `KeyError` from inside the glyph map or the kind
    grouping, well away from the file that caused it.
    """
    if value in allowed:
        return cast('T', value)
    raise PytestGivenError(
        f'invalid {field} {value!r} in JSON report; expected one of '
        f'{", ".join(repr(option) for option in allowed)}.'
    )


# The literal alphabets `_literal` checks against. Spelled out rather than
# derived from the `Literal` aliases: `typing.get_args` on a PEP 695 `type`
# alias needs the alias object at runtime, and one list per alphabet is
# cheaper to read than the indirection.
_STATUSES: tuple[Status, ...] = ('passed', 'failed', 'skipped')
_TERM_KINDS: tuple[TermKind, ...] = ('actor', 'object', 'activity')
_COLUMN_KINDS: tuple[ColumnKind, ...] = ('param', 'derived', 'attachment')


def _term_kind(value: object) -> TermKind | None:
    """A glossary term's kind, which is legitimately absent while deferred."""
    return None if value is None else _literal(value, _TERM_KINDS, 'glossary term kind')


def _param_column_from_dict(d: dict[str, Any]) -> ParameterColumn:
    kind = _literal(d['kind'], _COLUMN_KINDS, 'parameter column kind')
    return ParameterColumn(id=ColumnId(d['id']), name=d['name'], kind=kind)


def _param_case_from_dict(d: dict[str, Any]) -> ParameterCase:
    status = _literal(d.get('status', 'passed'), _STATUSES, 'parameter case status')
    return ParameterCase(
        values=[_cell_from_json(v) for v in d['values']],
        status=status,
        error=_error_from_dict(d.get('error')),
    )


def _cell_from_json(value: Any) -> CellValue:
    """An object cell is an attachment payload; anything else is a scalar."""
    if isinstance(value, dict):
        return _attachment_from_dict(value)
    scalar: CellValue = value
    return scalar


def _narration_from_dict(d: dict[str, Any]) -> Narration:
    return Narration(
        text=d['text'],
        parts=tuple(_narration_part_from_dict(p) for p in d.get('parts', [])),
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
            column_id=ColumnId(d['column_id']),
            format_spec=d.get('format_spec', ''),
            conversion=d.get('conversion'),
        )
    raise PytestGivenError(
        f'Unknown narration part shape (keys: {sorted(d)!r}). Expected one of '
        '"value", "rendered", "name", or "term_id".'
    )
