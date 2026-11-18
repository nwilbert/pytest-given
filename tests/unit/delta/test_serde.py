import json
import re
from collections.abc import Callable

import pytest

from pytest_given.delta import (
    CasePair,
    DeltaData,
    DeltaSide,
    ParameterDelta,
    ScenarioDelta,
    delta_from_dict,
    delta_to_dict,
    other_side,
)
from pytest_given.delta.schema import (
    DELTA_SCHEMA_VERSION,
    CellDelta,
    ColumnPair,
    DeltaMetadata,
)
from pytest_given.model import (
    ColumnId,
    JsonObject,
    NodeId,
    PytestGivenError,
    is_delta_dict,
    report_to_dict,
)
from tests.unit.delta.builders import (
    meta,
    report,
    scn,
    term,
)
from tests.unit.model.builders import full_delta


def _through_json(delta: DeltaData) -> JsonObject:
    loaded = json.loads(json.dumps(delta_to_dict(delta)))
    assert isinstance(loaded, dict)
    return loaded


def test_a_delta_with_every_variant_round_trips_through_json() -> None:
    delta = full_delta()

    restored = delta_from_dict(_through_json(delta))

    assert delta_to_dict(restored) == delta_to_dict(delta)
    # `Glossary` compares by identity, so the rest is compared by value.
    assert restored.metadata == delta.metadata
    assert restored.scenarios == delta.scenarios
    assert restored.suggestions == delta.suggestions
    assert restored.glossary.terms == delta.glossary.terms
    assert restored.glossary.before is not None
    assert restored.glossary.before.terms == [
        term('coffee', 'coffee', definition='A drink.')
    ]


def test_a_delta_with_nothing_in_it_round_trips() -> None:
    delta = DeltaData(
        metadata=DeltaMetadata(
            before=DeltaSide(metadata=meta()),
            after=DeltaSide(metadata=meta()),
            plugin_version='0.2.0',
            timestamp='t',
        )
    )

    restored = delta_from_dict(_through_json(delta))

    assert restored == delta
    assert restored.metadata.schema_version == DELTA_SCHEMA_VERSION


def test_a_delta_dict_is_told_from_a_report_dict_by_its_kind() -> None:
    report_dict = report_to_dict(report(scn('t.py::a', 'A')))

    assert (
        is_delta_dict(_through_json(full_delta())),
        is_delta_dict(report_dict),
    ) == (
        True,
        False,
    )


def test_a_report_dict_is_refused_with_a_pointer_to_the_delta_command() -> None:
    report_dict = report_to_dict(report(scn('t.py::a', 'A')))

    with pytest.raises(PytestGivenError, match='is a report, not a delta') as raised:
        delta_from_dict(report_dict, 'before.json')

    assert 'before.json' in str(raised.value)
    assert 'pytest-given delta BEFORE.json AFTER.json' in str(raised.value)


def test_a_dict_that_is_neither_a_delta_nor_a_report_is_not_called_a_report() -> None:
    with pytest.raises(PytestGivenError) as raised:
        delta_from_dict({'name': 'x'}, 'other.json')

    assert str(raised.value) == 'other.json is not a delta report.'


@pytest.mark.parametrize(
    ('version', 'named'),
    [
        (DELTA_SCHEMA_VERSION + 1, f'schema version {DELTA_SCHEMA_VERSION + 1}'),
        (None, 'no schema version'),
        (True, 'schema version True'),
    ],
    ids=['another', 'none', 'boolean'],
)
def test_a_delta_of_another_schema_version_is_refused(
    version: int | bool | None, named: str
) -> None:
    """Before reading it, which might pass and leave a render to crash."""
    delta_dict = _through_json(full_delta())
    metadata = delta_dict['metadata']
    assert isinstance(metadata, dict)
    metadata['schema_version'] = version

    with pytest.raises(PytestGivenError) as raised:
        delta_from_dict(delta_dict, 'old.json')

    assert str(raised.value) == (
        f'old.json is a delta of {named}; this pytest-given reads version '
        f'{DELTA_SCHEMA_VERSION}. Build it again from its two reports.'
    )


def _drop_a_side(delta_dict: JsonObject) -> None:
    metadata = delta_dict['metadata']
    assert isinstance(metadata, dict)
    del metadata['before']


def _add_a_scenario(delta_dict: JsonObject, scenario: object) -> None:
    scenarios = delta_dict['scenarios']
    assert isinstance(scenarios, list)
    scenarios.append({'change': 'added', 'after': scenario})


@pytest.mark.parametrize(
    ('mutate', 'path'),
    [
        (_drop_a_side, r'metadata\.before'),
        (lambda delta_dict: _add_a_scenario(delta_dict, 3), r'scenarios\.\d+\.after'),
        (
            lambda delta_dict: _add_a_scenario(delta_dict, {}),
            r'scenarios\.\d+\.after\.id',
        ),
    ],
    ids=['missing-side', 'scenario-not-a-dict', 'scenario-missing-fields'],
)
def test_a_malformed_delta_raises_a_pytest_given_error(
    mutate: Callable[[JsonObject], None], path: str
) -> None:
    delta_dict = _through_json(full_delta())
    mutate(delta_dict)

    with pytest.raises(PytestGivenError) as raised:
        delta_from_dict(delta_dict, 'delta.json')

    message = str(raised.value)
    assert message.startswith('delta.json is not a valid pytest-given delta:\n')
    assert re.search(f'\n  {path}: ', message)


def test_a_malformed_delta_lists_the_path_and_reason_of_each_problem() -> None:
    delta_dict = _through_json(full_delta())
    _changed_scenario(delta_dict)['change'] = 'moved'

    with pytest.raises(PytestGivenError) as raised:
        delta_from_dict(delta_dict, 'd.json')

    assert str(raised.value).startswith('d.json is not a valid pytest-given delta:')
    assert "scenarios.0.change: Input should be 'added', 'removed' or 'changed'" in str(
        raised.value
    )


def test_a_side_with_an_uncitable_report_url_is_refused() -> None:
    delta_dict = _through_json(full_delta())
    metadata = delta_dict['metadata']
    assert isinstance(metadata, dict)
    before = metadata['before']
    assert isinstance(before, dict)
    side_metadata = before['metadata']
    assert isinstance(side_metadata, dict)
    side_metadata['report_url'] = 'ftp://x'

    with pytest.raises(
        PytestGivenError,
        match=(
            r'd\.json is not a valid pytest-given delta:\n'
            r'  metadata: before\.metadata\.report_url must be'
        ),
    ):
        delta_from_dict(delta_dict, 'd.json')


def _changed_scenario(delta_dict: JsonObject) -> JsonObject:
    scenarios = delta_dict['scenarios']
    assert isinstance(scenarios, list)
    changed = scenarios[0]
    assert isinstance(changed, dict)
    return changed


def _drop_the_after_scenario(delta_dict: JsonObject) -> None:
    del _changed_scenario(delta_dict)['after']


def _point_a_step_past_its_scenario(delta_dict: JsonObject) -> None:
    steps = _changed_scenario(delta_dict)['steps']
    assert isinstance(steps, list)
    steps.append({'change': 'removed', 'before': [9]})


def _name_a_missing_case(delta_dict: JsonObject) -> None:
    parameters = _changed_scenario(delta_dict)['parameters']
    assert isinstance(parameters, dict)
    cases = parameters['cases']
    assert isinstance(cases, list)
    cases.append({'before': 'nowhere'})


def _drop_the_after_table(delta_dict: JsonObject) -> None:
    after = _changed_scenario(delta_dict)['after']
    assert isinstance(after, dict)
    del after['parameters']


def _drop_the_after_term(delta_dict: JsonObject) -> None:
    glossary = delta_dict['glossary']
    assert isinstance(glossary, dict)
    terms = glossary['terms']
    assert isinstance(terms, list)
    changed = terms[0]
    assert isinstance(changed, dict)
    del changed['after']


@pytest.mark.parametrize(
    ('mutate', 'problem'),
    [
        (
            _drop_the_after_scenario,
            'scenarios.0: a changed entry in the delta lacks a side.',
        ),
        (
            _point_a_step_past_its_scenario,
            'scenarios.0: a step in the delta names a step its scenario lacks.',
        ),
        (
            _name_a_missing_case,
            (
                'scenarios.0: a table pairing in the delta names a column or case '
                'its table lacks.'
            ),
        ),
        (
            _drop_the_after_table,
            'scenarios.0: a table pairing in the delta lacks a table.',
        ),
        (_drop_the_after_term, 'glossary: a changed entry in the delta lacks a side.'),
    ],
    ids=[
        'changed-scenario-one-side',
        'step-path',
        'case-id',
        'table',
        'changed-term-one-side',
    ],
)
def test_a_delta_naming_what_it_lacks_is_refused_before_rendering(
    mutate: Callable[[JsonObject], None], problem: str
) -> None:
    """A delta whose shape a later version changed reads as malformed, not as
    a render that fails half-way."""
    delta_dict = _through_json(full_delta())
    mutate(delta_dict)

    with pytest.raises(PytestGivenError) as raised:
        delta_from_dict(delta_dict, 'delta.json')

    assert str(raised.value) == (
        f'delta.json is not a valid pytest-given delta:\n  {problem}'
    )


def test_an_unknown_changed_part_is_refused() -> None:
    delta_dict = _through_json(full_delta())
    _changed_scenario(delta_dict)['changed_in'] = ['title', 'colour']

    with pytest.raises(PytestGivenError) as raised:
        delta_from_dict(delta_dict)

    assert 'scenarios.0.changed_in.1: Input should be' in str(raised.value)


def _parameters(
    columns: tuple[ColumnPair, ...] = (), cases: tuple[CasePair, ...] = ()
) -> ParameterDelta:
    return ParameterDelta(columns=columns, cases=cases)


def _case(**kw: object) -> CasePair:
    return CasePair(before=NodeId('1'), after=NodeId('1'), paired_by='case-id', **kw)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ('parameters', 'parameters_changed', 'attachments_changed'),
    [
        (
            _parameters(
                (
                    ColumnPair(
                        kind='param',
                        before=ColumnId('a'),
                        after=ColumnId('a'),
                        paired_by='name',
                    ),
                ),
                (_case(),),
            ),
            False,
            False,
        ),
        (_parameters((ColumnPair(kind='param', after=ColumnId('b')),)), True, False),
        (
            _parameters(
                (
                    ColumnPair(
                        kind='param',
                        before=ColumnId('a'),
                        after=ColumnId('b'),
                        paired_by='values',
                    ),
                )
            ),
            True,
            False,
        ),
        (_parameters(cases=(CasePair(before=NodeId('1')),)), True, False),
        (_parameters(cases=(_case(changed_cells=(ColumnId('a'),)),)), True, False),
        (_parameters(cases=(_case(status_changed=True),)), True, False),
        (_parameters(cases=(_case(id_changed=True),)), True, False),
        (
            _parameters(
                (ColumnPair(kind='attachment', before=ColumnId('attachment:0')),)
            ),
            False,
            True,
        ),
        (
            _parameters(
                cases=(
                    _case(
                        changed_attachments=(
                            CellDelta(column=ColumnId('attachment:0'), lines=()),
                        )
                    ),
                )
            ),
            False,
            True,
        ),
    ],
    ids=[
        'all-paired',
        'unpaired-column',
        'renamed-column',
        'unpaired-case',
        'changed-cell',
        'changed-status',
        'changed-id',
        'unpaired-attachment-column',
        'changed-attachment-cell',
    ],
)
def test_a_parameter_delta_tells_a_parameter_change_from_an_attachment_change(
    parameters: ParameterDelta, parameters_changed: bool, attachments_changed: bool
) -> None:
    assert (parameters.parameters_changed, parameters.attachments_changed) == (
        parameters_changed,
        attachments_changed,
    )
    assert parameters.changed is (parameters_changed or attachments_changed)


def test_a_scenario_delta_derives_what_changed_from_its_two_sides() -> None:
    before = scn('t.py::t', 'T', tags=['slow', 'db', 'slow'], status='skipped')
    after = scn('t.py::t', 'T', tags=['db', 'fast'])
    changed = ScenarioDelta(change='changed', before=before, after=after)
    assert (changed.tags_added, changed.tags_removed) == (('fast',), ('slow',))
    assert changed.status_changed
    added = ScenarioDelta(change='added', after=after)
    assert (added.tags_added, added.tags_removed) == ((), ())
    assert (added.status_changed, added.reason_changed) == (False, False)


def test_the_other_side_of_a_side_is_the_one_it_is_not() -> None:
    assert (other_side('before'), other_side('after')) == ('after', 'before')
