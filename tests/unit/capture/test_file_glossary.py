import pytest

from pytest_given.capture.file_glossary import FileGlossary, FileTermHandle
from pytest_given.capture.story import activity
from pytest_given.model import ActivityTermRef, PytestGivenError

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


def test_lookup_is_case_insensitive(glossary_file):
    glossary = FileGlossary(glossary_file)
    assert isinstance(glossary['Guest'], FileTermHandle)
    assert glossary['guest'].id == glossary['GUEST'].id == 'guest'


def test_handles_are_memoized(glossary_file):
    glossary = FileGlossary(glossary_file)
    assert glossary['Room'] is glossary['room']


def test_terms_start_kindless(glossary_file):
    glossary = FileGlossary(glossary_file)
    assert glossary['Guest'].term.kind is None


def test_unknown_name_raises_with_suggestion(glossary_file):
    glossary = FileGlossary(glossary_file)
    with pytest.raises(PytestGivenError, match='Gues'):
        glossary['Gues']


def test_usable_inline_in_activity(glossary_file):
    glossary = FileGlossary(glossary_file)
    built = activity(glossary['Guest'], glossary['search'], glossary['Room'])
    parts = built.paths[0].parts
    assert parts[0] == ActivityTermRef(term_id='guest', display='Guest')
    assert parts[1] == ActivityTermRef(term_id='search', display='search')


def test_call_overrides_display(glossary_file):
    glossary = FileGlossary(glossary_file)
    built = activity(
        glossary['Guest']('Carol'), glossary['search']('searches for'), glossary['Room']
    )
    assert built.paths[0].parts[0] == ActivityTermRef(term_id='guest', display='Carol')


def test_explicit_kind_column(tmp_path):
    path = tmp_path / 'g.md'
    path.write_text(
        '| Term | Meaning | Kind |\n|---|---|---|\n'
        '| Guest | x | Actor |\n| Room | y | Work Object |\n',
        encoding='utf-8',
    )
    glossary = FileGlossary(path, kind_column='Kind')
    assert glossary['Guest'].term.kind == 'actor'
    assert glossary['Room'].term.kind == 'object'


def test_unrecognised_kind_value_raises(tmp_path):
    path = tmp_path / 'g.md'
    path.write_text(
        '| Term | Meaning | Kind |\n|---|---|---|\n| Guest | x | Wizard |\n',
        encoding='utf-8',
    )
    with pytest.raises(PytestGivenError, match='Wizard'):
        FileGlossary(path, kind_column='Kind')


def test_missing_file_raises(tmp_path):
    with pytest.raises(PytestGivenError, match=r'not found|exist'):
        FileGlossary(tmp_path / 'nope.md')
