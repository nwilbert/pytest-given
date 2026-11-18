import dataclasses
import typing

import pytest
from pydantic import BaseModel

from pytest_given.delta import DeltaData
from pytest_given.delta.document import DeltaDocument
from pytest_given.model import ReportData, Scenario
from pytest_given.model.documents import ReportDocument
from pytest_given.plugin.capture_document import SessionCaptureDocument
from pytest_given.plugin.session_capture import SessionCapture

_SCHEMA_URL = [('schema_url', str)]


@pytest.mark.parametrize(
    ('document_type', 'root', 'before'),
    [
        (ReportDocument, ReportData, _SCHEMA_URL),
        (SessionCaptureDocument, SessionCapture, []),
        (DeltaDocument, DeltaData, _SCHEMA_URL),
    ],
)
def test_each_document_type_restates_its_roots_fields_in_order(
    document_type: type[BaseModel], root: type, before: list[tuple[str, type]]
) -> None:
    """The writer emits a document's keys in its field order. A field's type
    is compared without its validators."""
    hints = typing.get_type_hints(root)
    if root is ReportData:
        # The report's document names the default step type.
        hints['scenarios'] = list[Scenario]
    document_hints = typing.get_type_hints(document_type)
    assert [(name, document_hints[name]) for name in document_type.model_fields] == [
        *before,
        *((field.name, hints[field.name]) for field in dataclasses.fields(root)),
    ]
