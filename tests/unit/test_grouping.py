"""Unit tests for the case-grouping pass."""

import dataclasses
from datetime import UTC, datetime

import pytest

from pytest_given import Glossary, given, scenario, then, when, when_then
from pytest_given.grouping import checks, columns, group, group_parametrized, templatize
from pytest_given.model import (
    Attachment,
    AttachmentRef,
    Narration,
    NarrationLiteral,
    NarrationPart,
    NarrationPlaceholder,
    NarrationTermRef,
    NarrationValue,
    NodeId,
    ParamInfo,
    ParamSpec,
    PytestGivenError,
    Scenario,
    SourceLocation,
    Step,
    TermId,
    narration_text,
)
from tests.ubiquitous_language import adopt_pytest_given, pg


def test_templatize_narration_rejects_unknown_placeholder() -> None:
    """Safety-net guard: a NarrationPlaceholder whose name isn't a parametrize
    column raises. Defense in depth on top of the collection-time hook, which
    catches Template placeholders in scenario names (and step text from
    Template can't happen since given/when/then reject Template). The runtime
    guard covers any future code path that might construct parts directly."""
    narration = Narration(
        text='', parts=[NarrationPlaceholder(name='cup_zize', column_id='cup_zize')]
    )
    with pytest.raises(PytestGivenError, match='cup_zize'):
        templatize.templatize_narration(narration, ['cup_size'])


def test_group_parametrized_all_skipped_groups_as_skipped() -> None:
    nid1, nid2 = NodeId('t::x[1]'), NodeId('t::x[2]')
    scenarios = [
        Scenario(id=nid1, narration=Narration(text='x'), module='m', status='skipped'),
        Scenario(id=nid2, narration=Narration(text='x'), module='m', status='skipped'),
    ]
    param_info = {
        nid1: ParamSpec(names=['n'], values=[1]),
        nid2: ParamSpec(names=['n'], values=[2]),
    }
    grouped = group_parametrized(scenarios, param_info)
    assert len(grouped) == 1
    assert grouped[0].status == 'skipped'


def test_group_parametrized_mixed_pass_skip_groups_as_passed() -> None:
    nid1, nid2 = NodeId('t::x[1]'), NodeId('t::x[2]')
    scenarios = [
        Scenario(id=nid1, narration=Narration(text='x'), module='m', status='passed'),
        Scenario(id=nid2, narration=Narration(text='x'), module='m', status='skipped'),
    ]
    param_info = {
        nid1: ParamSpec(names=['n'], values=[1]),
        nid2: ParamSpec(names=['n'], values=[2]),
    }
    grouped = group_parametrized(scenarios, param_info)
    assert grouped[0].status == 'passed'


@scenario(
    t'{pg["Group"]("Grouping")} collapses parametrize {pg["Case"]("cases")} into one '
    t'{pg["Scenario"].low}',
    tags=['parametrization'],
    story=adopt_pytest_given,
)
def test_group_parametrized_any_failed_groups_as_failed() -> None:
    with given(t'three {pg["Case"]} records of one {pg["Parametrized scenario"]}'):
        nid1, nid2, nid3 = NodeId('t::x[1]'), NodeId('t::x[2]'), NodeId('t::x[3]')
        scenarios = [
            Scenario(
                id=nid1, narration=Narration(text='x'), module='m', status='passed'
            ),
            Scenario(
                id=nid2, narration=Narration(text='x'), module='m', status='failed'
            ),
            Scenario(
                id=nid3, narration=Narration(text='x'), module='m', status='skipped'
            ),
        ]
        param_info = {
            nid1: ParamSpec(names=['n'], values=[1]),
            nid2: ParamSpec(names=['n'], values=[2]),
            nid3: ParamSpec(names=['n'], values=[3]),
        }
    with when(t'the {pg["Group"]("grouping")} pass collapses them', activity=9):
        grouped = group_parametrized(scenarios, param_info)
    with then(t'one scenario remains and any failed {pg["Case"]} fails it'):
        assert len(grouped) == 1
        assert grouped[0].status == 'failed'


def test_group_parametrized_distinct_functions_same_name_do_not_group() -> None:
    # Two different parametrized functions in one module that happen to share a
    # scenario label must stay separate — grouping keys on the test function
    # (node id without its parametrize tail), not on the rendered label.
    nid1, nid2 = NodeId('t::x[1]'), NodeId('t::y[1]')
    scenarios = [
        Scenario(id=nid1, narration=Narration(text='same label'), module='m'),
        Scenario(id=nid2, narration=Narration(text='same label'), module='m'),
    ]
    param_info = {
        nid1: ParamSpec(names=['n'], values=[1]),
        nid2: ParamSpec(names=['k'], values=[1]),
    }
    grouped = group_parametrized(scenarios, param_info)
    assert {s.id for s in grouped} == {nid1, nid2}
    assert {
        tuple(c.name for c in s.parameters.columns) for s in grouped if s.parameters
    } == {
        ('n',),
        ('k',),
    }


def test_param_cell_unwraps_a_term_instance_to_its_display() -> None:
    glossary = Glossary()
    guest = glossary.actor('Guest')
    nid1, nid2 = NodeId('t::x[alice]'), NodeId('t::x[bob]')
    scenarios = [
        Scenario(id=nid1, narration=Narration(text='x'), module='m', status='passed'),
        Scenario(id=nid2, narration=Narration(text='x'), module='m', status='passed'),
    ]
    param_info = {
        nid1: ParamSpec(names=['guest'], values=[guest('Alice')]),
        nid2: ParamSpec(names=['guest'], values=[guest('Bob')]),
    }
    grouped = group_parametrized(scenarios, param_info)
    assert [case.values[0] for case in grouped[0].parameters.cases] == ['Alice', 'Bob']


def test_a_non_scalar_parametrize_value_still_reaches_the_cell_as_a_string() -> None:
    """Coercion moved to the cell; the shape it produces is unchanged."""
    moment = datetime(2026, 1, 1, tzinfo=UTC)
    nid = NodeId('t::x[a]')
    scenarios = [
        Scenario(id=nid, narration=Narration(text='x'), module='m', status='passed')
    ]
    param_info = {nid: ParamSpec(names=['when'], values=[moment])}
    grouped = group_parametrized(scenarios, param_info)
    assert grouped[0].parameters.cases[0].values == [str(moment)]


def test_templatize_keeps_a_scenario_name_term_ref_verbatim() -> None:
    """Whether or not the ref's expression names a parametrize argument.

    A scenario name is evaluated once at decoration time, so nothing in it can
    vary per case — and a term ref in a *step* no longer varies either, so a
    parametrize name matching its expression means nothing here.
    """
    narration = Narration(
        text='Alice arrives',
        parts=[
            NarrationTermRef(
                term_id=TermId('guest'),
                display='Alice',
                expression='guest',
            ),
            NarrationLiteral(value=' arrives'),
        ],
    )
    for param_names in (['guest'], ['euros']):
        out = templatize.templatize_narration(narration, param_names=param_names)
        ref = next(p for p in out.parts if isinstance(p, NarrationTermRef))
        assert ref == narration.parts[0]


@scenario(
    t'The grouped tree comes from the first passed {pg["Case"].low}',
    tags=['parametrization'],
)
def test_baseline_is_the_first_passed_case_not_the_first_case() -> None:
    with given(t'a skipped first {pg["Case"]} and a second one that ran'):
        nid1, nid2 = NodeId('t.py::test_brew[200]'), NodeId('t.py::test_brew[350]')
        ran = Step(phase='when', narration=Narration(text='I brew'))
        scenarios = [
            Scenario(
                id=nid1, narration=Narration(text='brew'), module='m', status='skipped'
            ),
            Scenario(
                id=nid2,
                narration=Narration(text='brew'),
                module='m',
                status='passed',
                steps=[ran],
            ),
        ]
        param_info = {
            nid1: ParamSpec(names=['cup_size'], values=[200]),
            nid2: ParamSpec(names=['cup_size'], values=[350]),
        }
    with when(t'the {pg["Case"]("cases")} are {pg["Group"]("grouped")}'):
        grouped = group_parametrized(scenarios, param_info)
    with then(t'the tree is the one the passed {pg["Case"]} recorded'):
        assert [s.narration.text for s in grouped[0].steps] == ['I brew']


def test_grouped_scenario_keeps_the_first_cases_identity_fields() -> None:
    """Baseline selection scopes to the step tree — deep links and ordering
    must not shift with which case happened to pass."""
    nid1, nid2 = NodeId('t.py::test_brew[200]'), NodeId('t.py::test_brew[350]')
    src1 = SourceLocation(relpath='t.py', line=10)
    src2 = SourceLocation(relpath='t.py', line=99)
    scenarios = [
        Scenario(
            id=nid1,
            narration=Narration(text='brew'),
            module='m',
            status='skipped',
            source=src1,
            tags=['a'],
        ),
        Scenario(
            id=nid2,
            narration=Narration(text='brew'),
            module='m',
            status='passed',
            source=src2,
            tags=['b'],
        ),
    ]
    param_info = {
        nid1: ParamSpec(names=['cup_size'], values=[200]),
        nid2: ParamSpec(names=['cup_size'], values=[350]),
    }
    grouped = group_parametrized(scenarios, param_info)
    assert (grouped[0].id, grouped[0].source, grouped[0].tags) == (nid1, src1, ['a'])


def test_no_case_passed_falls_back_to_the_first_case() -> None:
    nid1, nid2 = NodeId('t.py::test_brew[200]'), NodeId('t.py::test_brew[350]')
    scenarios = [
        Scenario(
            id=nid1,
            narration=Narration(text='brew'),
            module='m',
            status='failed',
            steps=[Step(phase='when', narration=Narration(text='first'))],
        ),
        Scenario(
            id=nid2,
            narration=Narration(text='brew'),
            module='m',
            status='failed',
            steps=[Step(phase='when', narration=Narration(text='second'))],
        ),
    ]
    param_info = {
        nid1: ParamSpec(names=['cup_size'], values=[200]),
        nid2: ParamSpec(names=['cup_size'], values=[350]),
    }
    grouped = group_parametrized(scenarios, param_info)
    assert [s.narration.text for s in grouped[0].steps] == ['first']


def test_with_no_passed_case_the_baseline_is_one_that_recorded_a_tree() -> None:
    """A skipped case records no steps at all, so taking it as the baseline
    just because it came first renders the whole scenario step-less — hiding
    the failing case's steps and its error, which is the one thing a reader
    opens a failed scenario for."""
    nid1, nid2 = NodeId('t.py::test_brew[200]'), NodeId('t.py::test_brew[350]')
    scenarios = [
        Scenario(
            id=nid1,
            narration=Narration(text='brew'),
            module='m',
            status='skipped',
            steps=[],
        ),
        Scenario(
            id=nid2,
            narration=Narration(text='brew'),
            module='m',
            status='failed',
            steps=[Step(phase='when', narration=Narration(text='it brews'))],
        ),
    ]
    param_info = {
        nid1: ParamSpec(names=['cup_size'], values=[200]),
        nid2: ParamSpec(names=['cup_size'], values=[350]),
    }
    grouped = group_parametrized(scenarios, param_info)[0]
    assert [s.narration.text for s in grouped.steps] == ['it brews']


def test_comparable_is_every_passed_case() -> None:
    """Rule 6 refuses a group whose passed cases differ in shape, so by the
    time cells are filled every passed case is comparable by construction."""
    base = Scenario(
        id=NodeId('t.py::t[1]'),
        narration=Narration(text='x'),
        module='m',
        status='passed',
        steps=[Step(phase='given', narration=Narration(text='a'))],
    )
    other = dataclasses.replace(base, id=NodeId('t.py::t[2]'))
    assert group._comparable([base, other]) == [base, other]


def test_comparable_excludes_a_non_passed_case() -> None:
    """A failed case with the exact same step structure as the baseline must
    still drop out — status is now the only thing that disqualifies a case."""
    base = Scenario(
        id=NodeId('t.py::t[1]'),
        narration=Narration(text='x'),
        module='m',
        status='passed',
        steps=[Step(phase='given', narration=Narration(text='a'))],
    )
    other = Scenario(
        id=NodeId('t.py::t[2]'),
        narration=Narration(text='x'),
        module='m',
        status='failed',
        steps=[Step(phase='given', narration=Narration(text='a'))],
    )
    assert group._comparable([base, other]) == [base]


def test_test_name_drops_the_path_and_the_case_suffix() -> None:
    assert (
        checks._test_name(
            Scenario(
                id=NodeId('tests/t.py::test_brew[200]'),
                narration=Narration(text='x'),
                module='m',
            )
        )
        == 'test_brew'
    )


def _two_case_group(
    steps1: list[Step], steps2: list[Step]
) -> tuple[list[Scenario], ParamInfo]:
    nid1, nid2 = NodeId('t.py::test_brew[200]'), NodeId('t.py::test_brew[350]')
    scenarios = [
        Scenario(
            id=nid1,
            narration=Narration(text='brew'),
            module='m',
            status='passed',
            steps=steps1,
            source=SourceLocation(relpath='tests/t.py', line=12),
        ),
        Scenario(
            id=nid2,
            narration=Narration(text='brew'),
            module='m',
            status='passed',
            steps=steps2,
            source=SourceLocation(relpath='tests/t.py', line=12),
        ),
    ]
    return scenarios, {
        nid1: ParamSpec(names=['cup_size'], values=[200]),
        nid2: ParamSpec(names=['cup_size'], values=[350]),
    }


def _three_case_group(
    steps1: list[Step], steps2: list[Step], steps3: list[Step]
) -> tuple[list[Scenario], ParamInfo]:
    """`_two_case_group` with a middle case, for the several tests that must
    distinguish "checks every case" from "checks only an end one"."""
    nid1, nid2, nid3 = (
        NodeId('t.py::test_brew[a]'),
        NodeId('t.py::test_brew[b]'),
        NodeId('t.py::test_brew[c]'),
    )
    scenarios = [
        Scenario(
            id=nid,
            narration=Narration(text='brew'),
            module='m',
            status='passed',
            steps=case_steps,
            source=SourceLocation(relpath='tests/t.py', line=12),
        )
        for nid, case_steps in ((nid1, steps1), (nid2, steps2), (nid3, steps3))
    ]
    return scenarios, {
        nid1: ParamSpec(names=['cup_size'], values=[200]),
        nid2: ParamSpec(names=['cup_size'], values=[350]),
        nid3: ParamSpec(names=['cup_size'], values=[500]),
    }


@scenario(
    t'A plain-str {pg["Narration"].low} that varies across '
    t'{pg["Case"]("cases")} is refused',
    tags=['parametrization', 'validation'],
)
def test_a_varying_str_narration_raises_rule_one() -> None:
    with given(t'two {pg["Case"]("cases")} whose text differs but records no parts'):
        scenarios, info = _two_case_group(
            [Step(phase='when', narration=Narration(text='the machine brews 200 ml'))],
            [Step(phase='when', narration=Narration(text='the machine brews 350 ml'))],
        )
    with (
        when_then(
            t'the {pg["Case"]("cases")} are {pg["Group"]("grouped")}',
            'the grouping is refused',
        ),
        pytest.raises(PytestGivenError) as excinfo,
    ):
        group_parametrized(scenarios, info)
    with then('the error names the test, the missing parts and the t-string fix'):
        message = str(excinfo.value)
        assert (
            "step narration in 'test_brew' varies across parametrize cases" in message
        )
        assert 'records no parts' in message
        assert 'Use a t-string' in message
        assert message.endswith('(t.py:12)')


def test_a_varying_str_narration_names_the_violating_steps_own_phase() -> None:
    """The fix hint must name the keyword for the step that actually violated
    rule 1, not a hardcoded 'when' — a violating `given` step must be told to
    write `given(t"…")`, not `when(...)`."""
    scenarios, info = _two_case_group(
        [Step(phase='given', narration=Narration(text='a 200 ml cup'))],
        [Step(phase='given', narration=Narration(text='a 350 ml cup'))],
    )
    with pytest.raises(PytestGivenError) as excinfo:
        group_parametrized(scenarios, info)
    message = str(excinfo.value)
    assert 'given(t"…")' in message
    assert 'when(' not in message


def test_a_constant_str_narration_does_not_raise() -> None:
    scenarios, info = _two_case_group(
        [Step(phase='when', narration=Narration(text='the machine brews'))],
        [Step(phase='when', narration=Narration(text='the machine brews'))],
    )
    assert group_parametrized(scenarios, info)[0].steps[0].narration.text == (
        'the machine brews'
    )


def test_rule_one_checks_every_comparable_case_not_just_an_end_one() -> None:
    """Rule 1 sweeps `comparable`, and a two-case fixture cannot tell "checks
    every case" from "checks the last one". Here only the *middle* case renders
    differently: sweeping an end case alone finds nothing and the group ships
    the baseline's text as if it spoke for all three."""
    scenarios, info = _three_case_group(
        [Step(phase='when', narration=Narration(text='the machine brews 200 ml'))],
        [Step(phase='when', narration=Narration(text='the machine brews 350 ml'))],
        [Step(phase='when', narration=Narration(text='the machine brews 200 ml'))],
    )
    with pytest.raises(PytestGivenError) as excinfo:
        group_parametrized(scenarios, info)
    assert 'records no parts' in str(excinfo.value)


def test_rule_one_reads_the_walked_step_in_a_nested_position() -> None:
    """Rule 1 looks each case's step up by path, which must be the path being
    walked and not a fixed top-level one. The parent here is constant *and*
    reads exactly like the child's baseline text, so reading `(0,)` for the
    child compares it against that constant parent, finds them equal, and lets
    the varying child text ship as the baseline's."""

    def steps(child_text: str) -> list[Step]:
        return [
            Step(
                phase='given',
                narration=Narration(text='the machine brews 200 ml'),
                children=[Step(phase='when', narration=Narration(text=child_text))],
            ),
        ]

    scenarios, info = _two_case_group(
        steps('the machine brews 200 ml'), steps('the machine brews 350 ml')
    )
    with pytest.raises(PytestGivenError) as excinfo:
        group_parametrized(scenarios, info)
    assert 'records no parts' in str(excinfo.value)


def _value_step(
    rendered: str,
    expression: str = 'price',
    format_spec: str = '',
    conversion: str | None = None,
) -> Step:
    return Step(
        phase='then',
        narration=Narration(
            text=f'the drink costs {rendered} euros',
            parts=[
                NarrationLiteral(value='the drink costs '),
                NarrationValue(
                    rendered=rendered,
                    expression=expression,
                    format_spec=format_spec,
                    conversion=conversion,
                ),
                NarrationLiteral(value=' euros'),
            ],
        ),
    )


@scenario(
    t'A narrated value that varies becomes a derived {pg["Parameter table"].low} '
    t'column',
    tags=['parametrization'],
)
def test_a_varying_bare_name_interpolation_becomes_a_derived_column() -> None:
    with given(t'two {pg["Case"]("cases")} narrating a value that differs'):
        scenarios, info = _two_case_group(
            [_value_step('2.0', format_spec='.2f', conversion='r')],
            [_value_step('3.5', format_spec='.2f', conversion='r')],
        )
    with when(t'{pg["Templatize"]("templatizing")} walks the {pg["Case"]("cases")}'):
        grouped = group_parametrized(scenarios, info)[0]
    with then('the value becomes a derived column beside the parametrize one'):
        assert [(c.id, c.name, c.kind) for c in grouped.parameters.columns] == [
            ('cup_size', 'cup_size', 'param'),
            ('derived:0', 'price', 'derived'),
        ]
        assert [case.values for case in grouped.parameters.cases] == [
            [200, '2.0'],
            [350, '3.5'],
        ]
    with then(t'the {pg["Step"]} keeps a placeholder pointing at that column'):
        part = grouped.steps[0].narration.parts[1]
        assert isinstance(part, NarrationPlaceholder)
        assert (part.name, part.column_id) == ('price', 'derived:0')
    # format_spec/conversion pass through the derived-placeholder site
    # unchanged — rule 3 (a later task) re-applies them to the raw value.
    assert (part.format_spec, part.conversion) == ('.2f', 'r')


def test_a_grouped_steps_text_is_rebuilt_from_its_parts() -> None:
    scenarios, info = _two_case_group([_value_step('2.0')], [_value_step('3.5')])
    grouped = group_parametrized(scenarios, info)[0]
    step = grouped.steps[0]
    assert step.narration.text == 'the drink costs {price} euros'
    assert step.narration.text == ''.join(
        p.value if isinstance(p, NarrationLiteral) else '{' + p.name + '}'
        for p in step.narration.parts
    )


def test_a_plain_str_steps_text_survives_grouping_when_another_step_promotes() -> None:
    """`_templatize_step_narration`'s `if not narration.parts: return narration`
    guard: a step with `parts == []` (plain str narration) must return its
    narration unchanged, even inside a scenario where a *different* step
    promotes a value. Without the guard, the rebuild's list comprehension
    would iterate zero parts and reduce the str step's text to ''."""

    def steps(price: str) -> list[Step]:
        return [
            Step(phase='given', narration=Narration(text='a fresh cup')),
            _value_step(price),
        ]

    scenarios, info = _two_case_group(steps('2.0'), steps('3.5'))
    grouped = group_parametrized(scenarios, info)[0]
    assert grouped.steps[0].narration.text == 'a fresh cup'
    assert grouped.steps[0].narration.parts == []


def test_a_param_placeholders_step_text_is_rebuilt_too() -> None:
    # rendered values must be a faithful `!r:>6` rendering of cup_size (200,
    # 350) so rule 3 doesn't flag this fixture as a rebinding.
    step = Step(
        phase='when',
        narration=Narration(
            text='I insert $   200',
            parts=[
                NarrationLiteral(value='I insert $'),
                NarrationValue(
                    rendered='   200',
                    expression='cup_size',
                    format_spec='>6',
                    conversion='r',
                ),
            ],
        ),
    )
    other = dataclasses.replace(
        step,
        narration=Narration(
            text='I insert $   350',
            parts=[
                NarrationLiteral(value='I insert $'),
                NarrationValue(
                    rendered='   350',
                    expression='cup_size',
                    format_spec='>6',
                    conversion='r',
                ),
            ],
        ),
    )
    scenarios, info = _two_case_group([step], [other])
    grouped = group_parametrized(scenarios, info)[0]
    assert grouped.steps[0].narration.text == 'I insert ${cup_size}'
    placeholder = grouped.steps[0].narration.parts[1]
    assert isinstance(placeholder, NarrationPlaceholder)
    # format_spec/conversion pass through the param-name placeholder site
    # unchanged — rule 3 re-applies them to the raw value.
    assert (placeholder.format_spec, placeholder.conversion) == ('>6', 'r')


def test_a_constant_interpolation_stays_inline_and_makes_no_column() -> None:
    scenarios, info = _two_case_group([_value_step('2.0')], [_value_step('2.0')])
    grouped = group_parametrized(scenarios, info)[0]
    assert [c.kind for c in grouped.parameters.columns] == ['param']
    assert isinstance(grouped.steps[0].narration.parts[1], NarrationValue)
    assert grouped.steps[0].narration.text == 'the drink costs 2.0 euros'


@scenario(
    t'A varying interpolation that is not a bare name is refused',
    tags=['diagnostics', 'parametrization', 'validation'],
)
def test_a_varying_compound_interpolation_raises_rule_two() -> None:
    with given(t'two {pg["Case"]("cases")} narrating a computed expression'):
        scenarios, info = _two_case_group(
            [_value_step('2.0', expression='cup_size * 0.01')],
            [_value_step('3.5', expression='cup_size * 0.01')],
        )
    with (
        when_then(
            t'the {pg["Case"]("cases")} are {pg["Group"]("grouped")}',
            'the grouping is refused',
        ),
        pytest.raises(PytestGivenError) as excinfo,
    ):
        group_parametrized(scenarios, info)
    with then('the error quotes the expression and shows the bind-a-local fix'):
        message = str(excinfo.value)
        assert (
            "'cup_size * 0.01' in 'test_brew' varies across parametrize cases"
            in message
        )
        assert 'value = cup_size * 0.01' in message
        assert message.endswith('(t.py:12)')


def test_rule_two_names_the_violating_steps_own_phase() -> None:
    """Mirrors the rule-1 phase test: rule 2's fix hint must name the keyword
    for the step that actually violated it, not a hardcoded 'when'."""
    scenarios, info = _two_case_group(
        [
            Step(
                phase='given',
                narration=Narration(
                    text='a 2.0 euro cup',
                    parts=[
                        NarrationLiteral(value='a '),
                        NarrationValue(rendered='2.0', expression='cup_size * 0.01'),
                        NarrationLiteral(value=' euro cup'),
                    ],
                ),
            )
        ],
        [
            Step(
                phase='given',
                narration=Narration(
                    text='a 3.5 euro cup',
                    parts=[
                        NarrationLiteral(value='a '),
                        NarrationValue(rendered='3.5', expression='cup_size * 0.01'),
                        NarrationLiteral(value=' euro cup'),
                    ],
                ),
            )
        ],
    )
    with pytest.raises(PytestGivenError) as excinfo:
        group_parametrized(scenarios, info)
    message = str(excinfo.value)
    assert 'given(t"… {value} …").' in message
    assert 'when(' not in message


def test_a_constant_compound_interpolation_stays_inline() -> None:
    scenarios, info = _two_case_group(
        [_value_step('2.0', expression='m.balance')],
        [_value_step('2.0', expression='m.balance')],
    )
    assert [
        c.kind for c in group_parametrized(scenarios, info)[0].parameters.columns
    ] == ['param']


def test_two_same_named_derived_columns_get_distinct_ids() -> None:
    """Two steps interpolating the same expression with different values would
    cross-wire if the expression were the key."""

    def steps(a: str, b: str) -> list[Step]:
        return [_value_step(a), _value_step(b)]

    scenarios, info = _two_case_group(steps('2.0', '9.0'), steps('3.5', '9.9'))
    grouped = group_parametrized(scenarios, info)[0]
    assert [c.id for c in grouped.parameters.columns] == [
        'cup_size',
        'derived:0',
        'derived:1',
    ]
    # Same expression, so the second column's *name* is disambiguated for the
    # rendered table the way its id already is for the JSON.
    assert [c.name for c in grouped.parameters.columns] == [
        'cup_size',
        'price',
        'price #2',
    ]
    ids: list[str] = []
    for s in grouped.steps:
        part = s.narration.parts[1]
        assert isinstance(part, NarrationPlaceholder)
        ids.append(part.column_id)
    assert ids == ['derived:0', 'derived:1']


def test_derived_column_ids_are_assigned_pre_order_across_nesting() -> None:
    """`_templatize_steps` builds a step's own narration and its children's
    narrations in one `dataclasses.replace` call; swapping the `narration=`
    and `children=` keyword arguments would reorder evaluation (Python
    evaluates keyword arguments left to right) and hand the child's promotion
    `derived:0` instead of the parent's. A promotion at both the parent and a
    nested child pins pre-order id assignment."""

    def steps(parent_price: str, child_discount: str) -> list[Step]:
        return [
            Step(
                phase='then',
                narration=Narration(
                    text=f'the drink costs {parent_price} euros',
                    parts=[
                        NarrationLiteral(value='the drink costs '),
                        NarrationValue(rendered=parent_price, expression='price'),
                        NarrationLiteral(value=' euros'),
                    ],
                ),
                children=[
                    Step(
                        phase='then',
                        narration=Narration(
                            text=f'a {child_discount} discount applies',
                            parts=[
                                NarrationLiteral(value='a '),
                                NarrationValue(
                                    rendered=child_discount, expression='discount'
                                ),
                                NarrationLiteral(value=' discount applies'),
                            ],
                        ),
                    ),
                ],
            ),
        ]

    scenarios, info = _two_case_group(steps('2.0', '5%'), steps('3.5', '10%'))
    grouped = group_parametrized(scenarios, info)[0]
    assert [(c.id, c.name) for c in grouped.parameters.columns] == [
        ('cup_size', 'cup_size'),
        ('derived:0', 'price'),
        ('derived:1', 'discount'),
    ]
    parent_part = grouped.steps[0].narration.parts[1]
    child_part = grouped.steps[0].children[0].narration.parts[1]
    assert isinstance(parent_part, NarrationPlaceholder)
    assert isinstance(child_part, NarrationPlaceholder)
    assert (parent_part.column_id, child_part.column_id) == ('derived:0', 'derived:1')


def test_a_nested_steps_varying_value_reads_the_walked_step() -> None:
    """The derived comparison looks each case's step up by path too. The parent
    here interpolates a *constant* value at the same part index as the child's
    varying one, so reading `(0,)` instead of `(0, 0)` compares the child
    against the parent's constant: no column, and the child's differing value
    ships as the baseline's."""

    def steps(child_rendered: str) -> list[Step]:
        parent = _value_step('9.0', expression='fee')
        child = _value_step(child_rendered, expression='price')
        return [dataclasses.replace(parent, children=[child])]

    scenarios, info = _two_case_group(steps('2.0'), steps('3.5'))
    grouped = group_parametrized(scenarios, info)[0]
    assert grouped.parameters is not None
    assert [(c.id, c.name) for c in grouped.parameters.columns] == [
        ('cup_size', 'cup_size'),
        ('derived:0', 'price'),
    ]
    assert [c.values[1] for c in grouped.parameters.cases] == ['2.0', '3.5']
    # The parent's own interpolation is constant, so it stays inline.
    assert grouped.steps[0].narration.text == 'the drink costs 9.0 euros'
    assert grouped.steps[0].children[0].narration.text == (
        'the drink costs {price} euros'
    )


def test_a_skipped_case_gets_blank_derived_cells() -> None:
    nid1, nid2, nid3 = (
        NodeId('t.py::test_brew[200]'),
        NodeId('t.py::test_brew[350]'),
        NodeId('t.py::test_brew[500]'),
    )
    scenarios = [
        Scenario(
            id=nid1,
            narration=Narration(text='brew'),
            module='m',
            status='passed',
            steps=[_value_step('2.0')],
        ),
        Scenario(
            id=nid2,
            narration=Narration(text='brew'),
            module='m',
            status='passed',
            steps=[_value_step('3.5')],
        ),
        Scenario(
            id=nid3, narration=Narration(text='brew'), module='m', status='skipped'
        ),
    ]
    info = {
        nid1: ParamSpec(names=['cup_size'], values=[200]),
        nid2: ParamSpec(names=['cup_size'], values=[350]),
        nid3: ParamSpec(names=['cup_size'], values=[500]),
    }
    assert [
        c.values for c in group_parametrized(scenarios, info)[0].parameters.cases
    ] == [
        [200, '2.0'],
        [350, '3.5'],
        [500, None],
    ]


def test_a_step_placeholder_naming_an_unknown_column_raises() -> None:
    """Defense in depth for the step-level walk, mirroring
    test_templatize_narration_rejects_unknown_placeholder for the scenario-name
    walk: a Template placeholder in a step's own narration that doesn't match
    any parametrize column must still raise, not silently pass through."""
    step = Step(
        phase='given',
        narration=Narration(
            text='',
            parts=[NarrationPlaceholder(name='cup_zize', column_id='cup_zize')],
        ),
    )
    other = Step(
        phase='given',
        narration=Narration(
            text='',
            parts=[NarrationPlaceholder(name='cup_zize', column_id='cup_zize')],
        ),
    )
    scenarios, info = _two_case_group([step], [other])
    with pytest.raises(PytestGivenError, match='cup_zize'):
        group_parametrized(scenarios, info)


def test_a_same_length_case_with_a_different_part_kind_refuses_the_merge() -> None:
    """Rule 6 compares part *kinds*, not part counts: a case whose parts list
    is as long as the baseline's but carries a literal where the baseline
    carries an interpolation is differently shaped all the same."""
    other_step = Step(
        phase='then',
        narration=Narration(
            text='the drink costs 2.0 euros',
            parts=[
                NarrationLiteral(value='the drink costs '),
                NarrationLiteral(value='2.0'),
                NarrationLiteral(value=' euros'),
            ],
        ),
    )
    scenarios, info = _two_case_group([_value_step('2.0')], [other_step])
    with pytest.raises(PytestGivenError, match='differently shaped'):
        group_parametrized(scenarios, info)


def test_a_grouped_steps_text_rebuild_covers_every_part_kind() -> None:
    """A step mixing all four part kinds, where only one interpolation
    promotes: the rebuilt text must still carry the constant NarrationValue's
    rendered text and both NarrationTermRefs' displays verbatim. One term ref's
    expression matches `cup_size` (the group's own param name) and the other's
    matches nothing; both pass through untouched, since rule 4 holds a term ref
    constant either way."""

    def step(price: str) -> Step:
        return Step(
            phase='then',
            narration=Narration(
                text=f'cost {price} for Alice at 1.2 with Bob tax',
                parts=[
                    NarrationLiteral(value='cost '),
                    NarrationValue(rendered=price, expression='price'),
                    NarrationLiteral(value=' for '),
                    NarrationTermRef(
                        term_id=TermId('guest'), display='Alice', expression='cup_size'
                    ),
                    NarrationLiteral(value=' at '),
                    NarrationValue(rendered='1.2', expression='tax_rate'),
                    NarrationLiteral(value=' with '),
                    NarrationTermRef(
                        term_id=TermId('host'), display='Bob', expression='unrelated'
                    ),
                    NarrationLiteral(value=' tax'),
                ],
            ),
        )

    scenarios, info = _two_case_group([step('2.0')], [step('3.5')])
    grouped = group_parametrized(scenarios, info)[0]
    step_out = grouped.steps[0]
    assert step_out.narration.text == 'cost {price} for Alice at 1.2 with Bob tax'
    assert step_out.narration.parts[3] == step('2.0').narration.parts[3]
    assert step_out.narration.parts[7] == step('2.0').narration.parts[7]


def test_templatize_narration_converts_a_matching_value_to_a_placeholder() -> None:
    """The scenario-name counterpart to the step-level NarrationValue
    promotion: a bare-name interpolation matching a parametrize column becomes
    a placeholder; one that doesn't match stays an inline value."""
    narration = Narration(
        text='Brew 200 ml for $12.5',
        parts=[
            NarrationLiteral(value='Brew '),
            NarrationValue(rendered='200', expression='cup_size'),
            NarrationLiteral(value=' ml for $'),
            NarrationValue(rendered='12.5', expression='price'),
        ],
    )
    out = templatize.templatize_narration(narration, param_names=['cup_size'])
    placeholder = out.parts[1]
    assert isinstance(placeholder, NarrationPlaceholder)
    assert (placeholder.name, placeholder.column_id) == ('cup_size', 'cup_size')
    assert isinstance(out.parts[3], NarrationValue)


def _param_value_step(
    rendered: str, *, spec: str = '', conv: str | None = None
) -> Step:
    return Step(
        phase='when',
        narration=Narration(
            text=f'the machine brews {rendered} ml',
            parts=[
                NarrationLiteral(value='the machine brews '),
                NarrationValue(
                    rendered=rendered,
                    expression='cup_size',
                    format_spec=spec,
                    conversion=conv,
                ),
                NarrationLiteral(value=' ml'),
            ],
        ),
    )


def _named_group(
    name: Narration, steps1: list[Step], steps2: list[Step]
) -> tuple[list[Scenario], ParamInfo]:
    """`_two_case_group` with a `Template`-style scenario name carrying parts."""
    scenarios, info = _two_case_group(steps1, steps2)
    for case in scenarios:
        case.narration = name
    return scenarios, info


def _price_name(spec: str) -> Narration:
    parts: list[NarrationPart] = [
        NarrationLiteral(value='charge '),
        NarrationPlaceholder(name='cup_size', column_id='cup_size', format_spec=spec),
        NarrationLiteral(value=' ml'),
    ]
    return Narration(text=narration_text(parts), parts=parts)


@scenario(
    t'A {pg["Parameter table"].low} cell reads the way the scenario name formats it',
    tags=['parametrization'],
)
def test_a_scenario_name_format_spec_reaches_its_cell() -> None:
    with given('a Template scenario name formatting its parameter'):
        scenarios, info = _named_group(_price_name('.2f'), [], [])
    with when(t'the {pg["Case"]("cases")} are {pg["Group"]("grouped")}'):
        grouped = group_parametrized(scenarios, info)
    with then('the cells carry the formatting the name declared'):
        table = grouped[0].parameters
        assert table is not None
        assert [c.values for c in table.cases] == [['200.00'], ['350.00']]


@scenario(
    t'A scenario name formatting a parameter a {pg["Step"].low} reads plainly '
    t'gets its own column',
    tags=['parametrization'],
)
def test_a_scenario_name_disagreeing_with_a_step_gets_its_own_column() -> None:
    with given('a name formatting the parameter and a step reading it plainly'):
        scenarios, info = _named_group(
            _price_name('.2f'), [_param_value_step('200')], [_param_value_step('350')]
        )
    with when(t'the {pg["Case"]("cases")} are {pg["Group"]("grouped")}'):
        grouped = group_parametrized(scenarios, info)
    with then('the name points at a column holding what it renders'):
        table = grouped[0].parameters
        assert table is not None
        assert [(c.id, c.name) for c in table.columns] == [
            ('cup_size', 'cup_size'),
            ('derived:0', 'cup_size #2'),
        ]
        assert [c.values for c in table.cases] == [
            [200, '200.00'],
            [350, '350.00'],
        ]
    with then('the name renders the disambiguated token, text and parts agreeing'):
        slot = grouped[0].narration.parts[1]
        assert isinstance(slot, NarrationPlaceholder)
        assert (slot.name, slot.column_id) == ('cup_size #2', 'derived:0')
        assert grouped[0].narration.text == 'charge {cup_size #2} ml'


def _placeholder_step(spec: str) -> Step:
    """A step whose narration is a `Template` slot — what an
    `Annotated[..., given(Template(...))]` label grafts in."""
    parts: list[NarrationPart] = [
        NarrationLiteral(value='a cup of '),
        NarrationPlaceholder(name='cup_size', column_id='cup_size', format_spec=spec),
        NarrationLiteral(value=' ml'),
    ]
    return Step(
        phase='given', narration=Narration(text=narration_text(parts), parts=parts)
    )


@scenario(
    t'A {pg["Step"].low} formatting a parameter the scenario name reads plainly '
    t'gets its own column',
    tags=['parametrization'],
)
def test_a_step_slot_disagreeing_with_the_name_gets_its_own_column() -> None:
    """The mirror of the scenario-name case: a `Template` slot in a *step* is a
    hover-substitution slot too, so a cell it cannot serve has to become a
    column of its own rather than leave the slot reading a value no case
    narrated.
    """
    with given('a step formatting the parameter and a name reading it plainly'):
        scenarios, info = _named_group(
            _price_name(''),
            [_placeholder_step('.2f')],
            [_placeholder_step('.2f')],
        )
    with when(t'the {pg["Case"]("cases")} are {pg["Group"]("grouped")}'):
        grouped = group_parametrized(scenarios, info)
    with then('the step points at a column holding what it renders'):
        table = grouped[0].parameters
        assert table is not None
        assert [(c.id, c.name) for c in table.columns] == [
            ('cup_size', 'cup_size'),
            ('derived:0', 'cup_size #2'),
        ]
        assert [c.values for c in table.cases] == [
            [200, '200.00'],
            [350, '350.00'],
        ]
    with then('the step renders the disambiguated token, text and parts agreeing'):
        slot = grouped[0].steps[0].narration.parts[1]
        assert isinstance(slot, NarrationPlaceholder)
        assert (slot.name, slot.column_id) == ('cup_size #2', 'derived:0')
        assert grouped[0].steps[0].narration.text == 'a cup of {cup_size #2} ml'


def test_a_step_slot_agreeing_with_its_cell_keeps_pointing_at_it() -> None:
    """The ordinary case: the column already carries the one formatting every
    slot agreed on, so no second column is made."""
    scenarios, info = _named_group(
        _price_name('.2f'), [_placeholder_step('.2f')], [_placeholder_step('.2f')]
    )
    grouped = group_parametrized(scenarios, info)[0]
    table = grouped.parameters
    assert table is not None
    assert [c.kind for c in table.columns] == ['param']
    assert [c.values for c in table.cases] == [['200.00'], ['350.00']]
    slot = grouped.steps[0].narration.parts[1]
    assert isinstance(slot, NarrationPlaceholder)
    assert slot.column_id == 'cup_size'


class _SpecRefusing:
    """A value that renders bare but rejects any format spec — `datetime`'s
    behavior for a nonsense spec, in miniature."""

    def __format__(self, spec: str) -> str:
        if spec:
            raise ValueError(f'unsupported format string: {spec}')
        return 'cup'

    def __str__(self) -> str:
        return 'cup'


def test_a_name_slot_a_value_cannot_render_keeps_the_shared_column() -> None:
    """A value whose own `__format__` refuses the spec never rendered that way
    in the name either, so there is no better column to point the slot at."""
    scenarios, info = _named_group(_price_name('.2f'), [], [])
    for spec in info.values():
        spec.values[0] = _SpecRefusing()
    grouped = group_parametrized(scenarios, info)
    table = grouped[0].parameters
    assert table is not None
    assert [c.id for c in table.columns] == ['cup_size']
    assert [c.values for c in table.cases] == [['cup'], ['cup']]
    slot = grouped[0].narration.parts[1]
    assert isinstance(slot, NarrationPlaceholder)
    assert slot.column_id == 'cup_size'


@scenario(
    t'A {pg["Step"].low} narrating a parameter its column no longer holds is refused',
    tags=['parametrization', 'validation'],
)
def test_a_rebound_parametrize_name_raises_rule_three() -> None:
    with given(t'two {pg["Case"]("cases")} narrating a value their column lacks'):
        scenarios, info = _two_case_group(
            [_param_value_step('400')], [_param_value_step('700')]
        )
    with (
        when_then(
            t'the {pg["Case"]("cases")} are {pg["Group"]("grouped")}',
            'the grouping is refused',
        ),
        pytest.raises(PytestGivenError) as excinfo,
    ):
        group_parametrized(scenarios, info)
    with then('the error names the column and what the case actually narrated'):
        message = str(excinfo.value)
        assert "'cup_size' in 'test_brew' matches a parametrize column" in message
        assert "case [200] narrates '400'" in message
        assert message.endswith('(t.py:12)')


def test_rule_three_offers_both_remedies_it_cannot_tell_apart() -> None:
    """A mismatch proves the cell and the step disagree, not *why*: a rebound
    local and a value mutated in place before narration both land here. The
    message must not assert one cause and send the reader looking for a local
    that does not exist."""
    scenarios, info = _two_case_group(
        [_param_value_step('400')], [_param_value_step('700')]
    )
    with pytest.raises(PytestGivenError) as excinfo:
        group_parametrized(scenarios, info)
    message = str(excinfo.value)
    assert 'rename the local' in message
    assert 'mutates the value in place' in message


def test_rule_three_fires_on_a_single_case_parametrize() -> None:
    """A per-case check, so one case is enough — no comparison rule can do this."""
    nid = NodeId('t.py::test_brew[200]')
    scenarios = [
        Scenario(
            id=nid,
            narration=Narration(text='brew'),
            module='m',
            status='passed',
            steps=[_param_value_step('400')],
            source=SourceLocation(relpath='tests/t.py', line=12),
        ),
    ]
    with pytest.raises(PytestGivenError, match='matches a parametrize column'):
        group_parametrized(
            scenarios, {nid: ParamSpec(names=['cup_size'], values=[200])}
        )


def test_a_faithful_interpolation_does_not_raise_rule_three() -> None:
    scenarios, info = _two_case_group(
        [_param_value_step('200')], [_param_value_step('350')]
    )
    assert group_parametrized(scenarios, info)[0].parameters is not None


def test_rule_three_reformats_the_raw_value_for_a_conversion_and_spec() -> None:
    """`t"{cup_size!r:>8}"` is faithful — comparing against the coerced cell
    would accuse it of rebinding."""
    scenarios, info = _two_case_group(
        [_param_value_step(format(repr(200), '>8'), spec='>8', conv='r')],
        [_param_value_step(format(repr(350), '>8'), spec='>8', conv='r')],
    )
    assert group_parametrized(scenarios, info)[0].parameters is not None


def test_rule_three_applies_the_conversion_before_comparing() -> None:
    """The int fixture above can't tell whether `!r` is actually applied —
    `repr(200) == str(200)`, so skipping the conversion entirely would still
    match. A `str` parameter is the smallest fixture where `repr` and `str`
    diverge: `repr('guest') == "'guest'"` but `str('guest') == 'guest'`."""
    nid1, nid2 = NodeId('t.py::test_greet[guest]'), NodeId('t.py::test_greet[host]')

    def step(value: str) -> Step:
        rendered = format(repr(value), '>8')
        return Step(
            phase='when',
            narration=Narration(
                text=f'the guest is {rendered}',
                parts=[
                    NarrationLiteral(value='the guest is '),
                    NarrationValue(
                        rendered=rendered,
                        expression='name',
                        format_spec='>8',
                        conversion='r',
                    ),
                ],
            ),
        )

    scenarios = [
        Scenario(
            id=nid1,
            narration=Narration(text='greet'),
            module='m',
            status='passed',
            steps=[step('guest')],
        ),
        Scenario(
            id=nid2,
            narration=Narration(text='greet'),
            module='m',
            status='passed',
            steps=[step('host')],
        ),
    ]
    info = {
        nid1: ParamSpec(names=['name'], values=['guest']),
        nid2: ParamSpec(names=['name'], values=['host']),
    }
    assert group_parametrized(scenarios, info)[0].parameters is not None


def test_rule_three_reformats_a_non_scalar_parameter() -> None:
    """`t"{when:%Y}"` on a datetime: formatting the *string* cell would raise
    ValueError, and `!r` would compare the string's repr."""
    when1, when2 = datetime(2026, 1, 1, tzinfo=UTC), datetime(2027, 1, 1, tzinfo=UTC)
    nid1, nid2 = NodeId('t.py::test_at[a]'), NodeId('t.py::test_at[b]')

    def step(value: datetime) -> Step:
        rendered = format(value, '%Y')
        return Step(
            phase='when',
            narration=Narration(
                text=f'it happens in {rendered}',
                parts=[
                    NarrationLiteral(value='it happens in '),
                    NarrationValue(
                        rendered=rendered, expression='when', format_spec='%Y'
                    ),
                ],
            ),
        )

    scenarios = [
        Scenario(
            id=nid1,
            narration=Narration(text='at'),
            module='m',
            status='passed',
            steps=[step(when1)],
        ),
        Scenario(
            id=nid2,
            narration=Narration(text='at'),
            module='m',
            status='passed',
            steps=[step(when2)],
        ),
    ]
    info = {
        nid1: ParamSpec(names=['when'], values=[when1]),
        nid2: ParamSpec(names=['when'], values=[when2]),
    }
    grouped = group_parametrized(scenarios, info)[0]
    assert grouped.parameters is not None
    assert [c.kind for c in grouped.parameters.columns] == ['param']


def test_rule_three_treats_an_unformattable_raw_value_as_a_rebinding() -> None:
    """`cup_size` rebound to a datetime, then `t"{cup_size:%H:%M}"`: re-applying
    that spec to the raw int raises, which is itself evidence of a rebinding."""
    nid = NodeId('t.py::test_brew[200]')
    scenarios = [
        Scenario(
            id=nid,
            narration=Narration(text='brew'),
            module='m',
            status='passed',
            steps=[_param_value_step('08:30', spec='%H:%M')],
            source=SourceLocation(relpath='tests/t.py', line=12),
        ),
    ]
    with pytest.raises(PytestGivenError, match='matches a parametrize column'):
        group_parametrized(
            scenarios, {nid: ParamSpec(names=['cup_size'], values=[200])}
        )


class _Unformattable:
    """A raw value whose type defines no `__format__` of its own — `format(x,
    spec)` falls back to `object.__format__`, which raises TypeError for any
    non-empty spec. `__str__` is defined so the value also has a stable
    display when it reaches a parameter cell via `_param_value`, rather than
    the default `<object object at 0x...>`."""

    def __str__(self) -> str:
        return 'unformattable'


def test_rule_three_treats_an_unformattable_type_as_a_rebinding() -> None:
    """Distinct arm from the ValueError case above: `cup_size` rebound to a
    plain object with no `__format__`, then narrated with a non-empty spec.
    `object.__format__` raises TypeError, not ValueError — reachable through
    exactly the rebinding rule 3 exists to catch."""
    nid = NodeId('t.py::test_brew[200]')
    scenarios = [
        Scenario(
            id=nid,
            narration=Narration(text='brew'),
            module='m',
            status='passed',
            steps=[_param_value_step('right', spec='>6')],
            source=SourceLocation(relpath='tests/t.py', line=12),
        ),
    ]
    with pytest.raises(PytestGivenError, match='matches a parametrize column'):
        group_parametrized(
            scenarios, {nid: ParamSpec(names=['cup_size'], values=[_Unformattable()])}
        )


class _Exploding:
    """A raw value whose own `__format__` raises something rule 3 cannot read
    as evidence — the shape a stateful parametrize object takes once the test
    body has emptied it."""

    def __format__(self, spec: str) -> str:
        raise IndexError('list index out of range')


def test_a_raw_value_whose_format_explodes_is_skipped_not_raised() -> None:
    """A `ValueError`/`TypeError` from re-formatting is evidence of a
    rebinding; anything else is a broken value, and rule 3 cannot tell. It has
    to skip: raising would abort every sink in the session over an object the
    author may not even narrate deliberately, and letting the exception through
    escapes `pytest_sessionfinish` as a bare traceback."""
    nid = NodeId('t.py::test_brew[200]')
    scenarios = [
        Scenario(
            id=nid,
            narration=Narration(text='brew'),
            module='m',
            status='passed',
            steps=[_param_value_step('200')],
            source=SourceLocation(relpath='tests/t.py', line=12),
        ),
    ]
    grouped = group_parametrized(
        scenarios, {nid: ParamSpec(names=['cup_size'], values=[_Exploding()])}
    )[0]
    assert grouped.parameters is not None


def test_rule_three_skips_a_failed_case() -> None:
    """A failed case's tree may be truncated mid-step; grouping trusts nothing
    else from it either."""
    nid1, nid2 = NodeId('t.py::test_brew[200]'), NodeId('t.py::test_brew[350]')
    scenarios = [
        Scenario(
            id=nid1,
            narration=Narration(text='brew'),
            module='m',
            status='passed',
            steps=[_param_value_step('200')],
        ),
        Scenario(
            id=nid2,
            narration=Narration(text='brew'),
            module='m',
            status='failed',
            steps=[_param_value_step('999')],
        ),
    ]
    info = {
        nid1: ParamSpec(names=['cup_size'], values=[200]),
        nid2: ParamSpec(names=['cup_size'], values=[350]),
    }
    assert group_parametrized(scenarios, info)[0].parameters is not None


def test_rule_three_checks_every_passed_case_not_just_the_first() -> None:
    """Case 1's t-string is faithful; only case 2 rebinds `cup_size`. Every
    other raise-test in this file violates on the anchor (case 1), so none of
    them pins that rule 3 keeps checking past it. This also pins that the
    message names the case that actually violated, not the anchor: it must
    read case 2's tail `[350]`, not case 1's `[200]`."""
    nid1, nid2 = NodeId('t.py::test_brew[200]'), NodeId('t.py::test_brew[350]')
    scenarios = [
        Scenario(
            id=nid1,
            narration=Narration(text='brew'),
            module='m',
            status='passed',
            steps=[_param_value_step('200')],
            source=SourceLocation(relpath='tests/t.py', line=12),
        ),
        Scenario(
            id=nid2,
            narration=Narration(text='brew'),
            module='m',
            status='passed',
            steps=[_param_value_step('999')],
            source=SourceLocation(relpath='tests/t.py', line=12),
        ),
    ]
    info = {
        nid1: ParamSpec(names=['cup_size'], values=[200]),
        nid2: ParamSpec(names=['cup_size'], values=[350]),
    }
    with pytest.raises(PytestGivenError) as excinfo:
        group_parametrized(scenarios, info)
    message = str(excinfo.value)
    assert "case [350] narrates '999'" in message
    assert 'case [200]' not in message


def test_a_single_case_group_cannot_raise_a_comparison_rule() -> None:
    nid = NodeId('t.py::test_brew[200]')
    scenarios = [
        Scenario(
            id=nid,
            narration=Narration(text='brew'),
            module='m',
            status='passed',
            steps=[Step(phase='when', narration=Narration(text='brews 200 ml'))],
        ),
    ]
    info = {nid: ParamSpec(names=['cup_size'], values=[200])}
    assert group_parametrized(scenarios, info)[0].steps[0].narration.text == (
        'brews 200 ml'
    )


def _term_ref_step(
    term_id: str, display: str, expression: str = "pg['Customer'](name)"
) -> Step:
    return Step(
        phase='given',
        narration=Narration(
            text=f'{display} places an order',
            parts=[
                NarrationTermRef(
                    term_id=TermId(term_id), display=display, expression=expression
                ),
                NarrationLiteral(value=' places an order'),
            ],
        ),
    )


@scenario(
    t'A {pg["Term ref"].low} whose display differs between {pg["Case"]("cases")} '
    t'is refused',
    tags=['parametrization', 'validation'],
)
def test_a_varying_term_ref_display_raises_rule_four() -> None:
    with given(t'two {pg["Case"]("cases")} whose {pg["Term ref"]} reads differently'):
        scenarios, info = _two_case_group(
            [_term_ref_step('customer', 'Alice')], [_term_ref_step('customer', 'Bob')]
        )
    with (
        when_then(
            t'the {pg["Case"]("cases")} are {pg["Group"]("grouped")}',
            'the grouping is refused',
        ),
        pytest.raises(PytestGivenError) as excinfo,
    ):
        group_parametrized(scenarios, info)
    with then(t'the error names the {pg["Term ref"]} and the split-it-out fix'):
        message = str(excinfo.value)
        assert (
            "glossary term ref {pg['Customer'](name)} in 'test_brew' varies" in message
        )
        assert 'Split the term ref from the value' in message
        assert message.endswith('(t.py:12)')


def test_a_varying_term_ref_term_id_raises_rule_four() -> None:
    scenarios, info = _two_case_group(
        [_term_ref_step('customer', 'Alice')], [_term_ref_step('guest', 'Alice')]
    )
    with pytest.raises(PytestGivenError, match='glossary term ref'):
        group_parametrized(scenarios, info)


def test_rule_four_names_the_violating_steps_own_phase() -> None:
    """The hint must name the author's keyword, not the spec example's."""
    scenarios, info = _two_case_group(
        [dataclasses.replace(_term_ref_step('customer', 'Alice'), phase='then')],
        [dataclasses.replace(_term_ref_step('customer', 'Bob'), phase='then')],
    )
    with pytest.raises(PytestGivenError) as excinfo:
        group_parametrized(scenarios, info)
    message = str(excinfo.value)
    assert 'then(t"{pg[\'Term\']} {value} …")' in message


def test_an_identical_term_ref_stays_inline() -> None:
    scenarios, info = _two_case_group(
        [_term_ref_step('customer', 'Alice')], [_term_ref_step('customer', 'Alice')]
    )
    grouped = group_parametrized(scenarios, info)[0]
    assert isinstance(grouped.steps[0].narration.parts[0], NarrationTermRef)
    assert grouped.parameters is not None
    assert [c.kind for c in grouped.parameters.columns] == ['param']


@scenario(
    t'A {pg["Term ref"].low} that *is* the parametrize value is refused too',
    tags=['parametrization', 'validation'],
)
def test_a_param_bound_term_ref_that_varies_raises_rule_four() -> None:
    """Rule 4 admits no exemption for a term ref a parametrize column binds.

    Letting its display vary bought a `param_column` on the pill and a per-case
    pass over the grouped tree in `compute_coverage`; `group_parametrized=False`
    gives each case its own term ref and covers the same ground with neither.
    """
    with given(
        t'two {pg["Case"]("cases")} whose {pg["Term ref"]} is the parameter itself'
    ):
        scenarios, info = _two_case_group(
            [_term_ref_step('guest', 'Alice', expression='cup_size')],
            [_term_ref_step('guest', 'Bob', expression='cup_size')],
        )
    with (
        when_then(
            t'the {pg["Case"]("cases")} are {pg["Group"]("grouped")}',
            'the grouping is refused',
        ),
        pytest.raises(PytestGivenError) as excinfo,
    ):
        group_parametrized(scenarios, info)
    with then(t'the error points at the per-case {pg["Scenario"].low} opt-out'):
        message = str(excinfo.value)
        assert 'must name the same term and read the same in every case' in message
        assert 'group_parametrized=False' in message


def test_a_differently_shaped_term_ref_refuses_the_merge_before_rule_four() -> None:
    """A case carrying no parts where the baseline carries a term ref is caught
    as a shape difference — rule 4 speaks only for a term ref that is still a
    term ref in
    every case."""
    scenarios, info = _two_case_group(
        [_term_ref_step('customer', 'Alice')],
        [Step(phase='given', narration=Narration(text='Bob places an order'))],
    )
    with pytest.raises(PytestGivenError, match='differently shaped'):
        group_parametrized(scenarios, info)


def test_a_same_length_term_ref_with_a_different_part_kind_refuses_the_merge() -> None:
    other_step = Step(
        phase='given',
        narration=Narration(
            text='Bob places an order',
            parts=[
                NarrationLiteral(value='Bob'),
                NarrationLiteral(value=' places an order'),
            ],
        ),
    )
    scenarios, info = _two_case_group(
        [_term_ref_step('customer', 'Alice')], [other_step]
    )
    with pytest.raises(PytestGivenError, match='differently shaped'):
        group_parametrized(scenarios, info)


def test_rule_four_checks_every_comparable_case_not_just_an_end_one() -> None:
    """Every other rule-4 fixture in this file is a two-case group with the
    varying case last, so nothing distinguishes "checks all cases" from
    "checks only the first" or "checks only the last". Case 1 and case 3
    share an identical term ref; only case 2's varies, so a raise can only
    come from actually checking the middle case."""
    nid1, nid2, nid3 = (
        NodeId('t.py::test_brew[a]'),
        NodeId('t.py::test_brew[b]'),
        NodeId('t.py::test_brew[c]'),
    )
    scenarios = [
        Scenario(
            id=nid1,
            narration=Narration(text='brew'),
            module='m',
            status='passed',
            steps=[_term_ref_step('customer', 'Alice')],
            source=SourceLocation(relpath='tests/t.py', line=12),
        ),
        Scenario(
            id=nid2,
            narration=Narration(text='brew'),
            module='m',
            status='passed',
            steps=[_term_ref_step('customer', 'Carol')],
            source=SourceLocation(relpath='tests/t.py', line=12),
        ),
        Scenario(
            id=nid3,
            narration=Narration(text='brew'),
            module='m',
            status='passed',
            steps=[_term_ref_step('customer', 'Alice')],
            source=SourceLocation(relpath='tests/t.py', line=12),
        ),
    ]
    info = {
        nid1: ParamSpec(names=['cup_size'], values=[200]),
        nid2: ParamSpec(names=['cup_size'], values=[350]),
        nid3: ParamSpec(names=['cup_size'], values=[500]),
    }
    with pytest.raises(PytestGivenError, match='glossary term ref'):
        group_parametrized(scenarios, info)


def test_a_varying_term_ref_in_a_nested_step_raises_rule_four() -> None:
    """`_term_at`'s comparison must read the case's step at the path it is
    actually walking, not always the first top-level step. The parent step's
    own term ref is identical across cases and, deliberately, shares the nested
    baseline term ref's identity too: a comparison that always read the parent
    (rather than the nested child it is meant to check) would find that
    coincidental match on every case and swallow the nested violation
    entirely, rather than raising for it."""

    def steps(child_display: str) -> list[Step]:
        return [
            Step(
                phase='given',
                narration=Narration(
                    text='an order for Coffee',
                    parts=[
                        NarrationTermRef(
                            term_id=TermId('item'),
                            display='Coffee',
                            expression="pg['Item'](item)",
                        ),
                        NarrationLiteral(value=' order'),
                    ],
                ),
                children=[
                    Step(
                        phase='given',
                        narration=Narration(
                            text=f'contains {child_display}',
                            parts=[
                                NarrationTermRef(
                                    term_id=TermId('item'),
                                    display=child_display,
                                    expression="pg['Item'](item)",
                                ),
                            ],
                        ),
                    )
                ],
            )
        ]

    scenarios, info = _two_case_group(steps('Coffee'), steps('Tea'))
    with pytest.raises(PytestGivenError, match='glossary term ref'):
        group_parametrized(scenarios, info)


def _att_step(*attachments: Attachment) -> Step:
    return Step(
        phase='given',
        narration=Narration(text='the machine is stocked'),
        attachments=list(attachments),
    )


@scenario(
    t'An {pg["Attachment"].low} whose payload varies becomes an '
    t'{pg["Attachment"].low} column',
    tags=['parametrization'],
)
def test_a_varying_attachment_becomes_a_column_and_leaves_a_content_less_badge() -> (
    None
):
    with given(t'two {pg["Case"]("cases")} attaching a label with differing payloads'):
        scenarios, info = _two_case_group(
            [_att_step(Attachment(label='brew log', content='log-for-vanilla'))],
            [_att_step(Attachment(label='brew log', content='log-for-mocha'))],
        )
    with when(t'{pg["Templatize"]("templatizing")} walks the {pg["Case"]("cases")}'):
        grouped = group_parametrized(scenarios, info)[0]
    with then(t'the payload moves into an {pg["Attachment"].low} column'):
        assert grouped.parameters is not None
        assert [(c.id, c.name, c.kind) for c in grouped.parameters.columns] == [
            ('cup_size', 'cup_size', 'param'),
            ('attachment:0', 'brew log', 'attachment'),
        ]
        assert [c.values[1] for c in grouped.parameters.cases] == [
            Attachment(label='brew log', content='log-for-vanilla'),
            Attachment(label='brew log', content='log-for-mocha'),
        ]
    with then(t'the {pg["Step"]} keeps a content-less badge pointing at it'):
        badge = grouped.steps[0].attachments[0]
        assert badge == AttachmentRef(
            label='brew log', content_type='text', column_id='attachment:0'
        )
        assert not hasattr(badge, 'content')


def test_a_byte_identical_attachment_stays_inline_and_makes_no_column() -> None:
    scenarios, info = _two_case_group(
        [_att_step(Attachment(label='brew log', content='same'))],
        [_att_step(Attachment(label='brew log', content='same'))],
    )
    grouped = group_parametrized(scenarios, info)[0]
    assert grouped.steps[0].attachments == [
        Attachment(label='brew log', content='same')
    ]
    assert grouped.parameters is not None
    assert [c.kind for c in grouped.parameters.columns] == ['param']


def test_a_varying_content_type_promotes_too() -> None:
    scenarios, info = _two_case_group(
        [_att_step(Attachment(label='state', content='{}', content_type='json'))],
        [_att_step(Attachment(label='state', content='{}', content_type='text'))],
    )
    grouped = group_parametrized(scenarios, info)[0]
    assert grouped.parameters is not None
    assert [c.kind for c in grouped.parameters.columns] == ['param', 'attachment']


@scenario(
    t'A {pg["Step"].low} whose set of {pg["Attachment"]("attachment")} labels '
    t'differs between {pg["Case"]("cases")} is refused',
    tags=['parametrization', 'validation'],
)
def test_a_label_present_in_one_case_only_raises_rule_five() -> None:
    with given(t'an {pg["Attachment"]} label only one {pg["Case"]} attaches'):
        scenarios, info = _two_case_group(
            [_att_step(Attachment(label='vanilla log', content='x'))],
            [_att_step()],
        )
    with (
        when_then(
            t'the {pg["Case"]("cases")} are {pg["Group"]("grouped")}',
            'the grouping is refused',
        ),
        pytest.raises(PytestGivenError) as excinfo,
    ):
        group_parametrized(scenarios, info)
    with then('the error names the label and asks for a constant one'):
        message = str(excinfo.value)
        assert (
            "attachment label 'vanilla log' in 'test_brew' is attached in some"
            in message
        )
        assert 'attach("<constant>", …).' in message  # pins correction 4
        assert message.endswith('(t.py:12)')


def test_rule_five_fires_when_the_extra_label_is_on_the_other_case() -> None:
    """The comparison is a symmetric difference, so it must catch a label the
    baseline lacks, not only one the baseline has."""
    scenarios, info = _two_case_group(
        [_att_step()],
        [_att_step(Attachment(label='mocha log', content='x'))],
    )
    with pytest.raises(PytestGivenError, match='attachment label'):
        group_parametrized(scenarios, info)


def test_rule_five_checks_every_comparable_case_not_just_an_end_one() -> None:
    """Both other rule-5 fixtures are two-case groups, where "checks all
    cases" and "checks only the last one" are indistinguishable. Cases 1 and 3
    share a label set and only case 2 carries the extra label, so a raise can
    only come from actually checking the middle case. Without it the run
    silently emits a column with a blank cell for the offending case."""
    scenarios, info = _three_case_group(
        [_att_step()],
        [_att_step(Attachment(label='log', content='x'))],
        [_att_step()],
    )
    with pytest.raises(PytestGivenError, match='attachment label'):
        group_parametrized(scenarios, info)


def test_reordered_attach_calls_pair_by_label_rather_than_raising() -> None:
    a, b = Attachment(label='a', content='A'), Attachment(label='b', content='B')
    scenarios, info = _two_case_group([_att_step(a, b)], [_att_step(b, a)])
    grouped = group_parametrized(scenarios, info)[0]
    assert grouped.steps[0].attachments == [a, b]
    assert grouped.parameters is not None
    assert [c.kind for c in grouped.parameters.columns] == ['param']


def test_the_same_label_attached_fewer_times_blanks_the_short_case() -> None:
    scenarios, info = _two_case_group(
        [
            _att_step(
                Attachment(label='log', content='1'),
                Attachment(label='log', content='2'),
            )
        ],
        [_att_step(Attachment(label='log', content='1'))],
    )
    grouped = group_parametrized(scenarios, info)[0]
    assert grouped.parameters is not None
    assert [c.id for c in grouped.parameters.columns] == ['cup_size', 'attachment:0']
    assert [c.values[1] for c in grouped.parameters.cases] == [
        Attachment(label='log', content='2'),
        None,
    ]
    assert grouped.steps[0].attachments == [
        Attachment(label='log', content='1'),
        AttachmentRef(label='log', content_type='text', column_id='attachment:0'),
    ]


def test_the_same_label_attached_more_times_by_a_non_baseline_case_adds_a_column() -> (
    None
):
    """I4/F1: a non-baseline case attaching a label *more* times than the
    baseline must not silently drop the extra payloads. Rule 5 only checks
    the label *set*, so this doesn't raise; occurrence 0 differs (baseline
    'X' vs the other case's 'Y'), which is what makes a real badge — pinning
    that the *extra* occurrence adds a column but no second badge."""
    scenarios, info = _two_case_group(
        [_att_step(Attachment(label='log', content='X'))],
        [
            _att_step(
                Attachment(label='log', content='Y'),
                Attachment(label='log', content='EXTRA-PAYLOAD'),
            )
        ],
    )
    grouped = group_parametrized(scenarios, info)[0]
    assert grouped.parameters is not None
    assert [c.id for c in grouped.parameters.columns] == [
        'cup_size',
        'attachment:0',
        'attachment:1',
    ]
    assert [c.values[1:] for c in grouped.parameters.cases] == [
        [Attachment(label='log', content='X'), None],
        [
            Attachment(label='log', content='Y'),
            Attachment(label='log', content='EXTRA-PAYLOAD'),
        ],
    ]
    assert grouped.steps[0].attachments == [
        AttachmentRef(label='log', content_type='text', column_id='attachment:0'),
    ]


def test_an_extra_occurrence_on_a_middle_case_is_carried_into_the_table() -> None:
    """`_promote_extra_occurrences` sweeps `ctx.comparable` twice — once for
    `max_count`, once to fill the cells — and the only other fixture for it is
    a two-case group with the extra occurrence on the *last* case, where
    "sweeps every case" and "sweeps the last one" are indistinguishable. Here
    only the middle case attaches `log` twice: reading just the end case would
    drop the column entirely (no error, payload silently lost) or emit it with
    every cell blank."""
    scenarios, info = _three_case_group(
        [_att_step(Attachment(label='log', content='c1'))],
        [
            _att_step(
                Attachment(label='log', content='c2'),
                Attachment(label='log', content='MIDDLE-EXTRA'),
            )
        ],
        [_att_step(Attachment(label='log', content='c3'))],
    )
    grouped = group_parametrized(scenarios, info)[0]
    assert grouped.parameters is not None
    assert [(c.id, c.name) for c in grouped.parameters.columns] == [
        ('cup_size', 'cup_size'),
        ('attachment:0', 'log'),
        ('attachment:1', 'log #2'),
    ]
    assert [c.values[1:] for c in grouped.parameters.cases] == [
        [Attachment(label='log', content='c1'), None],
        [
            Attachment(label='log', content='c2'),
            Attachment(label='log', content='MIDDLE-EXTRA'),
        ],
        [Attachment(label='log', content='c3'), None],
    ]


def test_the_extra_occurrence_trigger_fires_once_per_label() -> None:
    """The baseline attaches `log` twice and the other case three times — the
    only shape that separates "the extras trigger fires at the label's last
    baseline occurrence" from "it fires on every occurrence". Firing on every
    occurrence emits the third payload into two different columns and
    re-points the second badge at the wrong one."""
    scenarios, info = _two_case_group(
        [
            _att_step(
                Attachment(label='log', content='b1'),
                Attachment(label='log', content='b2'),
            )
        ],
        [
            _att_step(
                Attachment(label='log', content='o1'),
                Attachment(label='log', content='o2'),
                Attachment(label='log', content='o3'),
            )
        ],
    )
    grouped = group_parametrized(scenarios, info)[0]
    assert grouped.parameters is not None
    assert [(c.id, c.name) for c in grouped.parameters.columns] == [
        ('cup_size', 'cup_size'),
        ('attachment:0', 'log'),
        ('attachment:1', 'log #2'),
        ('attachment:2', 'log #3'),
    ]
    assert [c.values[1:] for c in grouped.parameters.cases] == [
        [
            Attachment(label='log', content='b1'),
            Attachment(label='log', content='b2'),
            None,
        ],
        [
            Attachment(label='log', content='o1'),
            Attachment(label='log', content='o2'),
            Attachment(label='log', content='o3'),
        ],
    ]
    assert grouped.steps[0].attachments == [
        AttachmentRef(label='log', content_type='text', column_id='attachment:0'),
        AttachmentRef(label='log #2', content_type='text', column_id='attachment:1'),
    ]


def test_an_extra_occurrence_beside_an_identical_one_makes_an_orphan_column() -> None:
    """Deliberate shape, pinned so it is not mistaken for a regression: when
    occurrence 0 is byte-identical across cases it stays inline and gets no
    badge, yet the extra occurrence still emits a column — a case-table column
    nothing in the grouped tree points at.

    Promoting occurrence 0 just to manufacture a badge was considered and
    rejected: the tree is not lying (every case does attach `log` with content
    `SAME`) and a synthesized badge would have to claim an attach order no case
    ever had. What is missing is only a pointer.
    """
    scenarios, info = _two_case_group(
        [_att_step(Attachment(label='log', content='SAME'))],
        [
            _att_step(
                Attachment(label='log', content='SAME'),
                Attachment(label='log', content='EXTRA'),
            )
        ],
    )
    grouped = group_parametrized(scenarios, info)[0]
    assert grouped.parameters is not None
    assert [(c.id, c.name) for c in grouped.parameters.columns] == [
        ('cup_size', 'cup_size'),
        ('attachment:0', 'log'),
    ]
    assert [c.values[1] for c in grouped.parameters.cases] == [
        None,
        Attachment(label='log', content='EXTRA'),
    ]
    # No badge anywhere: the inline attachment stands, so `attachment:0` is an
    # orphan column.
    assert grouped.steps[0].attachments == [Attachment(label='log', content='SAME')]


def test_an_extra_column_lands_after_its_own_labels_baseline_occurrences() -> None:
    """Interleaved labels: baseline `a b a`, the other case `a b a b a`. A
    label's extra columns go immediately after *that label's* last baseline
    occurrence, so `b`'s extra column sits between `a`'s two baseline columns
    rather than after them. That is what keeps badge order in the tree matching
    column order in the table — the only correlation a Markdown reader has,
    since a badge carries no column id."""
    scenarios, info = _two_case_group(
        [
            _att_step(
                Attachment(label='a', content='a1'),
                Attachment(label='b', content='b1'),
                Attachment(label='a', content='a2'),
            )
        ],
        [
            _att_step(
                Attachment(label='a', content='a1*'),
                Attachment(label='b', content='b1'),
                Attachment(label='a', content='a2*'),
                Attachment(label='b', content='b2*'),
                Attachment(label='a', content='a3*'),
            )
        ],
    )
    grouped = group_parametrized(scenarios, info)[0]
    assert grouped.parameters is not None
    assert [(c.id, c.name) for c in grouped.parameters.columns] == [
        ('cup_size', 'cup_size'),
        ('attachment:0', 'a'),
        ('attachment:1', 'b'),
        ('attachment:2', 'a #2'),
        ('attachment:3', 'a #3'),
    ]
    assert [c.values[1:] for c in grouped.parameters.cases] == [
        [
            Attachment(label='a', content='a1'),
            None,
            Attachment(label='a', content='a2'),
            None,
        ],
        [
            Attachment(label='a', content='a1*'),
            Attachment(label='b', content='b2*'),
            Attachment(label='a', content='a2*'),
            Attachment(label='a', content='a3*'),
        ],
    ]
    assert grouped.steps[0].attachments == [
        AttachmentRef(label='a', content_type='text', column_id='attachment:0'),
        Attachment(label='b', content='b1'),
        AttachmentRef(label='a #2', content_type='text', column_id='attachment:2'),
    ]


def test_attachment_column_ids_are_assigned_pre_order_across_nesting() -> None:
    """`_templatize_steps` builds a step's own attachments and its children's
    in one `replace` call; swapping the `attachments=` and
    `children=` keyword arguments would reorder evaluation (Python evaluates
    keyword arguments left to right) and hand the child's promotion
    `attachment:0` instead of the parent's. A promotion at both the parent and
    a nested child pins pre-order id assignment."""

    def steps(parent_content: str, child_content: str) -> list[Step]:
        return [
            Step(
                phase='given',
                narration=Narration(text='the machine is stocked'),
                attachments=[Attachment(label='parent log', content=parent_content)],
                children=[
                    Step(
                        phase='given',
                        narration=Narration(text='the tank is filled'),
                        attachments=[
                            Attachment(label='child log', content=child_content)
                        ],
                    ),
                ],
            ),
        ]

    scenarios, info = _two_case_group(steps('p1', 'c1'), steps('p2', 'c2'))
    grouped = group_parametrized(scenarios, info)[0]
    assert grouped.parameters is not None
    assert [(c.id, c.name) for c in grouped.parameters.columns] == [
        ('cup_size', 'cup_size'),
        ('attachment:0', 'parent log'),
        ('attachment:1', 'child log'),
    ]
    parent_badge = grouped.steps[0].attachments[0]
    child_badge = grouped.steps[0].children[0].attachments[0]
    assert isinstance(parent_badge, AttachmentRef)
    assert isinstance(child_badge, AttachmentRef)
    assert (parent_badge.column_id, child_badge.column_id) == (
        'attachment:0',
        'attachment:1',
    )
    # The child's promotion must read each case's step *at the nested path*.
    # Reading a fixed `(0,)` still emits the column — the parent's payload
    # carries no `child log`, which reads as "differs" — but every cell comes
    # out blank, leaving a badge that points at an empty column.
    assert [c.values[2] for c in grouped.parameters.cases] == [
        Attachment(label='child log', content='c1'),
        Attachment(label='child log', content='c2'),
    ]


def test_a_nested_steps_extra_occurrence_reads_the_walked_step() -> None:
    """`_promote_extra_occurrences` looks each case's step up by path twice —
    once to count the label, once to read the occurrence — and both must use
    the path being walked, not a fixed top-level one. The parent here attaches
    `plog` and never `clog`, so reading `(0,)` instead of the child's `(0, 0)`
    counts zero occurrences (the column vanishes, payload silently lost) or
    finds no attachment to put in the cell (the column comes out blank)."""

    def steps(*child_contents: str) -> list[Step]:
        return [
            Step(
                phase='given',
                narration=Narration(text='the machine is stocked'),
                attachments=[Attachment(label='plog', content='p')],
                children=[
                    Step(
                        phase='given',
                        narration=Narration(text='the tank is filled'),
                        attachments=[
                            Attachment(label='clog', content=content)
                            for content in child_contents
                        ],
                    ),
                ],
            ),
        ]

    scenarios, info = _two_case_group(steps('c1'), steps('c1', 'CHILD2'))
    grouped = group_parametrized(scenarios, info)[0]
    assert grouped.parameters is not None
    assert [(c.id, c.name) for c in grouped.parameters.columns] == [
        ('cup_size', 'cup_size'),
        ('attachment:0', 'clog'),
    ]
    assert [c.values[1] for c in grouped.parameters.cases] == [
        None,
        Attachment(label='clog', content='CHILD2'),
    ]
    # The parent's `plog` and the child's first `clog` are both identical
    # across cases, so neither promotes — `attachment:0` is the child's extra.
    assert grouped.steps[0].attachments == [Attachment(label='plog', content='p')]
    assert grouped.steps[0].children[0].attachments == [
        Attachment(label='clog', content='c1')
    ]


def test_two_occurrences_of_one_label_get_distinct_column_names() -> None:
    """A column id disambiguates two occurrences of a label in the JSON, but a
    reader of the rendered table sees only the name — and a Markdown badge
    carries no id at all. So the *name* has to be unique too: the first
    occurrence stays bare and later ones take a ` #N` suffix."""
    scenarios, info = _two_case_group(
        [
            _att_step(
                Attachment(label='log', content='1'),
                Attachment(label='log', content='2'),
            )
        ],
        [
            _att_step(
                Attachment(label='log', content='1*'),
                Attachment(label='log', content='2*'),
            )
        ],
    )
    grouped = group_parametrized(scenarios, info)[0]
    assert grouped.parameters is not None
    assert [(c.id, c.name) for c in grouped.parameters.columns] == [
        ('cup_size', 'cup_size'),
        ('attachment:0', 'log'),
        ('attachment:1', 'log #2'),
    ]


def test_the_step_tree_points_at_the_disambiguated_column_name() -> None:
    """The tree's pointers are the reader's only way back to a column: a
    `{name}` token for a derived column, a badge label for an attachment one.
    Both have to name the column they point at, so the second occurrence of a
    name reads ` #2` in the tree exactly as it does in the table header."""
    scenarios, info = _two_case_group(
        [_value_step('2.0'), _att_step(Attachment(label='price', content='1'))],
        [_value_step('3.5'), _att_step(Attachment(label='price', content='2'))],
    )
    grouped = group_parametrized(scenarios, info)[0]
    assert grouped.parameters is not None
    assert [c.name for c in grouped.parameters.columns] == [
        'cup_size',
        'price',
        'price #2',
    ]
    placeholder = grouped.steps[0].narration.parts[1]
    assert isinstance(placeholder, NarrationPlaceholder)
    assert placeholder.name == 'price'
    ref = grouped.steps[1].attachments[0]
    assert isinstance(ref, AttachmentRef)
    assert ref.label == 'price #2'


def test_a_second_derived_column_of_one_expression_reads_its_suffixed_name() -> None:
    """Two steps interpolating the same expression give two columns, and the
    second step's token has to say which one it means — `{price}` in both steps
    points the reader at the first column twice, and the HTML palette (keyed on
    the column name) hands the token a color belonging to the other column."""
    scenarios, info = _two_case_group(
        [_value_step('2.0'), _value_step('9.0')],
        [_value_step('3.5'), _value_step('9.9')],
    )
    grouped = group_parametrized(scenarios, info)[0]
    names: list[str] = []
    for step in grouped.steps:
        part = step.narration.parts[1]
        assert isinstance(part, NarrationPlaceholder)
        names.append(part.name)
    assert names == ['price', 'price #2']
    assert grouped.steps[1].narration.text == 'the drink costs {price #2} euros'


def test_a_generated_column_name_colliding_with_a_parametrize_name_is_suffixed() -> (
    None
):
    """Disambiguation spans *all* columns, so the name registry has to be
    seeded with the parametrize names — those columns are built inline rather
    than through `new_column`. Without the seeding this table would head two
    columns `cup_size`."""
    scenarios, info = _two_case_group(
        [_att_step(Attachment(label='cup_size', content='1'))],
        [_att_step(Attachment(label='cup_size', content='2'))],
    )
    grouped = group_parametrized(scenarios, info)[0]
    assert grouped.parameters is not None
    assert [(c.id, c.name, c.kind) for c in grouped.parameters.columns] == [
        ('cup_size', 'cup_size', 'param'),
        ('attachment:0', 'cup_size #2', 'attachment'),
    ]


def test_a_label_that_already_reads_as_a_suffixed_name_still_comes_out_distinct() -> (
    None
):
    """An attachment label is arbitrary text, so a suffix can collide with a
    *literal* label: `log`, `log #2`, `log` would hand the third column the
    name the second already has. Counting occurrences per label is not enough
    — the candidate has to be checked against the names already taken."""
    scenarios, info = _two_case_group(
        [
            _att_step(
                Attachment(label='log', content='1'),
                Attachment(label='log #2', content='2'),
                Attachment(label='log', content='3'),
            )
        ],
        [
            _att_step(
                Attachment(label='log', content='1*'),
                Attachment(label='log #2', content='2*'),
                Attachment(label='log', content='3*'),
            )
        ],
    )
    grouped = group_parametrized(scenarios, info)[0]
    assert grouped.parameters is not None
    names = [c.name for c in grouped.parameters.columns]
    assert names == ['cup_size', 'log', 'log #2', 'log #3']


def test_extra_occurrences_count_from_the_baseline_not_the_first_case() -> None:
    """The baseline is the first *passed* case, which is not the first case
    when that one was skipped. Counting a label's baseline occurrences off the
    first case instead would promote occurrences the baseline already carries a
    badge for — a second column holding the same payload."""
    scenarios, info = _three_case_group(
        [],
        [_att_step(Attachment(label='log', content='b1'))],
        [
            _att_step(
                Attachment(label='log', content='c1'),
                Attachment(label='log', content='c2'),
            )
        ],
    )
    scenarios[0].status = 'skipped'
    grouped = group_parametrized(scenarios, info)[0]
    assert grouped.parameters is not None
    assert [(c.id, c.name) for c in grouped.parameters.columns] == [
        ('cup_size', 'cup_size'),
        ('attachment:0', 'log'),
        ('attachment:1', 'log #2'),
    ]
    assert [c.values[1:] for c in grouped.parameters.cases] == [
        [None, None],
        [Attachment(label='log', content='b1'), None],
        [
            Attachment(label='log', content='c1'),
            Attachment(label='log', content='c2'),
        ],
    ]


# --- `param` cells carry the formatting their placeholders render with ---


@scenario(
    t'A {pg["Parameter table"].low} cell reads the way the {pg["Step"].low} '
    t'that points at it read',
    tags=['parametrization'],
    story=adopt_pytest_given,
)
def test_a_formatted_param_cell_holds_the_text_the_step_narrated() -> None:
    with given(t'two {pg["Case"]("cases")} narrating a parameter with a format spec'):
        scenarios, info = _two_case_group(
            [_param_value_step('200.00', spec='.2f')],
            [_param_value_step('350.00', spec='.2f')],
        )
    with when(t'{pg["Group"]("grouping")} builds the {pg["Parameter table"].low}'):
        [grouped] = group_parametrized(scenarios, info)
    with then('each cell carries the formatted text, under one column'):
        assert grouped.parameters is not None
        assert [c.name for c in grouped.parameters.columns] == ['cup_size']
        assert [case.values for case in grouped.parameters.cases] == [
            ['200.00'],
            ['350.00'],
        ]
    with then('the step keeps its placeholder, which that cell substitutes into'):
        assert grouped.steps[0].narration.text == 'the machine brews {cup_size} ml'


def test_a_param_conversion_reaches_the_cell_too() -> None:
    """`!r` is a formatting like any other: the cell has to carry it."""
    scenarios, info = _two_case_group(
        [_param_value_step('200', conv='r')], [_param_value_step('350', conv='r')]
    )
    [grouped] = group_parametrized(scenarios, info)
    assert grouped.parameters is not None
    assert [case.values for case in grouped.parameters.cases] == [['200'], ['350']]


def test_two_steps_formatting_one_param_differently_each_get_a_column() -> None:
    """No single cell can serve both slots, so the column keeps its plain value
    and each slot is promoted like any other varying value — the ` #2` suffix
    keeping each token pointed at the column that holds its own text."""
    scenarios, info = _two_case_group(
        [
            _param_value_step('200.00', spec='.2f'),
            _param_value_step('   200', spec='>6'),
        ],
        [
            _param_value_step('350.00', spec='.2f'),
            _param_value_step('   350', spec='>6'),
        ],
    )
    [grouped] = group_parametrized(scenarios, info)
    assert grouped.parameters is not None
    assert [(c.name, c.kind) for c in grouped.parameters.columns] == [
        ('cup_size', 'param'),
        ('cup_size #2', 'derived'),
        ('cup_size #3', 'derived'),
    ]
    assert [case.values for case in grouped.parameters.cases] == [
        [200, '200.00', '   200'],
        [350, '350.00', '   350'],
    ]
    assert grouped.steps[0].narration.text == 'the machine brews {cup_size #2} ml'
    assert grouped.steps[1].narration.text == 'the machine brews {cup_size #3} ml'


def test_a_param_read_plainly_in_one_step_and_formatted_in_another() -> None:
    """The trivial formatting counts as one of the two disagreeing ones: the
    plain slot keeps the column and the formatted slot takes its own."""
    scenarios, info = _two_case_group(
        [_param_value_step('200'), _param_value_step('200.00', spec='.2f')],
        [_param_value_step('350'), _param_value_step('350.00', spec='.2f')],
    )
    [grouped] = group_parametrized(scenarios, info)
    assert grouped.parameters is not None
    assert [(c.name, c.kind) for c in grouped.parameters.columns] == [
        ('cup_size', 'param'),
        ('cup_size #2', 'derived'),
    ]
    assert [case.values for case in grouped.parameters.cases] == [
        [200, '200.00'],
        [350, '350.00'],
    ]
    assert grouped.steps[0].narration.text == 'the machine brews {cup_size} ml'
    assert grouped.steps[1].narration.text == 'the machine brews {cup_size #2} ml'


def test_a_param_cell_falls_back_when_the_value_refuses_the_format() -> None:
    """A value whose own rendering raises could not have been narrated through
    that spec either, so there is nothing for the cell to agree with — the
    plain coercion is the honest fallback rather than an aborted session."""

    class _Awkward:
        def __format__(self, spec: str) -> str:
            if spec:
                raise ValueError('no')
            return 'awkward'

        def __str__(self) -> str:
            return 'awkward'

    value = _Awkward()
    assert columns.param_cell(value, (None, '.2f')) == 'awkward'
    assert columns.param_cell(value, None) == 'awkward'


def test_a_format_that_reads_like_the_plain_cell_adds_no_column() -> None:
    """Promotion keys on the rendered text, not on the presence of a spec:
    `{cup_size:d}` reads exactly as the plain cell does, so the slot keeps
    pointing at the column it already agrees with."""
    scenarios, info = _two_case_group(
        [_param_value_step('200'), _param_value_step('200', spec='d')],
        [_param_value_step('350'), _param_value_step('350', spec='d')],
    )
    [grouped] = group_parametrized(scenarios, info)
    assert grouped.parameters is not None
    assert [(c.name, c.kind) for c in grouped.parameters.columns] == [
        ('cup_size', 'param')
    ]
    assert [case.values for case in grouped.parameters.cases] == [[200], [350]]
    assert [s.narration.text for s in grouped.steps] == [
        'the machine brews {cup_size} ml',
        'the machine brews {cup_size} ml',
    ]


def _tstring_step(phase: str, literal: str, expression: str, rendered: str) -> Step:
    """A step narrated `phase(t"{expr}<literal>")`, as the recorder records it."""
    return Step(
        phase=phase,
        narration=Narration(
            text=f'{rendered}{literal}',
            parts=[
                NarrationValue(rendered=rendered, expression=expression),
                NarrationLiteral(value=literal),
            ],
        ),
    )


@scenario(
    t'{pg["Case"]("Cases")} that narrate different {pg["Step"]("steps")} are '
    t'refused rather than {pg["Group"]("grouped")}',
    tags=['parametrization', 'validation'],
    story=adopt_pytest_given,
)
def test_divergent_step_structure_refuses_the_merge() -> None:
    with given(t'two {pg["Case"]("cases")} whose {pg["Step"]("step")} trees differ'):
        scenarios, info = _two_case_group(
            [Step(phase='when', narration=Narration(text='it brews'))],
            [
                Step(phase='when', narration=Narration(text='it brews')),
                Step(phase='then', narration=Narration(text='it is hot')),
            ],
        )
    with (
        when_then(
            t'the {pg["Case"]("cases")} are {pg["Group"]("grouped")}',
            'the grouping is refused',
        ),
        pytest.raises(PytestGivenError) as excinfo,
    ):
        group_parametrized(scenarios, info)
    with then('the error names the divergence and the opt-out that answers it'):
        message = str(excinfo.value)
        assert 'different step structure' in message
        assert 'group_parametrized=False' in message


def test_differently_shaped_narration_refuses_the_merge() -> None:
    """`when(t"{n} items load" if n else "nothing loads")` leaves both cases
    structurally comparable while their part lists are laid out differently."""
    scenarios, info = _two_case_group(
        [_tstring_step('when', ' items load', 'n', '3')],
        [Step(phase='when', narration=Narration(text='nothing loads'))],
    )
    with pytest.raises(PytestGivenError, match='differently shaped'):
        group_parametrized(scenarios, info)


def test_narration_differing_only_in_wording_refuses_the_merge() -> None:
    scenarios, info = _two_case_group(
        [_tstring_step('when', ' items load', 'n', '3')],
        [_tstring_step('when', ' things break', 'n', '4')],
    )
    with pytest.raises(PytestGivenError, match='different wording') as excinfo:
        group_parametrized(scenarios, info)
    message = str(excinfo.value)
    assert "' items load'" in message
    # The message names both sides of the comparison, not just the offender.
    assert 'case [350] of ' in message
    assert 'than case [200]' in message


def test_narration_interpolating_a_different_expression_refuses_the_merge() -> None:
    scenarios, info = _two_case_group(
        [_tstring_step('when', ' items load', 'n', '3')],
        [_tstring_step('when', ' items load', 'total', '4')],
    )
    with pytest.raises(PytestGivenError, match='different expression') as excinfo:
        group_parametrized(scenarios, info)
    assert "'total'" in str(excinfo.value)


def test_cases_differing_only_in_rendered_values_still_merge() -> None:
    scenarios, info = _two_case_group(
        [_tstring_step('when', ' ml is brewed', 'cup_size', '200')],
        [_tstring_step('when', ' ml is brewed', 'cup_size', '350')],
    )
    grouped = group_parametrized(scenarios, info)
    assert grouped[0].steps[0].narration.text == '{cup_size} ml is brewed'


def test_a_single_passed_case_has_nothing_to_compare() -> None:
    """A failed case may abort mid-tree, so it is never held to the baseline's
    shape."""
    scenarios, info = _two_case_group(
        [Step(phase='when', narration=Narration(text='it brews'))],
        [Step(phase='when', narration=Narration(text='it brews'))],
    )
    scenarios[1] = dataclasses.replace(scenarios[1], status='failed', steps=[])
    assert len(group_parametrized(scenarios, info)) == 1


def test_a_varying_str_narration_keeps_rule_ones_diagnosis() -> None:
    """Rule 6 stays silent on a `str` narration — both cases contribute no
    parts — so rule 1 still explains the f-string trap."""
    scenarios, info = _two_case_group(
        [Step(phase='when', narration=Narration(text='the machine brews 200 ml'))],
        [Step(phase='when', narration=Narration(text='the machine brews 350 ml'))],
    )
    with pytest.raises(PytestGivenError, match='records no parts'):
        group_parametrized(scenarios, info)


def _term_group(
    steps1: list[Step], steps2: list[Step]
) -> tuple[list[Scenario], ParamInfo]:
    """`_two_case_group` over a glossary term instance rather than an int."""
    glossary = Glossary()
    guest = glossary.actor('Guest')
    scenarios, info = _two_case_group(steps1, steps2)
    return scenarios, {
        nid: ParamSpec(names=['who'], values=[guest(display)])
        for nid, display in zip(info, ('Alice', 'Bob'), strict=True)
    }


def _who_slot(text_before: str) -> list[NarrationPart]:
    return [
        NarrationLiteral(value=text_before),
        NarrationPlaceholder(name='who', column_id='who'),
        NarrationLiteral(value=' arrives'),
    ]


def _who_step() -> Step:
    parts = _who_slot('the ')
    return Step(
        phase='given', narration=Narration(text=narration_text(parts), parts=parts)
    )


def _who_name() -> Narration:
    parts = _who_slot('')
    return Narration(text=narration_text(parts), parts=parts)


@scenario(
    t'A {pg["Step"].low} narrating a glossary term parameter keeps pointing at '
    t'its {pg["Parameter table"].low} column',
    tags=['parametrization'],
)
def test_a_step_slot_over_a_term_instance_keeps_pointing_at_its_cell() -> None:
    """The cell unwraps a term instance to its display, so what the slot
    renders has to be built the same way. Compared against a bare
    `format(value, '')` — the whole `Glossary` dataclass repr — it never
    matches, and that repr lands in a `derived` column the report then shows.
    """
    with given('a step narrating a parameter bound to a glossary term instance'):
        scenarios, info = _term_group([_who_step()], [_who_step()])
    with when(t'the {pg["Case"]("cases")} are {pg["Group"]("grouped")}'):
        grouped = group_parametrized(scenarios, info)[0]
    with then(t'the {pg["Parameter table"].low} holds the term displays alone'):
        table = grouped.parameters
        assert table is not None
        assert [(c.id, c.kind) for c in table.columns] == [('who', 'param')]
        assert [c.values for c in table.cases] == [['Alice'], ['Bob']]
    with then('the step still points at that column'):
        slot = grouped.steps[0].narration.parts[1]
        assert isinstance(slot, NarrationPlaceholder)
        assert slot.column_id == 'who'


def test_a_scenario_name_slot_over_a_term_instance_keeps_pointing_at_its_cell() -> None:
    """The name half of the same rule."""
    scenarios, info = _term_group([], [])
    for case in scenarios:
        case.narration = _who_name()
    grouped = group_parametrized(scenarios, info)[0]
    table = grouped.parameters
    assert table is not None
    assert [(c.id, c.kind) for c in table.columns] == [('who', 'param')]
    slot = grouped.narration.parts[1]
    assert isinstance(slot, NarrationPlaceholder)
    assert slot.column_id == 'who'


def test_a_formatted_step_slot_over_a_term_instance_falls_back_to_the_display() -> None:
    """A slot carrying a format spec does not unwrap the term itself — but the
    term instance refuses the spec, so cell and slot both fall back to the
    plain coercion, agree, and the slot keeps the shared column."""
    parts: list[NarrationPart] = [
        NarrationLiteral(value='the '),
        NarrationPlaceholder(name='who', column_id='who', format_spec='>8'),
        NarrationLiteral(value=' arrives'),
    ]
    step = Step(
        phase='given', narration=Narration(text=narration_text(parts), parts=parts)
    )
    scenarios, info = _term_group([step], [dataclasses.replace(step)])
    grouped = group_parametrized(scenarios, info)[0]
    table = grouped.parameters
    assert table is not None
    assert [(c.id, c.kind) for c in table.columns] == [('who', 'param')]
    assert [c.values for c in table.cases] == [['Alice'], ['Bob']]
    slot = grouped.steps[0].narration.parts[1]
    assert isinstance(slot, NarrationPlaceholder)
    assert slot.column_id == 'who'
