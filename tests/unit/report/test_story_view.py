"""Unit tests for the Stories-view rollups (`report/story_view.py`), plus
the tab visibility the report shell derives."""

import dataclasses

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
    t'An under-anchored {pg["Sentence"].low} is flagged ineligible in rollups',
)
def test_build_story_rollups_flags_under_anchored_sentence_ineligible() -> None:
    with given(
        t'a {pg["Story"].low} with an anchored and an under-anchored '
        t'{pg["Sentence"].low}'
    ):
        g = _g()
        eligible = Sentence(
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
        under_anchored = Sentence(
            id=SentenceId(2),
            clauses=(
                Clause(
                    parts=(
                        _ent('guest', 'Guest'),
                        ClauseWord(text='browses'),
                        ClauseWord(text='listings'),
                    )
                ),
            ),
        )
        story = Story(
            id=StoryId('book'), title='Book', sentences=(eligible, under_anchored)
        )
        rd = ReportData(metadata=_meta(), scenarios=[], stories=[story], glossary=g)
    with when('the story rollups are built'):
        rollups = build_story_rollups(rd, build_coverage_map(rd))
    with then(
        t'only the anchored {pg["Sentence"].low} is {pg["Coverage"].low}-eligible'
    ):
        per_sentence = rollups[StoryId('book')].per_sentence
        assert per_sentence[SentenceId(1)].eligible is True
        assert per_sentence[SentenceId(2)].eligible is False


@scenario(
    t'A pinned under-anchored {pg["Sentence"].low} stops reading as untracked',
)
def test_build_story_rollups_pinned_under_anchored_sentence_is_tracked() -> None:
    """`untracked` is what the timeline renders as '—'. An under-anchored
    sentence earns it only while nothing pins it."""
    with given(
        t'a {pg["Story"].low} whose only {pg["Sentence"].low} is under-anchored'
    ):
        g = _g()
        under_anchored = Sentence(
            id=SentenceId(1),
            clauses=(
                Clause(
                    parts=(
                        _ent('guest', 'Guest'),
                        ClauseWord(text='browses'),
                        ClauseWord(text='listings'),
                    )
                ),
            ),
        )
        story = Story(id=StoryId('book'), title='Book', sentences=(under_anchored,))
    with given(t'a {pg["Scenario"].low} whose {pg["Step"].low} pins it by id'):
        pinned = Scenario(
            id=NodeId('test::a'),
            narration=Narration(text='a'),
            module='m',
            status='passed',
            story_ids=(StoryId('book'),),
            steps=[
                Step(
                    phase='when',
                    narration=Narration(text='the listing page is opened'),
                    pins=(Pin(story_id=StoryId('book'), sentence_id=SentenceId(1)),),
                )
            ],
        )
        rd = ReportData(
            metadata=_meta(), scenarios=[pinned], stories=[story], glossary=g
        )
    with when('the story rollups are built'):
        rollups = build_story_rollups(rd, build_coverage_map(rd))
    with then(t'it stays narration-ineligible but is no longer untracked'):
        cov = rollups[StoryId('book')].per_sentence[SentenceId(1)]
        assert cov.eligible is False
        assert cov.total == 1
        assert cov.untracked is False


def _covering_scn(node_id: str, status: str) -> Scenario:
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


def test_build_story_rollups_counts_passed_failed_and_skipped() -> None:
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
    ]
    rd = ReportData(metadata=_meta(), scenarios=scns, stories=[story], glossary=g)
    rollups = build_story_rollups(rd, build_coverage_map(rd))
    cov = rollups[StoryId('book')].per_sentence[SentenceId(1)]
    assert cov.total == 4
    assert cov.passed == 2
    assert cov.failed == 1
    assert cov.skipped == 1


@scenario(
    t'A {pg["Scenario"].low} bound to two {pg["Story"]("stories")} is matched '
    t'against each',
)
def test_build_story_rollups_lists_a_scenario_under_each_bound_story() -> None:
    with given(
        t'two {pg["Story"]("stories")} each with a guest-search-room '
        t'{pg["Sentence"].low}'
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
        t'a {pg["Scenario"].low} bound to both whose {pg["Step"].low} names those terms'
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
        t'the {pg["Scenario"].low} is listed under, and covers, both '
        t'{pg["Story"]("stories")}'
    ):
        for story_id in (StoryId('book'), StoryId('stay')):
            assert rollups[story_id].scenarios == [both]
            assert rollups[story_id].per_sentence[SentenceId(1)].scenario_ids == [
                both.id
            ]


@scenario(
    t'A {pg["Sentence"].low} is labeled by the prose of its {pg["Clause"]("clauses")}',
)
def test_build_sentence_labels_joins_parts_into_prose() -> None:
    with given(
        t'a {pg["Story"].low} with a two-{pg["Clause"].low} {pg["Sentence"].low}'
    ):
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
    with when(t'the {pg["Sentence"].low} labels are built'):
        labels = build_sentence_labels(rd)
    with then(
        t'the label gives the number, then reads as prose under a story-scoped '
        t'key, with the {pg["Clause"].low} texts joined'
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
