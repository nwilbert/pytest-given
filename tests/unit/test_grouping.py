"""Unit tests for the case-grouping pass."""

import dataclasses
from datetime import UTC, datetime

import pytest

from pytest_given import given, grouping, scenario, then, when
from pytest_given.grouping import group_parametrized
from pytest_given.model import (
    Glossary,
    Narration,
    NarrationLiteral,
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
        grouping._templatize_narration(narration, ['cup_size'])


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


def test_templatize_sets_param_column_when_term_ref_expression_matches() -> None:
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
    out = grouping._templatize_narration(narration, param_names=['guest'])
    ref = next(p for p in out.parts if isinstance(p, NarrationTermRef))
    assert ref.param_column == 'guest'
    assert ref.display == 'Alice'


def test_templatize_term_ref_param_column_stays_none_when_no_column_match() -> None:
    narration = Narration(
        text='Alice arrives',
        parts=[
            NarrationTermRef(
                term_id=TermId('guest'),
                display='Alice',
                expression='guest',
            ),
        ],
    )
    out = grouping._templatize_narration(narration, param_names=['euros'])
    ref = next(p for p in out.parts if isinstance(p, NarrationTermRef))
    assert ref.param_column is None


def test_baseline_is_the_first_passed_case_not_the_first_case() -> None:
    """A skipped first case records no steps; the grouped tree must come from a
    case that actually ran."""
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
    grouped = group_parametrized(scenarios, param_info)
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


def test_comparable_excludes_a_structurally_divergent_case() -> None:
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
        status='passed',
        steps=[Step(phase='when', narration=Narration(text='a'))],
    )
    assert grouping._comparable([base, other], base) == [base]


def test_comparable_excludes_a_non_passed_case() -> None:
    """A failed case with the exact same step structure as the baseline must
    still drop out — only its status disqualifies it, isolating that
    condition from the structure-signature check above."""
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
    assert grouping._comparable([base, other], base) == [base]


def test_test_name_drops_the_path_and_the_case_suffix() -> None:
    assert (
        grouping._test_name(
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


def test_a_varying_str_narration_raises_rule_one() -> None:
    scenarios, info = _two_case_group(
        [Step(phase='when', narration=Narration(text='the machine brews 200 ml'))],
        [Step(phase='when', narration=Narration(text='the machine brews 350 ml'))],
    )
    with pytest.raises(PytestGivenError) as excinfo:
        group_parametrized(scenarios, info)
    message = str(excinfo.value)
    assert "step narration in 'test_brew' varies across parametrize cases" in message
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


def test_a_structurally_divergent_case_raises_nothing() -> None:
    """A shifted tree lining a `when` up against a `given` gets blank cells and
    the existing lint finding, not rule 1."""
    scenarios, info = _two_case_group(
        [Step(phase='when', narration=Narration(text='brews 200 ml'))],
        [
            Step(phase='given', narration=Narration(text='a machine')),
            Step(phase='when', narration=Narration(text='brews 350 ml')),
        ],
    )
    assert group_parametrized(scenarios, info)[0].steps[0].narration.text == (
        'brews 200 ml'
    )


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


def test_a_varying_bare_name_interpolation_becomes_a_derived_column() -> None:
    scenarios, info = _two_case_group(
        [_value_step('2.0', format_spec='.2f', conversion='r')],
        [_value_step('3.5', format_spec='.2f', conversion='r')],
    )
    grouped = group_parametrized(scenarios, info)[0]
    assert [(c.id, c.name, c.kind) for c in grouped.parameters.columns] == [
        ('cup_size', 'cup_size', 'param'),
        ('derived:0', 'price', 'derived'),
    ]
    assert [case.values for case in grouped.parameters.cases] == [
        [200, '2.0'],
        [350, '3.5'],
    ]
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


def test_a_varying_compound_interpolation_raises_rule_two() -> None:
    scenarios, info = _two_case_group(
        [_value_step('2.0', expression='cup_size * 0.01')],
        [_value_step('3.5', expression='cup_size * 0.01')],
    )
    with pytest.raises(PytestGivenError) as excinfo:
        group_parametrized(scenarios, info)
    message = str(excinfo.value)
    assert "'cup_size * 0.01' in 'test_brew' varies across parametrize cases" in message
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
    assert [c.name for c in grouped.parameters.columns] == [
        'cup_size',
        'price',
        'price',
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


def test_a_differently_shaped_comparable_case_reads_as_differing() -> None:
    """`_value_at`'s bounds check: a comparable case shares the baseline's
    `structure_signature` (phase + nesting only) but can still carry a
    differently shaped `parts` list at the same path — a known limitation,
    deferred with divergent structure itself. It reads as "differs", so the
    value still gets promoted rather than compared past the end of the list."""
    baseline_step = _value_step('2.0')
    other_step = Step(
        phase='then',
        narration=Narration(
            text='the drink costs 3.5 euros',
            parts=[NarrationLiteral(value='the drink costs 3.5 euros')],
        ),
    )
    scenarios, info = _two_case_group([baseline_step], [other_step])
    grouped = group_parametrized(scenarios, info)[0]
    assert [c.kind for c in grouped.parameters.columns] == ['param', 'derived']
    assert [case.values for case in grouped.parameters.cases] == [
        [200, '2.0'],
        [350, None],
    ]


def test_a_same_length_case_with_a_different_part_kind_reads_as_differing() -> None:
    """`_value_at`'s isinstance guard: a comparable case can share the
    baseline's `structure_signature` *and* have an equal-length `parts` list
    at the promoted path, yet carry a different part kind there — e.g. a
    NarrationLiteral where the baseline has a NarrationValue. The bounds
    check above does not catch this (the index is in range); only the
    isinstance check does. It must read as "differs" (None), not assert the
    kind away."""
    baseline_step = _value_step('2.0')
    other_step = Step(
        phase='then',
        narration=Narration(
            text='x 2.0 euros',
            parts=[
                NarrationLiteral(value='the drink costs '),
                NarrationLiteral(value='2.0'),
                NarrationLiteral(value=' euros'),
            ],
        ),
    )
    scenarios, info = _two_case_group([baseline_step], [other_step])
    grouped = group_parametrized(scenarios, info)[0]
    assert [c.kind for c in grouped.parameters.columns] == ['param', 'derived']
    assert [case.values for case in grouped.parameters.cases] == [
        [200, '2.0'],
        [350, None],
    ]


def test_a_grouped_steps_text_rebuild_covers_every_part_kind() -> None:
    """A step mixing all four part kinds, where only one interpolation
    promotes: the rebuilt text must still carry the constant NarrationValue's
    rendered text and both NarrationTermRefs' displays verbatim. The first
    term ref's expression matches `cup_size` (the group's own param name) and
    gets `param_column` set; the second's doesn't match anything and passes
    through untouched — a glossary term unrelated to the parametrize column,
    the common case."""

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
    matched_ref = step_out.narration.parts[3]
    assert isinstance(matched_ref, NarrationTermRef)
    assert matched_ref.param_column == 'cup_size'
    unmatched_ref = step_out.narration.parts[7]
    assert isinstance(unmatched_ref, NarrationTermRef)
    assert unmatched_ref.param_column is None


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
    out = grouping._templatize_narration(narration, param_names=['cup_size'])
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


def test_a_rebound_parametrize_name_raises_rule_three() -> None:
    scenarios, info = _two_case_group(
        [_param_value_step('400')], [_param_value_step('700')]
    )
    with pytest.raises(PytestGivenError) as excinfo:
        group_parametrized(scenarios, info)
    message = str(excinfo.value)
    assert "'cup_size' in 'test_brew' matches a parametrize column" in message
    assert "case [200] narrates '400'" in message
    assert message.endswith('(t.py:12)')


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


def _pill_step(
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


def test_a_varying_pill_display_raises_rule_four() -> None:
    scenarios, info = _two_case_group(
        [_pill_step('customer', 'Alice')], [_pill_step('customer', 'Bob')]
    )
    with pytest.raises(PytestGivenError) as excinfo:
        group_parametrized(scenarios, info)
    message = str(excinfo.value)
    assert "glossary term ref {pg['Customer'](name)} in 'test_brew' varies" in message
    assert 'Split the pill from the value' in message
    assert message.endswith('(t.py:12)')


def test_a_varying_pill_term_id_raises_rule_four() -> None:
    scenarios, info = _two_case_group(
        [_pill_step('customer', 'Alice')], [_pill_step('guest', 'Alice')]
    )
    with pytest.raises(PytestGivenError, match='glossary term ref'):
        group_parametrized(scenarios, info)


def test_rule_four_names_the_violating_steps_own_phase() -> None:
    """The hint must name the author's keyword, not the spec example's."""
    scenarios, info = _two_case_group(
        [dataclasses.replace(_pill_step('customer', 'Alice'), phase='then')],
        [dataclasses.replace(_pill_step('customer', 'Bob'), phase='then')],
    )
    with pytest.raises(PytestGivenError) as excinfo:
        group_parametrized(scenarios, info)
    message = str(excinfo.value)
    assert 'then(t"{pg[\'Term\']} {value} …").' in message


def test_an_identical_pill_stays_inline() -> None:
    scenarios, info = _two_case_group(
        [_pill_step('customer', 'Alice')], [_pill_step('customer', 'Alice')]
    )
    grouped = group_parametrized(scenarios, info)[0]
    assert isinstance(grouped.steps[0].narration.parts[0], NarrationTermRef)
    assert grouped.parameters is not None
    assert [c.kind for c in grouped.parameters.columns] == ['param']


def test_a_pill_bound_to_a_parametrize_column_does_not_raise() -> None:
    """The exemption: its display varies by construction, and the `param`
    column already holds every case's value. This is what keeps
    `param_column` alive."""
    scenarios, info = _two_case_group(
        [_pill_step('guest', 'Alice', expression='cup_size')],
        [_pill_step('guest', 'Bob', expression='cup_size')],
    )
    grouped = group_parametrized(scenarios, info)[0]
    part = grouped.steps[0].narration.parts[0]
    assert isinstance(part, NarrationTermRef)
    assert part.param_column == 'cup_size'
    assert grouped.parameters is not None
    assert [c.kind for c in grouped.parameters.columns] == ['param']


def test_a_differently_shaped_comparable_pill_reads_as_differing() -> None:
    """`_term_at`'s bounds check: a comparable case shares the baseline's
    `structure_signature` (phase + nesting only) but can carry a shorter
    `parts` list at the same path — the compared index is out of range. It
    reads as "differs" (None != identity), so rule 4 raises rather than
    indexing past the end of the list."""
    baseline_step = _pill_step('customer', 'Alice')
    other_step = Step(
        phase='given',
        narration=Narration(text='Bob places an order', parts=[]),
    )
    scenarios, info = _two_case_group([baseline_step], [other_step])
    with pytest.raises(PytestGivenError, match='glossary term ref'):
        group_parametrized(scenarios, info)


def test_a_same_length_pill_with_a_different_part_kind_reads_as_differing() -> None:
    """`_term_at`'s isinstance guard: a comparable case can share the
    baseline's `structure_signature` *and* have an equal-length `parts` list
    at the compared path, yet carry a different part kind there — e.g. a
    NarrationLiteral where the baseline has a NarrationTermRef. The bounds
    check above does not catch this (the index is in range); only the
    isinstance check does. It must read as "differs" (None), not assert the
    kind away — this is the exact shape that survived Task 8's equivalent
    check in `_value_at` while line coverage called it covered."""
    baseline_step = _pill_step('customer', 'Alice')
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
    scenarios, info = _two_case_group([baseline_step], [other_step])
    with pytest.raises(PytestGivenError, match='glossary term ref'):
        group_parametrized(scenarios, info)


def test_rule_four_checks_every_comparable_case_not_just_an_end_one() -> None:
    """Every other rule-4 fixture in this file is a two-case group with the
    varying case last, so nothing distinguishes "checks all cases" from
    "checks only the first" or "checks only the last". Case 1 and case 3
    share an identical pill; only case 2's pill varies, so a raise can only
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
            steps=[_pill_step('customer', 'Alice')],
            source=SourceLocation(relpath='tests/t.py', line=12),
        ),
        Scenario(
            id=nid2,
            narration=Narration(text='brew'),
            module='m',
            status='passed',
            steps=[_pill_step('customer', 'Carol')],
            source=SourceLocation(relpath='tests/t.py', line=12),
        ),
        Scenario(
            id=nid3,
            narration=Narration(text='brew'),
            module='m',
            status='passed',
            steps=[_pill_step('customer', 'Alice')],
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


def test_a_varying_pill_in_a_nested_step_raises_rule_four() -> None:
    """`_term_at`'s comparison must read the case's step at the path it is
    actually walking, not always the first top-level step. The parent step's
    own pill is identical across cases and, deliberately, shares the nested
    baseline pill's identity too: a comparison that always read the parent
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
