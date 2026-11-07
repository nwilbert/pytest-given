"""A changed scenario's steps side by side (`report/delta/steps.py`): the rows,
blocks and marked words the delta page renders, never the markup."""

from pytest_given.delta import DeltaInputs, build_delta, parse_rename_log
from pytest_given.model import (
    DiffSegment,
    Glossary,
    NarrationTermRef,
    Scenario,
    ScenarioDelta,
    Side,
    narration_text,
)
from pytest_given.report.delta.steps import (
    MarkedRun,
    StepRow,
    StepsView,
    block_keys,
    side_runs,
    steps_view,
)
from tests.unit.delta.builders import lit, narr, ref, report, scn, step, term


def _scenario_delta(
    before: Scenario,
    after: Scenario,
    *,
    glossaries: tuple[Glossary, Glossary] | None = None,
    renames: str = '',
) -> ScenarioDelta:
    before_glossary, after_glossary = glossaries or (None, None)
    [scenario_delta] = build_delta(
        DeltaInputs(
            before=report(before, glossary=before_glossary),
            after=report(after, glossary=after_glossary),
            renames=parse_rename_log(renames, 'log'),
            plugin_version='0.1.0',
            timestamp='now',
        )
    ).delta.scenarios
    assert scenario_delta.change == 'changed'
    return scenario_delta


def _side(view: StepsView, side: Side) -> list[tuple[object, ...]]:
    return [
        (
            block.phase,
            block.key,
            block.continued,
            [_line(row, side) for row in block.rows],
        )
        for block in view.side(side)
    ]


def _line(row: StepRow, side: Side) -> tuple[object, ...]:
    line = row.line(side)
    return (row.path, row.change, line.step.narration.text if line else None)


def test_steps_pair_up_in_rows_each_side_under_its_own_phases() -> None:
    """A row the side lacks holds its place outside any phase, and a phase it
    interrupts goes on below it under the same key."""
    scenario_delta = _scenario_delta(
        scn(
            't.py::test_stay',
            'Stay',
            step('given', 'a guest', step('given', 'with her passport')),
            step('when', 'she phones the desk'),
            step('when', 'she checks in'),
            step('then', 'she gets a key card'),
        ),
        scn(
            't.py::test_stay',
            'Stay',
            step('given', 'a guest', step('given', 'with her passport and visa')),
            step('given', 'a free room'),
            step('when', 'she checks in'),
            step('when', 'she gets a key card'),
            step('then', 'her phone opens the door'),
        ),
    )
    view = steps_view(scenario_delta, block_keys(scenario_delta))
    assert _side(view, 'before') == [
        ('given', '0', False, [((0,), 'equal', 'a guest')]),
        ('when', '1', False, [((1,), 'removed', 'she phones the desk')]),
        (None, None, False, [((2,), 'added', None)]),
        ('when', '1', True, [((3,), 'equal', 'she checks in')]),
        # Its step went to the after side's When, so it keys as that block.
        ('then', '1', False, [((4,), 'modified', 'she gets a key card')]),
        (None, None, False, [((5,), 'added', None)]),
    ]
    assert _side(view, 'after') == [
        ('given', '0', False, [((0,), 'equal', 'a guest')]),
        (None, None, False, [((1,), 'removed', None)]),
        ('given', '0', True, [((2,), 'added', 'a free room')]),
        (
            'when',
            '1',
            False,
            [
                ((3,), 'equal', 'she checks in'),
                ((4,), 'modified', 'she gets a key card'),
            ],
        ),
        ('then', '2', False, [((5,), 'added', 'her phone opens the door')]),
    ]
    [guest] = view.before[0].rows
    assert [
        (_line(child, 'before'), _line(child, 'after')) for child in guest.children
    ] == [
        (
            ((0, 0), 'modified', 'with her passport'),
            ((0, 0), 'modified', 'with her passport and visa'),
        )
    ]


def test_a_before_block_the_after_side_kept_nothing_of_keys_as_its_own() -> None:
    """And rows a side lacks ahead of its first step open no phase."""
    scenario_delta = _scenario_delta(
        scn(
            't.py::test_stay',
            'Stay',
            step('when', 'it rains hard'),
            step('then', 'the bell rings loudly'),
        ),
        scn(
            't.py::test_stay',
            'Stay',
            step('given', 'a guest arrives'),
            step('when', 'it rains hard'),
        ),
    )
    assert block_keys(scenario_delta) == {
        'before': ['1', 'before:1'],
        'after': ['0', '1'],
    }
    assert _side(steps_view(scenario_delta, block_keys(scenario_delta)), 'before') == [
        (None, None, False, [((0,), 'added', None)]),
        ('when', '1', False, [((1,), 'equal', 'it rains hard')]),
        ('then', 'before:1', False, [((2,), 'removed', 'the bell rings loudly')]),
    ]


def test_each_side_reads_its_own_text_with_only_its_own_words_marked() -> None:
    """Here a renamed term's display, and the space after `Dana`."""
    scenario_delta = _scenario_delta(
        scn(
            't.py::test_walk_in',
            'Walk in',
            step(
                'given',
                narr(ref('desk', 'Dana'), lit(' has one free '), ref('room', 'Room')),
            ),
        ),
        scn(
            't.py::test_walk_in',
            'Walk in',
            step(
                'given',
                narr(lit('the front desk has one free '), ref('suite', 'Suite')),
            ),
        ),
        glossaries=(
            Glossary(terms=[term('desk', 'Receptionist'), term('room', 'Room')]),
            Glossary(terms=[term('suite', 'Suite')]),
        ),
        renames='[[term]]\nold = "room"\nnew = "suite"\n',
    )
    [block] = steps_view(scenario_delta, block_keys(scenario_delta)).before
    [row] = block.rows
    words = {
        side: line.words
        for side, line in (('before', row.before), ('after', row.after))
        if line is not None
    }
    assert {
        side: [(run.mark, narration_text(run.parts)) for run in runs]
        for side, runs in words.items()
    } == {
        'before': [('removed', 'Dana'), ('equal', ' has one free Room')],
        'after': [('added', 'the front desk '), ('equal', 'has one free Suite')],
    }
    assert [
        part.term_id
        for run in words['before']
        for part in run.parts
        if isinstance(part, NarrationTermRef)
    ] == ['desk', 'room']


def test_a_side_reads_its_own_parts_with_a_changed_stretch_as_one_run() -> None:
    runs = (
        DiffSegment(mark='equal', before=(lit('a  '),), after=(lit('a '),)),
        DiffSegment(mark='removed', before=(lit('X'),)),
        DiffSegment(mark='equal', before=(lit(' '),), after=(lit(' '),)),
        DiffSegment(mark='removed', before=(lit('Y'),)),
        DiffSegment(mark='added', after=(lit('Z'),)),
    )
    # A lone space between two changes of one mark joins them.
    assert side_runs(runs, 'before') == (
        MarkedRun('equal', (lit('a  '),)),
        MarkedRun('removed', (lit('X Y'),)),
    )
    # Runs of one mark merge, once the other side's are left out.
    assert side_runs(runs, 'after') == (
        MarkedRun('equal', (lit('a  '),)),
        MarkedRun('added', (lit('Z'),)),
    )
