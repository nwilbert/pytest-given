"""Precomputed aggregations for the HTML report renderer.

Everything the Jinja templates would otherwise have to compute per render:
coverage maps, story rollups, glossary cross-references, and the URL-fragment
slugs. Each `build_*` takes the report and returns one indexed view of it.
"""

from collections import Counter
from dataclasses import dataclass, field

from ..model import (
    ActivityId,
    ActivityPath,
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
    pill_display,
)

type ActivityKey = str
"""`'<story id>:<activity id>'` — an activity's handle outside its own story.

Activity ids are per-story ints, so the story id has to travel with them
wherever activities from different stories can meet: the report's activity
filter, and the URL fragment that carries it.
"""


def activity_key(story_id: StoryId, activity_id: ActivityId) -> ActivityKey:
    return f'{story_id}:{activity_id}'


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


def tab_visibility(report: ReportData) -> dict[str, bool]:
    """Return a dict of tab-name → visible bool for the report UI."""
    return {
        'scenarios': True,
        'stories': bool(report.stories),
        'glossary': bool(report.glossary is not None and report.glossary.terms),
    }


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


def build_activity_labels(report: ReportData) -> dict[ActivityKey, str]:
    """For each activity, its prose as plain text, keyed by `ActivityKey`.

    Lets the report name an activity outside the story timeline — in the
    Scenarios view's activity filter chip — where the numbered bubble that
    identifies it in the timeline carries no meaning on its own.
    """
    return {
        activity_key(story.id, activity.id): ' · '.join(
            _path_text(path) for path in activity.paths
        )
        for story in report.stories
        for activity in story.activities
    }


def _path_text(path: ActivityPath) -> str:
    """One activity path as plain prose. Term refs read as their surface form,
    the same word the timeline shows in a pill."""
    return ' '.join(
        part.display if isinstance(part, ActivityTermRef) else part.text
        for part in path.parts
    )


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
    parametrize column, otherwise just the one it carries.

    `pill_display` decides each of them, so the Glossary lists exactly the
    instances coverage credits — the two views reading one case differently is
    a report disagreeing with itself.
    """
    if part.param_column is None or not cases:
        return [part.display]
    displays = (pill_display(part, case) for case in cases)
    return [display for display in displays if display is not None]


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


def build_scenario_slug_index(report: ReportData) -> dict[NodeId, str]:
    """Map each scenario's node id to a short, readable slug for the URL
    fragment (`#scenario=<slug>`).

    The short form is `<file>/<func>`: the node id's basename with `.py` and a
    leading `test_` removed, the part after `::` with a leading `test_`
    removed, and the parametrization tail (`[water]`) dropped — a parametrized
    test usually groups into one scenario, so the tail is just noise.

    What was dropped comes back when it has to disambiguate, and only for the
    scenarios that need it, so the common case stays short and stable across
    re-runs. The tail returns first, for several scenarios out of one
    parametrized function — they share a file and a name, so nothing else
    separates them. Then directory components, innermost first, for two test
    files sharing a basename: a `tests/unit` + `tests/integration` layout is
    ordinary, and asking the author to rename a file to satisfy a URL fragment
    is not a fix. Colliding scenarios escalate together, never greedily — which
    slug a scenario gets must not depend on the order the report lists them in.

    A pair that survives a full path (`a/test_x.py` beside `a/x.py`, both
    defining `test_y`) falls back to the node id, which is unique by
    construction.
    """
    base_counts = Counter(
        _scenario_slug(s.id, with_tail=False) for s in report.scenarios
    )
    tails = {
        s.id: base_counts[_scenario_slug(s.id, with_tail=False)] > 1
        for s in report.scenarios
    }
    slugs = {
        s.id: _scenario_slug(s.id, with_tail=tails[s.id]) for s in report.scenarios
    }
    depth = 0
    while colliding := _colliding_ids(slugs):
        depth += 1
        moved = False
        for node_id in colliding:
            candidate = _scenario_slug(node_id, with_tail=tails[node_id], depth=depth)
            moved = moved or candidate != slugs[node_id]
            slugs[node_id] = candidate
        if not moved:
            # Every directory is already in the slug and the pair still reads
            # the same. Nothing shorter than the node id can separate them.
            slugs.update({node_id: node_id for node_id in colliding})
            break
    return slugs


def _colliding_ids(slugs: dict[NodeId, str]) -> list[NodeId]:
    """The node ids whose slug another scenario also holds, in report order."""
    counts = Counter(slugs.values())
    return [node_id for node_id, slug in slugs.items() if counts[slug] > 1]


def _scenario_slug(node_id: NodeId, *, with_tail: bool, depth: int = 0) -> str:
    """The slug for one node id, carrying `depth` of its parent directories."""
    file_part, _, func_part = node_id.partition('::')
    segments = file_part.split('/')
    basename = segments[-1].removesuffix('.py').removeprefix('test_')
    parents = segments[max(len(segments) - 1 - depth, 0) : -1]
    func = func_part.removeprefix('test_')
    if not with_tail:
        func = node_base(func)
    return '/'.join([*parents, basename, func])
