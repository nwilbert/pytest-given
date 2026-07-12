import pytest

from pytest_given import attach, given, scenario, then, when, when_then
from pytest_given.capture.markdown_glossary import GlossaryRow, parse_glossary_tables
from pytest_given.model import PytestGivenError
from tests.ubiquitous_language import pg

SIMPLE = """# Glossary

| Term | Meaning |
|------|---------|
| Guest | A person booking. |
| Room  | A bookable room. |
"""


@pytest.fixture
@given('a Markdown document with one pipe table')
def simple_doc():
    attach('Markdown document', SIMPLE)
    return SIMPLE


@scenario(
    'A pipe table parses into term and definition rows',
    tags=['markdown', 'happy-path'],
)
def test_parses_default_columns(simple_doc):
    with when(t'the parser reads it into rows for a {pg["File glossary"]}'):
        rows = parse_glossary_tables(
            simple_doc, term_column=0, description_column=1, kind_column=None
        )
    with then(t'each row carries a {pg["Term"]}, definition and source line'):
        assert rows == [
            GlossaryRow(
                term='Guest', definition='A person booking.', kind=None, line=5
            ),
            GlossaryRow(term='Room', definition='A bookable room.', kind=None, line=6),
        ]


@scenario(
    'Multiple tables in one file are merged',
    tags=['markdown', 'happy-path'],
)
def test_merges_multiple_tables():
    with given('a document containing two separate pipe tables'):
        text = (
            SIMPLE
            + '\n## More\n\n| Term | Meaning |\n|---|---|\n| Search | Look up. |\n'
        )
        attach('Markdown document', text)
    with when('the parser reads the whole document'):
        rows = parse_glossary_tables(
            text, term_column=0, description_column=1, kind_column=None
        )
    with then(t'every table contributes its {pg["Term"]} rows'):
        assert [row.term for row in rows] == ['Guest', 'Room', 'Search']


@scenario(
    'Columns can be selected by header name',
    tags=['markdown', 'happy-path'],
)
def test_column_by_header_name_case_insensitive():
    with given('a table with custom, differently-cased header names'):
        text = '| Word | Note | Role |\n|---|---|---|\n| Guest | x | Actor |\n'
        attach('Markdown document', text)
    with when('the parser selects columns by header name'):
        rows = parse_glossary_tables(
            text, term_column='word', description_column='note', kind_column='role'
        )
    with then('the named columns are matched case-insensitively'):
        assert rows == [GlossaryRow(term='Guest', definition='x', kind='Actor', line=3)]


@scenario(
    'Escaped pipes are preserved in cells',
    tags=['markdown', 'happy-path'],
)
def test_escaped_pipe_in_cell():
    with given(r'cells containing escaped pipe characters (\|)'):
        text = '| Term | Meaning |\n|---|---|\n| A\\|B | pipe\\|here |\n'
        attach('Markdown document', text)
    with when('the parser splits the row'):
        rows = parse_glossary_tables(
            text, term_column=0, description_column=1, kind_column=None
        )
    with then('the escaped pipe survives as a literal pipe'):
        assert rows == [
            GlossaryRow(term='A|B', definition='pipe|here', kind=None, line=3)
        ]


@scenario(
    'Tables inside fenced code blocks are skipped',
    tags=['markdown', 'happy-path'],
)
def test_skips_tables_in_fenced_code_blocks():
    with given('a fenced code block that contains a look-alike table'):
        text = (
            '```\n| Term | Meaning |\n|---|---|\n| Fake | nope |\n```\n\n'
            '| Term | Meaning |\n|---|---|\n| Real | yes |\n'
        )
        attach('Markdown document', text)
    with when('the parser reads the document'):
        rows = parse_glossary_tables(
            text, term_column=0, description_column=1, kind_column=None
        )
    with then('only the real table outside the fence contributes rows'):
        assert [row.term for row in rows] == ['Real']


@scenario(
    'A file with no pipe table is rejected',
    tags=['markdown', 'validation'],
)
def test_no_table_raises():
    with given('a document with no pipe table'):
        text = '# Just a heading\n\nNo tables here.'
        attach('Markdown document', text)
    with (
        when_then(
            t'the parser reads it for a {pg["File glossary"]}',
            'no pipe table is reported',
        ),
        pytest.raises(PytestGivenError, match=r'no .*table'),
    ):
        parse_glossary_tables(
            text, term_column=0, description_column=1, kind_column=None
        )


@scenario(
    'A missing named column is rejected',
    tags=['markdown', 'validation'],
)
def test_missing_named_column_raises(simple_doc):
    with (
        when_then(
            'the parser selects a header name that is absent',
            'a PytestGivenError names the missing column',
        ),
        pytest.raises(PytestGivenError, match=r"column 'Nope' not found"),
    ):
        parse_glossary_tables(
            simple_doc, term_column='Nope', description_column=1, kind_column=None
        )


@scenario(
    'A column index out of range is rejected',
    tags=['markdown', 'validation'],
)
def test_index_out_of_range_raises(simple_doc):
    with (
        when_then(
            'the parser selects a column index past the table width',
            'a PytestGivenError names the out-of-range column',
        ),
        pytest.raises(PytestGivenError, match='column index 5 is out of range'),
    ):
        parse_glossary_tables(
            simple_doc, term_column=0, description_column=5, kind_column=None
        )


SHORT_ROW_TABLE = """| Term | Meaning | Type |
|---|---|---|
| Guest | A person |
| Room | A bookable room | place |
"""


@scenario(
    'A data row with too few columns is rejected',
    tags=['markdown', 'validation'],
)
def test_data_row_with_fewer_columns_raises():
    with given('a table with a data row narrower than its header'):
        text = SHORT_ROW_TABLE
        attach('Markdown document', text)
    with (
        when_then(
            'the parser reads the short row',
            'a PytestGivenError points at the short row',
        ),
        pytest.raises(PytestGivenError, match='row at line 3'),
    ):
        parse_glossary_tables(text, term_column=0, description_column=1, kind_column=2)


@scenario(
    'Bold term cells render as clean terms',
    tags=['markdown', 'happy-path'],
)
def test_strips_bold_from_term_cell():
    with given(t'a {pg["Term"]} cell written with **bold** emphasis'):
        text = '| Term | Meaning |\n|---|---|\n| **Scenario** | A decorated test. |\n'
        attach('Markdown document', text)
    with when('the parser reads the term cell'):
        rows = parse_glossary_tables(
            text, term_column=0, description_column=1, kind_column=None
        )
    with then('the emphasis is unwrapped to the plain canonical'):
        assert rows == [
            GlossaryRow(
                term='Scenario', definition='A decorated test.', kind=None, line=3
            )
        ]


@scenario(
    'Italic and inline-code term cells are unwrapped',
    tags=['markdown', 'happy-path'],
)
def test_strips_italic_and_inline_code_from_term_cell():
    with given(t'{pg["Term"]} cells using *italic* and `code` emphasis'):
        text = '| Term | Meaning |\n|---|---|\n| *Step* | one. |\n| `given` | two. |\n'
        attach('Markdown document', text)
    with when('the parser reads the term cells'):
        rows = parse_glossary_tables(
            text, term_column=0, description_column=1, kind_column=None
        )
    with then('each unwraps to its plain text'):
        assert [row.term for row in rows] == ['Step', 'given']


@scenario(
    'Underscores inside an identifier survive',
    tags=['markdown', 'happy-path'],
)
def test_preserves_underscores_inside_term_identifier():
    with given(t'a {pg["Term"]} literally named work_object'):
        text = '| Term | Meaning |\n|---|---|\n| work_object | a thing. |\n'
        attach('Markdown document', text)
    with when('the parser reads the term cell'):
        rows = parse_glossary_tables(
            text, term_column=0, description_column=1, kind_column=None
        )
    with then('the single underscores are not treated as emphasis'):
        assert rows[0].term == 'work_object'


@scenario(
    'Emphasis is stripped from kind cells too',
    tags=['markdown', 'happy-path'],
)
def test_strips_emphasis_from_kind_cell():
    with given('a Kind cell written with bold emphasis'):
        text = '| Term | Meaning | Kind |\n|---|---|---|\n| Guest | x | **Actor** |\n'
        attach('Markdown document', text)
    with when('the parser reads the kind cell'):
        rows = parse_glossary_tables(
            text, term_column=0, description_column=1, kind_column=2
        )
    with then('the kind is unwrapped to plain text'):
        assert rows[0].kind == 'Actor'


@scenario(
    'Definition markdown is left intact',
    tags=['markdown', 'happy-path'],
)
def test_leaves_description_markdown_intact():
    with given('a definition cell rich with inline code'):
        text = (
            '| Term | Meaning |\n|---|---|\n'
            '| Scenario | A test decorated with `@scenario(...)`. |\n'
        )
        attach('Markdown document', text)
    with when('the parser reads the row'):
        rows = parse_glossary_tables(
            text, term_column=0, description_column=1, kind_column=None
        )
    with then('the definition keeps its markup for the tooltip'):
        assert rows[0].definition == 'A test decorated with `@scenario(...)`.'


@scenario(
    'A pipe line without a separator is not a table',
    tags=['markdown', 'happy-path'],
)
def test_pipe_line_without_separator_is_skipped():
    with given('prose containing a stray pipe, then a real table'):
        text = (
            'This line has a | in it but no separator follows.\n'
            'Next line is not a separator.\n'
            '\n'
            '| Term | Meaning |\n'
            '|---|---|\n'
            '| Real | yes |\n'
        )
        attach('Markdown document', text)
    with when('the parser reads the document'):
        rows = parse_glossary_tables(
            text, term_column=0, description_column=1, kind_column=None
        )
    with then('only the real pipe table produces rows'):
        assert [row.term for row in rows] == ['Real']
