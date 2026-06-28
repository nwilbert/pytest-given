import json

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
from pytest_given import scenario, when, story, activity
from conftest import g

book = story('Book a room', [activity(g['Guest'], g['search'], g['Room'])])


@scenario('Guest searches', story=book)
def test_guest_searches():
    with when(t'{g["Guest"]} {g["search"]("searches for")} a {g["Room"]}'):
        pass
"""


def test_file_glossary_kinds_resolved_in_report(pytester):
    pytester.makefile('.md', GLOSSARY=GLOSSARY_MD)
    pytester.makeconftest(CONFTEST)
    pytester.makepyfile(test_file=TEST_FILE)
    json_path = pytester.path / 'report-data.json'
    result = pytester.runpytest_subprocess('--given-json', str(json_path))
    result.assert_outcomes(passed=1)

    data = json.loads(json_path.read_text(encoding='utf-8'))
    kinds = {term['id']: term['kind'] for term in data['glossary']['terms']}
    assert kinds == {'guest': 'actor', 'search': 'verb', 'room': 'object'}
