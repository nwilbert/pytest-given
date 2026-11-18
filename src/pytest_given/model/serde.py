"""ReportData ↔ JSON-shaped dict (de)serialization, both through `documents`.

The renderer reads the JSON, calls `report_from_dict` once, and operates on
typed dataclasses from there.
"""

# Only reading or writing needs Pydantic; a session that does neither never
# loads it.
__lazy_modules__ = ['pytest_given.model.documents']

import json
from pathlib import Path

from .documents import ReportDocument, dump_document, load_document
from .errors import PytestGivenError
from .schema import REPORT_SCHEMA_VERSION, ReportData, Step


def report_to_dict[S: Step](report: ReportData[S]) -> JsonObject:
    return dump_document(ReportDocument, report)


def is_delta_dict(d: JsonObject) -> bool:
    metadata = d.get('metadata')
    return isinstance(metadata, dict) and metadata.get('kind') == 'delta'


def report_from_dict(d: JsonObject, source: str | None = None) -> ReportData:
    """Rebuild a report from its serialized form, or raise `PytestGivenError`.
    `source` names where the dict came from, for the caller that read it from
    somewhere the user can point at."""
    if is_delta_dict(d):
        raise PytestGivenError(
            f'{source or "input"} is a delta report, not a report; '
            f'render it with `pytest-given delta {source or "<file>"}`.'
        )
    refuse_another_schema_version(
        d,
        'report',
        REPORT_SCHEMA_VERSION,
        'Regenerate it by running the suite under this pytest-given.',
        source,
    )
    return load_document(ReportDocument, ReportData, d, 'report', source)


def refuse_another_schema_version(
    d: JsonObject, kind: str, current: int, remedy: str, source: str | None
) -> None:
    """One line for a document of another version, whose validation errors
    would only list the fields the versions disagree on. A `metadata` that is
    no object is left to validation to name."""
    metadata = d.get('metadata')
    if not isinstance(metadata, dict):
        return
    version = metadata.get('schema_version')
    if is_schema_version(version, current):
        return
    named = 'no schema version' if version is None else f'schema version {version!r}'
    raise PytestGivenError(
        f'{source or "input"} is a {kind} of {named}; this pytest-given reads '
        f'version {current}. {remedy}'
    )


def schema_version(d: JsonObject) -> JsonValue:
    metadata = d.get('metadata')
    return metadata.get('schema_version') if isinstance(metadata, dict) else None


def is_schema_version(version: JsonValue, current: int) -> bool:
    # `True == 1`, and validation would read `true` or `1.0` as version 1.
    return type(version) is int and version == current


type JsonValue = (
    str | int | float | bool | list[JsonValue] | dict[str, JsonValue] | None
)
type JsonObject = dict[str, JsonValue]


def read_report(json_file: Path) -> ReportData:
    return report_from_dict(read_report_json(json_file), json_file.as_posix())


def read_report_json(json_file: Path) -> JsonObject:
    """The file's JSON object; `report_from_dict` rejects one that is not a
    report. Any other `OSError` (a directory, say) is left to the caller."""
    if not json_file.exists():
        raise PytestGivenError(f'{json_file.as_posix()} not found')
    try:
        loaded = json.loads(json_file.read_text(encoding='utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise PytestGivenError(
            f'{json_file.as_posix()} is not valid JSON — {error}'
        ) from error
    if not isinstance(loaded, dict):
        raise PytestGivenError(
            f'{json_file.as_posix()} is not a pytest-given report: it holds no '
            'JSON object.'
        )
    return loaded
