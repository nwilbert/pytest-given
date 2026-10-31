"""Aligning two step trees into equal, modified, added and removed steps."""

from pytest_given import given, scenario, then, when
from pytest_given.delta.narration import Reading, similarity
from pytest_given.delta.steps import MODIFIED_SIMILARITY, align_steps, steps_changed
from pytest_given.model import (
    Attachment,
    AttachmentLabel,
    Glossary,
    Step,
    StepChange,
    StepDelta,
    TermId,
)
from tests.ubiquitous_language import pg
from tests.unit.delta.builders import step

_READING = Reading(
    glossary=Glossary(terms=[]),
    term_id=lambda term_id: TermId(term_id),
    column=lambda part: part.column_id,
)


def _changes(deltas: tuple[StepDelta, ...]) -> list[StepChange]:
    return [delta.change for delta in deltas]


def _align(before: list[Step], after: list[Step]) -> tuple[StepDelta, ...]:
    return align_steps(before, _READING, after, _READING)


@scenario(
    t'A reworded {pg["Step"].l} reads as modified, an unrelated one as '
    t'removed and added',
    tags=['delta'],
)
def test_a_reworded_step_reads_as_modified() -> None:
    with given(t'a before and an after {pg["Step"].l} list of one booking story'):
        before = [
            step('given', 'our guest Alice'),
            step('when', 'Alice checks in to the Deluxe Suite'),
            step('then', 'the later booking is cancelled'),
            step('when', 'she tries to cancel the stay she has checked in to'),
        ]
        after = [
            step('given', 'our guest Alice'),
            step('when', 'Alice checks in to the Garden Suite'),
            step('then', 'the later Booking is cancelled and refunded in full'),
            step('when', 'she tries to cancel the stay she has checked in to'),
        ]
    with when('the two are aligned'):
        deltas = _align(before, after)
    with then(
        'the reworded When and Then are modified between the two unchanged steps'
    ):
        assert _changes(deltas) == ['equal', 'modified', 'modified', 'equal']
        assert [(delta.before, delta.after) for delta in deltas] == [
            ((0,), (0,)),
            ((1,), (1,)),
            ((2,), (2,)),
            ((3,), (3,)),
        ]
    with then('the modified Then carries the words that changed'):
        assert any(segment.mark == 'added' for segment in deltas[2].words)
    with when('the second Then is swapped for a wholly different one'):
        swapped = _align(
            [step('then', 'the deposit is kept')],
            [step('then', 'a voucher is issued')],
        )
    with then('the old Then is removed and the new one added'):
        assert _changes(swapped) == ['removed', 'added']
        assert (swapped[0].before, swapped[0].after) == ((0,), None)
        assert (swapped[1].before, swapped[1].after) == (None, (0,))
        assert steps_changed(swapped)


def test_the_brief_texts_fall_on_either_side_of_the_threshold() -> None:
    reworded = similarity(
        step('then', 'the later booking is cancelled').narration,
        _READING,
        step('then', 'the later Booking is cancelled and refunded in full').narration,
        _READING,
    )
    unrelated = similarity(
        step('then', 'the deposit is kept').narration,
        _READING,
        step('then', 'a voucher is issued').narration,
        _READING,
    )
    assert unrelated < MODIFIED_SIMILARITY <= reworded


def test_a_child_added_under_an_equal_parent_leaves_the_parent_equal() -> None:
    deltas = _align(
        [step('given', 'a room', step('given', 'a bed'))],
        [step('given', 'a room', step('given', 'a bed'), step('given', 'a view'))],
    )
    assert _changes(deltas) == ['equal']
    assert _changes(deltas[0].children) == ['equal', 'added']
    assert deltas[0].children[1].after == (0, 1)
    assert steps_changed(deltas)


def test_a_modified_step_aligns_its_children_by_full_path() -> None:
    deltas = _align(
        [step('given', 'a room'), step('when', 'Alice pays', step('then', 'a bill'))],
        [
            step('given', 'a room'),
            step(
                'when', 'Alice pays now', step('then', 'a bill'), step('then', 'a tip')
            ),
        ],
    )
    assert _changes(deltas) == ['equal', 'modified']
    assert [
        (delta.change, delta.before, delta.after) for delta in deltas[1].children
    ] == [
        ('equal', (1, 0), (1, 0)),
        ('added', None, (1, 1)),
    ]


def test_a_same_text_step_in_another_phase_is_modified_with_its_phase_changed() -> None:
    deltas = _align(
        [step('when', 'the room is booked')], [step('then', 'the room is booked')]
    )
    assert _changes(deltas) == ['modified']
    assert deltas[0].phase_changed
    assert {segment.mark for segment in deltas[0].words} == {'equal'}
    assert steps_changed(deltas)


def test_an_unrelated_step_before_a_match_is_added_first() -> None:
    deltas = _align(
        [step('given', 'a room is free'), step('then', 'the bill is paid')],
        [step('given', 'a view'), step('given', 'a room is free today')],
    )
    assert [(delta.change, delta.before, delta.after) for delta in deltas] == [
        ('added', None, (0,)),
        ('modified', (0,), (1,)),
        ('removed', (1,), None),
    ]


def test_attachments_pins_and_fixture_names_are_ignored() -> None:
    attached = Step(
        phase='given',
        narration=step('given', 'a room').narration,
        attachments=[Attachment(label=AttachmentLabel('note'), content='x')],
        fixture_name='room',
    )
    deltas = _align([attached], [step('given', 'a room')])
    assert _changes(deltas) == ['equal']
    assert not steps_changed(deltas)
