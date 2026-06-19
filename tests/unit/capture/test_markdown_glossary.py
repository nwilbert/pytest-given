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
