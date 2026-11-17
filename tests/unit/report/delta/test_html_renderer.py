"""The delta page's context (`report/delta/html_renderer.py`, its listed scenarios and
term cards): the data its template and `delta.js` read, never the markup."""

import dataclasses
import html
import re
import typing
from collections.abc import Iterator

from pytest_given.delta import DeltaInputs, build_delta
from pytest_given.delta.renames import parse_rename_log
from pytest_given.model import (
    CHANGES,
    Attachment,
    AttachmentRef,
    ColumnId,
    ContentType,
    DeltaData,
    DeltaMetadata,
    DeltaSide,
    Glossary,
    NarrationPlaceholder,
    ReportData,
    Scenario,
    ScenarioDelta,
    Side,
    Status,
    Step,
    TermId,
    TextSegment,
    narration_text,
)
from pytest_given.report.delta.attachments import LineRow
from pytest_given.report.delta.glossary import (
    DeltaGlossaryView,
    ListedTerm,
    OtherForm,
    term_ref_targets,
)
from pytest_given.report.delta.html_renderer import (
    delta_render_context,
    render_delta_html,
    text_diff,
)
from pytest_given.report.delta.scenarios import (
    ListedScenario,
    ReasonRow,
    TableSide,
    TableView,
)
from tests.unit.delta.builders import (
    built_delta,
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
    html = render_delta_html(built_delta(before, after), source_link_template=None)
    assert embedded_app_data(html)['module_changes'] == {
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
    context = delta_render_context(built_delta(before, after))
    assert context['change_counts'] == {'added': 2, 'changed': 1, 'removed': 1}
    assert context['unchanged_count'] == 1


def test_a_search_matches_either_side_s_title_and_a_removed_tag() -> None:
    before = report(scn('t.py::test_pay', 'Pay at the desk', tags=['legacy']))
    after = report(scn('t.py::test_pay', 'Pay online'))
    data = embedded_app_data(render_delta_html(built_delta(before, after), None))
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
    [item] = _listed(built_delta(before, after))
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
    [item] = _listed(built_delta(before, after))
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
    delta = built_delta(before, after)
    data = embedded_app_data(render_delta_html(delta, None))
    # A term only the before side has can't be read otherwise by the after
    # one, so it stands with the after terms, where the Terms axis names it.
    # A before term reading otherwise than the after one of its ID follows,
    # keyed apart.
    assert [
        (entry['id'], entry['canonical'], entry['definition'])
        for entry in data['glossary']['terms']
    ] == [
        ('guest', 'Visitor', None),
        ('desk', 'Desk', 'Front desk.'),
        ('bill', 'Bill', 'New.'),
        ('room', 'Room', None),
        ('before:guest', 'Guest', None),
        ('before:bill', 'Bill', 'Old.'),
    ]
    targets = term_ref_targets(delta)
    assert [
        targets['before'](TermId(term_id)).tip for term_id in ('guest', 'desk', 'room')
    ] == ['before:guest', 'desk', 'room']
    assert targets['after'](TermId('guest')).tip == 'guest'


def test_a_term_ref_opens_the_card_of_the_side_it_was_read_on_if_one_is_listed() -> (
    None
):
    """An unchanged term has no card to open."""
    before = report(
        scn('t.py::test_stay', 'Stay', step('given', narr(ref('guest', 'a guest')))),
        glossary=Glossary(terms=[term('guest', 'Guest'), term('desk', 'Desk')]),
    )
    after = report(
        scn(
            't.py::test_stay', 'Stay', step('given', narr(ref('visitor', 'a visitor')))
        ),
        glossary=Glossary(terms=[term('visitor', 'Visitor'), term('desk', 'Desk')]),
    )
    targets = term_ref_targets(built_delta(before, after))
    assert [
        (side, term_id, targets[side](TermId(term_id)).entry)
        for side, term_id in (
            ('before', 'guest'),
            ('after', 'visitor'),
            ('before', 'desk'),
            ('after', 'desk'),
        )
    ] == [
        ('before', 'guest', 'removed:guest'),
        ('after', 'visitor', 'visitor'),
        ('before', 'desk', None),
        ('after', 'desk', None),
    ]


def test_a_modified_step_reads_its_markdown_as_the_whole_line_does() -> None:
    """Only the term ref changed, so the literal after it is a run of its own."""
    before = report(
        scn(
            't.py::test_a',
            'A',
            step('given', narr(ref('guest', 'guest'), lit('*"x"* y'))),
        ),
        glossary=Glossary(terms=[term('guest', 'Guest')]),
    )
    after = report(
        scn(
            't.py::test_a',
            'A',
            step('given', narr(ref('host', 'host'), lit('*"x"* y'))),
        ),
        glossary=Glossary(terms=[term('host', 'Host')]),
    )
    html = render_delta_html(built_delta(before, after), None)
    assert html.count('*&#34;x&#34;* y') == 2
    assert '&#34;x&#34;</em>' not in html


def test_the_change_glyphs_reach_delta_js_in_the_model_s_change_order() -> None:
    """`delta.js` reads its changes' order off the glyphs' keys."""
    data = embedded_app_data(render_delta_html(built_delta(report(), report()), None))
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
    delta = built_delta(before, after)
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
    targets = term_ref_targets(delta)
    assert (
        targets['before'](TermId('room')).entry,
        targets['after'](TermId('suite')).entry,
    ) == ('suite', 'suite')


def test_a_term_whose_kind_changed_is_listed_under_each_kind() -> None:
    before = report(glossary=Glossary(terms=[term('upgrade', 'Upgrade', 'object')]))
    after = report(glossary=Glossary(terms=[term('upgrade', 'upgrade', 'activity')]))
    view = _glossary(built_delta(before, after))
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
    keys = [card.key for card in _glossary(built_delta(before, after)).listed]
    assert len(set(keys)) == len(keys) == 2


def test_a_side_without_a_glossary_lists_the_other_side_s_terms() -> None:
    """And a delta that changed no term has no Glossary tab."""
    with_terms = report(glossary=Glossary(terms=[term('desk', 'Desk')]))
    without = report(scn('t.py::test_new', 'New'))
    for before, after, change in (
        (with_terms, without, 'removed'),
        (without, with_terms, 'added'),
    ):
        data = embedded_app_data(render_delta_html(built_delta(before, after), None))
        [card] = data['term_rows']
        assert (card['change'], data['expandable_term_ids']) == (change, [card['key']])
        assert data['views'] == ['scenarios', 'glossary']
        assert [entry['id'] for entry in data['glossary']['terms']] == ['desk']
    unchanged = embedded_app_data(
        render_delta_html(built_delta(with_terms, with_terms), None)
    )
    assert unchanged['expandable_term_ids'] == []
    assert unchanged['views'] == ['scenarios']


def test_added_and_removed_scenarios_read_their_steps_unmarked() -> None:
    before = report(scn('t.py::test_old', 'Old', step('given', 'a guest')))
    after = report(scn('t.py::test_new', 'New', step('given', 'a host')))
    assert [item.steps for item in _listed(built_delta(before, after))] == [None, None]


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
    delta = built_delta(before, after)
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
    [item] = _listed(built_delta(before, after))
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

    html = render_delta_html(built_delta(paying(1), paying(2)), None)
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
            step('when', narr(lit('she pays a fee of '), ph('fee', 'derived:0'))),
            parameters=table(
                [('reason', 'param'), ('fee', 'derived'), ('receipt', 'attachment')],
                ('t.py::test_pay[a]', ['expired', '12', receipt]),
                ('t.py::test_pay[b]', ['blocked', '8', receipt]),
            ),
        )
    )
    [item] = _listed(built_delta(before, after))
    assert item.table is not None
    before_side, after_side = item.table.sides
    assert _columns(before_side) == [
        ('reason', None, None),
        ('before:derived:0', 'removed', None),
        ('attachment:0', None, None),
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
    ] == ['attachment:0']


def test_no_before_column_id_outlives_the_page_keys_wherever_the_delta_holds_one():
    """Every field typed as a column ID is walked, so a field added later that
    `_BeforeKeys` misses fails here rather than unpairing hover in the page."""
    before = report(
        scn(
            't.py::test_pay',
            'Pay',
            step('when', narr(lit('she pays because of '), ph('decline_reason'))),
            parameters=table(
                [('decline_reason', 'param')], ('t.py::test_pay[a]', ['expired'])
            ),
        )
    )
    after = report(
        scn(
            't.py::test_pay',
            'Pay',
            step('when', narr(lit('she is refused because of '), ph('reason'))),
            parameters=table([('reason', 'param')], ('t.py::test_pay[a]', ['expired'])),
        )
    )
    delta = built_delta(before, after)
    [item] = _listed(delta)
    assert 'decline_reason' in set(_column_ids(delta.scenarios[0]))
    assert 'decline_reason' not in set(_column_ids(item.delta))


def _column_ids(value: object) -> Iterator[str]:
    """The value of every field typed as a column ID, anywhere in `value`."""
    if isinstance(value, (list, tuple)):
        for element in value:
            yield from _column_ids(element)
        return
    if not dataclasses.is_dataclass(value) or isinstance(value, type):
        return
    hints = typing.get_type_hints(type(value))
    for field in dataclasses.fields(value):
        field_value = getattr(value, field.name)
        if not _names_column_id(hints[field.name]):
            yield from _column_ids(field_value)
        elif isinstance(field_value, tuple):
            yield from field_value
        elif field_value is not None:
            yield field_value


def _names_column_id(hint: object) -> bool:
    return hint is ColumnId or any(
        _names_column_id(arg) for arg in typing.get_args(hint)
    )


def test_a_changed_table_s_attachment_column_of_another_name_keeps_its_own_key():
    """Attachment IDs are positional, so one ID can name another attachment on
    the other side: only the name tells them apart."""
    payload = Attachment(label='payload', content='paid')

    def side(amount: int, name: str) -> ReportData:
        return report(
            scn(
                't.py::test_pay',
                'Pay',
                parameters=table(
                    [('amount', 'param'), (name, 'attachment')],
                    ('t.py::test_pay[a]', [amount, payload]),
                ),
            )
        )

    [item] = _listed(built_delta(side(1, 'receipt'), side(2, 'invoice')))
    assert item.table is not None
    before_side, after_side = item.table.sides
    assert _columns(before_side)[1][0] == 'before:attachment:0'
    assert _columns(after_side)[1][0] == 'attachment:0'


def test_an_attachment_column_that_changed_position_keeps_its_after_key():
    payload = Attachment(label='payload', content='paid')
    before = report(
        scn(
            't.py::test_pay',
            'Pay',
            parameters=table(
                [('amount', 'param'), ('receipt', 'attachment')],
                ('t.py::test_pay[a]', [1, payload]),
            ),
        )
    )
    after = report(
        scn(
            't.py::test_pay',
            'Pay',
            parameters=table(
                [
                    ('amount', 'param'),
                    ('invoice', 'attachment'),
                    ('receipt', 'attachment'),
                ],
                ('t.py::test_pay[a]', [2, payload, payload]),
            ),
        )
    )
    [item] = _listed(built_delta(before, after))
    assert item.table is not None
    before_side, after_side = item.table.sides
    assert _columns(before_side) == [
        ('amount', None, None),
        ('attachment:1', None, None),
    ]
    assert _columns(after_side) == [
        ('amount', None, None),
        ('attachment:0', 'added', None),
        ('attachment:1', None, None),
    ]


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

    [item] = _listed(built_delta(side('she pays for '), side('she settles for ')))
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
    status_only, unchanged = _listed(built_delta(before, after))
    assert status_only.table is not None
    assert [side.side for side in status_only.table.sides] == ['before', 'after']
    assert [row.change for row in status_only.table.rows] == ['changed']
    assert unchanged.table is None


def test_a_table_gained_or_lost_with_its_parametrization_shows_alone():
    def unparametrized(name: str) -> Scenario:
        return scn(f't.py::test_{name}', name, step('when', 'she pays'))

    before = report(unparametrized('gains'), _paying('loses', [1, 2]))
    after = report(_paying('gains', [1, 2]), unparametrized('loses'))
    gains, loses = (item.table for item in _listed(built_delta(before, after)))
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
    [item] = _listed(built_delta(before, after))
    assert item.table is not None
    assert [side.column_blocks for side in item.table.sides] == [
        {'amount': '0', 'before:deposit': 'before:1'},
        {'amount': '0', 'fee': '1'},
    ]


def test_each_side_s_table_knows_the_columns_its_own_steps_narrate_as_a_repr() -> None:
    before = report(
        scn(
            't.py::test_pay',
            'Pay',
            step(
                'given',
                narr(
                    NarrationPlaceholder(
                        name='code', column_id=ColumnId('code'), conversion='r'
                    )
                ),
            ),
            parameters=table([('code', 'param')], ('t.py::test_pay[a]', ['x'])),
        )
    )
    after = report(
        scn(
            't.py::test_pay',
            'Pay',
            step('given', narr(ph('code'))),
            parameters=table([('code', 'param')], ('t.py::test_pay[a]', ['y'])),
        )
    )
    [item] = _listed(built_delta(before, after))
    assert item.table is not None
    assert [side.repr_columns for side in item.table.sides] == [{'code'}, set()]


def test_each_scenario_lists_where_it_changed_and_each_part_counts_its_scenarios():
    receipt = dataclasses.replace(
        step('given', 'a receipt'), attachments=[Attachment(label='r', content='old')]
    )
    changed_receipt = dataclasses.replace(
        step('given', 'the receipt'),
        attachments=[Attachment(label='r', content='new')],
    )
    before = report(
        scn('t.py::test_a', 'Same title', receipt),
        scn('t.py::test_b', 'Old title'),
        scn('t.py::test_c', 'Gone'),
    )
    after = report(
        scn('t.py::test_a', 'Same title', changed_receipt),
        scn('t.py::test_b', 'New title'),
        scn('t.py::test_d', 'New'),
    )
    delta = built_delta(before, after)
    data = embedded_app_data(render_delta_html(delta, None))
    assert {entry['id']: entry['changed_in'] for entry in data['scenarios']} == {
        't/a': ['steps', 'attachments'],
        't/b': ['title'],
        'removed:t/c': [],
        't/d': [],
    }
    assert data['changed_parts'] == [
        'title',
        'steps',
        'tags',
        'status',
        'parameters',
        'attachments',
    ]
    assert delta_render_context(delta)['changed_in_counts'] == {
        'title': 1,
        'steps': 1,
        'tags': 0,
        'status': 0,
        'parameters': 0,
        'attachments': 1,
    }


def test_a_changed_attachment_cell_marks_its_cell_and_carries_its_line_diff():
    def built(content: str) -> ReportData:
        return report(
            scn(
                't.py::test_pay',
                'Pay',
                parameters=table(
                    [('amount', 'param'), ('receipt', 'attachment')],
                    ('t.py::test_pay[a]', [1, Attachment(label='r', content=content)]),
                ),
            )
        )

    [item] = _listed(built_delta(built('a\nb'), built('a\nc')))
    assert item.table is not None
    [row] = item.table.rows
    assert row.change == 'changed'
    assert [
        (line.change, line.before, line.after)
        for line in row.attachment_diffs['attachment:0']
        if isinstance(line, LineRow)
    ] == [('equal', 'a', 'a'), ('removed', 'b', None), ('added', None, 'c')]
    marks = [
        [mark for _, _, _, mark in side.cells(case, row.pair)]
        for side, case in zip(
            item.table.sides, (row.before_case, row.after_case), strict=True
        )
        if case is not None
    ]
    assert marks == [[None, 'removed'], [None, 'added']]


def test_a_removed_attachment_column_leaves_the_diff_on_the_paired_column_s_content():
    log = Attachment(label='log', content='log')
    before = report(
        scn(
            't.py::test_pay',
            'Pay',
            parameters=table(
                [('log', 'attachment'), ('invoice', 'attachment')],
                ('t.py::test_pay[a]', [log, Attachment(label='i', content='a\nb')]),
            ),
        )
    )
    after = report(
        scn(
            't.py::test_pay',
            'Pay',
            parameters=table(
                [('invoice', 'attachment')],
                ('t.py::test_pay[a]', [Attachment(label='i', content='a\nc')]),
            ),
        )
    )
    [item] = _listed(built_delta(before, after))
    assert item.table is not None
    [row] = item.table.rows
    assert [
        (line.change, line.before, line.after)
        for line in row.attachment_diffs['attachment:0']
        if isinstance(line, LineRow)
    ] == [('equal', 'a', 'a'), ('removed', 'b', None), ('added', None, 'c')]


def test_a_cell_changed_in_content_type_only_carries_a_diff_without_lines():
    """Its badge then opens on both sides, as a step attachment's does."""

    def built(content_type: ContentType) -> ReportData:
        cell = Attachment(label='r', content='{}', content_type=content_type)
        return report(
            scn(
                't.py::test_pay',
                'Pay',
                parameters=table(
                    [('amount', 'param'), ('receipt', 'attachment')],
                    ('t.py::test_pay[a]', [1, cell]),
                ),
            )
        )

    [item] = _listed(built_delta(built('json'), built('text')))
    assert item.table is not None
    [row] = item.table.rows
    assert row.attachment_diffs == {'attachment:0': ()}


def test_an_attachment_cell_a_side_lacks_diffs_as_all_added_lines():
    def side(cell: Attachment | None) -> ReportData:
        return report(
            scn(
                't.py::test_pay',
                'Pay',
                parameters=table(
                    [('amount', 'param'), ('receipt', 'attachment')],
                    ('t.py::test_pay[a]', [1, cell]),
                ),
            )
        )

    [item] = _listed(
        built_delta(side(None), side(Attachment(label='r', content='a\nb')))
    )
    assert item.table is not None
    [row] = item.table.rows
    assert [
        (line.change, line.before, line.after)
        for line in row.attachment_diffs['attachment:0']
        if isinstance(line, LineRow)
    ] == [('added', None, 'a'), ('added', None, 'b')]


def test_each_side_of_a_changed_line_reads_its_own_words_escaped():
    """A space alone between two of a side's changes joins them, as a step's
    narration diff does, and the line's text reads literally."""
    words = (
        TextSegment(mark='equal', text='<b>*x*</b> '),
        TextSegment(mark='removed', text='15'),
        TextSegment(mark='added', text='14'),
        TextSegment(mark='equal', text=' '),
        TextSegment(mark='removed', text='pm'),
        TextSegment(mark='added', text='h'),
    )

    def read(side: Side) -> tuple[str, list[str]]:
        rendered = str(text_diff(words, side))
        elements = re.findall(r'<(\w+)[^>]*>(.*?)</\1>', rendered)
        marked = [html.unescape(text) for _, text in elements]
        return html.unescape(re.sub(r'<[^>]+>', '', rendered)), marked

    assert read('before') == ('<b>*x*</b> 15 pm', ['15 pm'])
    assert read('after') == ('<b>*x*</b> 14 h', ['14 h'])
