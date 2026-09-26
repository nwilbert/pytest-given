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

# Which sentences a scenario covers, per story it is listed under.
type CoverageMap = dict[NodeId, dict[StoryId, set[SentenceId]]]


@dataclass(frozen=True)
class StoryIndex:
    """A story's sentences reduced to what matching needs, built once.

    Depends only on the story, so it is shared across every scenario instead
    of rebuilt per scenario — which computes `a_refs` once per sentence rather
    than once per sentence per scenario. `refs_by_sentence` is keyed by exactly
    the eligible sentences.
    """

    story_id: StoryId
    refs_by_sentence: dict[SentenceId, set[TermId]]
    sentences_by_term: dict[TermId, set[SentenceId]]
    ids: set[SentenceId]


def build_coverage_map(report: ReportData) -> CoverageMap:
    """Which sentences each scenario covers, keyed by node id, then by story:
    every story in its `stories=`, even where nothing matched, and every other
    story it covers a sentence of, which only a pin reaches.

    Each story is indexed once and reused across scenarios.

    Here rather than beside the Story view it feeds: this is matching, not
    presentation, and it is the only reason `StoryIndex` would have to be part
    of another module's vocabulary.
    """
    indexes = {story.id: build_story_index(story) for story in report.stories}
    result: CoverageMap = {}
    for scenario in report.scenarios:
        # The stories it names, then those its pins point into, each once.
        candidates = dict.fromkeys(
            [
                *scenario.story_ids,
                *(pin.story_id for pin in scenario.pins or ()),
                *(
                    pin.story_id
                    for step in iter_steps(scenario.steps)
                    for pin in step.pins or ()
                ),
            ]
        )
        per_story: dict[StoryId, set[SentenceId]] = {}
        for story_id in candidates:
            if story_id not in indexes:
                continue
            covered = compute_coverage(scenario, indexes[story_id])
            if covered or story_id in scenario.story_ids:
                per_story[story_id] = covered
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


def compute_coverage(scenario: Scenario, index: StoryIndex) -> set[SentenceId]:
    """The sentences this scenario covers in the indexed story.

    Narration matching runs only where nothing pins: not in a scenario with
    `pins=` (an empty one included), not for a step with `pins=`, and only
    against a story in the scenario's `stories=`. Every pin counts, whichever
    story it points into. Pins are intersected with the story's ids: a report
    replayed through `pytest-given report` is deserialized unvalidated, and a
    stale pin must not put a chip on a sentence that does not exist.
    """
    covered = _pinned_ids(scenario.pins or (), index)
    matching = scenario.pins is None and index.story_id in scenario.story_ids
    for step in iter_steps(scenario.steps):
        if step.pins is not None:
            covered |= _pinned_ids(step.pins, index)
        elif matching:
            covered |= _matched_ids(step, index)
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


def _is_anchored(refs: set[TermId]) -> bool:
    return len(refs) >= 2


def _pinned_ids(pins: tuple[Pin, ...], index: StoryIndex) -> set[SentenceId]:
    """The indexed story's sentences these pins name."""
    return {
        pin.sentence_id for pin in pins if pin.story_id == index.story_id
    } & index.ids


def _matched_ids(step: Step, index: StoryIndex) -> set[SentenceId]:
    """The indexed story's sentences a step's narration matches: those whose
    every term ref the step names."""
    s_cache = s_for_step(step)
    candidates: set[SentenceId] = set()
    for term_id in s_cache:
        candidates |= index.sentences_by_term.get(term_id, set())
    return {
        sentence_id
        for sentence_id in candidates
        if index.refs_by_sentence[sentence_id].issubset(s_cache)
    }
