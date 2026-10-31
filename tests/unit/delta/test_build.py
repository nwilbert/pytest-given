"""Building a delta: scenario identities, pairing, what counts as a change."""

import dataclasses
from collections.abc import Sequence

import pytest

from pytest_given import given, scenario, then, when
from pytest_given.delta import (
    DeltaInputs,
    DeltaResult,
    RenameEntry,
    RenameLog,
    build_delta,
    check_reports,
    comparable_title,
    is_per_case,
    scenario_identity,
)
from pytest_given.model import (
    REPORT_SCHEMA_VERSION,
    Attachment,
    AttachmentLabel,
    DeltaData,
    ErrorInfo,
    Glossary,
    IdentityPair,
    NarrationValue,
    NodeId,
    Pin,
    PytestGivenError,
    ReportData,
    Scenario,
    ScenarioDelta,
    SentenceId,
    SourceLocation,
    StoryId,
)
from tests.ubiquitous_language import pg
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


def _delta(
    before: ReportData,
    after: ReportData,
    *moves: RenameEntry,
    before_label: str | None = None,
) -> DeltaResult:
    return build_delta(
        DeltaInputs(
            before=before,
            after=after,
            renames=RenameLog(entries=moves),
            before_label=before_label,
            plugin_version='0.9.0',
            timestamp='2026-10-31T00:00:00+00:00',
        )
    )


def _move(
    old: str, new: str | None, cases: tuple[tuple[str, str], ...] = ()
) -> RenameEntry:
    return RenameEntry(table='scenario', position=1, old=old, new=new, cases=cases)


def _per_case(node_id: str, title: str, tags: Sequence[str] = ()) -> Scenario:
    """A case of a scenario with `group_parametrized` off: its title ends in
    its case ID, as grouping appends it."""
    case = node_id[node_id.index('[') + 1 : -1]
    titled = narr(
        lit(title),
        lit(' ['),
        NarrationValue(rendered=case, expression=''),
        lit(']'),
    )
    return scn(node_id, titled, tags=tags)


def _rows(delta: DeltaData) -> list[tuple[str, str | None, str | None]]:
    return [
        (
            scenario_delta.change,
            scenario_delta.before.id if scenario_delta.before else None,
            scenario_delta.after.id if scenario_delta.after else None,
        )
        for scenario_delta in delta.scenarios
    ]


def _pairs(delta: DeltaData) -> list[tuple[str, str]]:
    return [(pair.before, pair.after) for pair in delta.unchanged]


@scenario(
    t"A grouped scenario's {pg['Scenario identity'].l} survives its first "
    t'{pg["Case"].l} changing',
    tags=['delta'],
)
def test_a_grouped_identity_survives_its_first_case_changing() -> None:
    with given(
        t'a grouped scenario whose first {pg["Case"].l} is `t[1]` before and a new '
        t'`t[0]` after'
    ):
        before = report(
            scn(
                't.py::t[1]',
                'Counts',
                parameters=table([('n', 'param')], ('t.py::t[1]', [1])),
            )
        )
        after = report(
            scn(
                't.py::t[0]',
                'Counts',
                parameters=table(
                    [('n', 'param')], ('t.py::t[0]', [0]), ('t.py::t[1]', [1])
                ),
            )
        )
    with when(t'a {pg["Delta report"].l} is built'):
        delta = _delta(before, after).delta
    with then(t'both sides have the {pg["Scenario identity"].l} `t.py::t`'):
        assert scenario_identity(before.scenarios[0]) == 't.py::t'
        assert scenario_identity(after.scenarios[0]) == 't.py::t'
    with then('the two pair by it, changed by the added case'):
        (changed,) = delta.scenarios
        assert (changed.change, changed.paired_by) == ('changed', 'node-id')
        assert changed.parameters is not None
        assert [(case.before, case.after) for case in changed.parameters.cases] == [
            (None, 't.py::t[0]'),
            ('t.py::t[1]', 't.py::t[1]'),
        ]


@scenario(
    t"A {pg['Per-case scenario'].l}'s {pg['Scenario identity'].l} is its full "
    t'{pg["Node ID"].l}',
    tags=['delta'],
)
def test_a_per_case_identity_is_its_full_node_id() -> None:
    with given(
        t'{pg["Per-case scenario"].l.s} `t[a]` and `t[b]`, and a `t[c]` only after'
    ):
        before = report(
            _per_case('t.py::t[a]', 'Cases'), _per_case('t.py::t[b]', 'Cases')
        )
        after = report(
            _per_case('t.py::t[a]', 'Cases'),
            _per_case('t.py::t[b]', 'Cases'),
            _per_case('t.py::t[c]', 'Cases'),
        )
    with when(t'a {pg["Delta report"].l} is built'):
        delta = _delta(before, after).delta
    with then('`t[a]` and `t[b]` are unchanged, each under its own node ID'):
        assert _pairs(delta) == [
            ('t.py::t[a]', 't.py::t[a]'),
            ('t.py::t[b]', 't.py::t[b]'),
        ]
    with then('`t[c]` is added'):
        assert _rows(delta) == [('added', None, 't.py::t[c]')]


@scenario(
    t'A moved test file pairs by its unique {pg["Scenario title"].l}',
    tags=['delta'],
)
def test_a_moved_test_file_pairs_by_its_unique_title() -> None:
    with given(
        t'a scenario moved from `a.py` to `b.py` with its {pg["Scenario title"].l} '
        t'kept and a tag added'
    ):
        before = report(scn('a.py::t', 'Pays the bill'))
        moved = scn('b.py::t', 'Pays the bill', tags=['billing'])
    with when(t'a {pg["Delta report"].l} is built'):
        delta = _delta(before, report(moved)).delta
    with then(t'the two pair by {pg["Scenario title"].l}'):
        (changed,) = delta.scenarios
        assert (changed.change, changed.paired_by) == ('changed', 'title')
        assert changed.tags_added == ('billing',)
    with when(t'a second after scenario has the same {pg["Scenario title"].l}'):
        twice = report(moved, scn('c.py::t', 'Pays the bill'))
        ambiguous = _delta(before, twice).delta
    with then('nothing pairs: the old one is removed and both new ones added'):
        assert _rows(ambiguous) == [
            ('removed', 'a.py::t', None),
            ('added', None, 'b.py::t'),
            ('added', None, 'c.py::t'),
        ]


@scenario(
    t'{pg["Pairing"]} on the rewritten {pg["Scenario identity"].l} keeps a '
    t'reused ID honest',
    tags=['delta'],
)
def test_pairing_on_the_rewritten_identity_keeps_a_reused_id_honest() -> None:
    with given(t'a {pg["Rename log"].l} entry renaming `A` to `B`'):
        renamed = _move('t.py::A', 't.py::B')
    with given(
        'before holds `A`, after holds `B` and a new test that took the name `A`'
    ):
        before = report(scn('t.py::A', 'Books a room'))
        after = report(
            scn('t.py::A', 'Sends a receipt'), scn('t.py::B', 'Books a suite')
        )
    with when(t'a {pg["Delta report"].l} is built'):
        delta = _delta(before, after, renamed).delta
    with then('the old `A` pairs with `B` through the rename log'):
        added, changed = delta.scenarios
        assert (changed.before, changed.after) == (
            before.scenarios[0],
            after.scenarios[1],
        )
        assert changed.paired_by == 'rename-log'
    with then('the new `A` is added'):
        assert (added.change, added.after) == ('added', after.scenarios[0])


@scenario(
    t"What doesn't make a scenario changed in a {pg['Delta report'].l}",
    tags=['delta'],
)
def test_what_does_not_make_a_scenario_changed() -> None:
    with given(
        t'a parametrized scenario, moved and renamed through the {pg["Rename log"].l}'
    ):
        renamed = _move('a.py::t', 'b.py::u')
        before = report(
            scn(
                'a.py::t[1]',
                'Prints',
                step('given', 'a page'),
                parameters=table(
                    [('n', 'param'), ('page', 'attachment')],
                    ('a.py::t[1]', [1, Attachment(AttachmentLabel('page'), 'one')]),
                ),
            )
        )
    with given(
        'its after side differs in module, source, duration, error message, '
        'fixture name, story IDs, pins, attachments and an attachment column'
    ):
        original = before.scenarios[0]
        after_step = dataclasses.replace(
            original.steps[0],
            fixture_name='page',
            attachments=[Attachment(AttachmentLabel('log'), 'text')],
            pins=(Pin(story_id=StoryId('s'), sentence_id=SentenceId(1)),),
        )
        after = report(
            dataclasses.replace(
                original,
                id=NodeId('b.py::u[1]'),
                module='b',
                source=SourceLocation('b.py', 9),
                duration_ms=99,
                error=ErrorInfo(message='flaky'),
                story_ids=(StoryId('s'),),
                pins=(Pin(story_id=StoryId('s'), sentence_id=SentenceId(2)),),
                steps=[after_step],
                parameters=table(
                    [('n', 'param'), ('page', 'attachment')],
                    ('b.py::u[1]', [1, Attachment(AttachmentLabel('page'), 'two')]),
                ),
            )
        )
    with when(t'a {pg["Delta report"].l} is built'):
        delta = _delta(before, after, renamed).delta
    with then('the scenario is unchanged and nothing is listed'):
        assert delta.scenarios == ()
        assert _pairs(delta) == [('a.py::t', 'b.py::u')]


@scenario(
    t'What makes a scenario changed in a {pg["Delta report"].l}',
    tags=['delta'],
)
def test_what_makes_a_scenario_changed() -> None:
    with given(
        'six scenarios whose after sides each differ in one of title, step, tag, '
        'status, reason and parameter table'
    ):
        cases = table([('n', 'param')], ('t.py::table[1]', [1]))
        before = report(
            scn('t.py::title', 'Old title'),
            scn('t.py::step', 'Steps', step('given', 'a room')),
            scn('t.py::tag', 'Tags', tags=['a']),
            scn('t.py::status', 'Status'),
            dataclasses.replace(scn('t.py::reason', 'Reason'), skip_reason='slow'),
            scn('t.py::table[1]', 'Table', parameters=cases),
        )
        after = report(
            scn('t.py::title', 'New title'),
            scn('t.py::step', 'Steps', step('given', 'a suite')),
            scn('t.py::tag', 'Tags', tags=['b']),
            scn('t.py::status', 'Status', status='failed'),
            dataclasses.replace(scn('t.py::reason', 'Reason'), skip_reason='flaky'),
            scn(
                't.py::table[1]',
                'Table',
                parameters=table([('n', 'param')], ('t.py::table[1]', [2])),
            ),
        )
    with when(t'a {pg["Delta report"].l} is built'):
        title, steps, tags, status, reason, parameters = _delta(
            before, after
        ).delta.scenarios
    with then('each is changed, with the flag of what differs'):
        assert all(
            listed.change == 'changed'
            for listed in (title, steps, tags, status, reason, parameters)
        )
        assert title.title_changed
        assert [step_delta.change for step_delta in steps.steps] == ['modified']
        assert (tags.tags_added, tags.tags_removed) == (('b',), ('a',))
        assert status.status_changed
        assert reason.reason_changed
        assert parameters.parameters is not None
        assert parameters.parameters.changed


@scenario(
    t'A schema version mismatch is refused, naming both versions',
    tags=['delta'],
)
def test_a_schema_version_mismatch_is_refused_naming_both_versions() -> None:
    with given(
        'a before report at the current schema version and an after report without one'
    ):
        before = _versioned(REPORT_SCHEMA_VERSION)
        after = _versioned(None)
    with when('the reports are checked'), pytest.raises(PytestGivenError) as raised:
        check_reports(before, after, 'before.json', 'after.json')
    with then('the error names both versions and points at the delta skill'):
        message = str(raised.value)
        assert f'{REPORT_SCHEMA_VERSION}' in message
        assert 'none' in message
        assert 'pytest-given-delta' in message


def _versioned(schema_version: int | None, **overrides: object) -> ReportData:
    return ReportData(metadata=meta(schema_version=schema_version, **overrides))


def test_matching_schema_versions_pass_without_warnings() -> None:
    current = _versioned(REPORT_SCHEMA_VERSION)

    assert check_reports(current, current, 'a.json', 'b.json') == ()


def test_a_before_report_at_another_schema_version_is_refused() -> None:
    with pytest.raises(PytestGivenError, match=r'old\.json.*0'):
        check_reports(
            _versioned(0), _versioned(REPORT_SCHEMA_VERSION), 'old.json', 'new.json'
        )


def test_different_plugin_and_pytest_versions_each_warn_naming_both() -> None:
    before = _versioned(REPORT_SCHEMA_VERSION)
    after = _versioned(
        REPORT_SCHEMA_VERSION, plugin_version='0.2.0', pytest_version='9.2.0'
    )

    plugin, pytest_warning = check_reports(before, after, 'a.json', 'b.json')

    assert '0.1.0' in plugin
    assert '0.2.0' in plugin
    assert '9.0.0' in pytest_warning
    assert '9.2.0' in pytest_warning


def test_identical_reports_list_nothing_and_keep_every_pair_unchanged() -> None:
    glossary = Glossary([term('room', 'Room')])
    same = report(
        scn('t.py::a', narr(lit('Books a '), ref('room', 'room'))),
        scn('t.py::b[1]', 'B', parameters=table([('n', 'param')], ('t.py::b[1]', [1]))),
        _per_case('t.py::c[x]', 'C'),
        glossary=glossary,
    )

    delta = _delta(same, same).delta

    assert delta.scenarios == ()
    assert _pairs(delta) == [
        ('t.py::a', 't.py::a'),
        ('t.py::b', 't.py::b'),
        ('t.py::c[x]', 't.py::c[x]'),
    ]
    assert delta.glossary.terms == ()
    assert delta.suggestions == ()


def test_a_before_report_without_a_glossary_compares_against_one_with() -> None:
    before = report(scn('t.py::a', 'Books a room'))
    after = report(
        scn('t.py::a', narr(lit('Books a '), ref('room', 'room'))),
        glossary=Glossary([term('room', 'Room')]),
    )

    result = _delta(before, after)

    assert _rows(result.delta) == [('changed', 't.py::a', 't.py::a')]
    assert [term_delta.change for term_delta in result.delta.glossary.terms] == [
        'added'
    ]
    assert result.delta.glossary.before is None
    assert result.warnings == ()


def test_scenarios_follow_the_after_order_with_removed_ones_in_place() -> None:
    before = report(scn('t.py::a', 'A'), scn('t.py::gone', 'Gone'), scn('t.py::c', 'C'))
    after = report(scn('t.py::new', 'New'), scn('t.py::a', 'A2'), scn('t.py::c', 'C2'))

    delta = _delta(before, after).delta

    assert _rows(delta) == [
        ('added', None, 't.py::new'),
        ('changed', 't.py::a', 't.py::a'),
        ('removed', 't.py::gone', None),
        ('changed', 't.py::c', 't.py::c'),
    ]


def test_duplicate_identities_never_pair_one_after_scenario_twice() -> None:
    before = report(scn('t.py::a', 'A'), scn('t.py::a', 'A'))
    after = report(scn('t.py::a', 'A'))

    delta = _delta(before, after).delta

    assert _pairs(delta) == [('t.py::a', 't.py::a')]
    assert _rows(delta) == [('removed', 't.py::a', None)]


def test_a_title_pairing_rewrites_term_refs_and_reads_placeholders_by_name() -> None:
    before = report(
        scn(
            'a.py::t[1]',
            narr(lit('A '), ref('guest', 'guest'), lit(' pays '), ph('price')),
            parameters=table([('price', 'param')], ('a.py::t[1]', [1])),
        ),
        glossary=Glossary([term('guest', 'Guest')]),
    )
    after = report(
        scn(
            'b.py::t[1]',
            narr(lit('A '), ref('visitor', 'visitor'), lit(' pays '), ph('price')),
            parameters=table([('price', 'param')], ('b.py::t[1]', [1])),
        ),
        glossary=Glossary([term('visitor', 'Visitor')]),
    )
    log = RenameEntry(table='term', position=1, old='guest', new='visitor')

    delta = _delta(before, after, log).delta

    assert delta.scenarios == ()
    assert _pairs(delta) == [('a.py::t', 'b.py::t')]


def test_a_title_equal_on_two_before_scenarios_pairs_neither() -> None:
    before = report(scn('a.py::t', 'Pays  the bill'), scn('a.py::u', 'Pays the  bill'))
    after = report(scn('b.py::t', 'Pays the bill'))

    delta = _delta(before, after).delta

    assert [row[0] for row in _rows(delta)] == ['removed', 'removed', 'added']


def test_a_title_whose_term_ref_reads_in_another_form_does_not_pair() -> None:
    glossary = Glossary([term('room', 'Room')])
    before = report(
        scn('a.py::t', narr(lit('Books '), ref('room', 'rooms'))), glossary=glossary
    )
    after = report(
        scn('b.py::t', narr(lit('Books '), ref('room', 'room'))), glossary=glossary
    )

    delta = _delta(before, after).delta

    assert [row[0] for row in _rows(delta)] == ['removed', 'added']


def test_a_renamed_column_keeps_its_placeholders_equal() -> None:
    before = report(
        scn(
            't.py::t[1]',
            'Prices',
            step('given', narr(lit('a price of '), ph('cost'))),
            parameters=table([('cost', 'param')], ('t.py::t[1]', [1])),
        )
    )
    after = report(
        scn(
            't.py::t[1]',
            'Prices',
            step('given', narr(lit('a price of '), ph('price'))),
            parameters=table([('price', 'param')], ('t.py::t[1]', [1])),
        )
    )

    (changed,) = _delta(before, after).delta.scenarios

    assert [step_delta.change for step_delta in changed.steps] == ['equal']
    assert changed.parameters is not None
    assert [column.paired_by for column in changed.parameters.columns] == ['values']


def test_a_placeholder_of_an_unpaired_column_reads_as_changed() -> None:
    before = report(
        scn(
            't.py::t[1]',
            'Prices',
            step('given', narr(lit('a price of '), ph('cost'))),
            parameters=table(
                [('cost', 'param'), ('size', 'param')], ('t.py::t[1]', [1, 2])
            ),
        )
    )
    after = report(
        scn(
            't.py::t[1]',
            'Prices',
            step('given', narr(lit('a price of '), ph('price'))),
            parameters=table(
                [('price', 'param'), ('weight', 'param')], ('t.py::t[1]', [3, 4])
            ),
        )
    )

    (changed,) = _delta(before, after).delta.scenarios

    assert [step_delta.change for step_delta in changed.steps] == ['modified']


def test_a_table_on_one_side_only_is_a_change() -> None:
    before = report(scn('t.py::t', 'Counts'))
    after = report(
        scn(
            't.py::t[1]',
            'Counts',
            parameters=table([('n', 'param')], ('t.py::t[1]', [1])),
        )
    )

    (changed,) = _delta(before, after).delta.scenarios

    assert (changed.change, changed.paired_by, changed.parameters) == (
        'changed',
        'node-id',
        None,
    )


def test_a_cases_map_pairs_cases_of_a_grouped_scenario() -> None:
    before = report(
        scn('t.py::t[x]', 'T', parameters=table([('n', 'param')], ('t.py::t[x]', [1])))
    )
    after = report(
        scn('t.py::t[y]', 'T', parameters=table([('n', 'param')], ('t.py::t[y]', [2])))
    )

    (changed,) = _delta(
        before, after, _move('t.py::t', None, (('x', 'y'),))
    ).delta.scenarios

    assert changed.paired_by == 'node-id'
    assert changed.parameters is not None
    (case,) = changed.parameters.cases
    assert (case.before, case.after, case.paired_by) == (
        't.py::t[x]',
        't.py::t[y]',
        'rename-log',
    )


def test_a_per_case_scenario_follows_its_base_and_case_through_the_log() -> None:
    before = report(_per_case('t.py::t[x]', 'Cases'))
    after = report(_per_case('t.py::u[y]', 'Cases'), _per_case('t.py::u[z]', 'Cases'))

    delta = _delta(before, after, _move('t.py::t', 't.py::u', (('x', 'y'),))).delta

    assert _pairs(delta) == [('t.py::t[x]', 't.py::u[y]')]
    assert _rows(delta) == [('added', None, 't.py::u[z]')]


def test_a_per_case_scenario_whose_case_alone_is_mapped_pairs_by_rename_log() -> None:
    before = report(_per_case('t.py::t[x]', 'Cases', tags=['a']))
    after = report(_per_case('t.py::t[y]', 'Cases'))

    (changed,) = _delta(
        before, after, _move('t.py::t', None, (('x', 'y'),))
    ).delta.scenarios

    assert (changed.paired_by, changed.title_changed) == ('rename-log', False)


def test_a_rename_log_merge_is_warned_and_pairs_nothing_through_it() -> None:
    before = report(scn('t.py::a', 'A'), scn('t.py::b', 'B'))
    after = report(scn('t.py::c', 'C'))

    result = _delta(
        before, after, _move('t.py::a', 't.py::c'), _move('t.py::b', 't.py::c')
    )

    assert [row[0] for row in _rows(result.delta)] == ['removed', 'removed', 'added']
    (warning,) = result.warnings
    assert '"t.py::c"' in warning


def test_each_side_carries_its_metadata_label_and_modules_in_order() -> None:
    before = report(
        scn('b.py::t', 'B'), scn('a.py::t', 'A'), scn('b.py::u', 'U'), sha='abc'
    )
    after = report(scn('c.py::t', 'C'))

    metadata = _delta(before, after, before_label='v1').delta.metadata

    assert metadata.before.metadata == before.metadata
    assert (metadata.before.label, metadata.before.modules) == ('v1', ('b', 'a'))
    assert (metadata.after.label, metadata.after.modules) == (None, ('c',))
    assert (metadata.plugin_version, metadata.timestamp) == (
        '0.9.0',
        '2026-10-31T00:00:00+00:00',
    )


def test_identity_and_per_case_of_each_kind_of_scenario() -> None:
    plain = scn('t.py::t', 'Plain')
    grouped = scn(
        't.py::g[1]', 'Grouped', parameters=table([('n', 'param')], ('t.py::g[1]', [1]))
    )
    per_case = _per_case('t.py::p[1]', 'Per case')

    assert [scenario_identity(item) for item in (plain, grouped, per_case)] == [
        't.py::t',
        't.py::g',
        't.py::p[1]',
    ]
    assert [is_per_case(item) for item in (plain, grouped, per_case)] == [
        False,
        False,
        True,
    ]


def test_a_comparable_title_drops_only_the_case_suffix_grouping_appends() -> None:
    per_case = _per_case('t.py::p[1]', 'Per case')
    lookalike = scn('t.py::q[1]', narr(lit('Per case'), lit(' ['), lit('1'), lit(']')))
    other_value = _per_case('t.py::r[1]', 'Per case')
    other_value.narration = narr(
        lit('Per case'),
        lit(' ['),
        NarrationValue(rendered='2', expression=''),
        lit(']'),
    )
    plain = scn('t.py::t', 'Plain')

    assert comparable_title(per_case) == narr(lit('Per case'))
    assert comparable_title(lookalike) == lookalike.narration
    assert comparable_title(other_value) == other_value.narration
    assert comparable_title(plain) == plain.narration
    assert comparable_title(scn('t.py::s[1]', 'Short')) == narr(lit('Short'))


def test_unchanged_identity_pairs_name_identities_not_node_ids() -> None:
    before = report(
        scn('t.py::t[1]', 'T', parameters=table([('n', 'param')], ('t.py::t[1]', [1])))
    )

    assert _delta(before, before).delta.unchanged == (
        IdentityPair(before='t.py::t', after='t.py::t'),
    )


def test_a_removed_scenario_carries_its_before_side_only() -> None:
    (removed,) = _delta(report(scn('t.py::t', 'T')), report()).delta.scenarios

    assert removed == ScenarioDelta(change='removed', before=scn('t.py::t', 'T'))


def test_a_per_case_title_pairs_only_with_its_case_suffix() -> None:
    before = report(_per_case('t.py::t[a]', 'Cases'), _per_case('t.py::t[b]', 'Cases'))
    after = report(_per_case('t.py::t[b]', 'Cases'), _per_case('t.py::t[c]', 'Cases'))

    delta = _delta(before, after, _move('t.py::t', None, (('a', 'b'),))).delta

    assert _pairs(delta) == [('t.py::t[a]', 't.py::t[b]')]
    assert _rows(delta) == [
        ('removed', 't.py::t[b]', None),
        ('added', None, 't.py::t[c]'),
    ]


def test_a_per_case_scenario_that_became_grouped_is_removed_and_added() -> None:
    before = report(_per_case('t.py::t[1]', 'Counts'))
    after = report(
        scn(
            't.py::t[1]',
            'Counts',
            parameters=table([('n', 'param')], ('t.py::t[1]', [1])),
        )
    )

    delta = _delta(before, after).delta

    assert _rows(delta) == [
        ('removed', 't.py::t[1]', None),
        ('added', None, 't.py::t[1]'),
    ]


def test_a_moved_per_case_scenario_pairs_by_its_title() -> None:
    before = report(_per_case('a.py::t[x]', 'Cases'))
    after = report(_per_case('b.py::t[x]', 'Cases', tags=['moved']))

    (changed,) = _delta(before, after).delta.scenarios

    assert (changed.change, changed.paired_by) == ('changed', 'title')
