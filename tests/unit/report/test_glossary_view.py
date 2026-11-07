"""Unit tests for the Glossary view's grouping (`report/glossary_view.py`)."""

import pytest

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
from pytest_given.report.glossary_view import OTHER_SECTION, build_glossary_view


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


def _sectioned(*sections: str | None, kind: bool = True) -> ReportData:
    glossary = Glossary(
        terms=[
            GlossaryTerm(
                id=TermId(f't{index}'),
                kind='actor' if kind else None,
                canonical=f'Term {index}',
                section=section,
            )
            for index, section in enumerate(sections)
        ]
    )
    return ReportData(metadata=_meta(), glossary=glossary)


def test_section_order_by_first_term() -> None:
    view = build_glossary_view(_sectioned('Stay', 'Booking', 'Stay', 'Payment'))
    assert [group.label for group in view.section_groups] == [
        'Stay',
        'Booking',
        'Payment',
    ]
    assert [len(group.entries) for group in view.section_groups] == [2, 1, 1]


def test_other_group_for_sectionless_terms() -> None:
    view = build_glossary_view(_sectioned(None, 'Stay', 'Booking'))
    assert [(group.label, group.key) for group in view.section_groups] == [
        ('Stay', 'Stay'),
        ('Booking', 'Booking'),
        ('Other', OTHER_SECTION),
    ]


def test_section_counts() -> None:
    view = build_glossary_view(_sectioned('Stay', 'Booking', 'Stay', None))
    assert [(group.label, len(group.entries)) for group in view.section_groups] == [
        ('Stay', 2),
        ('Booking', 1),
        ('Other', 1),
    ]


def test_authored_other_merges_and_comes_last() -> None:
    view = build_glossary_view(_sectioned('Misc other', 'other', None, 'Stay'))
    assert [(group.label, group.key) for group in view.section_groups] == [
        ('Misc other', 'Misc other'),
        ('Stay', 'Stay'),
        ('other', OTHER_SECTION),
    ]
    assert len(view.section_groups[-1].entries) == 2


def test_authored_other_last_without_sectionless_terms() -> None:
    view = build_glossary_view(_sectioned('Other', 'Stay'))
    assert [group.key for group in view.section_groups] == ['Stay', OTHER_SECTION]


def test_other_spellings_merge_counted_once() -> None:
    view = build_glossary_view(_sectioned('Other', 'other', 'Booking'))
    assert view.default_grouping == 'section'
    assert [(group.label, len(group.entries)) for group in view.section_groups] == [
        ('Booking', 1),
        ('Other', 2),
    ]


def test_single_section_shown_as_none() -> None:
    view = build_glossary_view(_sectioned('Terms', 'Terms', None))
    assert view.section_groups == []
    assert view.default_grouping == 'kind'


@pytest.mark.parametrize(
    ('sectioned', 'kinds', 'switch', 'grouping'),
    [
        (True, True, True, 'section'),
        (True, False, False, 'section'),
        (False, True, False, 'kind'),
        (False, False, False, 'flat'),
    ],
)
def test_switch_visibility(
    sectioned: bool, kinds: bool, switch: bool, grouping: str
) -> None:
    sections = ('Stay', 'Booking') if sectioned else (None, None)
    view = build_glossary_view(_sectioned(*sections, kind=kinds))
    assert (view.show_grouping_switch, view.default_grouping) == (switch, grouping)


def test_a_term_reaches_the_view_with_its_section_and_avoided_words() -> None:
    report = ReportData(
        metadata=_meta(),
        glossary=Glossary(
            terms=[
                GlossaryTerm(
                    id=TermId('guest'),
                    kind='actor',
                    canonical='Guest',
                    section='People',
                    avoid=('Customer (too broad)', '**Client**'),
                ),
                GlossaryTerm(
                    id=TermId('room'),
                    kind='object',
                    canonical='Room',
                    section='Places',
                ),
            ]
        ),
    )
    view = build_glossary_view(report)
    assert [group.label for group in view.section_groups] == ['People', 'Places']
    [entry] = view.section_groups[0].entries
    assert entry.term.avoid == ('Customer (too broad)', '**Client**')
