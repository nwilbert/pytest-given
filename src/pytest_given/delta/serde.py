"""DeltaData ↔ JSON-shaped dict (de)serialization, both through `model`."""

# Only reading or writing a delta needs Pydantic.
__lazy_modules__ = ['pytest_given.delta.document', 'pytest_given.model']

from ..model import (
    JsonObject,
    PytestGivenError,
    dump_document,
    is_delta_dict,
    load_document,
    refuse_another_schema_version,
)
from .document import DeltaDocument
from .schema import DELTA_SCHEMA_VERSION, DeltaData


def delta_to_dict(delta: DeltaData) -> JsonObject:
    return dump_document(DeltaDocument, delta)


def delta_from_dict(d: JsonObject, source: str | None = None) -> DeltaData:
    """Rebuild a delta from its serialized form.

    Anything that is not one raises `PytestGivenError`, as `report_from_dict`
    does, and a report is refused with the command that compares two of them.
    A delta of another schema version is refused before it is read: one that
    still reads can break an invariant the renderer relies on.
    """
    if not is_delta_dict(d):
        if isinstance(d.get('metadata'), dict) and 'scenarios' in d:
            raise PytestGivenError(
                f'{source or "input"} is a report, not a delta; compare it with '
                'a second report: `pytest-given delta BEFORE.json AFTER.json`.'
            )
        raise PytestGivenError(f'{source or "input"} is not a delta report.')
    refuse_another_schema_version(
        d,
        'delta',
        DELTA_SCHEMA_VERSION,
        'Build it again from its two reports.',
        source,
    )
    return load_document(DeltaDocument, DeltaData, d, 'delta', source)
