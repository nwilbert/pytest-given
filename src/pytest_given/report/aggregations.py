"""Precomputed aggregations for the HTML report renderer.

Helpers exposed:
  - `build_coverage_maps`        — per-scenario activity coverage dicts
  - `build_story_rollups`        — per-story scenarios + per-activity rollup
  - `build_scenario_activity_index` — per-scenario sorted activity ids
  - `build_glossary_aggregations` — per-term instance/form/story aggregations
  - `build_term_scenario_index`  — per-term scenario ids
  - `build_scenario_slug_index` — per-scenario short URL-fragment slug
  - `tab_visibility`             — which top-level tabs should be visible
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from ..model import (
    ActivityId,
    ActivityTermRef,
    NarrationTermRef,
    NodeId,
    ReportData,
    Scenario,
    Story,
    StoryId,
    TermId,
    node_base,
    walk_steps,
)
from .coverage import (
    StepRef,
    compute_coverage,
    is_coverage_eligible,
    param_case_displays,
)

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


@dataclass
class ActivityCoverage:
    """Per-activity coverage rollup: which scenarios cover it, pass/skip counts,
    total, and whether it is eligible for coverage matching at all."""

    scenario_ids: list[NodeId] = field(default_factory=list)
    passed: int = 0
    skipped: int = 0
    eligible: bool = True

    @property
    def total(self) -> int:
        return len(self.scenario_ids)

    @property
    def failed(self) -> int:
        return self.total - self.passed - self.skipped


@dataclass
class StoryRollup:
    """Per-story precomputed view data: scenarios bound to the story plus a
    per-activity coverage breakdown. The Stories view consumes both."""

    scenarios: list[Scenario] = field(default_factory=list)
    per_activity: dict[ActivityId, ActivityCoverage] = field(default_factory=dict)


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


def build_story_rollups(
    report: ReportData,
    coverage_maps: dict[NodeId, dict[ActivityId, set[StepRef]]],
) -> dict[StoryId, StoryRollup]:
    """Per-story view-data: bound scenarios + per-activity coverage rollup."""
    scenarios_by_story: dict[StoryId, list[Scenario]] = {}
    for scn in report.scenarios:
        if scn.story_id is None:
            continue
        scenarios_by_story.setdefault(scn.story_id, []).append(scn)

    rollups: dict[StoryId, StoryRollup] = {}
    for story in report.stories:
        scenarios = scenarios_by_story.get(story.id, [])
        per_activity: dict[ActivityId, ActivityCoverage] = {}
        for activity in story.activities:
            covered_by: list[NodeId] = []
            passed = 0
            skipped = 0
            for scn in scenarios:
                if activity.id not in coverage_maps[scn.id]:
                    continue
                covered_by.append(scn.id)
                if scn.status == 'passed':
                    passed += 1
                elif scn.status == 'skipped':
                    skipped += 1
            per_activity[activity.id] = ActivityCoverage(
                scenario_ids=covered_by,
                passed=passed,
                skipped=skipped,
                eligible=is_coverage_eligible(activity),
            )
        rollups[story.id] = StoryRollup(scenarios=scenarios, per_activity=per_activity)
    return rollups


def build_scenario_activity_index(
    coverage_maps: dict[NodeId, dict[ActivityId, set[StepRef]]],
) -> dict[NodeId, list[ActivityId]]:
    """For each scenario, the sorted list of activity ids it covers."""
    return {scn_id: sorted(amap.keys()) for scn_id, amap in coverage_maps.items()}


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
        cases = param_case_displays(scenario)
        for _, step in walk_steps(scenario.steps):
            for part in step.narration.parts:
                if not isinstance(part, NarrationTermRef):
                    continue
                term = glossary.get(part.term_id)
                if term is None or term.kind not in ('actor', 'object'):
                    continue
                # A pill bound to a parametrize column reads the baseline's
                # display in the grouped tree; collect one instance per case so
                # the Glossary view lists them all.
                for display in _pill_displays(part, cases):
                    _record_entity_observation(
                        agg=_ensure(part.term_id),
                        term_id=part.term_id,
                        display=display,
                        canonical=term.canonical,
                        fixture_name=step.fixture_name,
                        seen_instances=seen_instances,
                    )

    # --- Walk story activities ---
    for story in report.stories:
        for activity in story.activities:
            for path in activity.paths:
                for apath_part in path.parts:
                    if isinstance(apath_part, ActivityTermRef):
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
                        if term.kind in ('actor', 'object'):
                            _record_entity_observation(
                                agg=agg,
                                term_id=apath_part.term_id,
                                display=apath_part.display,
                                canonical=term.canonical,
                                fixture_name=None,
                                seen_instances=seen_instances,
                            )
                        elif term.kind == 'verb':
                            form_key = (apath_part.term_id, apath_part.display)
                            if form_key not in seen_forms:
                                if apath_part.display != term.canonical:
                                    agg.forms.append(
                                        TermForm(display=apath_part.display)
                                    )
                                seen_forms.add(form_key)

    return aggs


def _pill_displays(part: NarrationTermRef, cases: list[dict[str, str]]) -> list[str]:
    """Every display this pill takes: one per case when it is bound to a
    parametrize column, otherwise just the one it carries."""
    if part.param_column is None or not cases:
        return [part.display]
    return [case.get(part.param_column, part.display) for case in cases]


def _record_entity_observation(
    *,
    agg: GlossaryAggregation,
    term_id: TermId,
    display: str,
    canonical: str,
    fixture_name: str | None,
    seen_instances: dict[tuple[TermId, str], str | None],
) -> None:
    """Record a new instance for the given term, if not already seen.

    A reference whose display matches the term's canonical name is the
    canonical concept (identity `(term_id, None)`), not an instance, so it is
    not collected. Only specific instance displays (e.g. ``Alice`` for
    ``Guest``) end up in the Glossary view's Instances list.
    """
    if display == canonical:
        return
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


# ---------------------------------------------------------------------------
# Term-scenario index
# ---------------------------------------------------------------------------


def build_term_scenario_index(report: ReportData) -> dict[TermId, list[NodeId]]:
    """For each glossary term, the scenarios whose narration or steps reference
    it. Scenario render order is preserved; each scenario appears at most once
    per term. Terms never referenced are absent; no glossary → empty."""
    if report.glossary is None:
        return {}
    index: dict[TermId, list[NodeId]] = {}
    for scenario in report.scenarios:
        seen: set[TermId] = set()
        narrations = [scenario.narration] + [
            step.narration for _, step in walk_steps(scenario.steps)
        ]
        for narration in narrations:
            for part in narration.parts:
                if not isinstance(part, NarrationTermRef):
                    continue
                if part.term_id in seen:
                    continue
                seen.add(part.term_id)
                index.setdefault(part.term_id, []).append(scenario.id)
    return index


# ---------------------------------------------------------------------------
# Scenario slug index
# ---------------------------------------------------------------------------


def build_scenario_slug_index(report: ReportData) -> dict[NodeId, str]:
    """Map each scenario's node id to a short, readable slug for the URL
    fragment (`#scenario=<slug>`).

    Slug is `<file>/<func>` where the file is the node id's basename with `.py`
    and a leading `test_` removed, and the func is the part after `::` with a
    leading `test_` removed. The parametrization tail (`[water]`) is **dropped**
    to keep the fragment short — a parametrized test usually groups into a
    single scenario, so the tail is just noise.

    The tail is kept only when it is needed to disambiguate: a parametrized test
    whose narration varies per case yields several scenarios for the same
    function, which would otherwise share a slug. Those (and only those) keep
    their tails. This makes a colliding scenario's slug depend on the rest of
    the report, but the common case stays short and stable across re-runs.

    Raises ValueError if two scenarios still collide after that — two test files
    sharing a basename across directories — naming the colliding node ids.
    """
    base_counts = Counter(
        _scenario_slug(s.id, with_tail=False) for s in report.scenarios
    )
    slugs: dict[NodeId, str] = {}
    node_by_slug: dict[str, NodeId] = {}
    for scenario in report.scenarios:
        needs_tail = base_counts[_scenario_slug(scenario.id, with_tail=False)] > 1
        slug = _scenario_slug(scenario.id, with_tail=needs_tail)
        existing = node_by_slug.get(slug)
        if existing is not None:
            raise ValueError(
                f'Duplicate scenario slug {slug!r} from node ids '
                f'{existing!r} and {scenario.id!r}; rename one test file so '
                f'their basenames differ.'
            )
        node_by_slug[slug] = scenario.id
        slugs[scenario.id] = slug
    return slugs


def _scenario_slug(node_id: NodeId, *, with_tail: bool) -> str:
    file_part, _, func_part = node_id.partition('::')
    basename = file_part.rsplit('/', 1)[-1].removesuffix('.py')
    func = func_part.removeprefix('test_')
    if not with_tail:
        func = node_base(func)
    return f'{basename.removeprefix("test_")}/{func}'
