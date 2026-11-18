"""The JSON documents pytest-given reads and writes, as Pydantic models over the
schema's dataclasses: validation reads them, dumping writes them, and the
schema generator describes them.

A document's root restates the fields of the dataclass it rebuilds; its
config reaches the nested dataclasses, which a dataclass root's would not.
Its field validators check what is not shape, on read alone.
"""

# No `__lazy_modules__`: the `BaseModel` subclasses below import Pydantic as
# this module loads.

import dataclasses
from collections.abc import Mapping
from typing import TYPE_CHECKING, Annotated, Final

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, ValidationError
from pydantic.json_schema import (
    GenerateJsonSchema,
    JsonSchemaMode,
    JsonSchemaValue,
    core_schema,
)

from .errors import PytestGivenError
from .report_url import resolve_report_url
from .schema import (
    REPORT_SCHEMA_URL,
    CapturedScenario,
    Glossary,
    Metadata,
    NodeId,
    Scenario,
    Story,
)

if TYPE_CHECKING:
    from _typeshed import DataclassInstance

    # Type-only: `serde` imports this module.
    from .serde import JsonObject

_LISTED_ERRORS: Final = 10


class Document(BaseModel):
    # `defer_build`: a module that loads builds no validator it never uses.
    model_config = ConfigDict(extra='forbid', defer_build=True)


def with_resolved_report_url[M: Metadata](metadata: M, setting: str) -> M:
    """A `ValueError` for an uncitable URL, which validation lists as a problem."""
    try:
        report_url = resolve_report_url(metadata.report_url or '', setting)
    except PytestGivenError as error:
        raise ValueError(str(error)) from error
    return dataclasses.replace(metadata, report_url=report_url)


def _with_citable_report_url(metadata: Metadata) -> Metadata:
    return with_resolved_report_url(metadata, 'report_url')


class ReportDocument(Document):
    schema_url: str = Field(default=REPORT_SCHEMA_URL, alias='$schema')
    metadata: Annotated[Metadata, AfterValidator(_with_citable_report_url)]
    scenarios: list[Scenario]
    glossary: Glossary | None = None
    stories: list[Story] = []


class SessionCaptureDocument(Document):
    scenarios: list[CapturedScenario]
    collection_index: dict[NodeId, int]
    stories: list[Story]
    glossary: Glossary | None


def dump_document(document_type: type[Document], root: DataclassInstance) -> JsonObject:
    """The root's fields as the document type declares them, and `$schema`: a
    step written through a `Scenario` has no source, whatever its class.
    `model_construct` validates nothing."""
    document = document_type.model_construct(
        **{field.name: getattr(root, field.name) for field in dataclasses.fields(root)}
    )
    return document.model_dump(mode='json', by_alias=True)


def load_document[Root: DataclassInstance](
    document_type: type[Document],
    root_type: type[Root],
    data: Mapping[str, object],
    kind: str,
    source: str | None,
) -> Root:
    """The root rebuilt from the validated document, whose fields are the
    root's in name and type."""
    try:
        document = document_type.model_validate(data)
    except ValidationError as error:
        raise PytestGivenError(_problems(error, kind, source)) from error
    return root_type(
        **{
            field.name: getattr(document, field.name)
            for field in dataclasses.fields(root_type)
        }
    )


def json_schema(document_type: type[Document]) -> JsonObject:
    generated = document_type.model_json_schema(
        mode='serialization', schema_generator=_SchemaGenerator
    )
    return {
        '$schema': 'https://json-schema.org/draft/2020-12/schema',
        '$id': document_type.model_fields['schema_url'].default,
        **generated,
    }


class _SchemaGenerator(GenerateJsonSchema):
    """The JSON as the writer emits it: every field present, and no
    docstrings, which speak to the code's reader."""

    def field_is_required(
        self,
        field: core_schema.ModelField
        | core_schema.DataclassField
        | core_schema.TypedDictField,
        total: bool,
    ) -> bool:
        # `json_schema_serialization_defaults_required` reaches only some
        # nested dataclasses, so the generator decides it itself.
        return self.mode == 'serialization' or super().field_is_required(field, total)

    def generate(
        self, schema: core_schema.CoreSchema, mode: JsonSchemaMode = 'validation'
    ) -> JsonSchemaValue:
        generated = super().generate(schema, mode)
        generated.pop('description', None)
        for definition in generated.get('$defs', {}).values():
            definition.pop('description', None)
        return generated


def _problems(error: ValidationError, kind: str, source: str | None) -> str:
    problems: list[str] = []
    for problem in error.errors(include_url=False):
        path = '.'.join(str(part) for part in problem['loc']) or '<root>'
        # A check's own `ValueError` reads without Pydantic's "Value error, ".
        is_check = problem['type'] == 'value_error'
        reason = problem['ctx']['error'] if is_check else problem['msg']
        problems.append(f'  {path}: {reason}')
    lines = [
        f'{source or "input"} is not a valid pytest-given {kind}:',
        *problems[:_LISTED_ERRORS],
    ]
    if len(problems) > _LISTED_ERRORS:
        lines.append(f'  and {len(problems) - _LISTED_ERRORS} more')
    return '\n'.join(lines)
