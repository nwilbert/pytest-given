"""Unit tests for the Glossary view's grouping (`report/glossary_view.py`)."""

from pytest_given.model import (
    Clause,
    ClauseTermRef,
    Glossary,
    GlossaryTerm,
    Metadata,
    ReportData,
    Sentence,
    SentenceId,
    Story,
    StoryId,
    TermId,
)
from pytest_given.report.glossary_view import build_glossary_view


def _ent(tid: str, display: str) -> ClauseTermRef:
    return ClauseTermRef(term_id=TermId(tid), display=display)


def _g() -> Glossary:
    g = Glossary()
    g.register(GlossaryTerm(id=TermId('guest'), kind='actor', canonical='Guest'))
    g.register(GlossaryTerm(id=TermId('room'), kind='object', canonical='Room'))
    g.register(GlossaryTerm(id=TermId('search'), kind='activity', canonical='search'))
    return g


def _meta() -> Metadata:
    return Metadata(project='p', timestamp='t', pytest_version='8', plugin_version='0')


def test_a_term_summary_counts_its_other_forms_whatever_its_kind() -> None:
    sentence = Sentence(
        id=SentenceId(1),
        clauses=(
            Clause(
                parts=(
                    _ent('guest', 'Alice'),
                    ClauseTermRef(term_id=TermId('search'), display='searches for'),
                    _ent('room', 'Room'),
                )
            ),
        ),
    )
    story = Story(id=StoryId('book'), title='Book', sentences=(sentence,))
    view = build_glossary_view(
        ReportData(metadata=_meta(), stories=[story], glossary=_g())
    )
    summaries = {
        entry.term.id: entry.summary
        for group in view.grouping.groups
        for entry in group.entries
    }
    assert summaries[TermId('guest')] == ('1 other form', '1 story')
    assert summaries[TermId('search')] == ('1 other form', '1 story')
    assert summaries[TermId('room')] == ('1 story',)


def test_kind_summaries_use_irregular_plurals() -> None:
    glossary = _g()
    glossary.register(
        GlossaryTerm(id=TermId('book'), kind='activity', canonical='book')
    )
    view = build_glossary_view(ReportData(metadata=_meta(), glossary=glossary))
    assert [kind.summary for kind in view.grouping.kinds] == [
        '1 actor',
        '1 work object',
        '2 activities',
    ]
