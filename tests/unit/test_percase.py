"""Unit tests for the per-case path: a scenario that declines the merge."""

import pytest

from pytest_given import Template, given, scenario, then, when
from pytest_given.capture import narration_from
from pytest_given.grouping import group_parametrized
from pytest_given.model import (
    Narration,
    NarrationLiteral,
    NarrationPlaceholder,
    NarrationTermRef,
    NodeId,
    ParamInfo,
    ParamSpec,
    PytestGivenError,
    Scenario,
    Step,
    TermId,
    narration_text,
)
from tests.ubiquitous_language import adopt_pytest_given, pg


def _opted_out_group(
    name: str | Template | Narration,
    *,
    values: tuple[object, ...] = (200, 300),
    names: tuple[str, ...] = ('cup_size',),
    steps: list[Step] | None = None,
    statuses: tuple[str, ...] = ('passed', 'passed'),
) -> tuple[list[Scenario], ParamInfo]:
    """A group of cases whose scenario declined the merge.

    One entry of `values` per case — a tuple where `names` has more than one
    column, matching the node id pytest would build from it. `name` goes
    through `narration_from`, so the parts under test are the ones `@scenario`
    actually records rather than a hand-built stand-in.
    """
    cases = [v if isinstance(v, tuple) else (v,) for v in values]
    ids = [NodeId('t::x[{}]'.format('-'.join(str(v) for v in case))) for case in cases]
    scenarios = [
        Scenario(
            id=node_id,
            narration=narration_from(name),
            module='m',
            status=status,
            steps=steps or [],
        )
        for node_id, status in zip(ids, statuses, strict=True)
    ]
    param_info = {
        node_id: ParamSpec(names=list(names), values=list(case), group=False)
        for node_id, case in zip(ids, cases, strict=True)
    }
    return scenarios, param_info


@scenario(
    t'A {pg["Parametrized scenario"].low} can decline the '
    t'{pg["Group"]("grouping")} and keep one {pg["Scenario"].low} per '
    t'{pg["Case"].low}',
    tags=['parametrization'],
    story=adopt_pytest_given,
)
def test_opted_out_group_emits_one_scenario_per_case() -> None:
    with given(t'two {pg["Case"]("cases")} of a scenario that opted out'):
        scenarios, param_info = _opted_out_group('Brew coffee')
    with when(t'the {pg["Group"]("grouping")} pass runs', activity=9):
        result = group_parametrized(scenarios, param_info)
    with then(
        t'each {pg["Case"].low} stands alone, with no {pg["Parameter table"].low}'
    ):
        assert [s.id for s in result] == [s.id for s in scenarios]
        assert all(s.parameters is None for s in result)


def test_str_name_takes_the_parametrize_id() -> None:
    scenarios, param_info = _opted_out_group('Brew coffee')

    result = group_parametrized(scenarios, param_info)

    assert [s.narration.text for s in result] == [
        'Brew coffee [200]',
        'Brew coffee [300]',
    ]


def test_template_name_substitutes_this_case_values() -> None:
    scenarios, param_info = _opted_out_group(Template('Brew {cup_size} ml'))

    result = group_parametrized(scenarios, param_info)

    assert [s.narration.text for s in result] == [
        'Brew 200 ml [200]',
        'Brew 300 ml [300]',
    ]
    assert not any(
        isinstance(part, NarrationPlaceholder)
        for s in result
        for part in s.narration.parts
    )


def test_step_placeholders_substitute_this_case_values() -> None:
    """An `Annotated[..., given(Template(...))]` label reaches grouping
    unresolved; with no case table to fill it, this path renders it."""
    label = narration_from(Template('a {cup_size} ml cup'))
    scenarios, param_info = _opted_out_group(
        'Brew coffee',
        steps=[
            Step(
                phase='given',
                narration=label,
                children=[Step(phase='when', narration=label)],
            )
        ],
    )

    result = group_parametrized(scenarios, param_info)

    assert result[0].steps[0].narration.text == 'a 200 ml cup'
    assert result[0].steps[0].children[0].narration.text == 'a 200 ml cup'
    assert result[1].steps[0].narration.text == 'a 300 ml cup'


def test_every_title_carries_its_parametrize_id() -> None:
    """A Template naming only some columns renders the same text for cases that
    differ only in the rest; the id is what tells them apart, so every case
    carries it rather than only the ones that would collide."""
    scenarios, param_info = _opted_out_group(
        Template('Brew {cup_size} ml'),
        names=('cup_size', 'milk'),
        values=((200, 'oat'), (200, 'soy')),
    )

    result = group_parametrized(scenarios, param_info)

    assert [s.narration.text for s in result] == [
        'Brew 200 ml [200-oat]',
        'Brew 200 ml [200-soy]',
    ]


def test_suffixed_glossary_name_keeps_its_term_ref_and_carries_the_suffix() -> None:
    """The suffix lands in the parts too, so the term ref survives and the
    text still reads as what the parts render."""
    name = Narration(
        text='Barista brews',
        parts=[
            NarrationTermRef(
                term_id=TermId('barista'), display='Barista', expression='pg["Barista"]'
            ),
            NarrationLiteral(value=' brews'),
        ],
    )
    scenarios, param_info = _opted_out_group(name, values=(200,), statuses=('passed',))

    narration = group_parametrized(scenarios, param_info)[0].narration

    assert narration.text == 'Barista brews [200]'
    assert isinstance(narration.parts[0], NarrationTermRef)
    assert narration_text(narration.parts) == narration.text


def test_substitution_applies_format_spec_and_conversion() -> None:
    """Regression cover: a placeholder renders the way the same interpolation
    would in a t-string."""
    scenarios, param_info = _opted_out_group(
        Template('Brew {cup_size:03d} ml'), values=(7,), statuses=('passed',)
    )

    result = group_parametrized(scenarios, param_info)

    assert result[0].narration.text == 'Brew 007 ml [7]'


def test_failed_and_skipped_cases_are_emitted_with_their_own_outcome() -> None:
    """Regression cover: where the grouped view showed a table row, the report
    now shows one scenario per outcome."""
    scenarios, param_info = _opted_out_group(
        'Brew coffee', statuses=('failed', 'skipped')
    )

    result = group_parametrized(scenarios, param_info)

    assert [s.status for s in result] == ['failed', 'skipped']


def test_a_placeholder_naming_no_parameter_raises() -> None:
    """The safety net the grouped path has too: a placeholder that matches no
    parametrize column is a typo, not a value."""
    scenarios, param_info = _opted_out_group(
        Template('Brew {cup_zize} ml'), values=(200,), statuses=('passed',)
    )

    with pytest.raises(PytestGivenError, match='cup_zize'):
        group_parametrized(scenarios, param_info)
