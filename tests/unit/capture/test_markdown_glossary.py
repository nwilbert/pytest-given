import pytest

from pytest_given.capture.markdown_glossary import GlossaryRow, parse_glossary_tables
from pytest_given.model import PytestGivenError

SIMPLE = """# Glossary

| Term | Meaning |
|------|---------|
| Guest | A person booking. |
| Room  | A bookable room. |
"""


def test_parses_default_columns():
    rows = parse_glossary_tables(
        SIMPLE, term_column=0, description_column=1, kind_column=None
    )
    assert rows == [
        GlossaryRow(term='Guest', definition='A person booking.', kind=None, line=5),
        GlossaryRow(term='Room', definition='A bookable room.', kind=None, line=6),
    ]


def test_merges_multiple_tables():
    text = (
        SIMPLE + '\n## More\n\n| Term | Meaning |\n|---|---|\n| Search | Look up. |\n'
    )
    rows = parse_glossary_tables(
        text, term_column=0, description_column=1, kind_column=None
    )
    assert [row.term for row in rows] == ['Guest', 'Room', 'Search']


def test_column_by_header_name_case_insensitive():
    text = '| Word | Note | Role |\n|---|---|---|\n| Guest | x | Actor |\n'
    rows = parse_glossary_tables(
        text, term_column='word', description_column='note', kind_column='role'
    )
    assert rows == [GlossaryRow(term='Guest', definition='x', kind='Actor', line=3)]


def test_escaped_pipe_in_cell():
    text = '| Term | Meaning |\n|---|---|\n| A\\|B | pipe\\|here |\n'
    rows = parse_glossary_tables(
        text, term_column=0, description_column=1, kind_column=None
    )
    assert rows == [GlossaryRow(term='A|B', definition='pipe|here', kind=None, line=3)]


def test_skips_tables_in_fenced_code_blocks():
    text = (
        '```\n| Term | Meaning |\n|---|---|\n| Fake | nope |\n```\n\n'
        '| Term | Meaning |\n|---|---|\n| Real | yes |\n'
    )
    rows = parse_glossary_tables(
        text, term_column=0, description_column=1, kind_column=None
    )
    assert [row.term for row in rows] == ['Real']


def test_no_table_raises():
    with pytest.raises(PytestGivenError, match=r'no .*table'):
        parse_glossary_tables(
            '# Just a heading\n\nNo tables here.',
            term_column=0,
            description_column=1,
            kind_column=None,
        )


def test_missing_named_column_raises():
    with pytest.raises(PytestGivenError, match='column'):
        parse_glossary_tables(
            SIMPLE, term_column='Nope', description_column=1, kind_column=None
        )


def test_index_out_of_range_raises():
    with pytest.raises(PytestGivenError, match='column'):
        parse_glossary_tables(
            SIMPLE, term_column=0, description_column=5, kind_column=None
        )


SHORT_ROW_TABLE = """| Term | Meaning | Type |
|---|---|---|
| Guest | A person |
| Room | A bookable room | place |
"""


def test_data_row_with_fewer_columns_raises():
    with pytest.raises(PytestGivenError, match=r'(?i)column'):
        parse_glossary_tables(
            SHORT_ROW_TABLE,
            term_column=0,
            description_column=1,
            kind_column=2,
        )


def test_strips_bold_from_term_cell():
    text = '| Term | Meaning |\n|---|---|\n| **Scenario** | A decorated test. |\n'
    rows = parse_glossary_tables(
        text, term_column=0, description_column=1, kind_column=None
    )
    assert rows == [
        GlossaryRow(term='Scenario', definition='A decorated test.', kind=None, line=3)
    ]


def test_strips_italic_and_inline_code_from_term_cell():
    text = '| Term | Meaning |\n|---|---|\n| *Step* | one. |\n| `given` | two. |\n'
    rows = parse_glossary_tables(
        text, term_column=0, description_column=1, kind_column=None
    )
    assert [row.term for row in rows] == ['Step', 'given']


def test_preserves_underscores_inside_term_identifier():
    """Single underscores inside an identifier are not emphasis and must survive
    (e.g. a term literally named work_object)."""
    text = '| Term | Meaning |\n|---|---|\n| work_object | a thing. |\n'
    rows = parse_glossary_tables(
        text, term_column=0, description_column=1, kind_column=None
    )
    assert rows[0].term == 'work_object'


def test_strips_emphasis_from_kind_cell():
    text = '| Term | Meaning | Kind |\n|---|---|---|\n| Guest | x | **Actor** |\n'
    rows = parse_glossary_tables(
        text, term_column=0, description_column=1, kind_column=2
    )
    assert rows[0].kind == 'Actor'


def test_leaves_description_markdown_intact():
    """Emphasis is stripped only from term/kind cells; a definition keeps its
    inline markup (backticks, bold) for the tooltip."""
    text = (
        '| Term | Meaning |\n|---|---|\n'
        '| Scenario | A test decorated with `@scenario(...)`. |\n'
    )
    rows = parse_glossary_tables(
        text, term_column=0, description_column=1, kind_column=None
    )
    assert rows[0].definition == 'A test decorated with `@scenario(...)`.'


def test_pipe_line_without_separator_is_skipped():
    """A line with a pipe that is NOT followed by a |---| separator row is
    skipped. Only the real pipe table (with separator) produces rows."""
    text = (
        'This line has a | in it but no separator follows.\n'
        'Next line is not a separator.\n'
        '\n'
        '| Term | Meaning |\n'
        '|---|---|\n'
        '| Real | yes |\n'
    )
    rows = parse_glossary_tables(
        text, term_column=0, description_column=1, kind_column=None
    )
    assert [row.term for row in rows] == ['Real']
