"""A document's block structure: its tables, and each block's text placed in
the source."""

import pytest
from markdown_it import MarkdownIt

from pytest_given.markdown import table_cell_spans, tables, text_runs


@pytest.mark.parametrize(
    ('row', 'cells'),
    [
        ('| a | b |', [' a ', ' b ']),
        ('a | b', ['a ', ' b']),
        (r'| a \| b | c |', [r' a \| b ', ' c ']),
        # An escaped backslash still escapes the pipe after it, as GFM splits
        # the row before it reads escapes.
        (r'| a \\| b | c |', [r' a \\| b ', ' c ']),
        (r'| `a\|b` | c |', [r' `a\|b` ', ' c ']),
        ('| | a |', [' ', ' a ']),
        ('|', []),
    ],
)
def test_table_cell_spans_split_a_row_on_its_unescaped_pipes(
    row: str, cells: list[str]
) -> None:
    assert [row[start:end] for start, end in table_cell_spans(row)] == cells


def _contents(source: str) -> list[list[list[str]]]:
    return [
        [row.contents for row in (table.header, *table.rows)]
        for table in tables(source)
    ]


def test_a_table_reads_its_header_and_rows_with_their_lines() -> None:
    [table] = tables('text\n\n| A | B |\n|---|---|\n| 1 | 2 |\n| 3 | 4 |\n')
    assert table.header.contents == ['A', 'B']
    assert table.header.line == 3
    assert [row.line for row in table.rows] == [5, 6]
    assert table.rows[1].contents == ['3', '4']


def test_a_row_is_fitted_to_its_header() -> None:
    source = '| A | B |\n|---|---|\n| 1 |\n| 1 | 2 | 3 |\n'
    [table] = tables(source)
    short, long = table.rows
    missing = short.cells[1]
    assert (missing.text, missing.start) == ('', missing.end)
    assert missing.start == source.index('\n| 1 | 2')
    assert long.contents == ['1', '2']


def test_a_cell_is_placed_in_the_source_past_its_container_prefix() -> None:
    source = '> | A | B |\n> |---|---|\n> | `x` | y \\| z |\n'
    [table] = tables(source)
    cell = table.rows[0].cells[1]
    assert source[cell.start : cell.end] == cell.text == r' y \| z '
    assert cell.content == 'y | z'


def test_a_table_in_a_code_block_is_none() -> None:
    assert tables('```\n| A |\n|---|\n```\n') == []


def test_every_table_is_read_in_document_order() -> None:
    source = '| A |\n|---|\n| 1 |\n\ntext\n\n| B |\n|---|\n'
    assert _contents(source) == [[['A'], ['1']], [['B']]]


@pytest.mark.parametrize(
    'source',
    [
        '| A | B |\n|---|---|\n| 1 |\n| 1 | 2 | 3 |\n',
        '| A | B |\n|---|---|\n|  **a** \\| b  |\tc\t|\n',
        '| `a\\|b` | \\| c |\n|---|---|\n',
        '|A|B\n-|-\nx|y\n',
        'a | b\r\n--|--\r\n1 | 2\r\n',
        '| A\0 |\n|---|\n| \0 |\n',
        '- item\n\n  > | A |\n  > |---|\n  > | x |\n',
        '| A |\n|---|\n| 1 |\n> quote\n',
    ],
)
def test_a_cell_reads_as_markdown_it_reads_it(source: str) -> None:
    assert _contents(source) == _markdown_it_contents(source)


def _markdown_it_contents(source: str) -> list[list[list[str]]]:
    found: list[list[list[str]]] = []
    rows: list[list[str]] | None = None
    for token in MarkdownIt('commonmark').enable('table').parse(source):
        match token.type:
            case 'table_open':
                rows = []
                found.append(rows)
            case 'table_close':
                rows = None
            case 'tr_open' if rows is not None:
                rows.append([])
            case 'inline' if rows is not None:
                rows[-1].append(token.content)
    return found


def test_text_runs_place_prose_and_cells_in_document_order() -> None:
    source = '# Title\n\n> one\n> two\n\n| A |\n|---|\n| x |\n'
    runs = list(text_runs(source))
    assert [(run.text, run.line, run.in_table_row) for run in runs] == [
        ('Title', 1, False),
        ('one\ntwo', 3, False),
        (' A ', 6, True),
        (' x ', 8, True),
    ]
    one_two = runs[1]
    assert one_two.line_at(one_two.text.index('two')) == 4
    start, end = one_two.span(0, len(one_two.text))
    assert source[start:end] == 'one\n> two'


@pytest.mark.parametrize(('start', 'end'), [(2, 5), (3, 4), (4, 4), (0, 7)])
def test_a_slice_of_a_run_stays_placed_in_the_source(start: int, end: int) -> None:
    source = '> one\n> two\n'
    [run] = text_runs(source)
    piece = run.slice(start, end)
    assert piece.text == run.text[start:end]
    assert piece.span(0, len(piece.text)) == run.span(start, end)
    assert piece.line == run.line_at(start)
