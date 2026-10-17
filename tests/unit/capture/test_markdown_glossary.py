import re

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
    t'A pipe table parses into {pg["Term"].l} and definition rows',
)
def test_parses_default_columns(simple_doc):
    with when(t'the parser reads it into rows for a {pg["File glossary"].l}'):
        rows = parse_glossary_tables(
            simple_doc, term_column=0, definition_column=1, kind_column=None
        )
    with then(t'each row carries a {pg["Term"].l}, definition and source line'):
        assert rows == [
            GlossaryRow(
                term='Guest', definition='A person booking.', kind=None, line=5
            ),
            GlossaryRow(term='Room', definition='A bookable room.', kind=None, line=6),
        ]


@scenario(
    'Multiple tables in one file are merged',
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
            text, term_column=0, definition_column=1, kind_column=None
        )
    with then(t'every table contributes its {pg["Term"].l} rows'):
        assert [row.term for row in rows] == ['Guest', 'Room', 'Search']


@scenario(
    'Columns can be selected by header name',
)
def test_column_by_header_name_case_insensitive():
    with given('a table with custom, differently-cased header names'):
        text = '| Word | Note | Role |\n|---|---|---|\n| Guest | x | Actor |\n'
        attach('Markdown document', text)
    with when('the parser selects columns by header name'):
        rows = parse_glossary_tables(
            text, term_column='word', definition_column='note', kind_column='role'
        )
    with then('the named columns are matched case-insensitively'):
        assert rows == [GlossaryRow(term='Guest', definition='x', kind='Actor', line=3)]


@scenario(
    'Escaped pipes are preserved in cells',
)
def test_escaped_pipe_in_cell():
    with given(r'cells containing escaped pipe characters (\|)'):
        text = '| Term | Meaning |\n|---|---|\n| A\\|B | pipe\\|here |\n'
        attach('Markdown document', text)
    with when('the parser splits the row'):
        rows = parse_glossary_tables(
            text, term_column=0, definition_column=1, kind_column=None
        )
    with then('the escaped pipe survives as a literal pipe'):
        assert rows == [
            GlossaryRow(term='A|B', definition='pipe|here', kind=None, line=3)
        ]


@scenario(
    'Tables inside fenced code blocks are skipped',
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
            text, term_column=0, definition_column=1, kind_column=None
        )
    with then('only the real table outside the fence contributes rows'):
        assert [row.term for row in rows] == ['Real']


_UNREADABLE_DOCUMENTS = {
    'no pipe table': '# Just a heading\n\nNo tables here.',
    'one pipe table': SIMPLE,
}


@scenario(
    t'A {pg["File glossary"].l} table the parser cannot read is refused, saying '
    t'what is wrong',
    tags=['diagnostics', 'validation'],
)
@pytest.mark.parametrize(
    ('document', 'columns', 'message'),
    [
        ('no pipe table', {}, 'found no Markdown pipe table'),
        ('one pipe table', {'term_column': 'Nope'}, "column 'Nope' not found"),
        (
            'one pipe table',
            {'definition_column': 5},
            'column index 5 is out of range',
        ),
    ],
)
def test_an_unreadable_glossary_table_is_refused(document, columns, message):
    with given(t'a Markdown document with {document}'):
        text = _UNREADABLE_DOCUMENTS[document]
        attach('Markdown document', text)
    with given(t'the columns selected as {columns}, the rest left at their defaults'):
        selection = {
            'term_column': 0,
            'definition_column': 1,
            'kind_column': None,
            **columns,
        }
    with (
        when_then(
            'the parser reads the document',
            t'a PytestGivenError says {message}',
        ),
        pytest.raises(PytestGivenError, match=re.escape(message)),
    ):
        parse_glossary_tables(text, **selection)


REAL_TABLE = '| Term | Meaning |\n|---|---|\n| Real | yes |\n'

_GFM_DOCUMENTS = {
    'a table in a blockquote': (
        '> | Term | Meaning |\n> |---|---|\n> | Quoted | yes |\n'
    ),
    'a table in an indented code block': (
        '    | Term | Meaning |\n    |---|---|\n    | Code | no |\n\n' + REAL_TABLE
    ),
    'a separator row narrower than its header': (
        '| Term | Meaning |\n|---|\n| Odd | no |\n\n' + REAL_TABLE
    ),
    'a data row narrower than its header': (
        '| Term | Meaning |\n|---|---|\n| Short |\n'
    ),
}


@scenario(
    t'A {pg["File glossary"].l} reads the tables a GFM renderer shows, and no others',
    tags=['versions/0.5.0'],
)
@pytest.mark.parametrize(
    ('document', 'rows'),
    [
        ('a table in a blockquote', [('Quoted', 'yes')]),
        ('a table in an indented code block', [('Real', 'yes')]),
        ('a separator row narrower than its header', [('Real', 'yes')]),
        ('a data row narrower than its header', [('Short', '')]),
    ],
)
def test_a_glossary_reads_the_tables_a_gfm_renderer_shows(document, rows):
    with given(t'a Markdown document with {document}'):
        text = _GFM_DOCUMENTS[document]
        attach('Markdown document', text)
    with when('the parser reads the document'):
        read = parse_glossary_tables(
            text, term_column=0, definition_column=1, kind_column=None
        )
    with then(t'it reads the term and definition rows {rows}'):
        assert [(row.term, row.definition) for row in read] == rows


@scenario(
    t'A {pg["Term"].l} cell is read as its plain text, with emphasis unwrapped',
)
@pytest.mark.parametrize(
    ('cell', 'term'),
    [
        ('**Scenario**', 'Scenario'),
        ('*Step*', 'Step'),
        ('`given`', 'given'),
        ('work_object', 'work_object'),
        ('`a*b*c`', 'a*b*c'),
        ('__Scenario__', '__Scenario__'),
    ],
)
def test_a_term_cell_is_read_as_its_plain_text(cell, term):
    # Inside a code span `*` is text, which is how the same markup renders in a
    # definition cell — the canonical name has to agree with the pill.
    with given(t'a {pg["Term"].l} cell written as {cell}'):
        text = f'| Term | Meaning |\n|---|---|\n| {cell} | A thing. |\n'
    with when('the parser reads the term cell'):
        rows = parse_glossary_tables(
            text, term_column=0, definition_column=1, kind_column=None
        )
    with then(t'the {pg["Term"].l} is {term}'):
        assert [row.term for row in rows] == [term]


@scenario(
    'A kind cell is read as its plain text, with emphasis unwrapped',
)
def test_strips_emphasis_from_kind_cell():
    with given('a Kind cell written with bold emphasis'):
        text = '| Term | Meaning | Kind |\n|---|---|---|\n| Guest | x | **Actor** |\n'
        attach('Markdown document', text)
    with when('the parser reads the kind cell'):
        rows = parse_glossary_tables(
            text, term_column=0, definition_column=1, kind_column=2
        )
    with then('the kind is unwrapped to plain text'):
        assert rows[0].kind == 'Actor'


@scenario(
    'Definition markdown is left intact',
)
def test_leaves_definition_markdown_intact():
    with given('a definition cell rich with inline code'):
        text = (
            '| Term | Meaning |\n|---|---|\n'
            '| Scenario | A test decorated with `@scenario(...)`. |\n'
        )
        attach('Markdown document', text)
    with when('the parser reads the row'):
        rows = parse_glossary_tables(
            text, term_column=0, definition_column=1, kind_column=None
        )
    with then('the definition keeps its markup for the tooltip'):
        assert rows[0].definition == 'A test decorated with `@scenario(...)`.'


@scenario(
    'A pipe line without a separator is not a table',
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
            text, term_column=0, definition_column=1, kind_column=None
        )
    with then('only the real pipe table produces rows'):
        assert [row.term for row in rows] == ['Real']


def test_nested_emphasis_unwraps_all_the_way():
    text = '| Term | Meaning |\n|---|---|\n| **`Scenario`** | nested. |\n'
    rows = parse_glossary_tables(
        text, term_column=0, definition_column=1, kind_column=None
    )
    assert rows[0].term == 'Scenario'


def test_a_named_spec_skips_a_table_it_cannot_address() -> None:
    """A glossary file is a document; named columns are what lets one hold
    prose tables beside the glossary. Resolving one named column but not the
    other is a real glossary table with a wrong column, and still raises."""
    doc = (
        '| Term | Description |\n'
        '|------|-------------|\n'
        '| Guest | someone |\n'
        '\n'
        '| Option | Default |\n'
        '|--------|---------|\n'
        '| --flag | off |\n'
    )
    rows = parse_glossary_tables(
        doc, term_column='Term', definition_column='Description', kind_column=None
    )
    assert [(r.term, r.definition) for r in rows] == [('Guest', 'someone')]
    with pytest.raises(PytestGivenError, match='Nope'):
        parse_glossary_tables(
            doc, term_column='Term', definition_column='Nope', kind_column=None
        )
