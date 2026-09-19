"""Scenario ↔ story-activity coverage matching."""

from dataclasses import dataclass

from ..model import (
    Activity,
    ActivityId,
    ActivityTermRef,
    NarrationTermRef,
    NodeId,
    ReportData,
    Scenario,
    Step,
    Story,
    StoryId,
    TermId,
    iter_steps,
)

# Which activities a scenario covers.
type CoverageMap = dict[NodeId, set[ActivityId]]


@dataclass(frozen=True)
class StoryIndex:
    """A story's activities reduced to what matching needs, built once.

    Depends only on the story, so it is shared across every scenario bound to
    that story instead of rebuilt per scenario — which computes `a_refs` once
    per activity rather than once per activity per scenario.

    Eligibility is *not* recorded, even though `refs_by_activity` is keyed by
    exactly the eligible activities: the index is built lazily, only for a
    story some scenario is bound to, so absence here does not distinguish
    "ineligible" from "no scenario named this story". `build_story_rollups`
    asks `is_coverage_eligible` again for that reason.
    """

    refs_by_activity: dict[ActivityId, set[TermId]]
    activities_by_term: dict[TermId, set[ActivityId]]
    ids: set[ActivityId]


def build_coverage_map(report: ReportData) -> CoverageMap:
    """Which activities each scenario covers, keyed by node id — empty for one
    bound to no story.

    Each story is indexed once and reused across the scenarios bound to it.

    Here rather than beside the Story view it feeds: this is matching, not
    presentation, and it is the only reason `StoryIndex` would have to be part
    of another module's vocabulary.
    """
    stories = {story.id: story for story in report.stories}
    indexes: dict[StoryId, StoryIndex] = {}
    result: CoverageMap = {}
    for scenario in report.scenarios:
        story = stories.get(scenario.story_id) if scenario.story_id else None
        if story is None:
            result[scenario.id] = set()
            continue
        if story.id not in indexes:
            indexes[story.id] = build_story_index(story)
        result[scenario.id] = compute_coverage(scenario, indexes[story.id])
    return result


def build_story_index(story: Story) -> StoryIndex:
    """Index *story* for matching.

    Under-anchored activities (fewer than 2 distinct term refs) are excluded
    from *narration* matching — the ``A_refs ⊆ S`` rule would let one term, or
    none, be covered by almost any step. An explicit ``activity=`` pin says
    what the narration cannot, so it reaches them too.
    """
    refs_by_activity = {
        activity.id: a_refs(activity)
        for activity in story.activities
        if is_coverage_eligible(activity)
    }
    activities_by_term: dict[TermId, set[ActivityId]] = {}
    for aid, refs in refs_by_activity.items():
        for term_id in refs:
            activities_by_term.setdefault(term_id, set()).add(aid)
    return StoryIndex(
        refs_by_activity=refs_by_activity,
        activities_by_term=activities_by_term,
        ids={a.id for a in story.activities},
    )


def a_refs(activity: Activity) -> set[TermId]:
    """The term ids the A_refs ⊆ S rule matches an activity on, across all
    its paths. Words contribute nothing; an instance or inflection counts as
    its term, so `guest('Alice')` and `guest` are the same ref."""
    return {
        part.term_id
        for activity_path in activity.paths
        for part in activity_path.parts
        if isinstance(part, ActivityTermRef)
    }


def is_coverage_eligible(activity: Activity) -> bool:
    """An activity participates in *narration* matching only if it carries at
    least two distinct glossary term refs. Under-anchored activities (0 or 1
    distinct term) are excluded from it, and render 'not coverage-tracked'
    unless an `activity=` pin covers them anyway."""
    term_ids = {
        part.term_id
        for activity_path in activity.paths
        for part in activity_path.parts
        if isinstance(part, ActivityTermRef)
    }
    return len(term_ids) >= 2


def compute_coverage(scenario: Scenario, index: StoryIndex) -> set[ActivityId]:
    """The activities this scenario covers.

    A non-empty `scenario.activity_ids` bounds which can appear at all.
    """
    # Intersected with the story's own ids, never taken verbatim: `scope` is
    # the only guard the pin path below has, and an id naming no activity in
    # this story would render a `Covers:` chip pointing at a timeline row that
    # does not exist. Collection rules that out for a live run, but a saved
    # report replayed through `pytest-given report` is deserialized unvalidated.
    scope = (
        set(scenario.activity_ids) & index.ids if scenario.activity_ids else index.ids
    )
    covered: set[ActivityId] = set()
    for step in iter_steps(scenario.steps):
        if step.activity_ids:
            covered |= {aid for aid in step.activity_ids if aid in scope}
            continue
        s_cache = s_for_step(step)
        candidates: set[ActivityId] = set()
        for term_id in s_cache:
            candidates |= index.activities_by_term.get(term_id, set())
        covered |= {
            aid
            for aid in candidates
            if aid in scope and index.refs_by_activity[aid].issubset(s_cache)
        }
    return covered


def s_for_step(step: Step) -> set[TermId]:
    """The term ids a step's narration term refs contribute, whatever their
    surface form.

    One pass serves a grouped scenario as well as a plain one: rule 4 requires
    a term ref to read identically in every case, so the grouped tree's term
    refs are every case's.
    """
    return {
        part.term_id
        for part in step.narration.parts
        if isinstance(part, NarrationTermRef)
    }
