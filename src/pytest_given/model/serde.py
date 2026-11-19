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
from .schema import ReportData, Step


def report_to_dict[S: Step](report: ReportData[S]) -> JsonObject:
    return dump_document(ReportDocument, report)


def is_delta_dict(d: JsonObject) -> bool:
    return _metadata_kind(d) == 'delta'


def is_report_dict(d: JsonObject) -> bool:
    return _metadata_kind(d) == 'report'


def report_from_dict(d: JsonObject, source: str | None = None) -> ReportData:
    """Rebuild a report from its serialized form, or raise `PytestGivenError`.
    `source` names where the dict came from, for the caller that read it from
    somewhere the user can point at."""
    if is_delta_dict(d):
        raise PytestGivenError(
            f'{source or "input"} is a delta report, not a report; '
            f'render it with `pytest-given delta {source or "<file>"}`.'
        )
    return load_document(ReportDocument, ReportData, d, 'report', source)


def schema_version(d: JsonObject) -> JsonValue:
    metadata = d.get('metadata')
    return metadata.get('schema_version') if isinstance(metadata, dict) else None


def _metadata_kind(d: JsonObject) -> JsonValue:
    metadata = d.get('metadata')
    return metadata.get('kind') if isinstance(metadata, dict) else None


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
