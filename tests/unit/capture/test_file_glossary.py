import pytest

from pytest_given import attach, given, scenario, then, when, when_then
from pytest_given.capture.file_glossary import FileGlossary
from pytest_given.capture.glossary import TermHandle
from pytest_given.capture.story import activity
from pytest_given.model import ActivityTermRef, PytestGivenError, TermId
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
    t'{pg["File glossary"]("FileGlossary")} lookup is case-insensitive',
)
def test_lookup_is_case_insensitive(glossary_file):
    with given(t'a {pg["File glossary"]} loaded from a Markdown file'):
        attach('Glossary file', GLOSSARY_MD)
        glossary = FileGlossary(glossary_file)
    with when(t'the same {pg["Term"]} is looked up in three different cases'):
        handles = [glossary['Guest'], glossary['guest'], glossary['GUEST']]
    with then('every lookup resolves to one handle type and the same id'):
        assert all(isinstance(h, TermHandle) for h in handles)
        assert {h.id for h in handles} == {'guest'}


@scenario(
    'Repeated lookups return the same handle',
)
def test_handles_are_memoized(glossary_file):
    with given(t'a {pg["File glossary"]} loaded from a Markdown file'):
        attach('Glossary file', GLOSSARY_MD)
        glossary = FileGlossary(glossary_file)
    with when(t'the same {pg["Term"]} is looked up twice'):
        first, second = glossary['Room'], glossary['room']
    with then('both lookups return the one memoized handle'):
        assert first is second


@scenario(
    t'File-loaded {pg["Term"]("terms")} start {pg["Kindless"].low}',
)
def test_terms_start_kindless(glossary_file):
    with given('a Markdown glossary file with no kind column'):
        attach('Glossary file', GLOSSARY_MD)
    with when(t'a {pg["File glossary"]} loads it'):
        glossary = FileGlossary(glossary_file)
    with then(
        t'each {pg["Term"]} is {pg["Kindless"]} until {pg["Kind inference"]} runs'
    ):
        assert glossary['Guest'].term.kind is None
        assert glossary['Room'].term.kind is None
        assert glossary['search'].term.kind is None


@scenario(
    'An unknown name raises with a suggestion',
    tags=['diagnostics', 'validation'],
)
def test_unknown_name_raises_with_suggestion(glossary_file):
    with given(t'a {pg["File glossary"]} loaded from a Markdown file'):
        attach('Glossary file', GLOSSARY_MD)
        glossary = FileGlossary(glossary_file)
    with (
        when_then(
            t'a misspelt {pg["Term"]} is looked up',
            'a PytestGivenError is raised with a spelling hint',
        ),
        pytest.raises(PytestGivenError, match='Did you mean: Guest'),
    ):
        glossary['Gues']


@scenario(
    t'Handles are usable inline in an {pg["Activity"].low}',
)
def test_usable_inline_in_activity(glossary_file):
    with given(t'a {pg["File glossary"]} loaded from a Markdown file'):
        attach('Glossary file', GLOSSARY_MD)
        glossary = FileGlossary(glossary_file)
    with when(t'its handles build an {pg["Activity"]}'):
        built = activity(glossary['Guest'], glossary['search'], glossary['Room'])
    with then(t'each slot becomes a {pg["Term ref"]}'):
        parts = built.paths[0].parts
        assert parts[0] == ActivityTermRef(term_id='guest', display='Guest')
        assert parts[1] == ActivityTermRef(term_id='search', display='search')
        assert parts[2] == ActivityTermRef(term_id='room', display='Room')


@scenario(
    'Calling a handle overrides its display',
)
def test_call_overrides_display(glossary_file):
    with given(t'a {pg["File glossary"]} loaded from a Markdown file'):
        attach('Glossary file', GLOSSARY_MD)
        glossary = FileGlossary(glossary_file)
    with when(t'a handle is called to name an {pg["Instance"]}'):
        built = activity(
            glossary['Guest']('Carol'),
            glossary['search']('searches for'),
            glossary['Room'],
        )
    with then(t'the {pg["Term ref"]} carries the overridden display'):
        assert built.paths[0].parts[0] == ActivityTermRef(
            term_id='guest', display='Carol'
        )


@scenario(
    t'An explicit kind column sets {pg["Term"].low} kinds',
)
def test_explicit_kind_column(tmp_path):
    with given(t'a Markdown glossary with an explicit Kind column'):
        doc = (
            '| Term | Meaning | Kind |\n|---|---|---|\n'
            '| Guest | x | Actor |\n| Room | y | Work Object |\n'
        )
        attach('Glossary file', doc)
        path = tmp_path / 'g.md'
        path.write_text(doc, encoding='utf-8')
    with when(t'the {pg["File glossary"]} reads the Kind column'):
        glossary = FileGlossary(path, kind_column='Kind')
    with then(t'kinds come straight from the file, not {pg["Kindless"]} inference'):
        assert glossary['Guest'].term.kind == 'actor'
        assert glossary['Room'].term.kind == 'object'


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
    with when(t'the {pg["File glossary"]} selects the kind column by index'):
        glossary = FileGlossary(path, kind_column=2)
    with then('the kinds are read from that column'):
        assert glossary['Guest'].term.kind == 'actor'
        assert glossary['Room'].term.kind == 'object'


@scenario(
    t'A {pg["Work Object"]("work_object")} kind alias maps to the object kind',
)
def test_work_object_underscore_alias(tmp_path):
    with given(t'a glossary whose Kind cell says work_object'):
        doc = '| Term | Meaning | Kind |\n|---|---|---|\n| Room | y | work_object |\n'
        attach('Glossary file', doc)
        path = tmp_path / 'g.md'
        path.write_text(doc, encoding='utf-8')
    with when(t'the {pg["File glossary"]} parses the kind'):
        glossary = FileGlossary(path, kind_column='Kind')
    with then(t'it normalizes to the {pg["Work Object"]} kind'):
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
            t'the {pg["File glossary"]} loads the file',
            'a PytestGivenError names the unrecognized kind',
        ),
        pytest.raises(PytestGivenError, match='Wizard'),
    ):
        FileGlossary(path, kind_column='Kind')


@scenario(
    t'A missing {pg["Glossary"].low} file is reported clearly',
    tags=['validation'],
)
def test_missing_file_raises(tmp_path):
    with given('a path to a file that does not exist'):
        missing = tmp_path / 'nope.md'
    with (
        when_then(
            t'a {pg["File glossary"]} is opened on that path',
            'a PytestGivenError reports the file is not found',
        ),
        pytest.raises(PytestGivenError, match=r'not found|exist'),
    ):
        FileGlossary(missing)


def test_glossary_property_returns_inner_glossary(glossary_file):
    """FileGlossary.glossary property returns the inner Glossary with parsed terms."""
    fg = FileGlossary(glossary_file)
    inner = fg.glossary
    assert inner is not None
    assert inner.get(TermId('guest')) is not None


@scenario(
    t'A {pg["Term"].low} cell with no alphanumeric characters is rejected',
    tags=['diagnostics', 'validation'],
)
def test_empty_id_term_cell_raises(tmp_path):
    with given(t'a row whose {pg["Term"]} cell has no id-able characters'):
        doc = '| Term | Meaning |\n|---|---|\n| @#$ | some definition |\n'
        attach('Glossary file', doc)
        path = tmp_path / 'bad.md'
        path.write_text(doc, encoding='utf-8')
    with (
        when_then(
            t'the {pg["File glossary"]} loads the file',
            'a PytestGivenError is raised with file:line context',
        ),
        pytest.raises(PytestGivenError, match=r'bad\.md:3'),
    ):
        FileGlossary(path)


@scenario(
    'Conflicting duplicate rows are rejected',
    tags=['validation'],
)
def test_conflicting_duplicate_rows_raise(tmp_path):
    with given(t'two rows for one {pg["Term"]} with different definitions'):
        doc = (
            '| Term | Meaning |\n|---|---|\n'
            '| Guest | First definition. |\n'
            '| Guest | Second definition. |\n'
        )
        attach('Glossary file', doc)
        path = tmp_path / 'dup.md'
        path.write_text(doc, encoding='utf-8')
    with (
        when_then(
            t'the {pg["File glossary"]} loads the file',
            'a PytestGivenError reports the conflicting rows',
        ),
        pytest.raises(PytestGivenError, match='conflicts'),
    ):
        FileGlossary(path)


@scenario(
    t'A blank description normalizes to {pg["Undefined"].low}',
)
def test_blank_description_cell_normalizes_to_none(tmp_path):
    with given(t'a row whose description cell is blank'):
        doc = '| Term | Meaning |\n|---|---|\n| Guest |   |\n'
        attach('Glossary file', doc)
        path = tmp_path / 'g.md'
        path.write_text(doc, encoding='utf-8')
    with when(t'the {pg["File glossary"]} parses it'):
        fg = FileGlossary(path)
    with then(t'the {pg["Term"]} definition is None, i.e. {pg["Undefined"]}'):
        assert fg.glossary.get(TermId('guest')).definition is None


@scenario(
    t'Identical duplicate rows collapse to one {pg["Term"].low}',
)
def test_idempotent_duplicate_rows_ok(tmp_path):
    with given(t'two identical rows for the same {pg["Term"]}'):
        doc = (
            '| Term | Meaning |\n|---|---|\n'
            '| Guest | A person booking. |\n'
            '| Guest | A person booking. |\n'
        )
        attach('Glossary file', doc)
        path = tmp_path / 'dup_ok.md'
        path.write_text(doc, encoding='utf-8')
    with when(t'the {pg["File glossary"]} parses them'):
        fg = FileGlossary(path)
    with then(t'they collapse to a single {pg["Term"]}'):
        assert len(fg.glossary.terms) == 1
        assert fg.glossary.get(TermId('guest')) is not None


# --- Task 3: FileGlossary.__call__ (lookup-only, closed vocabulary) ---


@scenario(
    t'Calling {pg["File glossary"]("FileGlossary")} looks up a known {pg["Term"].low}',
)
def test_file_glossary_call_known_name_returns_handle(glossary_file):
    with given(t'a {pg["File glossary"]} loaded from a Markdown file'):
        attach('Glossary file', GLOSSARY_MD)
        glossary = FileGlossary(glossary_file)
    with when(t'a known {pg["Term"]} is looked up by call'):
        handle = glossary('Guest')
    with then(t'a {pg["Deferred term"]} is returned'):
        assert handle.declared_kind is None
        assert handle.term.canonical == 'Guest'


@scenario(
    t'{pg["File glossary"]("FileGlossary")} is a closed vocabulary',
    tags=['validation'],
)
def test_file_glossary_call_unknown_name_raises(glossary_file):
    with given(t'a {pg["File glossary"]} loaded from a Markdown file'):
        attach('Glossary file', GLOSSARY_MD)
        glossary = FileGlossary(glossary_file)
    with (
        when_then(
            'an unknown name is called',
            'a PytestGivenError is raised',
        ),
        pytest.raises(PytestGivenError, match='no glossary term'),
    ):
        glossary('Unknown Term')
    with then(t'no new {pg["Term"]} was created'):
        assert len(glossary.glossary.terms) == 3
