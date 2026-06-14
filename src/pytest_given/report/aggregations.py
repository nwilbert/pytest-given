"""Precomputed aggregations for the HTML report renderer.

Three helpers are exposed:
  - `build_coverage_maps`       — per-scenario activity coverage dicts
  - `build_glossary_aggregations` — per-term instance/form/story aggregations
  - `tab_visibility`            — which top-level tabs should be visible
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from ..model import (
    ActivityEntity,
    ActivityId,
    ActivityTerm,
    NarrationTermRef,
    NodeId,
    ReportData,
    Step,
    Story,
    StoryId,
    TermId,
)
from .coverage import StepRef, compute_coverage

# ---------------------------------------------------------------------------
# Public dataclasses
# ---------------------------------------------------------------------------


@dataclass
class TermInstance:
    """One concrete entity occurrence collected across all scenario steps."""

    display: str
    fixture_name: str | None = None


@dataclass
class TermForm:
    """One verb surface form collected from story activity parts."""

    display: str


@dataclass
class GlossaryAggregation:
    """Aggregated cross-reference data for a single glossary term."""

    instances: list[TermInstance] = field(default_factory=list)
    forms: list[TermForm] = field(default_factory=list)
    stories: list[StoryId] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Tab visibility
# ---------------------------------------------------------------------------


def tab_visibility(report: ReportData) -> dict[str, bool]:
    """Return a dict of tab-name → visible bool for the report UI."""
    return {
        'scenarios': True,
        'stories': bool(report.stories),
        'glossary': bool(report.glossary is not None and report.glossary.terms),
    }


# ---------------------------------------------------------------------------
# Coverage maps
# ---------------------------------------------------------------------------


def build_coverage_maps(
    report: ReportData,
) -> dict[NodeId, dict[ActivityId, set[StepRef]]]:
    """Compute per-scenario coverage maps.

    Returns a dict keyed by scenario node id; each value is the result of
    `compute_coverage` for that scenario (or an empty dict when the scenario
    has no story_id or the report has no glossary).
    """
    glossary = report.glossary
    story_index: dict[StoryId, Story] = {s.id: s for s in report.stories}
    result: dict[NodeId, dict[ActivityId, set[StepRef]]] = {}
    for scenario in report.scenarios:
        if glossary is None or scenario.story_id is None:
            result[scenario.id] = {}
            continue
        story = story_index.get(scenario.story_id)
        if story is None:
            result[scenario.id] = {}
            continue
        result[scenario.id] = compute_coverage(glossary, scenario, story)
    return result


# ---------------------------------------------------------------------------
# Glossary aggregations
# ---------------------------------------------------------------------------


def build_glossary_aggregations(
    report: ReportData,
) -> dict[TermId, GlossaryAggregation]:
    """Build per-term aggregations from scenarios and stories.

    Walks:
    1. All scenario steps (recursively) to collect entity instances and
       occurrence counts.
    2. All story activity paths to collect verb surface forms and story refs.
    """
    glossary = report.glossary
    if glossary is None:
        return {}

    aggs: dict[TermId, GlossaryAggregation] = {}
    # Track which (term_id, display) pairs have been seen to avoid duplicate
    # instance entries; keyed by (term_id, display) → fixture_name of first
    # observation.
    seen_instances: dict[tuple[TermId, str], str | None] = {}
    # Track which (term_id, display) verb forms have been seen.
    seen_forms: set[tuple[TermId, str]] = set()
    # Track which (term_id, story_id) story refs have been recorded.
    seen_story_refs: set[tuple[TermId, StoryId]] = set()

    def _ensure(term_id: TermId) -> GlossaryAggregation:
        if term_id not in aggs:
            aggs[term_id] = GlossaryAggregation()
        return aggs[term_id]

    # --- Walk scenario steps ---
    for scenario in report.scenarios:
        for step in _walk_steps_flat(scenario.steps):
            for part in step.narration.parts:
                if not isinstance(part, NarrationTermRef):
                    continue
                term = glossary.get(part.term_id)
                if term is None:
                    continue
                if term.kind in ('actor', 'object'):
                    _record_entity_observation(
                        agg=_ensure(part.term_id),
                        term_id=part.term_id,
                        display=part.display,
                        fixture_name=step.fixture_name,
                        seen_instances=seen_instances,
                    )
                # Verbs in scenario steps: no form collection (forms come from
                # story activities), but we still want them in aggs if needed.
                # The spec only mentions forms from activity paths.

    # --- Walk story activities ---
    for story in report.stories:
        for activity in story.activities:
            for path in activity.paths:
                for apath_part in path.parts:
                    if isinstance(apath_part, ActivityEntity):
                        term = glossary.get(apath_part.entity_id)
                        if term is None:
                            continue
                        agg = _ensure(apath_part.entity_id)
                        _record_entity_observation(
                            agg=agg,
                            term_id=apath_part.entity_id,
                            display=apath_part.display,
                            fixture_name=None,
                            seen_instances=seen_instances,
                        )
                        _record_story_ref(
                            agg=agg,
                            term_id=apath_part.entity_id,
                            story_id=story.id,
                            seen_story_refs=seen_story_refs,
                        )
                    elif isinstance(apath_part, ActivityTerm):
                        term = glossary.get(apath_part.term_id)
                        if term is None:
                            continue
                        agg = _ensure(apath_part.term_id)
                        _record_story_ref(
                            agg=agg,
                            term_id=apath_part.term_id,
                            story_id=story.id,
                            seen_story_refs=seen_story_refs,
                        )
                        # Collect verb surface form — only non-canonical forms
                        form_key = (apath_part.term_id, apath_part.display)
                        if form_key not in seen_forms:
                            if apath_part.display != term.canonical:
                                agg.forms.append(TermForm(display=apath_part.display))
                            seen_forms.add(form_key)

    return aggs


def _record_entity_observation(
    *,
    agg: GlossaryAggregation,
    term_id: TermId,
    display: str,
    fixture_name: str | None,
    seen_instances: dict[tuple[TermId, str], str | None],
) -> None:
    """Record a new instance for the given term, if not already seen."""
    key = (term_id, display)
    if key not in seen_instances:
        seen_instances[key] = fixture_name
        agg.instances.append(TermInstance(display=display, fixture_name=fixture_name))


def _record_story_ref(
    *,
    agg: GlossaryAggregation,
    term_id: TermId,
    story_id: StoryId,
    seen_story_refs: set[tuple[TermId, StoryId]],
) -> None:
    """Record a story ref for the given term, if not already seen."""
    ref_key = (term_id, story_id)
    if ref_key not in seen_story_refs:
        seen_story_refs.add(ref_key)
        agg.stories.append(story_id)


def _walk_steps_flat(steps: list[Step]) -> Iterable[Step]:
    """Yield all steps and their descendants in depth-first order."""
    for step in steps:
        yield step
        if step.children:
            yield from _walk_steps_flat(step.children)
