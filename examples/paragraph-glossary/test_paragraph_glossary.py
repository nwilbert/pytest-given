"""Paragraph glossary example: a lending library.

Demonstrates ParagraphGlossary reading `**Term**:` paragraphs from a Markdown
file in the format Matt Pocock's `domain-modeling` skill writes.

Key behaviours shown:
- Subheadings under `## Language` (Lending, Penalties, Q&A) become the
  glossary's sections, and the `Language` heading itself names none.
- `_Avoid_:` lines give the words the team does not use for a term.
- `## Relationships` and `## Flagged ambiguities` are not term text, so the
  reader skips them.
- Definition refs (`**Member**` inside a definition) link terms to each other.
"""

from datetime import date, timedelta
from pathlib import Path

from pytest_given import (
    ParagraphGlossary,
    given,
    scenario,
    sentence,
    story,
    then,
    when,
)

g = ParagraphGlossary(Path(__file__).parent / 'GLOSSARY.md')

lend_an_item = story(
    'Lend an Item',
    [
        sentence(g['Member'], g['lend'].s, g['Item']),
        sentence(g['Member'], 'returns', g['Item']),
    ],
)


class Library:
    LOAN_DAYS = 21

    def __init__(self):
        self.loans = {}

    def lend(self, item, member, on):
        self.loans[item] = {'member': member, 'due': on + timedelta(self.LOAN_DAYS)}
        return self.loans[item]

    def renew(self, item):
        self.loans[item]['due'] += timedelta(self.LOAN_DAYS)

    def fine(self, item, on):
        days_late = (on - self.loans[item]['due']).days
        return max(days_late, 0) * 10


@scenario('A Member borrows an Item for a Loan', stories=lend_an_item)
def test_lend_an_item():
    with given(t'a {g["Member"]} and an {g["Item"]}'):
        member, item = 'Ada', 'Dune'
    with when(t'the library {g["lend"].s} the {g["Item"]}'):
        loan = Library().lend(item, member, date(2026, 1, 1))
    with then(t'the {g["Loan"]} ends on its {g["Due Date"]}'):
        assert loan['due'] == date(2026, 1, 22)


@scenario('A Renewal moves the Due Date later')
def test_renewal():
    with given(t'a {g["Loan"]} of an {g["Item"]}'):
        library = Library()
        library.lend('Dune', 'Ada', date(2026, 1, 1))
    with when(t'the {g["Member"]} asks for a {g["Renewal"]}'):
        library.renew('Dune')
    with then(t'the {g["Due Date"]} moves three weeks later'):
        assert library.loans['Dune']['due'] == date(2026, 2, 12)


@scenario('A late return costs a Fine')
def test_fine_for_late_return():
    with given(t'a {g["Loan"]} that is past its {g["Due Date"]}'):
        library = Library()
        library.lend('Dune', 'Ada', date(2026, 1, 1))
    with when(t'the {g["Member"]} returns the {g["Item"]} four days late'):
        fine = library.fine('Dune', date(2026, 1, 26))
    with then(t'the {g["Member"]} owes a {g["Fine"]}'):
        assert fine == 40


@scenario('A timely return costs no Fine')
def test_no_fine_for_timely_return():
    with given(t'a {g["Loan"]} that is not yet past its {g["Due Date"]}'):
        library = Library()
        library.lend('Dune', 'Ada', date(2026, 1, 1))
    with when(t'the {g["Member"]} returns the {g["Item"]}'):
        fine = library.fine('Dune', date(2026, 1, 10))
    with then(t'the {g["Member"]} owes no {g["Fine"]}'):
        assert fine == 0
