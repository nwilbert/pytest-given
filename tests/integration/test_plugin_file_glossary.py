import json

from pytest_given import attach, given, scenario, then, when
from tests.ubiquitous_language import pg

GLOSSARY_MD = """# Glossary

| Term | Meaning |
|------|---------|
| Guest  | A person booking. |
| Room   | A bookable room. |
| search | Look up options. |
"""

CONFTEST = """
from pytest_given import FileGlossary

g = FileGlossary('GLOSSARY.md')
"""

TEST_FILE = """
from pytest_given import scenario, when, story, sentence
from conftest import g

book = story('Book a room', [sentence(g['Guest'], g['search'], g['Room'])])


@scenario('Guest searches', stories=book)
def test_guest_searches():
    with when(t'{g["Guest"]} {g["search"]("searches for")} a {g["Room"]}'):
        pass
"""


@scenario(
    t'A run gives each {pg["Kindless"].l} {pg["Term"].l} the kind of the '
    t'{pg["Slot"].l} it fills',
)
def test_file_glossary_kinds_resolved_in_report(pytester):
    with given(
        t'a {pg["File glossary"].l} of {pg["Kindless"].l} {pg["Term"].l.s} and a '
        t'{pg["Story"].l} whose {pg["Sentence"].l} uses them'
    ):
        pytester.makefile('.md', GLOSSARY=GLOSSARY_MD)
        pytester.makeconftest(CONFTEST)
        pytester.makepyfile(test_file=TEST_FILE)
        attach('GLOSSARY.md', GLOSSARY_MD.strip())
        attach('test_file.py', TEST_FILE.strip())
        json_path = pytester.path / 'report-data.json'
    with when('the suite runs with --given-json'):
        result = pytester.runpytest_subprocess('--given-json', str(json_path))
    with then('the scenario passes'):
        result.assert_outcomes(passed=1)
    with then(
        t'each {pg["Term"].l} in the {pg["Report"].l} takes the kind of its '
        t'{pg["Slot"].l}: actor, activity, object'
    ):
        data = json.loads(json_path.read_text(encoding='utf-8'))
        kinds = {term['id']: term['kind'] for term in data['glossary']['terms']}
        assert kinds == {'guest': 'actor', 'search': 'activity', 'room': 'object'}
