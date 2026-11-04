import json
from collections.abc import Callable

import pytest

from pytest_given.model import (
    DELTA_SCHEMA_VERSION,
    CasePair,
    ColumnId,
    ColumnPair,
    DeltaData,
    DeltaMetadata,
    DeltaSide,
    DiffSegment,
    Glossary,
    GlossaryDelta,
    IdentityPair,
    JsonObject,
    NarrationValue,
    NodeId,
    ParameterDelta,
    PytestGivenError,
    ScenarioDelta,
    StepDelta,
    Suggestion,
    TermDelta,
    TermFacts,
    delta_from_dict,
    delta_to_dict,
    is_delta_dict,
    other_side,
    report_to_dict,
)
from tests.unit.delta.builders import (
    lit,
    meta,
    narr,
    ph,
    ref,
    report,
    scn,
    step,
    table,
    term,
)


def _full_delta() -> DeltaData:
    value = NarrationValue(
        rendered='3', expression='n', format_spec='02', conversion='r'
    )
    words = (
        DiffSegment(
            mark='equal',
            before=(lit('a  '), ref('coffee', 'coffee')),
            after=(lit('a '), ref('coffee', 'Coffee')),
        ),
        DiffSegment(mark='removed', before=(lit('old'), value)),
        DiffSegment(mark='added', after=(ph('size', 'size'), lit('new'))),
    )
    before_scenario = scn(
        'tests/test_a.py::test_a[1]',
        'A brew',
        step(
            'given', narr(lit('a '), ref('coffee', 'coffee')), step('when', 'it pours')
        ),
        step('when', 'it cools'),
        step('then', 'it is gone'),
        parameters=table([('size', 'param')], ('1', [1]), ('gone', [2]), custom=True),
    )
    after_scenario = scn(
        'tests/test_a.py::test_a[2]',
        'A brew',
        step('given', 'a cup', step('when', 'it fills'), step('when', 'it brews')),
        step('then', 'it is served'),
        tags=['fast'],
        status='failed',
        parameters=table(
            [('size', 'param'), ('shown', 'derived')], ('2', [1, 'x'], 'failed')
        ),
    )
    changed = ScenarioDelta(
        change='changed',
        before=before_scenario,
        after=after_scenario,
        paired_by='rename-log',
        title_changed=True,
        steps=(
            StepDelta(
                change='modified',
                before=(0,),
                after=(0, 1),
                words=words,
                children=(StepDelta(change='equal', before=(0, 0), after=(0, 0)),),
            ),
            StepDelta(change='added', after=(1,)),
            StepDelta(change='removed', before=(2,)),
        ),
        parameters=ParameterDelta(
            columns=(
                ColumnPair(
                    before=ColumnId('size'), after=ColumnId('size'), paired_by='name'
                ),
                ColumnPair(after=ColumnId('derived:0')),
            ),
            cases=(
                CasePair(
                    before=NodeId('1'),
                    after=NodeId('2'),
                    paired_by='values',
                    changed_cells=(ColumnId('size'),),
                    id_changed=True,
                    status_changed=True,
                ),
                CasePair(before=NodeId('gone')),
            ),
        ),
    )
    return DeltaData(
        metadata=DeltaMetadata(
            before=DeltaSide(metadata=meta('aaa'), label='v1', modules=('m.a',)),
            after=DeltaSide(metadata=meta('bbb'), modules=('m.a', 'm.b')),
            plugin_version='0.2.0',
            timestamp='2026-02-02T00:00:00+00:00',
            title='Coffee changes for v2',
        ),
        scenarios=(
            changed,
            ScenarioDelta(change='added', after=after_scenario),
            ScenarioDelta(change='removed', before=before_scenario),
        ),
        unchanged=(IdentityPair(before='t::a', after='t::a'),),
        suggestions=(
            Suggestion(of='scenario', before='t::old', after='t::new'),
            Suggestion(
                of='case',
                before='1',
                after='2',
                scenario=IdentityPair(before='t::a', after='t::a'),
            ),
        ),
        glossary=GlossaryDelta(
            before=Glossary(terms=[term('coffee', 'coffee', definition='A drink.')]),
            after=Glossary(terms=[term('coffee', 'coffee', definition='A hot drink.')]),
            terms=(
                TermDelta(
                    change='changed',
                    before=term('coffee', 'coffee', definition='A drink.'),
                    after=term('coffee', 'coffee', definition='A hot drink.'),
                    paired_by='term-id',
                    before_facts=TermFacts(other_forms=('coffees',), scenario_count=2),
                    after_facts=TermFacts(scenario_count=3),
                    definition=(DiffSegment(mark='added', after=(lit('hot'),)),),
                ),
                TermDelta(change='added', after=term('tea', 'tea')),
            ),
            unchanged=(IdentityPair(before='tea', after='tea'),),
        ),
    )


def _through_json(delta: DeltaData) -> JsonObject:
    loaded = json.loads(json.dumps(delta_to_dict(delta)))
    assert isinstance(loaded, dict)
    return loaded


def test_a_delta_with_every_variant_round_trips_through_json() -> None:
    delta = _full_delta()

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
        is_delta_dict(_through_json(_full_delta())),
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


def _drop_a_side(delta_dict: JsonObject) -> None:
    metadata = delta_dict['metadata']
    assert isinstance(metadata, dict)
    del metadata['before']


def _add_a_scenario(delta_dict: JsonObject, scenario: object) -> None:
    scenarios = delta_dict['scenarios']
    assert isinstance(scenarios, list)
    scenarios.append({'change': 'added', 'after': scenario})


@pytest.mark.parametrize(
    'mutate',
    [
        _drop_a_side,
        lambda delta_dict: _add_a_scenario(delta_dict, 3),
        lambda delta_dict: _add_a_scenario(delta_dict, {}),
    ],
    ids=['missing-side', 'scenario-not-a-dict', 'scenario-missing-fields'],
)
def test_a_malformed_delta_raises_a_pytest_given_error(
    mutate: Callable[[JsonObject], None],
) -> None:
    delta_dict = _through_json(_full_delta())
    mutate(delta_dict)

    with pytest.raises(PytestGivenError, match='not a pytest-given delta'):
        delta_from_dict(delta_dict, 'delta.json')


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
    'mutate',
    [
        _drop_the_after_scenario,
        _point_a_step_past_its_scenario,
        _name_a_missing_case,
        _drop_the_after_table,
        _drop_the_after_term,
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
    mutate: Callable[[JsonObject], None],
) -> None:
    """A delta whose shape a later version changed reads as malformed, not as
    a render that fails half-way."""
    delta_dict = _through_json(_full_delta())
    mutate(delta_dict)

    with pytest.raises(PytestGivenError, match='not a pytest-given delta'):
        delta_from_dict(delta_dict, 'delta.json')


def test_an_unknown_change_is_refused() -> None:
    delta_dict = _through_json(_full_delta())
    scenarios = delta_dict['scenarios']
    assert isinstance(scenarios, list)
    first = scenarios[0]
    assert isinstance(first, dict)
    first['change'] = 'moved'

    with pytest.raises(PytestGivenError, match="invalid scenario change 'moved'"):
        delta_from_dict(delta_dict)


def _parameters(
    columns: tuple[ColumnPair, ...] = (), cases: tuple[CasePair, ...] = ()
) -> ParameterDelta:
    return ParameterDelta(columns=columns, cases=cases)


def _case(**kw: object) -> CasePair:
    return CasePair(before=NodeId('1'), after=NodeId('1'), paired_by='case-id', **kw)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ('parameters', 'changed'),
    [
        (
            _parameters(
                (
                    ColumnPair(
                        before=ColumnId('a'), after=ColumnId('a'), paired_by='name'
                    ),
                ),
                (_case(),),
            ),
            False,
        ),
        (_parameters((ColumnPair(after=ColumnId('b')),)), True),
        (
            _parameters(
                (
                    ColumnPair(
                        before=ColumnId('a'), after=ColumnId('b'), paired_by='values'
                    ),
                )
            ),
            True,
        ),
        (_parameters(cases=(CasePair(before=NodeId('1')),)), True),
        (_parameters(cases=(_case(changed_cells=(ColumnId('a'),)),)), True),
        (_parameters(cases=(_case(status_changed=True),)), True),
        (_parameters(cases=(_case(id_changed=True),)), True),
    ],
    ids=[
        'all-paired',
        'unpaired-column',
        'renamed-column',
        'unpaired-case',
        'changed-cell',
        'changed-status',
        'changed-id',
    ],
)
def test_a_parameter_delta_is_changed_when_a_pair_is(
    parameters: ParameterDelta, changed: bool
) -> None:
    assert parameters.changed is changed


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
