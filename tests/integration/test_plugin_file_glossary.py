import json

from pytest_given import attach, given, scenario, then, when
from pytest_given.cli import main
from pytest_given.model import read_report_json, report_from_dict
from pytest_given.report.glossary_view import build_glossary_view
from pytest_given.report.html_renderer import _app_data
from tests.ubiquitous_language import pg

GLOSSARY_MD = """# Glossary

| Term | Meaning |
|------|---------|
| Guest  | A person booking. |
| Room   | A bookable room. |
| search | Look up options. |
"""

CONFTEST = """
from pytest_given import TableGlossary

g = TableGlossary('GLOSSARY.md')
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
    t"A {pg['Markdown glossary'].l}'s {pg['Kindless'].l} {pg['Term'].l.s} reach the "
    t'{pg["Report"].l} with the kinds the run infers',
)
def test_file_glossary_kinds_resolved_in_report(pytester):
    with given(
        t'a {pg["Markdown glossary"].l} of {pg["Kindless"].l} {pg["Term"].l.s} and a '
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


PARAGRAPH_GLOSSARY_MD = """# Ordering

## Checkout

**Order**:
A customer's request for goods, placed in one checkout.
_Avoid_: Purchase, transaction
"""

PARAGRAPH_CONFTEST = """
from pytest_given import ParagraphGlossary

g = ParagraphGlossary('GLOSSARY.md')
"""

PARAGRAPH_TEST_FILE = """
from pytest_given import scenario, when
from conftest import g


@scenario('An order is placed')
def test_order_placed():
    with when(t'an {g["Order"]} is placed'):
        pass
"""


def test_paragraph_glossary_discovered_in_conftest(pytester):
    pytester.makefile('.md', GLOSSARY=PARAGRAPH_GLOSSARY_MD)
    pytester.makeconftest(PARAGRAPH_CONFTEST)
    pytester.makepyfile(test_file=PARAGRAPH_TEST_FILE)
    json_path = pytester.path / 'report-data.json'
    result = pytester.runpytest_subprocess('--given-json', str(json_path))
    result.assert_outcomes(passed=1)
    data = json.loads(json_path.read_text(encoding='utf-8'))
    [term] = data['glossary']['terms']
    assert (term['canonical'], term['section'], term['avoid']) == (
        'Order',
        'Checkout',
        ['Purchase', 'transaction'],
    )


SECTIONED_CONFTEST = """
from pytest_given import Glossary

g = Glossary()
people = g.section('People')
places = g.section('Places')
guest = people.actor('Guest', avoid=['Customer (too broad)', '**Client**'])
room = places.work_object('Room')
"""

SECTIONED_TEST_FILE = """
from pytest_given import scenario, when
from conftest import guest, room


@scenario('Guest books')
def test_guest_books():
    with when(t'{guest} books a {room}'):
        pass
"""


@scenario(
    t"A saved {pg['Report'].l} re-renders with each {pg['Term'].l}'s "
    t'{pg["Glossary section"].l} and {pg["Avoided word"].l.s}',
    tags=['spec/glossary-sections'],
)
def test_saved_json_rerenders_sections_and_avoid(pytester):
    with given(
        t'a suite whose code {pg["Glossary"].l} sorts {pg["Term"].l.s} into two '
        t'{pg["Glossary section"].l.s} and gives one {pg["Avoided word"].l.s}'
    ):
        pytester.makeconftest(SECTIONED_CONFTEST)
        pytester.makepyfile(test_file=SECTIONED_TEST_FILE)
        attach('conftest.py', SECTIONED_CONFTEST.strip())
        json_path = pytester.path / 'report-data.json'
        html_path = pytester.path / 'report.html'
    with when(t'it runs with --given-json and the {pg["Report"].l} is re-rendered'):
        result = pytester.runpytest_subprocess('--given-json', str(json_path))
        report = report_from_dict(read_report_json(json_path))
        exit_code = main(['report', str(json_path), '-o', str(html_path)])
    with then('the run passes and the re-render succeeds'):
        result.assert_outcomes(passed=1)
        assert exit_code == 0
        assert html_path.exists()
    with then(
        t'the {pg["Glossary"].l} view groups the {pg["Term"].l.s} by '
        t'{pg["Glossary section"].l}'
    ):
        view = build_glossary_view(report)
        assert [group.label for group in view.section_groups] == ['People', 'Places']
    with then(t'the {pg["Avoided word"].l.s} survive, note included'):
        [guest] = view.section_groups[0].entries
        assert guest.term.avoid == ('Customer (too broad)', '**Client**')
    with then(t'the page data carries each {pg["Avoided word"].l} as a plain word'):
        data = _app_data(report)['glossary']
        assert isinstance(data, dict)
        terms = {term['id']: term for term in data['terms']}
        assert terms['guest']['avoid'] == ['Customer', 'Client']
        assert terms['guest']['section_key'] == 'People'
