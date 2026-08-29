"""Scenario ↔ story-activity coverage matching."""

from typing import NamedTuple, assert_never

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
    walk_steps,
)


class Identity(NamedTuple):
    term_id: TermId
    instance_id: str | None


type StepRef = tuple[NodeId, tuple[int, ...]]


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
        case _:
            assert_never(part)


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


def compute_coverage(
    glossary: Glossary,
    scenario: Scenario,
    story: Story,
) -> dict[ActivityId, set[StepRef]]:
    """Per-scenario activity-coverage map.

    Each activity covered by at least one step appears in the result; the
    value is the set of StepRef tuples for the covering steps.

    Scope: if scenario.activity_ids is non-empty, only those activity ids
    can appear in the result. Otherwise every story activity is considered.
    Under-anchored activities (fewer than 2 distinct term refs) are excluded
    from *narration* matching — the ``A_refs ⊆ S`` rule would let one term, or
    none, be covered by almost any step. An explicit ``activity=`` pin says
    what the narration cannot, so it reaches them too; only scope bounds it.
    """
    # Intersected with the story's own ids, never taken verbatim: `scope` is
    # the only guard the pin path below has, and an id naming no activity in
    # this story would otherwise enter the coverage map and render a `Covers:`
    # chip pointing at a timeline row that does not exist. A live run cannot
    # reach that — collection validates `activities=` against the bound story —
    # but a saved report replayed through `pytest-given report` is deserialized
    # without validation, and this is the one place that would notice.
    story_ids = {a.id for a in story.activities}
    scope = (
        set(scenario.activity_ids) & story_ids if scenario.activity_ids else story_ids
    )
    refs_by_activity: dict[ActivityId, set[Identity]] = {}
    for activity in story.activities:
        if activity.id not in scope or not is_coverage_eligible(activity):
            continue
        refs_by_activity[activity.id] = a_refs(glossary, activity)
    identity_to_activities: dict[Identity, set[ActivityId]] = {}
    for aid, refs in refs_by_activity.items():
        for ident in refs:
            identity_to_activities.setdefault(ident, set()).add(aid)

    result: dict[ActivityId, set[StepRef]] = {}
    for path_index, step in walk_steps(scenario.steps):
        ref: StepRef = (scenario.id, path_index)
        if step.activity_ids:
            for aid in step.activity_ids:
                if aid in scope:
                    result.setdefault(aid, set()).add(ref)
            continue
        s_cache = s_for_step(glossary, step)
        candidates: set[ActivityId] = set()
        for ident in s_cache:
            candidates |= identity_to_activities.get(ident, set())
        for aid in candidates:
            if refs_by_activity[aid].issubset(s_cache):
                result.setdefault(aid, set()).add(ref)
    return result
