"""Precomputed aggregations for the HTML report renderer.

Everything the Jinja templates would otherwise have to compute per render:
coverage maps, story rollups and glossary cross-references. Each `build_*`
takes the report and returns one indexed view of it. The URL-fragment slugs
are `slugs.py`'s.
"""

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import NewType

from ..model import (
    ActivityId,
    ActivityPath,
    ActivityTermRef,
    Glossary,
    NarrationTermRef,
    NodeId,
    ReportData,
    Scenario,
    Story,
    StoryId,
    TermId,
    iter_narrations,
    walk_steps,
)
from .coverage import (
    StepRef,
    compute_coverage,
    is_coverage_eligible,
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
class TermOccurrence:
    """One sighting of a term in the recorded steps, as the Glossary shows it.

    Not `capture`'s `TermInstance`, which is the authored thing — a term
    wearing one surface form; this is the report-side tally of where that
    surface form turned up.
    """

    display: str
    fixture_name: str | None = None


TermForm = NewType('TermForm', str)
"""One verb surface form collected from story activity parts.

The inflection as story prose spells it (`books` for `book`), never the term's
own canonical name — `record_form` drops that one. A distinct type, so it
cannot be confused with the canonical name or with a `TermId`.
"""


@dataclass
class GlossaryAggregation:
    """Aggregated cross-reference data for a single glossary term."""

    instances: list[TermOccurrence] = field(default_factory=list)
    forms: list[TermForm] = field(default_factory=list)
    stories: list[StoryId] = field(default_factory=list)


@dataclass
class ActivityCoverage:
    """Per-activity coverage rollup: which scenarios cover it, pass/skip counts,
    total, and whether it is eligible for narration matching at all."""

    scenario_ids: list[NodeId] = field(default_factory=list)
    passed: int = 0
    skipped: int = 0
    eligible: bool = True

    @property
    def total(self) -> int:
        return len(self.scenario_ids)

    @property
    def untracked(self) -> bool:
        """Whether the report can say nothing about this activity.

        Ineligibility alone no longer settles it: an `activity=` pin covers an
        under-anchored activity that narration matching cannot reach, and a
        covered activity must never render as untracked.
        """
        return not self.eligible and not self.total

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
        story = (
            story_index.get(scenario.story_id)
            if scenario.story_id is not None
            else None
        )
        result[scenario.id] = (
            compute_coverage(glossary, scenario, story)
            if glossary is not None and story is not None
            else {}
        )
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

    Two walks feed one index: scenario steps contribute entity instances, and
    story activity prose contributes story refs, more instances, and verb
    surface forms. `_GlossaryIndex` owns the dedup, so each walk just reports
    what it sees.
    """
    glossary = report.glossary
    if glossary is None:
        return {}
    index = _GlossaryIndex(glossary)
    for scenario in report.scenarios:
        for _path, step in walk_steps(scenario.steps):
            for part in step.narration.parts:
                if not isinstance(part, NarrationTermRef):
                    continue
                index.record_instance(
                    part.term_id, part.display, fixture_name=step.fixture_name
                )
    for story in report.stories:
        for ref in _story_term_refs(story):
            # Each `record_*` no-ops for a term of the wrong kind, so the walk
            # states what it saw rather than re-deriving which bucket it lands in.
            index.record_story_ref(ref.term_id, story.id)
            index.record_instance(ref.term_id, ref.display)
            index.record_form(ref.term_id, ref.display)
    return index.result()


def _story_term_refs(story: Story) -> Iterator[ActivityTermRef]:
    """Every glossary reference in a story's activity prose."""
    return (
        part
        for activity in story.activities
        for path in activity.paths
        for part in path.parts
        if isinstance(part, ActivityTermRef)
    )


class _GlossaryIndex:
    """Accumulates the Glossary view's cross-references, deduping as it goes.

    Owns the three "already recorded" sets that the walks would otherwise have
    to thread through every helper. Every `record_*` is idempotent for a given
    identity and silently ignores a term whose kind the bucket does not take,
    so a caller can report an observation without first working out where it
    belongs.
    """

    def __init__(self, glossary: Glossary) -> None:
        self._glossary = glossary
        self._aggs: dict[TermId, GlossaryAggregation] = {}
        self._instances: set[tuple[TermId, str]] = set()
        self._forms: set[tuple[TermId, str]] = set()
        self._story_refs: set[tuple[TermId, StoryId]] = set()

    def result(self) -> dict[TermId, GlossaryAggregation]:
        """The aggregations, keyed by term id, in first-observation order."""
        return self._aggs

    def record_instance(
        self, term_id: TermId, display: str, fixture_name: str | None = None
    ) -> None:
        """Note one occurrence of an entity term reading as `display`.

        A reference whose display matches the term's canonical name is the
        concept itself, not an instance, so only specific displays (``Alice``
        for ``Guest``) reach the Instances list. Verbs and kindless terms have
        no instances and are ignored here.
        """
        term = self._glossary.get(term_id)
        if term is None or term.kind not in ('actor', 'object'):
            return
        if display == term.canonical or (term_id, display) in self._instances:
            return
        self._instances.add((term_id, display))
        self._agg(term_id).instances.append(
            TermOccurrence(display=display, fixture_name=fixture_name)
        )

    def record_form(self, term_id: TermId, display: str) -> None:
        """Note one surface form of a verb term.

        The canonical form is the term's own name and is not a *form* of it, so
        only inflections are listed. Non-verbs are ignored.
        """
        term = self._glossary.get(term_id)
        if term is None or term.kind != 'verb':
            return
        if (term_id, display) in self._forms:
            return
        self._forms.add((term_id, display))
        if display != term.canonical:
            self._agg(term_id).forms.append(TermForm(display))

    def record_story_ref(self, term_id: TermId, story_id: StoryId) -> None:
        """Note that `story_id` references this term. Every kind participates."""
        if self._glossary.get(term_id) is None:
            return
        if (term_id, story_id) in self._story_refs:
            return
        self._story_refs.add((term_id, story_id))
        self._agg(term_id).stories.append(story_id)

    def _agg(self, term_id: TermId) -> GlossaryAggregation:
        return self._aggs.setdefault(term_id, GlossaryAggregation())


def build_term_scenario_index(report: ReportData) -> dict[TermId, list[NodeId]]:
    """For each glossary term, the scenarios whose narration or steps reference
    it. Scenario render order is preserved; each scenario appears at most once
    per term. Terms never referenced are absent; no glossary → empty."""
    if report.glossary is None:
        return {}
    index: dict[TermId, list[NodeId]] = {}
    for scenario in report.scenarios:
        seen: set[TermId] = set()
        for narration in iter_narrations(scenario):
            for part in narration.parts:
                if not isinstance(part, NarrationTermRef):
                    continue
                if part.term_id in seen:
                    continue
                seen.add(part.term_id)
                index.setdefault(part.term_id, []).append(scenario.id)
    return index
