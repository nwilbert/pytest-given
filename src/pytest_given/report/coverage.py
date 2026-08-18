"""Scenario ↔ story-activity coverage matching."""

from collections.abc import Mapping
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
    """An activity participates in coverage matching only if it carries at
    least two distinct glossary term refs. Under-anchored activities (0 or 1
    distinct term) are excluded from matching and render 'not coverage-tracked'."""
    term_ids = {
        part.term_id
        for activity_path in activity.paths
        for part in activity_path.parts
        if isinstance(part, ActivityTermRef)
    }
    return len(term_ids) >= 2


def s_for_step(
    glossary: Glossary,
    step: Step,
    substitutions: Mapping[str, str] | None = None,
) -> set[Identity]:
    """Identity set contributed by a step's narration term refs.

    Applies the canonical-fallback rule: entity instance refs contribute
    both their specific identity and the canonical (term_id, None).

    `substitutions` maps a parametrize column name to the display that column
    holds for one case; a pill bound to that column reads that display instead
    of the baseline's, so a grouped scenario can be matched case by case.
    """
    out: set[Identity] = set()
    for part in step.narration.parts:
        if not isinstance(part, NarrationTermRef):
            continue
        term = glossary.get(part.term_id)
        if term is None:
            continue
        if term.kind == 'verb':
            out.add(Identity(term_id=part.term_id, instance_id=None))
            continue
        display = part.display
        if substitutions is not None and part.param_column is not None:
            display = substitutions.get(part.param_column, display)
        inst_id = instance_id_of(glossary, part.term_id, display)
        if inst_id is None:
            out.add(Identity(term_id=part.term_id, instance_id=None))
        else:
            out.add(Identity(term_id=part.term_id, instance_id=inst_id))
            out.add(Identity(term_id=part.term_id, instance_id=None))
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
    from matching and never appear in the result.

    Matching uses an inverted index `identity → activity_ids` built once
    per scenario: per step, the candidate set narrows to activities sharing
    at least one identity with the step's `s_for_step`, replacing the prior
    O(|activities|) inner scan with O(|s_cache| + |candidates|).

    A grouped scenario is matched once per case (see `param_case_displays`),
    so a term pill bound to a parametrize column is checked against every
    case's display, not only the baseline's.
    """
    scope = (
        set(scenario.activity_ids)
        if scenario.activity_ids
        else {a.id for a in story.activities}
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

    cases = param_case_displays(scenario)
    # A single-element list carrying `None`, typed to match `cases` for the
    # `cases or single_pass` fallback below — mypy's list invariance rejects
    # a bare `[None]` literal there since it infers the literal's element
    # type from `cases`'s `dict[str, str]`.
    single_pass: list[Mapping[str, str] | None] = [None]
    result: dict[ActivityId, set[StepRef]] = {}
    for path_index, step in walk_steps(scenario.steps):
        ref: StepRef = (scenario.id, path_index)
        if step.activity_ids:
            for aid in step.activity_ids:
                if aid in refs_by_activity:
                    result.setdefault(aid, set()).add(ref)
            continue
        # Match once per case and union the *matches*, never the identity sets:
        # a grouped identity set would let a step satisfy an activity by
        # combining one case's Alice with another's latte, which no single case
        # satisfies. `cases` is empty for a scenario with no param-linked pill.
        for substitutions in cases or single_pass:
            s_cache = s_for_step(glossary, step, substitutions)
            candidates: set[ActivityId] = set()
            for ident in s_cache:
                candidates |= identity_to_activities.get(ident, set())
            for aid in candidates:
                if refs_by_activity[aid].issubset(s_cache):
                    result.setdefault(aid, set()).add(ref)
    return result


def param_case_displays(scenario: Scenario) -> list[dict[str, str]]:
    """One `{param column name: cell text}` mapping per case, or `[]`.

    Empty when the scenario has no term ref bound to a parametrize column —
    the grouped tree then already tells the whole truth and callers keep their
    single-pass path.
    """
    if scenario.parameters is None:
        return []
    linked = {
        part.param_column
        for _path, step in walk_steps(scenario.steps)
        for part in step.narration.parts
        if isinstance(part, NarrationTermRef) and part.param_column is not None
    }
    if not linked:
        return []
    columns = scenario.parameters.columns
    return [
        {
            column.name: str(value)
            for column, value in zip(columns, case.values, strict=True)
            if column.kind == 'param' and column.name in linked and value is not None
        }
        for case in scenario.parameters.cases
    ]
