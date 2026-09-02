"""Scenario ↔ story-activity coverage matching."""

from dataclasses import dataclass
from typing import NamedTuple

from ..model import (
    Activity,
    ActivityId,
    ActivityPart,
    ActivityTermRef,
    ActivityWord,
    Glossary,
    NarrationTermRef,
    NodeId,
    Scenario,
    Step,
    Story,
    TermId,
    id_derive,
    iter_steps,
)


class Identity(NamedTuple):
    term_id: TermId
    instance_id: str | None


# Which activities a scenario covers.
type CoverageMap = dict[NodeId, set[ActivityId]]


def instance_id_of(
    glossary: Glossary,
    term_id: TermId,
    display: str,
) -> str | None:
    """None for the canonical display (or an unknown term), otherwise the
    slug of the display."""
    term = glossary.get(term_id)
    if term is None or display == term.canonical:
        return None
    return id_derive(display)


def identity_of_part(
    glossary: Glossary,
    part: ActivityPart,
) -> Identity | None:
    """Identity contributed by a single ActivityPart. Words → None.

    Verbs contribute the canonical (term_id, None); actors/work objects (and
    kindless terms) contribute an instance identity derived from display."""
    match part:
        case ActivityTermRef(term_id=tid, display=display):
            term = glossary.get(tid)
            if term is not None and term.kind == 'verb':
                return Identity(term_id=tid, instance_id=None)
            return Identity(
                term_id=tid,
                instance_id=instance_id_of(glossary, tid, display),
            )
        case ActivityWord():
            return None


def a_refs(glossary: Glossary, activity: Activity) -> set[Identity]:
    """Identity set used for strict A_refs ⊆ S coverage matching. Every
    activity participates; words contribute nothing."""
    out: set[Identity] = set()
    for activity_path in activity.paths:
        for part in activity_path.parts:
            ident = identity_of_part(glossary, part)
            if ident is not None:
                out.add(ident)
    return out


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


def s_for_step(glossary: Glossary, step: Step) -> set[Identity]:
    """Identity set contributed by a step's narration term refs.

    Applies the canonical-fallback rule: entity instance refs contribute
    both their specific identity and the canonical (term_id, None).

    One pass serves a grouped scenario as well as a plain one: rule 4 requires
    a term ref to read identically in every case, so the grouped tree's displays
    are every case's.
    """
    out: set[Identity] = set()
    for part in step.narration.parts:
        if not isinstance(part, NarrationTermRef):
            continue
        term = glossary.get(part.term_id)
        if term is None:
            continue
        out.add(Identity(term_id=part.term_id, instance_id=None))
        if term.kind == 'verb':
            continue
        instance_id = instance_id_of(glossary, part.term_id, part.display)
        if instance_id is not None:
            out.add(Identity(term_id=part.term_id, instance_id=instance_id))
    return out


@dataclass(frozen=True)
class StoryIndex:
    """A story's activities reduced to what matching needs, built once.

    Depends only on the story and the glossary, so it is shared across every
    scenario bound to that story instead of rebuilt per scenario — which also
    computes `a_refs` and `is_coverage_eligible` once per activity rather than
    once per activity per scenario.
    """

    refs_by_activity: dict[ActivityId, set[Identity]]
    activities_by_identity: dict[Identity, set[ActivityId]]
    eligible: dict[ActivityId, bool]
    ids: set[ActivityId]


def build_story_index(glossary: Glossary, story: Story) -> StoryIndex:
    """Index *story* for matching.

    Under-anchored activities (fewer than 2 distinct term refs) are excluded
    from *narration* matching — the ``A_refs ⊆ S`` rule would let one term, or
    none, be covered by almost any step. An explicit ``activity=`` pin says
    what the narration cannot, so it reaches them too.
    """
    eligible = {a.id: is_coverage_eligible(a) for a in story.activities}
    refs_by_activity = {
        activity.id: a_refs(glossary, activity)
        for activity in story.activities
        if eligible[activity.id]
    }
    activities_by_identity: dict[Identity, set[ActivityId]] = {}
    for aid, refs in refs_by_activity.items():
        for ident in refs:
            activities_by_identity.setdefault(ident, set()).add(aid)
    return StoryIndex(
        refs_by_activity=refs_by_activity,
        activities_by_identity=activities_by_identity,
        eligible=eligible,
        ids={a.id for a in story.activities},
    )


def compute_coverage(
    glossary: Glossary, scenario: Scenario, index: StoryIndex
) -> set[ActivityId]:
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
        s_cache = s_for_step(glossary, step)
        candidates: set[ActivityId] = set()
        for ident in s_cache:
            candidates |= index.activities_by_identity.get(ident, set())
        covered |= {
            aid
            for aid in candidates
            if aid in scope and index.refs_by_activity[aid].issubset(s_cache)
        }
    return covered
