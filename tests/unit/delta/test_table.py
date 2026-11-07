"""Pairing a paired scenario's parameter-table columns and cases."""

from pytest_given import given, scenario, then, when
from pytest_given.delta.order import interleaved
from pytest_given.delta.table import align_table
from pytest_given.model import (
    CasePair,
    CellValue,
    ColumnId,
    ColumnPair,
    NodeId,
    ParameterDelta,
    ParameterTable,
)
from tests.ubiquitous_language import pg
from tests.unit.delta.builders import table

_SCENARIO = 't.py::test_order'


def _node(case_id: str) -> NodeId:
    return NodeId(f'{_SCENARIO}[{case_id}]')


def _case(case_id: str, *values: CellValue) -> tuple[str, list[CellValue]]:
    return (_node(case_id), list(values))


def _align(
    before: ParameterTable,
    after: ParameterTable,
    rewrites: dict[str, str] | None = None,
) -> ParameterDelta:
    return align_table(before, after, rewrites or {})


def _case_pairs(alignment: ParameterDelta) -> list[tuple[str, str]]:
    return [
        (
            pair.before.split('[')[1][:-1] if pair.before else '',
            pair.after.split('[')[1][:-1] if pair.after else '',
        )
        for pair in alignment.cases
    ]


@scenario(
    t'An added column keeps the {pg["Parameter table"].l} paired case by case',
    tags=['delta', 'parametrization'],
)
def test_an_added_column_keeps_the_table_paired_case_by_case() -> None:
    with given(
        t'a {pg["Parameter table"].l} of n and big, and one gaining a size column '
        t'that changes every generated {pg["Case ID"].l}'
    ):
        before = table(
            [('n', 'param'), ('big', 'param')],
            _case('1-False', 1, False),
            _case('3-True', 3, True),
        )
        after = table(
            [('n', 'param'), ('size', 'param'), ('big', 'param')],
            _case('1-small-False', 1, 'small', False),
            _case('3-large-True', 3, 'large', True),
        )
    with when('the two are aligned'):
        alignment = _align(before, after)
    with then(
        t'the {pg["Pairing"].l} of both {pg["Case"].l.s} is by their values, '
        t'without a changed cell'
    ):
        assert [pair.paired_by for pair in alignment.cases] == ['values'] * 2
        assert [pair.changed_cells for pair in alignment.cases] == [(), ()]
    with then('the size column is added and the other two pair by name'):
        assert alignment.columns == (
            ColumnPair(before=ColumnId('n'), after=ColumnId('n'), paired_by='name'),
            ColumnPair(after=ColumnId('size')),
            ColumnPair(before=ColumnId('big'), after=ColumnId('big'), paired_by='name'),
        )
    with then('the table changed'):
        assert alignment.changed


@scenario(
    t"An inserted {pg['Case'].l} doesn't shift the positional IDs' pairing",
    tags=['delta', 'parametrization'],
)
def test_an_inserted_case_does_not_shift_the_positional_ids_pairing() -> None:
    with given(
        t'a {pg["Parameter table"].l} of objects A and B with the positional IDs '
        t'order0 and order1, and one with a new object Z in front of them'
    ):
        before = table([('order', 'param')], _case('order0', 'A'), _case('order1', 'B'))
        after = table(
            [('order', 'param')],
            _case('order0', 'Z'),
            _case('order1', 'A'),
            _case('order2', 'B'),
        )
    with when('the two are aligned'):
        alignment = _align(before, after)
    with then('A and B pair by their values, and Z is added'):
        assert _case_pairs(alignment) == [
            ('', 'order0'),
            ('order0', 'order1'),
            ('order1', 'order2'),
        ]
        assert [pair.paired_by for pair in alignment.cases] == [
            None,
            'values',
            'values',
        ]


@scenario(
    t'A renamed argname pairs when its values did not change',
    tags=['delta', 'parametrization'],
)
def test_a_renamed_argname_pairs_when_its_values_did_not_change() -> None:
    with given(
        t'a {pg["Parameter table"].l} with a euros column, and one naming it eur'
    ):
        before = table(
            [('euros', 'param'), ('big', 'param')],
            _case('1-False', 1, False),
            _case('3-True', 3, True),
        )
        after = table(
            [('eur', 'param'), ('big', 'param')],
            _case('1-False', 1, False),
            _case('3-True', 3, True),
        )
    with when('the two are aligned'):
        alignment = _align(before, after)
    with then('euros and eur pair as one column, by their values'):
        assert alignment.columns[0] == ColumnPair(
            before=ColumnId('euros'), after=ColumnId('eur'), paired_by='values'
        )
    with then('the table changed, though no cell did'):
        assert alignment.changed
        assert [pair.changed_cells for pair in alignment.cases] == [(), ()]


@scenario(
    t'A value changed under a generated {pg["Case ID"].l} reads as removed and added',
    tags=['delta', 'parametrization'],
)
def test_a_value_changed_under_a_generated_case_id_reads_as_removed_and_added() -> None:
    with given(t'a {pg["Parameter table"].l} whose case 2-True became 3-True'):
        before = table([('n', 'param'), ('big', 'param')], _case('2-True', 2, True))
        after = table([('n', 'param'), ('big', 'param')], _case('3-True', 3, True))
    with when('the two are aligned, with and without a rename-log rewrite'):
        plain = _align(before, after)
        rewritten = _align(before, after, {'2-True': '3-True'})
    with then('without the rewrite one case is removed and one added'):
        assert _case_pairs(plain) == [('2-True', ''), ('', '3-True')]
    with then('with the rewrite they pair by the rename log, the n cell changed'):
        assert rewritten.cases == (
            CasePair(
                before=_node('2-True'),
                after=_node('3-True'),
                paired_by='rename-log',
                changed_cells=(ColumnId('n'),),
            ),
        )


def test_cells_differ_by_type() -> None:
    before = table(
        [('value', 'param')],
        _case('a', 1),
        _case('b', 1.0),
        _case('c', True),
        custom=True,
    )
    after = table(
        [('value', 'param')],
        _case('a', 1.0),
        _case('b', True),
        _case('c', 1),
        custom=True,
    )
    alignment = _align(before, after)
    assert [pair.changed_cells for pair in alignment.cases] == [
        (ColumnId('value'),)
    ] * 3


def test_a_nan_cell_equals_a_nan_read_separately() -> None:
    before = table([('x', 'param')], _case('x0', float('nan')))
    after = table([('x', 'param')], _case('renamed', float('nan')))

    alignment = _align(before, after)

    assert _case_pairs(alignment) == [('x0', 'renamed')]
    assert [pair.paired_by for pair in alignment.cases] == ['values']
    assert not alignment.changed


def test_a_changed_custom_case_id_is_an_id_change_and_a_generated_one_is_not() -> None:
    before = table(
        [('n', 'param')],
        _case('same-name', 1),
        _case('1', 2),
        custom=True,
    )
    custom = _align(
        before,
        table(
            [('n', 'param')], _case('same-name', 1), _case('renamed', 2), custom=True
        ),
        {'1': 'renamed'},
    )
    generated = _align(
        table([('n', 'param')], _case('1', 1)),
        table([('n', 'param')], _case('x', 1)),
        {'1': 'x'},
    )
    assert [pair.id_changed for pair in custom.cases] == [False, True]
    assert [pair.paired_by for pair in custom.cases] == ['case-id', 'rename-log']
    assert [pair.id_changed for pair in generated.cases] == [False]
    assert not generated.changed


def test_a_status_change_marks_the_case_changed() -> None:
    alignment = _align(
        table([('n', 'param')], (_node('1'), [1], 'passed')),
        table([('n', 'param')], (_node('1'), [1], 'failed')),
    )
    assert alignment.cases[0].status_changed
    assert alignment.changed


def test_moved_columns_and_cases_alone_leave_the_table_unchanged() -> None:
    before = table(
        [('n', 'param'), ('big', 'param')],
        _case('1-False', 1, False),
        _case('3-True', 3, True),
    )
    after = table(
        [('big', 'param'), ('n', 'param')],
        _case('3-True', True, 3),
        _case('1-False', False, 1),
    )
    alignment = _align(before, after)
    assert not alignment.changed
    assert [pair.paired_by for pair in alignment.cases] == ['values', 'values']


def test_an_attachment_column_without_a_namesake_takes_no_part() -> None:
    before = table([('n', 'param'), ('log', 'attachment')], _case('1', 1, None))
    after = table([('n', 'param'), ('trace', 'attachment')], _case('1', 1, None))
    alignment = _align(before, after)
    assert [pair.before for pair in alignment.columns] == [ColumnId('n')]
    assert not alignment.changed


def test_an_attachment_column_pairs_by_name_whatever_its_position() -> None:
    before = table([('n', 'param'), ('receipt', 'attachment')], _case('1', 1, None))
    after = table(
        [('n', 'param'), ('invoice', 'attachment'), ('receipt', 'attachment')],
        _case('1', 1, None, None),
    )
    alignment = _align(before, after)
    assert [(pair.before, pair.after) for pair in alignment.columns] == [
        ('n', 'n'),
        ('attachment:0', 'attachment:1'),
    ]
    assert not alignment.changed


def test_a_renamed_derived_column_pairs_per_kind() -> None:
    alignment = _align(
        table([('n', 'param'), ('n * 2', 'derived')], _case('1', 1, 2)),
        table([('n', 'param'), ('n + n', 'derived')], _case('1', 1, 2)),
    )
    assert alignment.columns[1] == ColumnPair(
        before=ColumnId('derived:0'), after=ColumnId('derived:0'), paired_by='values'
    )


def test_two_unpaired_columns_of_a_kind_stay_unpaired() -> None:
    alignment = _align(
        table([('a', 'param'), ('b', 'param')], _case('1', 1, 2)),
        table([('c', 'param'), ('d', 'param')], _case('1', 1, 2)),
    )
    assert [(pair.before, pair.after) for pair in alignment.columns] == [
        (ColumnId('a'), None),
        (ColumnId('b'), None),
        (None, ColumnId('c')),
        (None, ColumnId('d')),
    ]
    assert [pair.paired_by for pair in alignment.cases] == ['case-id']


def test_a_renamed_column_needs_a_paired_case() -> None:
    alignment = _align(
        table([('a', 'param')], _case('1', 1)),
        table([('b', 'param')], _case('2', 1), _case('3', 1)),
    )
    assert all(pair.paired_by is None for pair in alignment.columns)


def test_cases_with_repeated_values_pair_by_case_id() -> None:
    alignment = _align(
        table([('n', 'param')], _case('a', 1), _case('b', 1)),
        table([('n', 'param')], _case('b', 1), _case('a', 1)),
    )
    assert [pair.paired_by for pair in alignment.cases] == ['case-id', 'case-id']
    assert _case_pairs(alignment) == [('b', 'b'), ('a', 'a')]


def test_interleaved_places_a_removed_row_after_its_before_predecessor() -> None:
    rows = interleaved(
        ['a', 'c', 'e'], ['a', 'b', 'c', 'd', 'x', 'e'], {'a': 'a', 'c': 'c', 'e': 'e'}
    )
    assert rows == [
        ('a', 'a'),
        ('b', None),
        ('c', 'c'),
        ('d', None),
        ('x', None),
        ('e', 'e'),
    ]


def test_interleaved_puts_leading_removed_rows_on_top() -> None:
    assert interleaved(['n'], ['o', 'p'], {}) == [('o', None), ('p', None), (None, 'n')]


def test_interleaved_follows_the_partner_not_the_before_position() -> None:
    rows = interleaved(['b', 'a'], ['a', 'x', 'b'], {'a': 'a', 'b': 'b'})
    assert rows == [('b', 'b'), ('a', 'a'), ('x', None)]


def test_cases_are_not_paired_by_values_when_no_param_column_is_shared() -> None:
    alignment = _align(
        table([('euros', 'param')], _case('fast', 1), _case('slow', 2), custom=True),
        table([('eur', 'param')], _case('fast', 1), _case('sluggish', 9), custom=True),
    )
    assert alignment.columns == (
        ColumnPair(before=ColumnId('euros'), after=ColumnId('eur'), paired_by='values'),
    )
    assert [(pair.before, pair.after, pair.paired_by) for pair in alignment.cases] == [
        (_node('fast'), _node('fast'), 'case-id'),
        (_node('slow'), None, None),
        (None, _node('sluggish'), None),
    ]
