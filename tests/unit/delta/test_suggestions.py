"""Suggested matches: removed and added items that look like one renamed item."""

import time

import pytest

from pytest_given import given, scenario, then, when
from pytest_given.delta import DeltaInputs, DeltaResult, build_delta, suggestions
from pytest_given.model import (
    DeltaData,
    IdentityPair,
    ParameterTable,
    ReportData,
    Scenario,
    Step,
    Suggestion,
)
from tests.ubiquitous_language import pg
from tests.unit.delta.builders import (
    glossary_of,
    lit,
    narr,
    ph,
    ref,
    report,
    scn,
    step,
    table,
    term,
)

STEPS = (
    'a guest picks a room for two nights',
    'the guest pays by card at the desk',
    'the hotel confirms the booking by email',
)


def _built(before: ReportData, after: ReportData) -> DeltaResult:
    return build_delta(
        DeltaInputs(
            before=before,
            after=after,
            plugin_version='0.9.0',
            timestamp='2026-10-31T00:00:00+00:00',
        )
    )


def _delta(before: ReportData, after: ReportData) -> DeltaData:
    return _built(before, after).delta


def _steps(*texts: str) -> list[Step]:
    return [step('given', text) for text in texts]


def _booking(node_id: str, *texts: str) -> Scenario:
    return scn(node_id, node_id.split('::')[1], *_steps(*texts))


def _grouped(*rows: tuple[str, int, bool]) -> Scenario:
    """A grouped scenario `t.py::t` with a case per (ID, n, flag) row."""
    parameters: ParameterTable = table(
        [('n', 'param'), ('flag', 'param')],
        *((f't.py::t[{case}]', [count, flag]) for case, count, flag in rows),
    )
    return scn(f't.py::t[{rows[0][0]}]', 'Counts', parameters=parameters)


def _swapping(term_id: str, display: str) -> Scenario:
    return scn(
        't.py::test_stay',
        'Stay',
        step(
            'given',
            narr(lit('a guest books the '), ref(term_id, display), lit(' tonight')),
        ),
    )


@scenario(
    t'A removed and an added scenario with nearly the same steps are a '
    t'{pg["Suggested match"].l}, never applied',
    tags=['delta'],
)
def test_nearly_the_same_steps_are_a_suggested_match_never_applied() -> None:
    with given(
        'a scenario removed, and one added under another name with one step reworded'
    ):
        before = report(_booking('t.py::test_old', *STEPS))
        after = report(
            _booking(
                't.py::test_new',
                *STEPS[:2],
                'the hotel confirms the booking by text',
            )
        )
    with when('the delta is built'):
        delta = _delta(before, after)
    with then('it records the two as a suggested match'):
        assert delta.suggestions == (
            Suggestion(of='scenario', before='t.py::test_old', after='t.py::test_new'),
        )
    with then('the scenarios stay removed and added, never paired'):
        assert [(listed.change, listed.paired_by) for listed in delta.scenarios] == [
            ('removed', None),
            ('added', None),
        ]


def test_scenarios_with_different_steps_are_no_match() -> None:
    delta = _delta(
        report(_booking('t.py::test_old', *STEPS)),
        report(_booking('t.py::test_new', 'a cook bakes bread', 'the oven cools')),
    )
    assert delta.suggestions == ()


def test_scenarios_without_steps_are_no_match() -> None:
    delta = _delta(
        report(scn('t.py::test_old', 'Old')), report(scn('t.py::test_new', 'New'))
    )
    assert delta.suggestions == ()


def test_only_the_mutual_best_scenario_is_suggested() -> None:
    delta = _delta(
        report(
            _booking('t.py::test_exact', *STEPS),
            _booking('t.py::test_near', *STEPS[:2], 'the hotel sends an email'),
        ),
        report(_booking('t.py::test_new', *STEPS)),
    )
    assert delta.suggestions == (
        Suggestion(of='scenario', before='t.py::test_exact', after='t.py::test_new'),
    )


def test_a_tie_for_best_scenario_is_no_match() -> None:
    delta = _delta(
        report(_booking('t.py::test_a', *STEPS), _booking('t.py::test_b', *STEPS)),
        report(_booking('t.py::test_new', *STEPS)),
    )
    assert delta.suggestions == ()


def test_a_paired_scenario_is_never_suggested() -> None:
    delta = _delta(
        report(_booking('t.py::test_same', *STEPS)),
        report(_booking('t.py::test_same', *STEPS, 'the guest leaves')),
    )
    assert delta.suggestions == ()


def test_a_removed_and_an_added_case_differing_in_one_value_are_a_match() -> None:
    delta = _delta(
        report(_grouped(('1-True', 1, True), ('2-False', 2, False))),
        report(_grouped(('3-True', 3, True), ('2-False', 2, False))),
    )
    assert delta.suggestions == (
        Suggestion(
            of='case',
            before='1-True',
            after='3-True',
            scenario=IdentityPair(before='t.py::t', after='t.py::t'),
        ),
    )


def test_cases_differing_in_two_values_are_no_match() -> None:
    delta = _delta(
        report(_grouped(('1-True', 1, True), ('2-False', 2, False))),
        report(_grouped(('3-False', 3, False), ('2-False', 2, False))),
    )
    assert delta.suggestions == ()


def test_a_case_with_two_candidates_is_no_match() -> None:
    delta = _delta(
        report(_grouped(('1-True', 1, True), ('2-True', 2, True))),
        report(_grouped(('3-True', 3, True))),
    )
    assert delta.suggestions == ()


def test_a_term_swapped_in_a_modified_step_is_a_match() -> None:
    delta = _delta(
        report(_swapping('room', 'room'), glossary=glossary_of(term('room', 'room'))),
        report(
            _swapping('suite', 'suite'), glossary=glossary_of(term('suite', 'suite'))
        ),
    )
    assert delta.suggestions == (Suggestion(of='term', before='room', after='suite'),)


def test_a_swap_of_a_term_that_is_not_removed_is_no_match() -> None:
    delta = _delta(
        report(
            _swapping('room', 'room'),
            glossary=glossary_of(term('room', 'room'), term('suite', 'suite')),
        ),
        report(
            _swapping('suite', 'suite'),
            glossary=glossary_of(term('room', 'room'), term('suite', 'suite')),
        ),
    )
    assert delta.suggestions == ()


def test_a_region_swapping_two_refs_is_no_match() -> None:
    before = scn(
        't.py::test_stay',
        'Stay',
        step(
            'given',
            narr(
                lit('a guest books the '),
                ref('room', 'room'),
                ref('bed', 'bed'),
            ),
        ),
    )
    after = scn(
        't.py::test_stay',
        'Stay',
        step(
            'given',
            narr(
                lit('a guest books the '),
                ref('suite', 'suite'),
                ref('cot', 'cot'),
            ),
        ),
    )
    delta = _delta(
        report(
            before,
            glossary=glossary_of(term('room', 'room'), term('bed', 'bed')),
        ),
        report(
            after,
            glossary=glossary_of(term('suite', 'suite'), term('cot', 'cot')),
        ),
    )
    assert delta.suggestions == ()


def test_a_renamed_column_s_placeholder_parts_two_swaps_beside_it() -> None:
    def paying(first: str, column: str, second: str) -> Scenario:
        return scn(
            't.py::t[1]',
            'Pay',
            step(
                'given',
                narr(
                    lit('a guest pays by '),
                    ref(first, first),
                    ph(column),
                    ref(second, second),
                    lit(' tonight'),
                ),
            ),
            parameters=table([(column, 'param')], ('t.py::t[1]', [1])),
        )

    delta = _delta(
        report(
            paying('card', 'cost', 'wallet'),
            glossary=glossary_of(term('card', 'card'), term('wallet', 'wallet')),
        ),
        report(
            paying('credit', 'price', 'purse'),
            glossary=glossary_of(term('credit', 'credit'), term('purse', 'purse')),
        ),
    )
    assert delta.suggestions == (
        Suggestion(of='term', before='card', after='credit'),
        Suggestion(of='term', before='wallet', after='purse'),
    )


def test_a_term_swapped_in_a_nested_step_is_a_match() -> None:
    def nested(term_id: str, display: str) -> Scenario:
        return scn(
            't.py::test_stay',
            'Stay',
            step(
                'given',
                'a guest arrives',
                step(
                    'given',
                    narr(
                        lit('a guest books the '),
                        ref(term_id, display),
                        lit(' tonight'),
                    ),
                ),
            ),
        )

    delta = _delta(
        report(nested('room', 'room'), glossary=glossary_of(term('room', 'room'))),
        report(nested('suite', 'suite'), glossary=glossary_of(term('suite', 'suite'))),
    )
    assert delta.suggestions == (Suggestion(of='term', before='room', after='suite'),)


DEFINITION = 'a place where a guest sleeps during a stay at the hotel'


def test_terms_of_one_kind_with_nearly_the_same_definition_are_a_match() -> None:
    delta = _delta(
        report(glossary=glossary_of(term('room', 'room', 'object', DEFINITION))),
        report(
            glossary=glossary_of(
                term('suite', 'suite', 'object', DEFINITION + ' for two')
            )
        ),
    )
    assert delta.suggestions == (Suggestion(of='term', before='room', after='suite'),)


def test_terms_of_different_kinds_are_no_match() -> None:
    delta = _delta(
        report(glossary=glossary_of(term('room', 'room', 'object', DEFINITION))),
        report(glossary=glossary_of(term('suite', 'suite', 'actor', DEFINITION))),
    )
    assert delta.suggestions == ()


def test_terms_without_a_definition_are_no_match() -> None:
    delta = _delta(
        report(glossary=glossary_of(term('room', 'room'))),
        report(glossary=glossary_of(term('suite', 'suite', 'object', DEFINITION))),
    )
    assert delta.suggestions == ()


def test_a_term_already_suggested_by_a_swap_is_suggested_once() -> None:
    delta = _delta(
        report(
            _swapping('room', 'room'),
            glossary=glossary_of(term('room', 'room', 'object', DEFINITION)),
        ),
        report(
            _swapping('suite', 'suite'),
            glossary=glossary_of(term('suite', 'suite', 'object', DEFINITION)),
        ),
    )
    assert delta.suggestions == (Suggestion(of='term', before='room', after='suite'),)


def _unrelated(prefix: str, count: int) -> list[Scenario]:
    return [
        scn(
            f't.py::test_{prefix}{index}',
            f'{prefix} {index}',
            *(
                step(
                    'given',
                    f'{prefix}{index} does thing{step_index} to {prefix}item{index}',
                )
                for step_index in range(10)
            ),
        )
        for index in range(count)
    ]


def _templated(prefix: str, count: int) -> list[Scenario]:
    """Scenarios that share a template, each marked by one word of its own."""
    return [
        scn(
            f't.py::test_{prefix}{index}',
            f'{prefix} {index}',
            *(
                step(
                    'given',
                    f'the guest does action{step_index} with item{step_index} in '
                    f'the shared hotel template today'
                    + (f' marker{index}' if step_index == 0 else ''),
                )
                for step_index in range(10)
            ),
        )
        for index in range(count)
    ]


def test_hundreds_of_unrelated_scenarios_stay_cheap_and_suggest_nothing() -> None:
    before = report(*_unrelated('removed', 500))
    after = report(*_unrelated('added', 500))
    started = time.perf_counter()
    built = _built(before, after)
    assert time.perf_counter() - started < 5
    assert built.delta.suggestions == ()
    assert built.warnings == ()


def test_hundreds_of_look_alike_scenarios_stay_cheap_and_still_match() -> None:
    before = report(*_templated('old', 500))
    after = report(*_templated('new', 500))
    started = time.perf_counter()
    built = _built(before, after)
    assert time.perf_counter() - started < 5
    assert built.delta.suggestions == tuple(
        Suggestion(
            of='scenario', before=f't.py::test_old{i}', after=f't.py::test_new{i}'
        )
        for i in range(500)
    )


def test_a_run_too_alike_to_compare_in_full_warns_that_suggestions_were_limited(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    before = report(*_templated('old', 6))
    after = report(*_templated('new', 6))
    assert _built(before, after).warnings == ()
    monkeypatch.setattr(suggestions, 'MAX_SUGGESTION_CANDIDATES', 2)
    built = _built(before, after)
    assert built.warnings == (suggestions.LIMITED_WARNING,)
    assert len(built.delta.suggestions) == 6
