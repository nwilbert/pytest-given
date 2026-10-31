"""The delta page's context (`report/delta_html.py`): the data its template and
`delta.js` read, never the markup."""

import dataclasses

from pytest_given.delta import DeltaInputs, build_delta
from pytest_given.model import (
    DeltaData,
    DeltaMetadata,
    DeltaSide,
    Glossary,
    ReportData,
    ScenarioDelta,
)
from pytest_given.report.delta_html import (
    ListedScenario,
    ReasonRow,
    StepBlock,
    StepRow,
    delta_render_context,
    render_delta_html,
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
from tests.unit.report.app_data import embedded_app_data


def _delta(before: ReportData, after: ReportData) -> DeltaData:
    return build_delta(
        DeltaInputs(
            before=before,
            after=after,
            plugin_version='0.1.0',
            timestamp='2026-01-02T00:00:00+00:00',
        )
    ).delta


def _listed(delta: DeltaData) -> list[ListedScenario]:
    listed = delta_render_context(delta)['listed']
    assert isinstance(listed, list)
    return listed


def test_a_removed_and_an_added_scenario_sharing_a_node_id_have_a_fragment_each():
    """Only a rename log pairs the old `test_x` elsewhere and leaves the new
    one unpaired, so the delta is built by hand."""
    side = DeltaSide(metadata=meta(), modules=('t',))
    delta = DeltaData(
        metadata=DeltaMetadata(
            before=side, after=side, plugin_version='0.1.0', timestamp='now'
        ),
        scenarios=(
            ScenarioDelta(change='removed', before=scn('t.py::test_x', 'Old')),
            ScenarioDelta(change='added', after=scn('t.py::test_x', 'New')),
        ),
    )
    assert [item.fragment for item in _listed(delta)] == [
        'scenario=removed-t/x',
        'scenario=t/x',
    ]
    app_data = embedded_app_data(render_delta_html(delta, source_link_template=None))
    assert [entry['id'] for entry in app_data['scenarios']] == ['removed-t/x', 't/x']
    assert app_data['scenario_slugs'] == {'removed-t/x': 'removed-t/x', 't/x': 't/x'}


def test_modules_are_marked_by_which_sides_have_them_and_a_moved_file_is_not():
    before = report(
        scn('a.py::test_moved', 'Moved, unchanged'),
        scn('gone.py::test_old', 'Old'),
        scn('both.py::test_pay', 'Pay'),
    )
    after = report(
        scn('b.py::test_moved', 'Moved, unchanged'),
        scn('new.py::test_new', 'New'),
        scn('both.py::test_pay', 'Pay by card'),
    )
    context = delta_render_context(_delta(before, after))
    assert context['module_changes'] == {
        'gone': 'removed',
        'new': 'added',
        'both': 'changed',
    }


def test_the_sidebar_counts_listed_scenarios_by_change_and_the_unchanged_ones():
    before = report(
        scn('t.py::test_same', 'Same'),
        scn('t.py::test_pay', 'Pay'),
        scn('t.py::test_gone', 'Gone'),
    )
    after = report(
        scn('t.py::test_same', 'Same'),
        scn('t.py::test_pay', 'Pay now'),
        scn('t.py::test_new', 'New'),
        scn('t.py::test_newer', 'Newer'),
    )
    context = delta_render_context(_delta(before, after))
    assert context['change_counts'] == {'added': 2, 'changed': 1, 'removed': 1}
    assert context['unchanged_count'] == 1


def test_a_search_matches_either_side_s_title_and_a_removed_tag() -> None:
    before = report(scn('t.py::test_pay', 'Pay at the desk', tags=['legacy']))
    after = report(scn('t.py::test_pay', 'Pay online'))
    data = embedded_app_data(render_delta_html(_delta(before, after), None))
    [entry] = data['scenarios']
    assert entry['search_text'] == 'Pay at the desk Pay online legacy'
    assert (entry['change'], entry['tags']) == ('changed', [])


def test_a_changed_reason_keeps_the_one_it_replaced() -> None:
    def skipped(reason: str):
        return dataclasses.replace(
            scn('t.py::test_pay', 'Pay', status='skipped'), skip_reason=reason
        )

    before = report(skipped('no card reader'))
    after = report(skipped('no network'))
    [item] = _listed(_delta(before, after))
    assert item.reasons == [
        ReasonRow('skipped', 'Skipped:', 'no network', was='no card reader')
    ]


def test_a_reason_the_after_side_dropped_is_kept_as_what_it_was() -> None:
    before = report(
        dataclasses.replace(
            scn('t.py::test_pay', 'Pay', status='xfailed'), xfail_reason='bug 12'
        )
    )
    after = report(scn('t.py::test_pay', 'Pay', status='failed'))
    [item] = _listed(_delta(before, after))
    assert item.reasons == [
        ReasonRow('xfailed', 'Expected to fail:', None, was='bug 12')
    ]


def test_a_before_side_ref_finds_its_term_where_the_after_one_reads_otherwise() -> None:
    before = report(
        glossary=Glossary(
            terms=[
                term('room', 'Room'),
                term('guest', 'Guest'),
                term('desk', 'Desk', definition='Front desk.'),
                term('bill', 'Bill', definition='Old.'),
            ]
        )
    )
    after = report(
        scn('t.py::test_new', 'New'),
        glossary=Glossary(
            terms=[
                term('guest', 'Visitor'),
                term('desk', 'Desk', definition='Front desk.'),
                term('bill', 'Bill', definition='New.'),
            ]
        ),
    )
    data = embedded_app_data(render_delta_html(_delta(before, after), None))
    assert [entry['id'] for entry in data['glossary']['terms']] == [
        'guest',
        'desk',
        'bill',
    ]
    assert [
        (entry['id'], entry['canonical'], entry['definition'])
        for entry in data['before_terms']
    ] == [('room', 'Room', None), ('guest', 'Guest', None), ('bill', 'Bill', 'Old.')]


def _shape(blocks: list[StepBlock] | None) -> list[tuple[object, ...]]:
    assert blocks is not None
    return [
        (
            block.phase,
            block.was_phase,
            block.after_block,
            [_row(row) for row in block.rows],
        )
        for block in blocks
    ]


def _row(row: StepRow) -> tuple[object, ...]:
    return (
        row.change,
        row.side,
        row.step.narration.text,
        row.was_phase,
        [_row(child) for child in row.children],
    )


def test_a_changed_scenario_reads_its_steps_in_after_order_with_removed_ones_in_place():
    before = report(
        scn(
            't.py::test_stay',
            'Stay',
            step('given', 'a guest', step('given', 'with her passport')),
            step('when', 'she phones the desk'),
            step('when', 'she checks in'),
            step('then', 'she gets a key card'),
        )
    )
    after = report(
        scn(
            't.py::test_stay',
            'Stay',
            step('given', 'a guest', step('given', 'with her passport and visa')),
            step('given', 'a free room'),
            step('when', 'she checks in'),
            step('when', 'she gets a digital key card'),
            step('then', 'her phone opens the door'),
        )
    )
    [item] = _listed(_delta(before, after))
    assert _shape(item.step_blocks) == [
        (
            'given',
            None,
            0,
            [
                (
                    'equal',
                    'after',
                    'a guest',
                    None,
                    [('modified', 'after', 'with her passport and visa', None, [])],
                ),
            ],
        ),
        # Removed at its before position, under its own phase, and so
        # splitting the after side's first block in two.
        ('when', None, None, [('removed', 'before', 'she phones the desk', None, [])]),
        ('given', None, 0, [('added', 'after', 'a free room', None, [])]),
        ('when', None, 1, [('equal', 'after', 'she checks in', None, [])]),
        (
            'when',
            'then',
            1,
            [
                ('modified', 'after', 'she gets a digital key card', 'then', []),
            ],
        ),
        ('then', None, 2, [('added', 'after', 'her phone opens the door', None, [])]),
    ]


def test_a_block_of_removed_steps_names_the_after_block_its_added_steps_are_in():
    """Until an after step joins it."""
    before = report(
        scn(
            't.py::test_stay',
            'Stay',
            step('given', 'a guest'),
            step('when', 'she waits'),
            step('when', 'she knocks'),
        )
    )
    after = report(
        scn(
            't.py::test_stay',
            'Stay',
            step('given', 'a guest'),
            step('when', 'she rings the bell twice'),
        )
    )
    [item] = _listed(_delta(before, after))
    assert [
        (block.phase, block.after_block, [row.change for row in block.rows])
        for block in item.step_blocks or []
    ] == [('given', 0, ['equal']), ('when', 1, ['removed', 'removed', 'added'])]


def test_added_and_removed_scenarios_read_their_steps_unmarked() -> None:
    before = report(scn('t.py::test_old', 'Old', step('given', 'a guest')))
    after = report(scn('t.py::test_new', 'New', step('given', 'a host')))
    assert [item.step_blocks for item in _listed(_delta(before, after))] == [
        None,
        None,
    ]


def test_a_removed_step_renders_a_placeholder_whose_column_only_the_before_side_has():
    before = report(
        scn(
            't.py::test_pay',
            'Pay',
            step('when', narr(lit('the clerk types '), ph('pin'))),
            step('then', narr(lit('she pays by '), ph('pin'))),
            parameters=table([('pin', 'param')], ('t.py::test_pay[1]', [1])),
        ),
    )
    after = report(
        scn(
            't.py::test_pay',
            'Pay',
            step('when', 'she taps her card'),
            step('then', narr(lit('she pays by '), ref('card', 'Card'))),
        ),
        glossary=Glossary(terms=[term('card', 'Card')]),
    )
    delta = _delta(before, after)
    [item] = _listed(delta)
    assert [row.change for block in item.step_blocks or [] for row in block.rows] == [
        'removed',
        'added',
        'modified',
    ]
    render_delta_html(delta, source_link_template=None)
