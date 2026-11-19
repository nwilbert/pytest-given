import json
import tomllib
from collections.abc import Iterator
from pathlib import Path
from typing import Literal

import jsonschema
import pydantic
import pytest

from pytest_given.delta import delta_to_dict
from pytest_given.delta.document import DeltaDocument
from pytest_given.delta.schema import DELTA_SCHEMA_VERSION
from pytest_given.model import (
    REPORT_SCHEMA_VERSION,
    JsonObject,
    report_to_dict,
    schema_file_name,
)
from pytest_given.model.documents import Document, ReportDocument, json_schema
from pytest_given.report import SinkConfig
from pytest_given.report.delta.sinks import DeltaSinkConfig, emit_delta_sinks
from pytest_given.report.sinks import render_sinks
from tests.unit.model.builders import every_field_populated, full_delta

SCHEMAS = Path(__file__).parents[3] / 'docs' / 'site' / 'schemas'


@pytest.fixture
def locked_pydantic() -> None:
    """Another Pydantic may generate the same contract in other words, so the
    comparison runs only where the generator is the one the files came from.
    A fixture, so only that test parses the lock."""
    lock = tomllib.loads(
        (Path(__file__).parents[3] / 'uv.lock').read_text(encoding='utf-8')
    )
    [locked] = [
        package['version']
        for package in lock['package']
        if package['name'] == 'pydantic'
    ]
    if locked != pydantic.VERSION:
        pytest.skip('the committed schemas are generated under the locked Pydantic')


_KINDS: list[tuple[Literal['report', 'delta'], int, type[Document]]] = [
    ('report', REPORT_SCHEMA_VERSION, ReportDocument),
    ('delta', DELTA_SCHEMA_VERSION, DeltaDocument),
]


def _committed(kind: Literal['report', 'delta'], version: int) -> JsonObject:
    loaded = json.loads(
        (SCHEMAS / schema_file_name(kind, version)).read_text(encoding='utf-8')
    )
    assert isinstance(loaded, dict)
    return loaded


@pytest.mark.usefixtures('locked_pydantic')
@pytest.mark.parametrize(('kind', 'version', 'document_type'), _KINDS)
def test_the_committed_schema_is_the_one_the_types_generate(
    kind: Literal['report', 'delta'],
    version: int,
    document_type: type[Document],
) -> None:
    path = SCHEMAS / schema_file_name(kind, version)
    advice = (
        f'The {kind} JSON changed shape: bump the {kind} schema version and commit '
        f'the new {path.name} (uv run nox -s schemas). A change that accepts the '
        'same JSON regenerates the current file with `-- --same-contract`.'
    )
    assert path.exists(), advice
    assert _committed(kind, version) == json_schema(document_type), advice


@pytest.mark.parametrize(('kind', 'version'), [kind[:2] for kind in _KINDS])
def test_every_object_in_a_committed_schema_refuses_unknown_keys(
    kind: Literal['report', 'delta'], version: int
) -> None:
    objects = [
        node for node in _nodes(_committed(kind, version)) if 'properties' in node
    ]
    assert objects
    assert all(node.get('additionalProperties') is False for node in objects)


def test_a_committed_schema_requires_every_field_and_leaves_out_skipped_ones() -> None:
    schema = _committed('report', REPORT_SCHEMA_VERSION)
    definitions = schema['$defs']
    assert isinstance(definitions, dict)
    assert definitions['Narration']['required'] == ['text', 'parts']  # type: ignore[index, call-overload]
    assert 'source' not in definitions['Step']['properties']  # type: ignore[index, call-overload, operator]
    assert list(definitions['Glossary']['properties']) == ['terms']  # type: ignore[index, call-overload, arg-type]


@pytest.mark.parametrize(
    ('kind', 'version'),
    [('report', REPORT_SCHEMA_VERSION), ('delta', DELTA_SCHEMA_VERSION)],
)
def test_a_committed_schema_describes_fields_but_no_class_and_titles_nothing(
    kind: Literal['report', 'delta'], version: int
) -> None:
    """A class's docstring speaks to the code's reader, and a derived title
    only restates a name."""
    schema = _committed(kind, version)
    nodes = list(_nodes(schema))
    assert not [node for node in nodes if isinstance(node.get('title'), str)]
    assert not [
        node for node in nodes if 'properties' in node and 'description' in node
    ]
    assert [node for node in nodes if 'description' in node]


def test_a_written_report_validates_against_the_committed_schema(
    tmp_path: Path,
) -> None:
    rendered = render_sinks(
        report_to_dict(every_field_populated()),
        SinkConfig(json_path=tmp_path / 'report.json'),
    )
    written = json.loads(rendered.files[0].text)
    jsonschema.Draft202012Validator(
        _committed('report', REPORT_SCHEMA_VERSION)
    ).validate(written)


def test_a_written_delta_validates_against_the_committed_schema(
    tmp_path: Path,
) -> None:
    json_path = tmp_path / 'delta.json'
    emit_delta_sinks(
        lambda: (delta_to_dict(full_delta()), None),
        DeltaSinkConfig(json_path=json_path),
    )
    written = json.loads(json_path.read_text(encoding='utf-8'))
    jsonschema.Draft202012Validator(_committed('delta', DELTA_SCHEMA_VERSION)).validate(
        written
    )


def _nodes(value: object) -> Iterator[dict[str, object]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _nodes(child)
    elif isinstance(value, list):
        for child in value:
            yield from _nodes(child)


@pytest.mark.parametrize(
    ('kind', 'version', 'page'),
    [
        ('report', REPORT_SCHEMA_VERSION, 'configuration/pytest-options.md'),
        ('delta', DELTA_SCHEMA_VERSION, 'delta-report.md'),
    ],
)
def test_the_docs_link_the_current_schema(
    kind: Literal['report', 'delta'], version: int, page: str
) -> None:
    text = (SCHEMAS.parent / page).read_text(encoding='utf-8')
    assert f'schemas/{schema_file_name(kind, version)})' in text
