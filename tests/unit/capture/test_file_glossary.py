import pytest

from pytest_given import given, scenario, then, when
from pytest_given.capture.file_glossary import FileGlossary
from pytest_given.capture.glossary import DeferredTermHandle
from pytest_given.capture.story import activity
from pytest_given.model import ActivityTermRef, PytestGivenError
from tests._vocab import pg, then_raises


@pytest.fixture(autouse=True)
def _reset_glossary_registry():
    from pytest_given.capture.glossary import clear_glossary_registry

    clear_glossary_registry()
    yield
    clear_glossary_registry()


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
    'FileGlossary lookup is case-insensitive',
    tags=['file-glossary', 'happy-path'],
)
def test_lookup_is_case_insensitive(glossary_file):
    with given(t'a {pg["FileGlossary"]} loaded from a Markdown file'):
        glossary = FileGlossary(glossary_file)
    with then(t'a {pg["Term"]} resolves regardless of case, to the same id'):
        assert isinstance(glossary['Guest'], DeferredTermHandle)
        assert glossary['guest'].id == glossary['GUEST'].id == 'guest'


@scenario(
    'Repeated lookups return the same handle',
    tags=['file-glossary', 'happy-path'],
)
def test_handles_are_memoized(glossary_file):
    with given(t'a {pg["FileGlossary"]} loaded from a Markdown file'):
        glossary = FileGlossary(glossary_file)
    with then(t'looking up the same {pg["Term"]} twice returns one handle'):
        assert glossary['Room'] is glossary['room']


@scenario(
    'File-loaded terms start kindless',
    tags=['file-glossary', 'inference'],
)
def test_terms_start_kindless(glossary_file):
    with given(t'a {pg["FileGlossary"]} with no kind column'):
        glossary = FileGlossary(glossary_file)
    with then(t'each {pg["Term"]} is {pg["Kindless"]} until inference runs'):
        assert glossary['Guest'].term.kind is None


@scenario(
    'An unknown name raises with a suggestion',
    tags=['file-glossary', 'validation'],
)
def test_unknown_name_raises_with_suggestion(glossary_file):
    with given(t'a {pg["FileGlossary"]} loaded from a Markdown file'):
        glossary = FileGlossary(glossary_file)
    with then_raises(
        t'looking up a misspelt {pg["Term"]} raises with a hint',
        PytestGivenError,
        match='Gues',
    ):
        glossary['Gues']


@scenario(
    'Handles are usable inline in an activity',
    tags=['file-glossary', 'story-grammar'],
)
def test_usable_inline_in_activity(glossary_file):
    with given(t'a {pg["FileGlossary"]} loaded from a Markdown file'):
        glossary = FileGlossary(glossary_file)
    with when(t'its handles build an {pg["Activity"]}'):
        built = activity(glossary['Guest'], glossary['search'], glossary['Room'])
    with then(t'each slot becomes a {pg["Term ref"]}'):
        parts = built.paths[0].parts
        assert parts[0] == ActivityTermRef(term_id='guest', display='Guest')
        assert parts[1] == ActivityTermRef(term_id='search', display='search')


@scenario(
    'Calling a handle overrides its display',
    tags=['file-glossary', 'story-grammar'],
)
def test_call_overrides_display(glossary_file):
    with given(t'a {pg["FileGlossary"]} loaded from a Markdown file'):
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
    'An explicit kind column sets term kinds',
    tags=['file-glossary', 'inference'],
)
def test_explicit_kind_column(tmp_path):
    with given(t'a Markdown glossary with an explicit Kind column'):
        path = tmp_path / 'g.md'
        path.write_text(
            '| Term | Meaning | Kind |\n|---|---|---|\n'
            '| Guest | x | Actor |\n| Room | y | Work Object |\n',
            encoding='utf-8',
        )
    with when(t'the {pg["FileGlossary"]} reads the Kind column'):
        glossary = FileGlossary(path, kind_column='Kind')
    with then(t'kinds come straight from the file, not {pg["Kindless"]} inference'):
        assert glossary['Guest'].term.kind == 'actor'
        assert glossary['Room'].term.kind == 'object'


@scenario(
    'A kind column can be selected by integer index',
    tags=['file-glossary', 'inference'],
)
def test_kind_column_by_integer_index(tmp_path):
    with given('a Markdown glossary with the kind in the third column'):
        path = tmp_path / 'g.md'
        path.write_text(
            '| Term | Meaning | Kind |\n|---|---|---|\n'
            '| Guest | x | Actor |\n| Room | y | Work Object |\n',
            encoding='utf-8',
        )
    with when(t'the {pg["FileGlossary"]} selects the kind column by index'):
        glossary = FileGlossary(path, kind_column=2)
    with then('the kinds are read from that column'):
        assert glossary['Guest'].term.kind == 'actor'
        assert glossary['Room'].term.kind == 'object'


@scenario(
    'A work_object kind alias maps to the object kind',
    tags=['file-glossary', 'inference'],
)
def test_work_object_underscore_alias(tmp_path):
    with given(t'a glossary whose Kind cell says work_object'):
        path = tmp_path / 'g.md'
        path.write_text(
            '| Term | Meaning | Kind |\n|---|---|---|\n| Room | y | work_object |\n',
            encoding='utf-8',
        )
    with when(t'the {pg["FileGlossary"]} parses the kind'):
        glossary = FileGlossary(path, kind_column='Kind')
    with then(t'it normalizes to the {pg["Work Object"]} kind'):
        assert glossary['Room'].term.kind == 'object'


@scenario(
    'An unrecognised kind value is rejected',
    tags=['file-glossary', 'validation'],
)
def test_unrecognised_kind_value_raises(tmp_path):
    with given('a glossary whose Kind cell holds an unknown value'):
        path = tmp_path / 'g.md'
        path.write_text(
            '| Term | Meaning | Kind |\n|---|---|---|\n| Guest | x | Wizard |\n',
            encoding='utf-8',
        )
    with then_raises(
        t'loading the {pg["FileGlossary"]} raises', PytestGivenError, match='Wizard'
    ):
        FileGlossary(path, kind_column='Kind')


@scenario(
    'A missing glossary file is reported clearly',
    tags=['file-glossary', 'validation'],
)
def test_missing_file_raises(tmp_path):
    with then_raises(
        t'pointing a {pg["FileGlossary"]} at a missing file raises',
        PytestGivenError,
        match=r'not found|exist',
    ):
        FileGlossary(tmp_path / 'nope.md')


def test_glossary_property_returns_inner_glossary(glossary_file):
    """FileGlossary.glossary property returns the inner Glossary with parsed terms."""
    from pytest_given.model import TermId

    fg = FileGlossary(glossary_file)
    inner = fg.glossary
    assert inner is not None
    assert inner.get(TermId('guest')) is not None


@scenario(
    'A term cell with no alphanumeric characters is rejected',
    tags=['file-glossary', 'validation'],
)
def test_empty_id_term_cell_raises(tmp_path):
    with given(t'a row whose {pg["Term"]} cell has no id-able characters'):
        path = tmp_path / 'bad.md'
        path.write_text(
            '| Term | Meaning |\n|---|---|\n| @#$ | some definition |\n',
            encoding='utf-8',
        )
    with then_raises(
        'loading raises with file:line context', PytestGivenError, match=r'@#\$|id'
    ):
        FileGlossary(path)


@scenario(
    'Conflicting duplicate rows are rejected',
    tags=['file-glossary', 'validation'],
)
def test_conflicting_duplicate_rows_raise(tmp_path):
    with given(t'two rows for one {pg["Term"]} with different definitions'):
        path = tmp_path / 'dup.md'
        path.write_text(
            '| Term | Meaning |\n|---|---|\n'
            '| Guest | First definition. |\n'
            '| Guest | Second definition. |\n',
            encoding='utf-8',
        )
    with then_raises(
        'loading raises a conflict error', PytestGivenError, match='conflicts'
    ):
        FileGlossary(path)


@scenario(
    'A blank description normalizes to undefined',
    tags=['file-glossary', 'happy-path'],
)
def test_blank_description_cell_normalizes_to_none(tmp_path):
    from pytest_given.model import TermId

    with given(t'a row whose description cell is blank'):
        path = tmp_path / 'g.md'
        path.write_text(
            '| Term | Meaning |\n|---|---|\n| Guest |   |\n',
            encoding='utf-8',
        )
    with when(t'the {pg["FileGlossary"]} parses it'):
        fg = FileGlossary(path)
    with then(t'the {pg["Term"]} definition is None, i.e. {pg["Undefined"]}'):
        assert fg.glossary.get(TermId('guest')).definition is None


@scenario(
    'Identical duplicate rows collapse to one term',
    tags=['file-glossary', 'happy-path'],
)
def test_idempotent_duplicate_rows_ok(tmp_path):
    from pytest_given.model import TermId

    with given(t'two identical rows for the same {pg["Term"]}'):
        path = tmp_path / 'dup_ok.md'
        path.write_text(
            '| Term | Meaning |\n|---|---|\n'
            '| Guest | A person booking. |\n'
            '| Guest | A person booking. |\n',
            encoding='utf-8',
        )
    with when(t'the {pg["FileGlossary"]} parses them'):
        fg = FileGlossary(path)
    with then(t'they collapse to a single {pg["Term"]}'):
        assert len(fg.glossary.terms) == 1
        assert fg.glossary.get(TermId('guest')) is not None


# --- Task 3: FileGlossary.__call__ (lookup-only, closed vocabulary) ---


@scenario(
    'Calling FileGlossary looks up a known term',
    tags=['file-glossary', 'happy-path'],
)
def test_file_glossary_call_known_name_returns_handle(glossary_file):
    with given(t'a {pg["FileGlossary"]} loaded from a Markdown file'):
        glossary = FileGlossary(glossary_file)
    with when(t'a known {pg["Term"]} is looked up by call'):
        handle = glossary('Guest')
    with then(t'a {pg["DeferredTermHandle"]} is returned'):
        assert isinstance(handle, DeferredTermHandle)
        assert handle.term.canonical == 'Guest'


@scenario(
    'FileGlossary is a closed vocabulary',
    tags=['file-glossary', 'validation'],
)
def test_file_glossary_call_unknown_name_raises(glossary_file):
    with given(t'a {pg["FileGlossary"]} loaded from a Markdown file'):
        glossary = FileGlossary(glossary_file)
    with then_raises(
        t'calling an unknown name raises — it never creates a {pg["Term"]}',
        PytestGivenError,
        match='no glossary term',
    ):
        glossary('Unknown Term')
