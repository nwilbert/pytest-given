import re

import pytest

from pytest_given import attach, given, scenario, then, when, when_then
from pytest_given.capture.markdown_glossary import (
    GlossaryRow,
    has_tables,
    has_term_lines,
    heading_section,
    parse_glossary_tables,
    split_avoid,
    title_level,
)
from pytest_given.markdown import document_blocks
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
            simple_doc,
            term_column=0,
            definition_column=1,
            kind_column=None,
            avoid_column=None,
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
            text,
            term_column=0,
            definition_column=1,
            kind_column=None,
            avoid_column=None,
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
            text,
            term_column='word',
            definition_column='note',
            kind_column='role',
            avoid_column=None,
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
            text,
            term_column=0,
            definition_column=1,
            kind_column=None,
            avoid_column=None,
        )
    with then('the escaped pipe survives as a literal pipe'):
        assert rows == [
            GlossaryRow(term='A|B', definition='pipe|here', kind=None, line=3)
        ]


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
            'avoid_column': None,
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
    'a table in a fenced code block': (
        '```\n| Term | Meaning |\n|---|---|\n| Fake | nope |\n```\n\n' + REAL_TABLE
    ),
    'a pipe line with no separator row': (
        'This line has a | in it but no separator follows.\n'
        'Next line is not a separator.\n\n' + REAL_TABLE
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
        ('a table in a fenced code block', [('Real', 'yes')]),
        ('a pipe line with no separator row', [('Real', 'yes')]),
    ],
)
def test_a_glossary_reads_the_tables_a_gfm_renderer_shows(document, rows):
    with given(t'a Markdown document with {document}'):
        text = _GFM_DOCUMENTS[document]
        attach('Markdown document', text)
    with when('the parser reads the document'):
        read = parse_glossary_tables(
            text,
            term_column=0,
            definition_column=1,
            kind_column=None,
            avoid_column=None,
        )
    with then(t'it reads the term and definition rows {rows}'):
        assert [(row.term, row.definition) for row in read] == rows


@scenario(
    t'A {pg["Term"].l} or kind cell is read as its plain text, with emphasis unwrapped',
)
@pytest.mark.parametrize(
    ('column', 'cell', 'plain'),
    [
        ('term', '**Scenario**', 'Scenario'),
        ('term', '*Step*', 'Step'),
        ('term', '`given`', 'given'),
        ('term', 'work_object', 'work_object'),
        ('term', '`a*b*c`', 'a*b*c'),
        ('term', '__Scenario__', '__Scenario__'),
        ('kind', '**Actor**', 'Actor'),
        ('kind', '`activity`', 'activity'),
    ],
)
def test_a_term_or_kind_cell_is_read_as_its_plain_text(column, cell, plain):
    # Inside a code span `*` is text, which is how the same markup renders in a
    # definition cell — the canonical name has to agree with the pill.
    with given(t'a {column} cell written as {cell}'):
        term, kind = (cell, 'Actor') if column == 'term' else ('Guest', cell)
        text = f'| Term | Meaning | Kind |\n|---|---|---|\n| {term} | x | {kind} |\n'
    with when('the parser reads the row'):
        [row] = parse_glossary_tables(
            text, term_column=0, definition_column=1, kind_column=2, avoid_column=None
        )
    with then(t'the {column} is {plain}'):
        assert (row.term if column == 'term' else row.kind) == plain


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
            text,
            term_column=0,
            definition_column=1,
            kind_column=None,
            avoid_column=None,
        )
    with then('the definition keeps its markup for the tooltip'):
        assert rows[0].definition == 'A test decorated with `@scenario(...)`.'


def test_nested_emphasis_unwraps_all_the_way():
    text = '| Term | Meaning |\n|---|---|\n| **`Scenario`** | nested. |\n'
    rows = parse_glossary_tables(
        text, term_column=0, definition_column=1, kind_column=None, avoid_column=None
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
        doc,
        term_column='Term',
        definition_column='Description',
        kind_column=None,
        avoid_column=None,
    )
    assert [(r.term, r.definition) for r in rows] == [('Guest', 'someone')]
    with pytest.raises(PytestGivenError, match='Nope'):
        parse_glossary_tables(
            doc,
            term_column='Term',
            definition_column='Nope',
            kind_column=None,
            avoid_column=None,
        )


def _read(text, **overrides):
    options = {
        'term_column': 0,
        'definition_column': 1,
        'kind_column': None,
        'avoid_column': None,
    } | overrides
    return parse_glossary_tables(text, **options)


_AVOID_TABLE = (
    '| Term | Meaning | Avoid |\n|---|---|---|\n'
    '| Guest | A person. | Customer, Client |\n'
)


@pytest.mark.parametrize('avoid_column', ['avoid', 2])
def test_avoid_column_by_name_and_index(avoid_column):
    rows = _read(_AVOID_TABLE, avoid_column=avoid_column)
    assert rows[0].avoid == ('Customer', 'Client')


def test_no_avoid_column_leaves_avoid_empty():
    assert _read(_AVOID_TABLE)[0].avoid == ()


def test_split_avoid_commas_in_parentheses():
    assert split_avoid('Bill, payment request (a, b), ') == [
        'Bill',
        'payment request (a, b)',
    ]


def test_missing_avoid_column_raises():
    with pytest.raises(PytestGivenError, match="column 'Avoid' not found"):
        _read(
            '| Term | Meaning |\n|---|---|\n| Guest | x |\n',
            avoid_column='Avoid',
            term_column='Term',
        )


def test_avoid_column_counts_for_addresses_another_table():
    text = (
        '| Avoid | Note |\n|---|---|\n| a | b |\n\n'
        '| Term | Meaning | Avoid |\n|---|---|---|\n| Guest | x | Client |\n'
    )
    with pytest.raises(PytestGivenError, match="column 'Term' not found"):
        _read(
            text, term_column='Term', definition_column='Meaning', avoid_column='Avoid'
        )


def _sections(text, **overrides):
    return [(row.term, row.section) for row in _read(text, **overrides)]


def _row_table(*terms):
    return '| Term | Meaning |\n|---|---|\n' + ''.join(f'| {t} | d |\n' for t in terms)


def test_section_from_nearest_heading_at_any_level():
    text = '## Core\n\n' + _row_table('Guest') + '\n#### Deep\n\n' + _row_table('Room')
    assert _sections(text) == [('Guest', 'Core'), ('Room', 'Deep')]


def test_title_heading_names_no_section():
    text = '# Glossary\n\n' + _row_table('Guest') + '\n## Core\n\n' + _row_table('Room')
    assert _sections(text) == [('Guest', None), ('Room', 'Core')]


def test_two_level_one_headings_are_sections():
    text = '# One\n\n' + _row_table('Guest') + '\n# Two\n\n' + _row_table('Room')
    assert _sections(text) == [('Guest', 'One'), ('Room', 'Two')]


def test_term_above_every_heading_has_no_section():
    text = _row_table('Guest') + '\n## Core\n\n' + _row_table('Room')
    assert _sections(text) == [('Guest', None), ('Room', 'Core')]


def test_same_heading_text_one_section():
    text = '## Core\n\n' + _row_table('Guest') + '\n## Core\n\n' + _row_table('Room')
    assert {section for _, section in _sections(text)} == {'Core'}


def test_heading_in_blockquote_ignored():
    text = (
        '## Core\n\n> ## Quoted\n>\n'
        '> | Term | Meaning |\n> |---|---|\n> | Guest | d |\n'
    )
    assert _sections(text) == [('Guest', 'Core')]


def test_heading_markup_and_closing_hashes():
    text = '## The *core* model ##\n\n' + _row_table('Guest')
    assert _sections(text) == [('Guest', 'The core model')]


def test_empty_heading_names_no_section():
    text = '## Core\n\n##\n\n' + _row_table('Guest')
    assert _sections(text) == [('Guest', None)]


def test_heading_section_holders_name_no_section():
    blocks = document_blocks('## Terms\n')
    heading = blocks[0].block
    assert (
        heading_section(heading, title_level=None, holders=frozenset({'terms'})) is None
    )
    assert heading_section(heading, title_level=None, holders=frozenset()) == 'Terms'


def test_title_level_needs_exactly_one_top_level_level_one_heading():
    assert title_level(document_blocks('# A\n\n## B\n')) == 1
    assert title_level(document_blocks('# A\n\n# B\n')) is None
    assert title_level(document_blocks('## B\n\n> # Q\n')) is None


def test_has_tables_and_term_lines():
    assert has_tables(SIMPLE)
    assert not has_tables('# x\n')
    assert has_term_lines('**Order**: a request\n')
    assert not has_term_lines('**Order:** a request\n')
