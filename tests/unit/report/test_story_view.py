"""Unit tests for the Stories-view rollups (`report/story_view.py`), plus
the tab visibility the report shell derives."""

import dataclasses

import pytest

from pytest_given import given, scenario, then, when
from pytest_given.model import (
    Clause,
    ClauseTermRef,
    ClauseWord,
    Glossary,
    GlossaryTerm,
    Metadata,
    Narration,
    NarrationTermRef,
    NodeId,
    Pin,
    ReportData,
    Scenario,
    Sentence,
    SentenceId,
    Status,
    Step,
    Story,
    StoryId,
    TermId,
)
from pytest_given.report.coverage import build_coverage_map
from pytest_given.report.html_renderer import TabVisibility, tab_visibility
from pytest_given.report.story_view import (
    build_sentence_labels,
    build_story_rollups,
)
from tests.ubiquitous_language import pg


def _ent(tid: str, display: str) -> ClauseTermRef:
    return ClauseTermRef(term_id=TermId(tid), display=display)


def _activity_part(tid: str) -> ClauseTermRef:
    return ClauseTermRef(term_id=TermId(tid), display=tid)


def _g() -> Glossary:
    g = Glossary()
    g.register(GlossaryTerm(id=TermId('guest'), kind='actor', canonical='Guest'))
    g.register(GlossaryTerm(id=TermId('room'), kind='object', canonical='Room'))
    g.register(GlossaryTerm(id=TermId('search'), kind='activity', canonical='search'))
    return g


def _meta() -> Metadata:
    return Metadata(project='p', timestamp='t', pytest_version='8', plugin_version='0')


def test_tab_visibility_only_scenarios_visible_with_empty_report() -> None:
    rd = ReportData(metadata=_meta())
    assert tab_visibility(rd) == TabVisibility(stories=False, glossary=False)
    assert tab_visibility(rd).visible_count == 1


def test_tab_visibility_stories_visible_when_stories_non_empty() -> None:
    a = Sentence(
        id=SentenceId(1),
        clauses=(
            Clause(
                parts=(
                    _ent('guest', 'Guest'),
                    _activity_part('search'),
                    _ent('room', 'Room'),
                )
            ),
        ),
    )
    s = Story(id=StoryId('s'), title='S', sentences=(a,))
    rd = ReportData(metadata=_meta(), stories=[s])
    assert tab_visibility(rd).stories is True


def test_tab_visibility_glossary_visible_when_glossary_has_terms() -> None:
    rd = ReportData(metadata=_meta(), glossary=_g())
    assert tab_visibility(rd).glossary is True


def test_tab_visibility_glossary_hidden_when_glossary_is_empty() -> None:
    rd = ReportData(metadata=_meta(), glossary=Glossary())
    assert tab_visibility(rd).glossary is False


def test_build_coverage_maps_produces_per_scenario_dicts() -> None:
    g = _g()
    a = Sentence(
        id=SentenceId(1),
        clauses=(
            Clause(
                parts=(
                    _ent('guest', 'Guest'),
                    _activity_part('search'),
                    _ent('room', 'Room'),
                )
            ),
        ),
    )
    story = Story(id=StoryId('book'), title='Book', sentences=(a,))
    step = Step(
        phase='when',
        narration=Narration(
            text='x',
            parts=(
                NarrationTermRef(term_id=TermId('guest'), display='Guest'),
                NarrationTermRef(term_id=TermId('search'), display='search'),
                NarrationTermRef(term_id=TermId('room'), display='Room'),
            ),
        ),
    )
    scn = Scenario(
        id=NodeId('test::x'),
        narration=Narration(text='scn'),
        module='m',
        steps=[step],
        story_ids=(StoryId('book'),),
    )
    rd = ReportData(metadata=_meta(), scenarios=[scn], stories=[story], glossary=g)
    maps = build_coverage_map(rd)
    assert SentenceId(1) in maps[NodeId('test::x')][StoryId('book')]


def test_build_coverage_maps_empty_for_scenario_without_story() -> None:
    g = _g()
    scn = Scenario(
        id=NodeId('t'),
        narration=Narration(text='s'),
        module='m',
        steps=[],
    )
    rd = ReportData(metadata=_meta(), scenarios=[scn], glossary=g)
    maps = build_coverage_map(rd)
    assert maps[NodeId('t')] == {}


def test_build_coverage_maps_empty_when_no_glossary() -> None:
    scn = Scenario(
        id=NodeId('t'),
        narration=Narration(text='s'),
        module='m',
        steps=[],
    )
    rd = ReportData(metadata=_meta(), scenarios=[scn])
    maps = build_coverage_map(rd)
    assert maps == {NodeId('t'): {}}


def test_build_coverage_maps_empty_for_scenario_with_unknown_story_id() -> None:
    """Scenario has a story id that doesn't match any story in the report."""
    g = _g()
    scn = Scenario(
        id=NodeId('t'),
        narration=Narration(text='s'),
        module='m',
        steps=[],
        story_ids=(StoryId('nonexistent'),),
    )
    rd = ReportData(metadata=_meta(), scenarios=[scn], glossary=g)
    maps = build_coverage_map(rd)
    assert maps[NodeId('t')] == {}


def _one_sentence_story(story_id: str) -> Story:
    return Story(
        id=StoryId(story_id),
        title=story_id,
        sentences=(Sentence(id=SentenceId(1), clauses=()),),
    )


def test_a_scenario_is_listed_under_its_stories_and_the_stories_it_covers() -> None:
    """Listed under `stories=` even where nothing matched, under a story only
    a step pin reaches, and not under one a stale pin names."""
    pinned_step = Step(
        phase='when',
        narration=Narration(text='x'),
        pins=(
            Pin(story_id=StoryId('pinned'), sentence_id=SentenceId(1)),
            Pin(story_id=StoryId('stale'), sentence_id=SentenceId(1)),
        ),
    )
    scn = Scenario(
        id=NodeId('t'),
        narration=Narration(text='s'),
        module='m',
        steps=[pinned_step],
        story_ids=(StoryId('named'),),
    )
    rd = ReportData(
        metadata=_meta(),
        scenarios=[scn],
        stories=[_one_sentence_story('named'), _one_sentence_story('pinned')],
    )
    maps = build_coverage_map(rd)
    assert maps[NodeId('t')] == {
        StoryId('named'): set(),
        StoryId('pinned'): {SentenceId(1)},
    }
    rollups = build_story_rollups(rd, maps)
    assert [one.id for one in rollups[StoryId('pinned')].scenarios] == [NodeId('t')]


@scenario(
    t'An under-anchored {pg["Sentence"].l} reads as untracked until a '
    t'{pg["Pin"].l} covers it',
)
@pytest.mark.parametrize(
    ('anchored', 'pinned', 'eligible', 'untracked'),
    [
        (True, False, True, False),
        (False, False, False, True),
        (False, True, False, False),
    ],
)
def test_an_under_anchored_sentence_reads_as_untracked_until_pinned(
    anchored, pinned, eligible, untracked
) -> None:
    """`untracked` is what the timeline renders as '—'."""
    with given(
        t'a {pg["Story"].l} whose only {pg["Sentence"].l} is anchored by at '
        t'least two distinct {pg["Term"].l.s}: {anchored}'
    ):
        guest = _ent('guest', 'Guest')
        parts = (
            (guest, _activity_part('search'), _ent('room', 'Room'))
            if anchored
            else (guest, ClauseWord(text='browses'), ClauseWord(text='listings'))
        )
        only = Sentence(id=SentenceId(1), clauses=(Clause(parts=parts),))
        story = Story(id=StoryId('book'), title='Book', sentences=(only,))
    with given(
        t'a {pg["Scenario"].l} whose {pg["Step"].l} {pg["Pin"].l.s} it: {pinned}'
    ):
        scenario_ = Scenario(
            id=NodeId('test::a'),
            narration=Narration(text='a'),
            module='m',
            status='passed',
            story_ids=(StoryId('book'),),
            steps=[
                Step(
                    phase='when',
                    narration=Narration(text='the listing page is opened'),
                    pins=(Pin(story_id=StoryId('book'), sentence_id=SentenceId(1)),)
                    if pinned
                    else None,
                )
            ],
        )
        rd = ReportData(
            metadata=_meta(), scenarios=[scenario_], stories=[story], glossary=_g()
        )
    with when('the story rollups are built'):
        coverage = build_story_rollups(rd, build_coverage_map(rd))
        sentence_coverage = coverage[StoryId('book')].per_sentence[SentenceId(1)]
    with then(t'it is {pg["Coverage"].l}-eligible: {eligible}'):
        assert sentence_coverage.eligible == eligible
    with then(t'it reads as untracked: {untracked}'):
        assert sentence_coverage.untracked == untracked


def _covering_scn(node_id: str, status: Status) -> Scenario:
    """A scenario whose single step references guest/search/room, so it covers
    the guest-search-room sentence used across the rollup-count tests."""
    step = Step(
        phase='when',
        narration=Narration(
            text='x',
            parts=(
                NarrationTermRef(term_id=TermId('guest'), display='Guest'),
                NarrationTermRef(term_id=TermId('search'), display='search'),
                NarrationTermRef(term_id=TermId('room'), display='Room'),
            ),
        ),
    )
    return Scenario(
        id=NodeId(node_id),
        narration=Narration(text='scn'),
        module='m',
        steps=[step],
        story_ids=(StoryId('book'),),
        status=status,
    )


def test_build_story_rollups_counts_each_status_apart() -> None:
    g = _g()
    sentence = Sentence(
        id=SentenceId(1),
        clauses=(
            Clause(
                parts=(
                    _ent('guest', 'Guest'),
                    _activity_part('search'),
                    _ent('room', 'Room'),
                )
            ),
        ),
    )
    story = Story(id=StoryId('book'), title='Book', sentences=(sentence,))
    scns = [
        _covering_scn('test::a', 'passed'),
        _covering_scn('test::b', 'passed'),
        _covering_scn('test::c', 'failed'),
        _covering_scn('test::d', 'skipped'),
        _covering_scn('test::e', 'xfailed'),
    ]
    rd = ReportData(metadata=_meta(), scenarios=scns, stories=[story], glossary=g)
    rollups = build_story_rollups(rd, build_coverage_map(rd))
    cov = rollups[StoryId('book')].per_sentence[SentenceId(1)]
    assert cov.total == 5
    assert cov.passed == 2
    assert cov.failed == 1
    assert cov.skipped == 1
    assert cov.xfailed == 1


@scenario(
    t'A {pg["Scenario"].l} bound to two {pg["Story"].l.s} is listed under each',
)
def test_build_story_rollups_lists_a_scenario_under_each_bound_story() -> None:
    with given(
        t'two {pg["Story"].l.s} each with a guest-search-room {pg["Sentence"].l}'
    ):
        glossary = _g()
        clauses = (
            Clause(
                parts=(
                    _ent('guest', 'Guest'),
                    _activity_part('search'),
                    _ent('room', 'Room'),
                )
            ),
        )
        book = Story(
            id=StoryId('book'),
            title='Book',
            sentences=(Sentence(id=SentenceId(1), clauses=clauses),),
        )
        stay = Story(
            id=StoryId('stay'),
            title='Stay',
            sentences=(Sentence(id=SentenceId(1), clauses=clauses),),
        )
    with given(
        t'a {pg["Scenario"].l} bound to both whose {pg["Step"].l} names those terms'
    ):
        both = dataclasses.replace(
            _covering_scn('test::both', 'passed'),
            story_ids=(StoryId('book'), StoryId('stay')),
        )
        report = ReportData(
            metadata=_meta(), scenarios=[both], stories=[book, stay], glossary=glossary
        )
    with when('the story rollups are built'):
        rollups = build_story_rollups(report, build_coverage_map(report))
    with then(
        t'the {pg["Scenario"].l} is listed under, and covers, both {pg["Story"].l.s}'
    ):
        for story_id in (StoryId('book'), StoryId('stay')):
            assert rollups[story_id].scenarios == [both]
            assert rollups[story_id].per_sentence[SentenceId(1)].scenario_ids == [
                both.id
            ]


@scenario(
    t'A {pg["Sentence"].l} is labeled by the prose of its {pg["Clause"].l.s}',
)
def test_build_sentence_labels_joins_parts_into_prose() -> None:
    with given(t'a {pg["Story"].l} with a two-{pg["Clause"].l} {pg["Sentence"].l}'):
        sentence = Sentence(
            id=SentenceId(3),
            clauses=(
                Clause(
                    parts=(
                        _ent('guest', 'Carol'),
                        _activity_part('search'),
                        ClauseWord(text='for'),
                        _ent('room', 'Room'),
                    )
                ),
                Clause(parts=(_ent('guest', 'Bob'), _activity_part('search'))),
            ),
        )
        story = Story(id=StoryId('book'), title='Book', sentences=(sentence,))
        rd = ReportData(metadata=_meta(), stories=[story], glossary=_g())
    with when(t'the {pg["Sentence"].l} labels are built'):
        labels = build_sentence_labels(rd)
    with then(
        t'the label gives the number, then reads as prose under a story-scoped '
        t'key, with the {pg["Clause"].l} texts joined'
    ):
        assert labels == {'book:3': 'Sentence 3: Carol search for Room · Bob search'}


def test_build_sentence_labels_keys_same_numbered_sentences_per_story() -> None:
    """Sentence ids are per-story ints: two stories both have a sentence 1, so
    the key has to carry the story id to keep them apart, and the label the
    story title."""
    parts = (_ent('guest', 'Guest'), _activity_part('search'))
    first = Story(
        id=StoryId('book'),
        title='Book',
        sentences=(Sentence(id=SentenceId(1), clauses=(Clause(parts=parts),)),),
    )
    second = Story(
        id=StoryId('cancel'),
        title='Cancel',
        sentences=(
            Sentence(
                id=SentenceId(1),
                clauses=(
                    Clause(parts=(_ent('guest', 'Guest'), _activity_part('cancel'))),
                ),
            ),
        ),
    )
    rd = ReportData(metadata=_meta(), stories=[first, second], glossary=_g())
    labels = build_sentence_labels(rd)
    assert labels == {
        'book:1': 'Book, sentence 1: Guest search',
        'cancel:1': 'Cancel, sentence 1: Guest cancel',
    }
