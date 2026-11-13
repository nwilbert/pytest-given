import re
from typing import Annotated

import pytest

from pytest_given import Template, attach, given, scenario, then, when, when_then
from pytest_given.capture.file_glossary import ParagraphGlossary, TableGlossary
from pytest_given.capture.glossary import TermHandle
from pytest_given.capture.story import sentence
from pytest_given.model import ClauseTermRef, Glossary, PytestGivenError, TermId
from tests.ubiquitous_language import pg

GLOSSARY_MD = """# Glossary

| Term | Meaning |
|------|---------|
| Guest  | A person booking. |
| Room   | A bookable room. |
| search | Look up options. |
"""


@pytest.fixture
def glossary_file(tmp_path):
    path = tmp_path / 'GLOSSARY.md'
    path.write_text(GLOSSARY_MD, encoding='utf-8')
    return path


@scenario(
    t'A {pg["Markdown glossary"].l} looks {pg["Term"].l.s} up case-insensitively',
)
def test_lookup_is_case_insensitive(glossary_file):
    with given(t'a {pg["Markdown glossary"].l} loaded from a Markdown file'):
        attach('Glossary file', GLOSSARY_MD)
        glossary = TableGlossary(glossary_file)
    with when(t'the same {pg["Term"].l} is looked up in three different cases'):
        handles = [glossary['Guest'], glossary['guest'], glossary['GUEST']]
    with then('every lookup resolves to one handle type and the same id'):
        assert all(isinstance(h, TermHandle) for h in handles)
        assert {h.id for h in handles} == {'guest'}


@scenario(
    'Repeated lookups return the same handle',
)
def test_handles_are_memoized(glossary_file):
    with given(t'a {pg["Markdown glossary"].l} loaded from a Markdown file'):
        attach('Glossary file', GLOSSARY_MD)
        glossary = TableGlossary(glossary_file)
    with when(t'the same {pg["Term"].l} is looked up twice'):
        first, second = glossary['Room'], glossary['room']
    with then('both lookups return the one memoized handle'):
        assert first is second


@scenario(
    t'File-loaded {pg["Term"].l.s} start {pg["Kindless"].l}',
)
def test_terms_start_kindless(glossary_file):
    with given('a Markdown glossary file with no kind column'):
        attach('Glossary file', GLOSSARY_MD)
    with when(t'a {pg["Markdown glossary"].l} loads it'):
        glossary = TableGlossary(glossary_file)
    with then(
        t'each {pg["Term"].l} is {pg["Kindless"].l} until {pg["Kind inference"].l} runs'
    ):
        assert glossary['Guest'].term.kind is None
        assert glossary['Room'].term.kind is None
        assert glossary['search'].term.kind is None


@scenario(
    t'A misspelt name looked up in a {pg["Markdown glossary"].l} gets a spelling hint',
    tags=['diagnostics', 'validation'],
)
def test_unknown_name_raises_with_suggestion(glossary_file):
    with given(t'a {pg["Markdown glossary"].l} loaded from a Markdown file'):
        attach('Glossary file', GLOSSARY_MD)
        glossary = TableGlossary(glossary_file)
    with (
        when_then(
            t'a misspelt {pg["Term"].l} is looked up',
            'a PytestGivenError is raised with a spelling hint',
        ),
        pytest.raises(PytestGivenError, match='Did you mean: Guest'),
    ):
        glossary['Gues']


@scenario(
    t'Handles are usable inline in a {pg["Sentence"].l}',
)
def test_usable_inline_in_sentence(glossary_file):
    with given(t'a {pg["Markdown glossary"].l} loaded from a Markdown file'):
        attach('Glossary file', GLOSSARY_MD)
        glossary = TableGlossary(glossary_file)
    with when(t'its handles build a {pg["Sentence"].l}'):
        built = sentence(glossary['Guest'], glossary['search'], glossary['Room'])
    with then(t'each slot becomes a {pg["Term ref"].l}'):
        parts = built.clauses[0].parts
        assert parts[0] == ClauseTermRef(term_id='guest', display='Guest')
        assert parts[1] == ClauseTermRef(term_id='search', display='search')
        assert parts[2] == ClauseTermRef(term_id='room', display='Room')


@scenario(
    'Calling a handle overrides its display',
)
def test_call_overrides_display(glossary_file):
    with given(t'a {pg["Markdown glossary"].l} loaded from a Markdown file'):
        attach('Glossary file', GLOSSARY_MD)
        glossary = TableGlossary(glossary_file)
    with when(t'a handle is called to name an {pg["Instance"].l}'):
        built = sentence(
            glossary['Guest']('Carol'),
            glossary['search']('searches for'),
            glossary['Room'],
        )
    with then(t'the {pg["Term ref"].l} carries the overridden display'):
        assert built.clauses[0].parts[0] == ClauseTermRef(
            term_id='guest', display='Carol'
        )


@scenario(
    t'An explicit kind column sets {pg["Term"].l} kinds',
)
def test_explicit_kind_column(tmp_path):
    with given(t'a Markdown glossary with an explicit Kind column'):
        doc = (
            '| Term | Meaning | Kind |\n|---|---|---|\n'
            '| Guest | x | Actor |\n| Room | y | Work Object |\n'
            '| book | z | Activity |\n'
        )
        attach('Glossary file', doc)
        path = tmp_path / 'g.md'
        path.write_text(doc, encoding='utf-8')
    with when(t'the {pg["Markdown glossary"].l} reads the Kind column'):
        glossary = TableGlossary(path, kind_column='Kind')
    with then(t'kinds come straight from the file, not {pg["Kind inference"].l}'):
        assert glossary['Guest'].term.kind == 'actor'
        assert glossary['Room'].term.kind == 'object'
        assert glossary['book'].term.kind == 'activity'


@scenario(
    'A kind column can be selected by integer index',
)
def test_kind_column_by_integer_index(tmp_path):
    with given('a Markdown glossary with the kind in the third column'):
        doc = (
            '| Term | Meaning | Kind |\n|---|---|---|\n'
            '| Guest | x | Actor |\n| Room | y | Work Object |\n'
        )
        attach('Glossary file', doc)
        path = tmp_path / 'g.md'
        path.write_text(doc, encoding='utf-8')
    with when(t'the {pg["Markdown glossary"].l} selects the kind column by index'):
        glossary = TableGlossary(path, kind_column=2)
    with then('the kinds are read from that column'):
        assert glossary['Guest'].term.kind == 'actor'
        assert glossary['Room'].term.kind == 'object'


@scenario(
    t'A `work_object` kind cell maps to the {pg["Work Object"].l} kind',
)
def test_work_object_underscore_alias(tmp_path):
    with given(t'a glossary whose Kind cell says work_object'):
        doc = '| Term | Meaning | Kind |\n|---|---|---|\n| Room | y | work_object |\n'
        attach('Glossary file', doc)
        path = tmp_path / 'g.md'
        path.write_text(doc, encoding='utf-8')
    with when(t'the {pg["Markdown glossary"].l} parses the kind'):
        glossary = TableGlossary(path, kind_column='Kind')
    with then(t'it normalizes to the {pg["Work Object"].l} kind'):
        assert glossary['Room'].term.kind == 'object'


@scenario(
    'An unrecognized kind value is rejected',
    tags=['diagnostics', 'validation'],
)
def test_unrecognized_kind_value_raises(tmp_path):
    with given('a glossary whose Kind cell holds an unknown value'):
        doc = '| Term | Meaning | Kind |\n|---|---|---|\n| Guest | x | Wizard |\n'
        attach('Glossary file', doc)
        path = tmp_path / 'g.md'
        path.write_text(doc, encoding='utf-8')
    with (
        when_then(
            t'the {pg["Markdown glossary"].l} loads the file',
            'a PytestGivenError names the unrecognized kind',
        ),
        pytest.raises(PytestGivenError, match='Wizard'),
    ):
        TableGlossary(path, kind_column='Kind')


@scenario(
    t'A missing {pg["Glossary"].l} file is refused as not found',
    tags=['validation'],
)
def test_missing_file_raises(tmp_path):
    with given('a path to a file that does not exist'):
        missing = tmp_path / 'nope.md'
    with (
        when_then(
            t'a {pg["Markdown glossary"].l} is opened on that path',
            'a PytestGivenError reports the file is not found',
        ),
        pytest.raises(PytestGivenError, match='glossary file not found'),
    ):
        TableGlossary(missing)


@pytest.mark.parametrize('unreadable', ['directory', 'not utf-8'])
def test_an_unreadable_glossary_file_is_reported_with_its_path(tmp_path, unreadable):
    path = tmp_path / 'GLOSSARY.md'
    if unreadable == 'directory':
        path.mkdir()
    else:
        path.write_bytes(b'| Term | Meaning |\n|---|---|\n| Gu\xe9st | x |\n')
    with pytest.raises(PytestGivenError, match='cannot read glossary file') as exc:
        TableGlossary(path)
    assert str(path) in str(exc.value)


def test_a_file_glossary_is_a_glossary(glossary_file):
    """A TableGlossary *is* the storage rather than wrapping it, so every
    consumer of a glossary takes one without a second isinstance arm."""
    fg = TableGlossary(glossary_file)
    assert isinstance(fg, Glossary)
    assert fg.get(TermId('guest')) is not None


@scenario(
    t'A {pg["Term"].l} cell with no alphanumeric characters is rejected',
    tags=['diagnostics', 'validation'],
)
def test_empty_id_term_cell_raises(tmp_path):
    with given(t'a row whose {pg["Term"].l} cell has no id-able characters'):
        doc = '| Term | Meaning |\n|---|---|\n| @#$ | some definition |\n'
        attach('Glossary file', doc)
        path = tmp_path / 'bad.md'
        path.write_text(doc, encoding='utf-8')
    with (
        when_then(
            t'the {pg["Markdown glossary"].l} loads the file',
            'a PytestGivenError is raised with file:line context',
        ),
        pytest.raises(PytestGivenError, match=r'bad\.md:3'),
    ):
        TableGlossary(path)


_BAD_TABLES = {
    'no table': '# no table here\n',
    'a header but no data rows': '| Term | Meaning |\n|---|---|\n',
    'no Term column': '| Word | Meaning |\n|---|---|\n| Guest | x |\n',
}


@scenario(
    t'A {pg["Markdown glossary"].l} error about its tables names the file',
    tags=['diagnostics', 'validation'],
)
@pytest.mark.parametrize(
    ('problem', 'message'),
    [
        ('no table', 'bad.md: found no Markdown pipe table'),
        (
            'a header but no data rows',
            "bad.md: the glossary file's Markdown table has no data rows",
        ),
        ('no Term column', "bad.md: column 'Term'"),
    ],
)
def test_table_errors_name_the_file(
    tmp_path,
    problem: Annotated[str, given(Template('a glossary file with {problem}'))],
    message,
):
    with given('that file on disk as bad.md'):
        doc = _BAD_TABLES[problem]
        attach('Glossary file', doc)
        path = tmp_path / 'bad.md'
        path.write_text(doc, encoding='utf-8')
    with (
        when_then(
            t'a {pg["Markdown glossary"].l} loads it',
            t'a PytestGivenError names the file before the problem: {message}',
        ),
        pytest.raises(PytestGivenError, match=re.escape(message)),
    ):
        TableGlossary(path, term_column='Term')


@scenario(
    t'Duplicate rows for one {pg["Term"].l} collapse only when identical',
    tags=['validation'],
)
@pytest.mark.parametrize(
    ('identical', 'outcome'),
    [(True, 'one term'), (False, 'refused')],
)
def test_duplicate_rows_collapse_only_when_identical(tmp_path, identical, outcome):
    with given(
        t'two rows for one {pg["Term"].l}, with '
        t'{identical:identical definitions|different definitions}'
    ):
        second = 'First definition.' if identical else 'Second definition.'
        doc = (
            '| Term | Meaning |\n|---|---|\n'
            '| Guest | First definition. |\n'
            f'| Guest | {second} |\n'
        )
        attach('Glossary file', doc)
        path = tmp_path / 'dup.md'
        path.write_text(doc, encoding='utf-8')
    with when(t'the {pg["Markdown glossary"].l} loads the file'):
        try:
            terms, refusal = TableGlossary(path).terms, ''
        except PytestGivenError as error:
            terms, refusal = [], str(error)
    with then(t'the rows yield {outcome}'):
        assert ('one term' if len(terms) == 1 else 'refused') == outcome
    with then('a refusal points at the second row as the conflict'):
        assert (
            re.search(r'dup\.md:4: .*conflicts with an earlier row', refusal)
            is not None
        ) == (outcome == 'refused')


@scenario(
    t'A blank definition normalizes to {pg["Undefined"].l}',
)
def test_blank_definition_cell_normalizes_to_none(tmp_path):
    with given(t'a row whose definition cell is blank'):
        doc = '| Term | Meaning |\n|---|---|\n| Guest |   |\n'
        attach('Glossary file', doc)
        path = tmp_path / 'g.md'
        path.write_text(doc, encoding='utf-8')
    with when(t'the {pg["Markdown glossary"].l} parses it'):
        fg = TableGlossary(path)
    with then(t'the {pg["Term"].l} definition is None, i.e. {pg["Undefined"].l}'):
        assert fg.get(TermId('guest')).definition is None


# --- Task 3: TableGlossary.__call__ (lookup-only, closed vocabulary) ---


@scenario(
    t'Calling a {pg["Markdown glossary"].l} looks up a known {pg["Term"].l}',
)
def test_file_glossary_call_known_name_returns_handle(glossary_file):
    with given(t'a {pg["Markdown glossary"].l} loaded from a Markdown file'):
        attach('Glossary file', GLOSSARY_MD)
        glossary = TableGlossary(glossary_file)
    with when(t'a known {pg["Term"].l} is looked up by call'):
        handle = glossary('Guest')
    with then(t'a {pg["Deferred term"].l} is returned'):
        assert handle.declared_kind is None
        assert handle.term.canonical == 'Guest'


@scenario(
    t'A {pg["Markdown glossary"].l} is a closed vocabulary',
    tags=['validation'],
)
def test_file_glossary_call_unknown_name_raises(glossary_file):
    with given(t'a {pg["Markdown glossary"].l} loaded from a Markdown file'):
        attach('Glossary file', GLOSSARY_MD)
        glossary = TableGlossary(glossary_file)
    with (
        when_then(
            'an unknown name is called',
            'a PytestGivenError is raised',
        ),
        pytest.raises(PytestGivenError, match='no glossary term'),
    ):
        glossary('Unknown Term')
    with then(t'no new {pg["Term"].l} was created'):
        assert len(glossary.terms) == 3


def _write(tmp_path, text):
    path = tmp_path / 'g.md'
    path.write_text(text, encoding='utf-8', newline='\n')
    return path


_SECTIONED = """# Glossary

## Booking

| Term | Meaning |
|---|---|
| Guest | A person. |

## Stay

| Term | Meaning |
|---|---|
| Room | A bookable room. |
"""


@scenario(
    t"A {pg['Markdown glossary'].l} reads each {pg['Term'].l}'s "
    t'{pg["Glossary section"].l} from the heading above it',
    tags=['spec/glossary-sections'],
)
def test_section_from_nearest_heading(tmp_path):
    with given('a Markdown glossary with a table under each of two headings'):
        attach('Glossary file', _SECTIONED)
        path = _write(tmp_path, _SECTIONED)
    with when(t'a {pg["Markdown glossary"].l} loads it'):
        glossary = TableGlossary(path)
    with then(t'each {pg["Term"].l} names the heading above its table'):
        assert glossary['Guest'].term.section == 'Booking'
        assert glossary['Room'].term.section == 'Stay'


def test_avoid_column_registers_avoided_words(tmp_path):
    path = _write(
        tmp_path,
        '| Term | Meaning | Avoid |\n|---|---|---|\n'
        '| Guest | A person. | Customer, client (old), Customer |\n',
    )
    glossary = TableGlossary(path, avoid_column='Avoid')
    assert glossary['Guest'].term.avoid == ('Customer', 'client (old)')


def test_avoided_word_naming_term_raises_with_path_and_line(tmp_path):
    path = _write(
        tmp_path,
        '| Term | Meaning | Avoid |\n|---|---|---|\n'
        '| Guest | A person. | |\n| Visitor | Another. | Guest |\n',
    )
    with pytest.raises(PytestGivenError, match=r'g\.md:4: avoided word .*Guest'):
        TableGlossary(path, avoid_column=2)


def test_note_only_avoid_entry_raises(tmp_path):
    path = _write(
        tmp_path,
        '| Term | Meaning | Avoid |\n|---|---|---|\n| Guest | A person. | (a note) |\n',
    )
    with pytest.raises(PytestGivenError, match=r'g\.md:3: avoid entry'):
        TableGlossary(path, avoid_column=2)


_REPEATED = """## Booking

| Term | Meaning |
|---|---|
| Guest | A person. |

## Stay

| Term | Meaning |
|---|---|
| Guest | A person. |
"""


@scenario(
    t'A {pg["Term"].l} repeated under two headings of a {pg["Markdown glossary"].l} '
    t'raises, identical rows included',
    tags=['spec/glossary-sections'],
)
def test_exact_repeat_in_other_section_raises(tmp_path):
    with given('a Markdown glossary with the same row under two headings'):
        attach('Glossary file', _REPEATED)
        path = _write(tmp_path, _REPEATED)
    with (
        when_then(
            t'a {pg["Markdown glossary"].l} loads it',
            'a PytestGivenError names the line of the second row',
        ),
        pytest.raises(PytestGivenError, match=r'g\.md:11: .*conflicts'),
    ):
        TableGlossary(path)


def test_hint_on_term_paragraph_file(tmp_path):
    path = _write(tmp_path, '**Order**: a request\n')
    with pytest.raises(
        PytestGivenError,
        match=r'\. For `\*\*Term\*\*:` paragraphs, use `ParagraphGlossary`\.$',
    ):
        TableGlossary(path)


def test_no_hint_without_term_lines(tmp_path):
    path = _write(tmp_path, '# nothing\n')
    with pytest.raises(PytestGivenError) as raised:
        TableGlossary(path)
    assert 'ParagraphGlossary' not in str(raised.value)


ORDERING = """# Ordering

Receives and tracks customer orders.

## Language

**Order**:
A customer's request for goods, placed in one checkout.
_Avoid_: Purchase, transaction

**Invoice**:
A request for payment sent to a customer after delivery, for one **Order**.
_Avoid_: Bill, payment request
"""


@scenario(
    t'A {pg["Markdown glossary"].l} reads {pg["Term paragraph"].l.s}',
    tags=['spec/glossary-sections'],
)
def test_paragraph_glossary_reads_term_paragraphs(tmp_path):
    with given(
        t'a Markdown glossary of {pg["Term paragraph"].l.s} under `## Language`'
    ):
        attach('Glossary file', ORDERING)
        path = _write(tmp_path, ORDERING)
    with when(t'a `ParagraphGlossary` loads it'):
        glossary = ParagraphGlossary(path)
    with then(
        t'each {pg["Term"].l} takes its definition from the lines under its bold name'
    ):
        order = glossary['Order'].term
        invoice = glossary['Invoice'].term
        assert order.definition is not None
        assert order.definition.text == (
            "A customer's request for goods, placed in one checkout."
        )
        assert invoice.definition is not None
        assert invoice.definition.text == (
            'A request for payment sent to a customer after delivery, '
            'for one **Order**.'
        )
    with then(t'the `_Avoid_:` line lists the words the {pg["Term"].l} avoids'):
        assert order.avoid == ('Purchase', 'transaction')
    with then(
        t'`## Language` holds the {pg["Term"].l.s} rather than naming a '
        t'{pg["Glossary section"].l}'
    ):
        assert order.section is None


def test_paragraph_glossary_crlf_file_reads_like_lf(tmp_path):
    lf = ParagraphGlossary(_write(tmp_path, ORDERING))
    crlf_path = tmp_path / 'crlf.md'
    crlf_path.write_bytes(ORDERING.replace('\n', '\r\n').encode('utf-8'))
    crlf = ParagraphGlossary(crlf_path)
    assert [(term.canonical, term.definition, term.avoid) for term in crlf.terms] == [
        (term.canonical, term.definition, term.avoid) for term in lf.terms
    ]


def test_paragraph_glossary_no_term_line_raises_with_path(tmp_path):
    path = _write(tmp_path, '# Ordering\n\nNo terms here.\n')
    with pytest.raises(
        PytestGivenError, match=r'g\.md: found no `\*\*Term\*\*:`'
    ) as raised:
        ParagraphGlossary(path)
    assert 'TableGlossary' not in str(raised.value)


def test_hint_on_table_file(tmp_path):
    path = _write(tmp_path, '| Term | Meaning |\n|---|---|\n| Order | x |\n')
    with pytest.raises(
        PytestGivenError,
        match=r'\. For a glossary in tables, use `TableGlossary`\.$',
    ):
        ParagraphGlossary(path)


def test_paragraph_glossary_row_error_names_its_line(tmp_path):
    path = _write(tmp_path, '**Order**: A request.\n_Avoid_: (a note)\n')
    with pytest.raises(PytestGivenError, match=r'g\.md:1: avoid entry'):
        ParagraphGlossary(path)


def test_paragraph_glossary_terms_are_kindless_and_closed(tmp_path):
    glossary = ParagraphGlossary(_write(tmp_path, ORDERING))
    assert {term.kind for term in glossary.terms} == {None}
    with pytest.raises(PytestGivenError, match='no glossary term'):
        glossary('Unknown')
