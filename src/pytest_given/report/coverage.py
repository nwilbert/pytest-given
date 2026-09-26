"""Scenario ↔ story-sentence coverage matching."""

from dataclasses import dataclass

from ..model import (
    ClauseTermRef,
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
    iter_steps,
)

# Which sentences a scenario covers, per story it binds.
type CoverageMap = dict[NodeId, dict[StoryId, set[SentenceId]]]


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

    story_id: StoryId
    refs_by_sentence: dict[SentenceId, set[TermId]]
    sentences_by_term: dict[TermId, set[SentenceId]]
    ids: set[SentenceId]


def build_coverage_map(report: ReportData) -> CoverageMap:
    """Which sentences each scenario covers in each story it binds, keyed by
    node id — empty for one bound to no story in the report.

    Each story is indexed once and reused across the scenarios bound to it.

    Here rather than beside the Story view it feeds: this is matching, not
    presentation, and it is the only reason `StoryIndex` would have to be part
    of another module's vocabulary.
    """
    stories = {story.id: story for story in report.stories}
    indexes: dict[StoryId, StoryIndex] = {}
    result: CoverageMap = {}
    for scenario in report.scenarios:
        per_story: dict[StoryId, set[SentenceId]] = {}
        for story_id in scenario.story_ids:
            story = stories.get(story_id)
            if story is None:
                continue
            if story_id not in indexes:
                indexes[story_id] = build_story_index(story)
            per_story[story_id] = compute_coverage(scenario, indexes[story_id])
        result[scenario.id] = per_story
    return result


def build_story_index(story: Story) -> StoryIndex:
    """Index *story* for matching.

    Under-anchored sentences (fewer than 2 distinct term refs) are excluded
    from *narration* matching — the ``A_refs ⊆ S`` rule would let one term, or
    none, be covered by almost any step. A pin says what the narration cannot,
    so it reaches them too.
    """
    refs_by_sentence = {
        sentence.id: refs
        for sentence in story.sentences
        if _is_anchored(refs := a_refs(sentence))
    }
    sentences_by_term: dict[TermId, set[SentenceId]] = {}
    for sentence_id, refs in refs_by_sentence.items():
        for term_id in refs:
            sentences_by_term.setdefault(term_id, set()).add(sentence_id)
    return StoryIndex(
        story_id=story.id,
        refs_by_sentence=refs_by_sentence,
        sentences_by_term=sentences_by_term,
        ids={sentence.id for sentence in story.sentences},
    )


def a_refs(sentence: Sentence) -> set[TermId]:
    """The term ids the A_refs ⊆ S rule matches a sentence on, across all
    its clauses. Words contribute nothing; an instance or inflection counts as
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
    unless a pin covers them anyway."""
    return _is_anchored(a_refs(sentence))


def _is_anchored(refs: set[TermId]) -> bool:
    return len(refs) >= 2


def compute_coverage(scenario: Scenario, index: StoryIndex) -> set[SentenceId]:
    """The sentences this scenario covers in the indexed story.

    A scenario pin into the story replaces narration matching for all of it; a
    step pin into it replaces matching for that step. Pins into other stories
    say nothing here. Every pin is intersected with the story's ids: a report
    replayed through `pytest-given report` is deserialized unvalidated, and a
    stale pin must not put a chip on a sentence that does not exist.
    """
    scenario_pins = _pinned_ids(scenario.pins, index)
    if scenario_pins is not None:
        return scenario_pins
    covered: set[SentenceId] = set()
    for step in iter_steps(scenario.steps):
        step_pins = _pinned_ids(step.pins, index)
        if step_pins is not None:
            covered |= step_pins
            continue
        s_cache = s_for_step(step)
        candidates: set[SentenceId] = set()
        for term_id in s_cache:
            candidates |= index.sentences_by_term.get(term_id, set())
        covered |= {
            sentence_id
            for sentence_id in candidates
            if index.refs_by_sentence[sentence_id].issubset(s_cache)
        }
    return covered


def _pinned_ids(pins: tuple[Pin, ...], index: StoryIndex) -> set[SentenceId] | None:
    """The indexed story's sentences these pins name, or None when none of them
    points into that story, which leaves it to narration matching."""
    into_story = {pin.sentence_id for pin in pins if pin.story_id == index.story_id}
    if not into_story:
        return None
    return into_story & index.ids


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
