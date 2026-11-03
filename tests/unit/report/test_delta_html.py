"""The delta page's context (`report/delta_html.py`, its listed scenarios and
term cards): the data its template and `delta.js` read, never the markup."""

import dataclasses
import re

from pytest_given.delta import DeltaInputs, build_delta, parse_rename_log
from pytest_given.model import (
    CHANGES,
    Attachment,
    AttachmentRef,
    ColumnId,
    DeltaData,
    DeltaMetadata,
    DeltaSide,
    Glossary,
    NarrationPlaceholder,
    ReportData,
    Scenario,
    ScenarioDelta,
    Status,
    Step,
    narration_text,
)
from pytest_given.report.delta_glossary import DeltaGlossaryView, ListedTerm, OtherForm
from pytest_given.report.delta_html import delta_render_context, render_delta_html
from pytest_given.report.delta_scenarios import (
    ListedScenario,
    ReasonRow,
    TableSide,
    TableView,
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
        'scenario=removed:t/x',
        'scenario=t/x',
    ]
    app_data = embedded_app_data(render_delta_html(delta, source_link_template=None))
    assert [entry['id'] for entry in app_data['scenarios']] == ['removed:t/x', 't/x']
    assert app_data['scenario_slugs'] == {'removed:t/x': 'removed:t/x', 't/x': 't/x'}


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
    # A term only the before side has can't be read otherwise by the after
    # one, so it stands with the after terms, where the Terms axis names it.
    assert [entry['id'] for entry in data['glossary']['terms']] == [
        'guest',
        'desk',
        'bill',
        'room',
    ]
    assert [
        (entry['id'], entry['canonical'], entry['definition'])
        for entry in data['before_terms']
    ] == [('guest', 'Guest', None), ('bill', 'Bill', 'Old.')]


def test_each_term_ref_names_the_side_whose_glossary_it_was_read_against() -> None:
    """`delta.js` reads the side off the ref, for its tooltip and its card."""
    before = report(
        scn('t.py::test_stay', 'Stay', step('given', narr(ref('guest', 'a guest')))),
        scn('t.py::test_leave', narr(lit('A '), ref('guest', 'guest'), lit(' leaves'))),
        glossary=Glossary(terms=[term('guest', 'Guest')]),
    )
    after = report(
        scn(
            't.py::test_stay', 'Stay', step('given', narr(ref('visitor', 'a visitor')))
        ),
        glossary=Glossary(terms=[term('visitor', 'Visitor')]),
    )
    html = render_delta_html(_delta(before, after), None)
    refs = [
        (attrs['data-term-id'], attrs['data-term-side'])
        for tag in re.findall(r'<[^>]* data-term-side="[^>]*>', html)
        for attrs in [dict(re.findall(r'([\w-]+)="([^"]*)"', tag))]
    ]
    assert sorted(refs) == [
        ('guest', 'before'),
        ('guest', 'before'),
        ('visitor', 'after'),
    ]


def test_the_change_glyphs_reach_delta_js_in_the_model_s_change_order() -> None:
    """`delta.js` reads its changes' order off the glyphs' keys."""
    data = embedded_app_data(render_delta_html(_delta(report(), report()), None))
    assert list(data['change_glyphs']) == list(CHANGES)


def _glossary(delta: DeltaData) -> DeltaGlossaryView:
    view = delta_render_context(delta)['glossary_view']
    assert isinstance(view, DeltaGlossaryView)
    return view


def _card(view: DeltaGlossaryView, key: str) -> ListedTerm:
    [card] = [card for card in view.listed if card.key == key]
    return card


def _invoicing(name: str, title: str = 'Pay') -> Scenario:
    return scn(f't.py::test_{name}', narr(lit(f'{title} the '), ref('bill', 'bill')))


def test_a_term_card_links_only_the_listed_scenarios_that_refer_to_it() -> None:
    """On the side each scenario's ref was read on: a removed scenario's
    before ref counts, an unchanged scenario only in the count."""
    before = report(
        _invoicing('same'),
        _invoicing('stay'),
        _invoicing('gone'),
        scn('t.py::test_other', 'Other'),
        glossary=Glossary(terms=[term('bill', 'Bill', definition='Old.')]),
    )
    after = report(
        _invoicing('same'),
        _invoicing('stay', 'Settle'),
        scn('t.py::test_other', 'Other, renamed'),
        glossary=Glossary(terms=[term('bill', 'Bill', definition='New.')]),
    )
    delta = _delta(before, after)
    card = _card(_glossary(delta), 'bill')
    assert sorted(item.slug for item in card.scenarios) == ['removed:t/gone', 't/stay']
    assert card.renamed_from is None
    assert [card.scenario_count(side) for side in card.sides] == [
        '3 scenarios',
        '2 scenarios',
    ]
    # The Terms axis takes each scenario's terms from the side it is shown from.
    data = embedded_app_data(render_delta_html(delta, None))
    assert sorted(data['term_scenarios']['bill']) == ['removed:t/gone', 't/stay']


def test_a_changed_term_reads_each_side_with_only_its_own_changes_marked():
    """Its name, its definition's words, its other forms and its count."""
    before = report(
        scn('t.py::test_a', narr(lit('Book '), ref('room', 'Room 101'))),
        scn('t.py::test_b', narr(lit('Clean '), ref('room', 'Room 102'))),
        glossary=Glossary(
            terms=[term('room', 'Room', definition='A bookable hotel room.')]
        ),
    )
    after = report(
        scn('t.py::test_a', narr(lit('Book '), ref('suite', 'Suite 101'))),
        scn('t.py::test_b', narr(lit('Clean '), ref('suite', 'Room 102'))),
        glossary=Glossary(
            terms=[term('suite', 'Suite', definition='A rentable hotel room.')]
        ),
    )
    delta = build_delta(
        DeltaInputs(
            before=before,
            after=after,
            renames=parse_rename_log('[[term]]\nold = "room"\nnew = "suite"\n', 'log'),
            plugin_version='0.1.0',
            timestamp='now',
        )
    ).delta
    card = _card(_glossary(delta), 'suite')
    assert (card.change, card.delta.paired_by) == ('changed', 'rename-log')
    # The card heads with its after name, and says what it was called.
    assert card.renamed_from == 'Room'
    assert {
        side: (
            card.term(side).canonical,
            [(run.mark, narration_text(run.parts)) for run in card.definition(side)],
            card.other_forms(side),
            card.scenario_count(side),
        )
        for side in card.sides
    } == {
        'before': (
            'Room',
            [('equal', 'A '), ('removed', 'bookable'), ('equal', ' hotel room.')],
            [OtherForm('Room 101', 'removed'), OtherForm('Room 102')],
            '2 scenarios',
        ),
        'after': (
            'Suite',
            [('equal', 'A '), ('added', 'rentable'), ('equal', ' hotel room.')],
            [OtherForm('Suite 101', 'added'), OtherForm('Room 102')],
            '2 scenarios',
        ),
    }
    # A ref to it on either side opens its card.
    [entry] = embedded_app_data(render_delta_html(delta, None))['term_cards']
    assert (entry['key'], entry['before'], entry['after']) == ('suite', 'room', 'suite')


def test_a_term_whose_kind_changed_is_listed_under_each_kind() -> None:
    before = report(glossary=Glossary(terms=[term('upgrade', 'Upgrade', 'object')]))
    after = report(glossary=Glossary(terms=[term('upgrade', 'upgrade', 'activity')]))
    view = _glossary(_delta(before, after))
    assert [
        (group.key, [(card.key, card.change) for card in group.entries])
        for group in view.grouping.groups
    ] == [
        ('object', [('removed:upgrade', 'removed')]),
        ('activity', [('upgrade', 'added')]),
    ]
    # Each on its own side alone.
    assert {card.key: card.sides for card in view.listed} == {
        'removed:upgrade': ('before',),
        'upgrade': ('after',),
    }


def test_a_removed_term_s_card_key_is_no_other_term_s_id() -> None:
    before = report(glossary=Glossary(terms=[term('booking', 'Booking')]))
    after = report(
        glossary=Glossary(terms=[term('removed-booking', 'Removed booking')])
    )
    keys = [card.key for card in _glossary(_delta(before, after)).listed]
    assert len(set(keys)) == len(keys) == 2


def test_a_side_without_a_glossary_lists_the_other_side_s_terms() -> None:
    """And a delta that changed no term has no Glossary tab."""
    with_terms = report(glossary=Glossary(terms=[term('desk', 'Desk')]))
    without = report(scn('t.py::test_new', 'New'))
    for before, after, change in (
        (with_terms, without, 'removed'),
        (without, with_terms, 'added'),
    ):
        data = embedded_app_data(render_delta_html(_delta(before, after), None))
        [card] = data['term_cards']
        assert (card['change'], data['term_ids']) == (change, [card['key']])
        assert [entry['id'] for entry in data['glossary']['terms']] == ['desk']
    unchanged = embedded_app_data(
        render_delta_html(_delta(with_terms, with_terms), None)
    )
    assert unchanged['term_ids'] == []


def test_added_and_removed_scenarios_read_their_steps_unmarked() -> None:
    before = report(scn('t.py::test_old', 'Old', step('given', 'a guest')))
    after = report(scn('t.py::test_new', 'New', step('given', 'a host')))
    assert [item.steps for item in _listed(_delta(before, after))] == [None, None]


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
    assert item.steps is not None
    assert [row.change for block in item.steps.before for row in block.rows] == [
        'removed',
        'added',
        'modified',
    ]
    render_delta_html(delta, source_link_template=None)


def _rows(view: TableView | None) -> list[tuple[str | None, str | None, str | None]]:
    assert view is not None
    return [
        (
            row.before_case.id if row.before_case else None,
            row.after_case.id if row.after_case else None,
            row.change,
        )
        for row in view.rows
    ]


def _columns(side: TableSide) -> list[tuple[str, str | None, str | None]]:
    return [(column.column.id, column.change, column.was) for column in side.columns]


def _paying(name: str, amounts: list[int], status: Status = 'passed') -> Scenario:
    return scn(
        f't.py::test_{name}',
        name,
        step('when', narr(lit('she pays '), ph('amount'))),
        parameters=table(
            [('amount', 'param')],
            *((f't.py::test_{name}[{amount}]', [amount]) for amount in amounts),
            status=status,
        ),
    )


def test_a_removed_case_follows_the_case_it_followed_before_in_the_after_order():
    before = report(_paying('pay', [1, 2, 3]))
    after = report(_paying('pay', [3, 1, 4]))
    [item] = _listed(_delta(before, after))
    assert _rows(item.table) == [
        ('t.py::test_pay[3]', 't.py::test_pay[3]', None),
        ('t.py::test_pay[1]', 't.py::test_pay[1]', None),
        ('t.py::test_pay[2]', None, 'removed'),
        (None, 't.py::test_pay[4]', 'added'),
    ]


def test_a_changed_value_is_marked_in_its_cell_on_each_side() -> None:
    """The old value faces the new one; a case whose values held is unmarked."""

    def paying(fee: int) -> ReportData:
        return report(
            scn(
                't.py::test_pay',
                'Pay',
                step('when', narr(lit('she pays '), ph('amount'))),
                parameters=table(
                    [('amount', 'param')],
                    ('t.py::test_pay[a]', [fee]),
                    ('t.py::test_pay[b]', [5]),
                ),
            )
        )

    html = render_delta_html(_delta(paying(1), paying(2)), None)
    cells = [
        (attrs['data-param'], attrs.get('data-change'))
        for tag in re.findall(r'<td [^>]*data-subst="[^>]*>', html)
        for attrs in [dict(re.findall(r'([\w-]+)="([^"]*)"', tag))]
    ]
    assert cells == [
        ('amount', 'removed'),
        ('amount', None),
        ('amount', 'added'),
        ('amount', None),
    ]


def test_each_side_marks_its_own_columns_and_keys_a_paired_one_as_the_after_side():
    """A placeholder in before-side text keys its column as the before table
    does, so it finds the column in both tables, even renamed; a column only
    the before side has can't meet an after column of the same generated ID."""
    receipt = Attachment(label='receipt', content='paid')
    before = report(
        scn(
            't.py::test_pay',
            'Pay',
            Step(
                phase='when',
                narration=narr(
                    lit('she pays a deposit of '),
                    ph('deposit', 'derived:0'),
                    lit(' because of '),
                    ph('decline_reason'),
                ),
                attachments=[
                    AttachmentRef(
                        label='receipt',
                        content_type='text',
                        column_id=ColumnId('attachment:0'),
                    )
                ],
            ),
            parameters=table(
                [
                    ('decline_reason', 'param'),
                    ('deposit', 'derived'),
                    ('receipt', 'attachment'),
                ],
                ('t.py::test_pay[a]', ['expired', '60', receipt]),
                ('t.py::test_pay[b]', ['blocked', '40', receipt]),
            ),
        )
    )
    after = report(
        scn(
            't.py::test_pay',
            'Pay',
            step('then', narr(lit('she pays a fee of '), ph('fee', 'derived:0'))),
            parameters=table(
                [('reason', 'param'), ('fee', 'derived'), ('receipt', 'attachment')],
                ('t.py::test_pay[a]', ['expired', '12', receipt]),
                ('t.py::test_pay[b]', ['blocked', '8', receipt]),
            ),
        )
    )
    [item] = _listed(_delta(before, after))
    assert item.table is not None
    before_side, after_side = item.table.sides
    assert _columns(before_side) == [
        ('reason', None, None),
        ('before:derived:0', 'removed', None),
        ('before:attachment:0', None, None),
    ]
    assert _columns(after_side) == [
        ('reason', None, 'decline_reason'),
        ('derived:0', 'added', None),
        ('attachment:0', None, None),
    ]
    # What the before side's steps render from: a step, and a modified step's
    # words.
    assert item.delta.before is not None
    [before_step] = item.delta.before.steps
    [modified] = item.delta.steps
    before_words = tuple(part for run in modified.words for part in run.before)
    assert [
        [part.column_id for part in parts if isinstance(part, NarrationPlaceholder)]
        for parts in (before_step.narration.parts, before_words)
    ] == [['before:derived:0', 'reason'], ['before:derived:0', 'reason']]
    assert [
        attachment.column_id
        for attachment in before_step.attachments
        if isinstance(attachment, AttachmentRef)
    ] == ['before:attachment:0']


def test_an_unchanged_table_s_attachment_column_is_keyed_alike_on_both_sides():
    """The page shows the after table alone, so a before-side badge keys the
    column it holds."""
    receipt = Attachment(label='receipt', content='paid')
    parameters = table(
        [('reason', 'param'), ('receipt', 'attachment')],
        ('t.py::test_pay[a]', ['expired', receipt]),
    )

    def side(text: str) -> ReportData:
        return report(
            scn(
                't.py::test_pay',
                'Pay',
                Step(
                    phase='when',
                    narration=narr(lit(text), ph('reason')),
                    attachments=[
                        AttachmentRef(
                            label='receipt',
                            content_type='text',
                            column_id=ColumnId('attachment:0'),
                        )
                    ],
                ),
                parameters=parameters,
            )
        )

    [item] = _listed(_delta(side('she pays for '), side('she settles for ')))
    assert item.table is None
    assert item.delta.before is not None
    [before_step] = item.delta.before.steps
    assert [
        attachment.column_id
        for attachment in before_step.attachments
        if isinstance(attachment, AttachmentRef)
    ] == ['attachment:0']


def test_a_table_changed_only_in_statuses_shows_both_sides_and_an_unchanged_one_none():
    before = report(_paying('status', [1]), _paying('same', [1]))
    after = report(
        _paying('status', [1], status='failed'),
        dataclasses.replace(_paying('same', [1]), tags=['new']),
    )
    status_only, unchanged = _listed(_delta(before, after))
    assert status_only.table is not None
    assert [side.side for side in status_only.table.sides] == ['before', 'after']
    assert [row.change for row in status_only.table.rows] == ['changed']
    assert unchanged.table is None


def test_a_table_gained_or_lost_with_its_parametrization_shows_alone():
    def unparametrized(name: str) -> Scenario:
        return scn(f't.py::test_{name}', name, step('when', 'she pays'))

    before = report(unparametrized('gains'), _paying('loses', [1, 2]))
    after = report(_paying('gains', [1, 2]), unparametrized('loses'))
    gains, loses = (item.table for item in _listed(_delta(before, after)))
    assert gains is not None
    assert loses is not None
    assert [side.side for side in gains.sides] == ['after']
    assert [row.change for row in gains.rows] == ['added', 'added']
    assert [side.side for side in loses.sides] == ['before']
    assert _columns(loses.sides[0]) == [('before:amount', None, None)]
    assert [row.change for row in loses.rows] == ['removed', 'removed']
    assert [table.sides[0].column_blocks for table in (gains, loses)] == [
        {'amount': '0'},
        {'before:amount': '0'},
    ]


def test_each_table_s_columns_key_their_phase_as_their_side_s_steps_do() -> None:
    """So a phase hover on either side outlines its columns in both tables."""
    before = report(
        scn(
            't.py::test_pay',
            'Pay',
            step('given', narr(lit('she pays '), ph('amount'))),
            step('when', narr(lit('the desk keeps a deposit of '), ph('deposit'))),
            parameters=table(
                [('amount', 'param'), ('deposit', 'param')],
                ('t.py::test_pay[a]', [1, 10]),
            ),
        )
    )
    after = report(
        scn(
            't.py::test_pay',
            'Pay',
            step('given', narr(lit('she pays '), ph('amount'))),
            step('then', narr(lit('the hotel charges a fee of '), ph('fee'))),
            parameters=table(
                [('amount', 'param'), ('fee', 'param')],
                ('t.py::test_pay[a]', [1, 2]),
            ),
        )
    )
    [item] = _listed(_delta(before, after))
    assert item.table is not None
    assert [side.column_blocks for side in item.table.sides] == [
        {'amount': '0', 'before:deposit': 'before:1'},
        {'amount': '0', 'fee': '1'},
    ]
