"""Unit tests for the Stories-view rollups (`report/story_view.py`), plus
the tab visibility the report shell derives."""

from pytest_given import given, scenario, then, when
from pytest_given.model import (
    Activity,
    ActivityId,
    ActivityPath,
    ActivityTermRef,
    ActivityWord,
    Glossary,
    GlossaryTerm,
    Metadata,
    Narration,
    NarrationTermRef,
    NodeId,
    ReportData,
    Scenario,
    Step,
    Story,
    StoryId,
    TermId,
)
from pytest_given.report.coverage import build_coverage_map
from pytest_given.report.html_renderer import TabVisibility, tab_visibility
from pytest_given.report.story_view import (
    build_activity_labels,
    build_story_rollups,
)
from tests.ubiquitous_language import pg


def _ent(tid: str, display: str) -> ActivityTermRef:
    return ActivityTermRef(term_id=TermId(tid), display=display)


def _verb_part(tid: str) -> ActivityTermRef:
    return ActivityTermRef(term_id=TermId(tid), display=tid)


def _g() -> Glossary:
    g = Glossary()
    g._register(GlossaryTerm(id=TermId('guest'), kind='actor', canonical='Guest'))
    g._register(GlossaryTerm(id=TermId('room'), kind='object', canonical='Room'))
    g._register(GlossaryTerm(id=TermId('search'), kind='verb', canonical='search'))
    return g


def _meta() -> Metadata:
    return Metadata(project='p', timestamp='t', pytest_version='8', plugin_version='0')


def test_tab_visibility_only_scenarios_visible_with_empty_report() -> None:
    rd = ReportData(metadata=_meta())
    assert tab_visibility(rd) == TabVisibility(
        scenarios=True, stories=False, glossary=False
    )
    assert tab_visibility(rd).visible_count == 1


def test_tab_visibility_stories_visible_when_stories_non_empty() -> None:
    a = Activity(
        id=ActivityId(1),
        paths=(
            ActivityPath(
                parts=(
                    _ent('guest', 'Guest'),
                    _verb_part('search'),
                    _ent('room', 'Room'),
                )
            ),
        ),
    )
    s = Story(id=StoryId('s'), title='S', activities=(a,))
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
    a = Activity(
        id=ActivityId(1),
        paths=(
            ActivityPath(
                parts=(
                    _ent('guest', 'Guest'),
                    _verb_part('search'),
                    _ent('room', 'Room'),
                )
            ),
        ),
    )
    story = Story(id=StoryId('book'), title='Book', activities=(a,))
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
        story_id=StoryId('book'),
    )
    rd = ReportData(metadata=_meta(), scenarios=[scn], stories=[story], glossary=g)
    maps = build_coverage_map(rd)
    assert ActivityId(1) in maps[NodeId('test::x')]


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
    assert maps[NodeId('t')] == set()


def test_build_coverage_maps_empty_when_no_glossary() -> None:
    scn = Scenario(
        id=NodeId('t'),
        narration=Narration(text='s'),
        module='m',
        steps=[],
    )
    rd = ReportData(metadata=_meta(), scenarios=[scn])
    maps = build_coverage_map(rd)
    assert maps == {NodeId('t'): set()}


def test_build_coverage_maps_empty_for_scenario_with_unknown_story_id() -> None:
    """Scenario has a story_id that doesn't match any story in the report."""
    g = _g()
    scn = Scenario(
        id=NodeId('t'),
        narration=Narration(text='s'),
        module='m',
        steps=[],
        story_id=StoryId('nonexistent'),
    )
    rd = ReportData(metadata=_meta(), scenarios=[scn], glossary=g)
    maps = build_coverage_map(rd)
    assert maps[NodeId('t')] == set()


@scenario(
    t'An under-anchored {pg["Activity"].low} is flagged ineligible in rollups',
)
def test_build_story_rollups_flags_under_anchored_activity_ineligible() -> None:
    with given(
        t'a {pg["Story"]} with an anchored and an under-anchored {pg["Activity"]}'
    ):
        g = _g()
        eligible = Activity(
            id=ActivityId(1),
            paths=(
                ActivityPath(
                    parts=(
                        _ent('guest', 'Guest'),
                        _verb_part('search'),
                        _ent('room', 'Room'),
                    )
                ),
            ),
        )
        under_anchored = Activity(
            id=ActivityId(2),
            paths=(
                ActivityPath(
                    parts=(
                        _ent('guest', 'Guest'),
                        ActivityWord(text='browses'),
                        ActivityWord(text='listings'),
                    )
                ),
            ),
        )
        story = Story(
            id=StoryId('book'), title='Book', activities=(eligible, under_anchored)
        )
        rd = ReportData(metadata=_meta(), scenarios=[], stories=[story], glossary=g)
    with when('the story rollups are built'):
        rollups = build_story_rollups(rd, build_coverage_map(rd))
    with then(t'only the anchored {pg["Activity"]} is {pg["Coverage"]}-eligible'):
        per_activity = rollups[StoryId('book')].per_activity
        assert per_activity[ActivityId(1)].eligible is True
        assert per_activity[ActivityId(2)].eligible is False


@scenario(
    t'A pinned under-anchored {pg["Activity"].low} stops reading as untracked',
)
def test_build_story_rollups_pinned_under_anchored_activity_is_tracked() -> None:
    """`untracked` is what the timeline renders as '—'. An under-anchored
    activity earns it only while nothing pins it."""
    with given(t'a {pg["Story"]} whose only {pg["Activity"]} is under-anchored'):
        g = _g()
        under_anchored = Activity(
            id=ActivityId(1),
            paths=(
                ActivityPath(
                    parts=(
                        _ent('guest', 'Guest'),
                        ActivityWord(text='browses'),
                        ActivityWord(text='listings'),
                    )
                ),
            ),
        )
        story = Story(id=StoryId('book'), title='Book', activities=(under_anchored,))
    with given(t'a {pg["Scenario"]} whose {pg["Step"].low} pins it by id'):
        pinned = Scenario(
            id=NodeId('test::a'),
            narration=Narration(text='a'),
            module='m',
            status='passed',
            story_id=StoryId('book'),
            steps=[
                Step(
                    phase='when',
                    narration=Narration(text='the listing page is opened'),
                    activity_ids=[ActivityId(1)],
                )
            ],
        )
        rd = ReportData(
            metadata=_meta(), scenarios=[pinned], stories=[story], glossary=g
        )
    with when('the story rollups are built'):
        rollups = build_story_rollups(rd, build_coverage_map(rd))
    with then(t'it stays narration-ineligible but is no longer untracked'):
        cov = rollups[StoryId('book')].per_activity[ActivityId(1)]
        assert cov.eligible is False
        assert cov.total == 1
        assert cov.untracked is False


def _covering_scn(node_id: str, status: str) -> Scenario:
    """A scenario whose single step references guest/search/room, so it covers
    the guest-search-room activity used across the rollup-count tests."""
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
        story_id=StoryId('book'),
        status=status,
    )


def test_build_story_rollups_counts_passed_failed_and_skipped() -> None:
    g = _g()
    activity = Activity(
        id=ActivityId(1),
        paths=(
            ActivityPath(
                parts=(
                    _ent('guest', 'Guest'),
                    _verb_part('search'),
                    _ent('room', 'Room'),
                )
            ),
        ),
    )
    story = Story(id=StoryId('book'), title='Book', activities=(activity,))
    scns = [
        _covering_scn('test::a', 'passed'),
        _covering_scn('test::b', 'passed'),
        _covering_scn('test::c', 'failed'),
        _covering_scn('test::d', 'skipped'),
    ]
    rd = ReportData(metadata=_meta(), scenarios=scns, stories=[story], glossary=g)
    rollups = build_story_rollups(rd, build_coverage_map(rd))
    cov = rollups[StoryId('book')].per_activity[ActivityId(1)]
    assert cov.total == 4
    assert cov.passed == 2
    assert cov.failed == 1
    assert cov.skipped == 1


@scenario(
    t'An {pg["Activity"]} is labeled by the prose of its {pg["Path"]("paths")}',
)
def test_build_activity_labels_joins_parts_into_prose() -> None:
    with given(t'a {pg["Story"]} with a two-{pg["Path"].low} {pg["Activity"].low}'):
        activity = Activity(
            id=ActivityId(3),
            paths=(
                ActivityPath(
                    parts=(
                        _ent('guest', 'Carol'),
                        _verb_part('search'),
                        ActivityWord(text='for'),
                        _ent('room', 'Room'),
                    )
                ),
                ActivityPath(parts=(_ent('guest', 'Bob'), _verb_part('search'))),
            ),
        )
        story = Story(id=StoryId('book'), title='Book', activities=(activity,))
        rd = ReportData(metadata=_meta(), stories=[story], glossary=_g())
    with when(t'the {pg["Activity"].low} labels are built'):
        labels = build_activity_labels(rd)
    with then(
        t'the label reads as prose under a story-scoped key, '
        t'with the {pg["Path"].low} texts joined'
    ):
        assert labels == {'book:3': 'Carol search for Room · Bob search'}


def test_build_activity_labels_keys_same_numbered_activities_per_story() -> None:
    """Activity ids are per-story ints: two stories both have an activity 1, so
    the key has to carry the story id to keep them apart."""
    parts = (_ent('guest', 'Guest'), _verb_part('search'))
    first = Story(
        id=StoryId('book'),
        title='Book',
        activities=(Activity(id=ActivityId(1), paths=(ActivityPath(parts=parts),)),),
    )
    second = Story(
        id=StoryId('cancel'),
        title='Cancel',
        activities=(
            Activity(
                id=ActivityId(1),
                paths=(
                    ActivityPath(parts=(_ent('guest', 'Guest'), _verb_part('cancel'))),
                ),
            ),
        ),
    )
    rd = ReportData(metadata=_meta(), stories=[first, second], glossary=_g())
    labels = build_activity_labels(rd)
    assert labels == {'book:1': 'Guest search', 'cancel:1': 'Guest cancel'}
