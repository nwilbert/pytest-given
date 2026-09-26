"""Scenario ↔ story-sentence coverage matching."""

from dataclasses import dataclass

from ..model import (
    ClauseTermRef,
    NarrationTermRef,
    NodeId,
    ReportData,
    Scenario,
    Sentence,
    SentenceId,
    Step,
    Story,
    StoryId,
    TermId,
    iter_steps,
)

# Which sentences a scenario covers.
type CoverageMap = dict[NodeId, set[SentenceId]]


@dataclass(frozen=True)
class StoryIndex:
    """A story's sentences reduced to what matching needs, built once.

    Depends only on the story, so it is shared across every scenario bound to
    that story instead of rebuilt per scenario — which computes `a_refs` once
    per sentence rather than once per sentence per scenario.

    Eligibility is *not* recorded, even though `refs_by_sentence` is keyed by
    exactly the eligible sentences: the index is built lazily, only for a
    story some scenario is bound to, so absence here does not distinguish
    "ineligible" from "no scenario named this story". `build_story_rollups`
    asks `is_coverage_eligible` again for that reason.
    """

    refs_by_sentence: dict[SentenceId, set[TermId]]
    sentences_by_term: dict[TermId, set[SentenceId]]
    ids: set[SentenceId]


def build_coverage_map(report: ReportData) -> CoverageMap:
    """Which sentences each scenario covers, keyed by node id — empty for one
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

    Under-anchored sentences (fewer than 2 distinct term refs) are excluded
    from *narration* matching — the ``A_refs ⊆ S`` rule would let one term, or
    none, be covered by almost any step. An explicit ``activity=`` pin says
    what the narration cannot, so it reaches them too.
    """
    refs_by_sentence = {
        sentence.id: a_refs(sentence)
        for sentence in story.sentences
        if is_coverage_eligible(sentence)
    }
    sentences_by_term: dict[TermId, set[SentenceId]] = {}
    for aid, refs in refs_by_sentence.items():
        for term_id in refs:
            sentences_by_term.setdefault(term_id, set()).add(aid)
    return StoryIndex(
        refs_by_sentence=refs_by_sentence,
        sentences_by_term=sentences_by_term,
        ids={a.id for a in story.sentences},
    )


def a_refs(sentence: Sentence) -> set[TermId]:
    """The term ids the A_refs ⊆ S rule matches a sentence on, across all
    its paths. Words contribute nothing; an instance or inflection counts as
    its term, so `guest('Alice')` and `guest` are the same ref."""
    return {
        part.term_id
        for clause in sentence.clauses
        for part in clause.parts
        if isinstance(part, ClauseTermRef)
    }


def is_coverage_eligible(sentence: Sentence) -> bool:
    """A sentence participates in *narration* matching only if it carries at
    least two distinct glossary term refs. Under-anchored sentences (0 or 1
    distinct term) are excluded from it, and render 'not coverage-tracked'
    unless an `activity=` pin covers them anyway."""
    return len(a_refs(sentence)) >= 2


def compute_coverage(scenario: Scenario, index: StoryIndex) -> set[SentenceId]:
    """The sentences this scenario covers.

    A non-empty `scenario.activity_ids` bounds which can appear at all.
    """
    # Intersected with the story's own ids, never taken verbatim: `scope` is
    # the only guard the pin path below has, and an id naming no sentence in
    # this story would render a `Covers:` chip pointing at a timeline row that
    # does not exist. Collection rules that out for a live run, but a saved
    # report replayed through `pytest-given report` is deserialized unvalidated.
    scope = (
        set(scenario.activity_ids) & index.ids if scenario.activity_ids else index.ids
    )
    covered: set[SentenceId] = set()
    for step in iter_steps(scenario.steps):
        if step.activity_ids:
            covered |= {aid for aid in step.activity_ids if aid in scope}
            continue
        s_cache = s_for_step(step)
        candidates: set[SentenceId] = set()
        for term_id in s_cache:
            candidates |= index.sentences_by_term.get(term_id, set())
        covered |= {
            aid
            for aid in candidates
            if aid in scope and index.refs_by_sentence[aid].issubset(s_cache)
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
