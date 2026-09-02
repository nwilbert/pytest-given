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
    GlossaryTerm,
    Narration,
    NarrationTermRef,
    NodeId,
    ReportData,
    Scenario,
    Story,
    StoryId,
    TermId,
    walk_steps,
)
from .coverage import (
    CoverageMap,
    StoryIndex,
    build_story_index,
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

    The report-side tally, not `capture`'s authored `TermInstance`.
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


@dataclass(frozen=True)
class TabVisibility:
    """Which browse tabs a report has anything to show in."""

    scenarios: bool
    stories: bool
    glossary: bool

    @property
    def visible_count(self) -> int:
        return sum((self.scenarios, self.stories, self.glossary))


def tab_visibility(report: ReportData) -> TabVisibility:
    return TabVisibility(
        scenarios=True,
        stories=bool(report.stories),
        glossary=bool(report.glossary is not None and report.glossary.terms),
    )


@dataclass(frozen=True)
class TermEntry:
    """One row of the Glossary view."""

    term: GlossaryTerm
    aggregation: GlossaryAggregation
    scenario_ids: list[NodeId]
    show_instances: bool
    summary: str


@dataclass(frozen=True)
class KindGroup:
    """The Glossary view's terms under one kind heading."""

    label: str
    key: str
    css_class: str
    entries: list[TermEntry]


@dataclass(frozen=True)
class GlossaryView:
    """Everything the Glossary tab renders, computed here rather than in Jinja.

    `all_uncategorized` says the kind grouping carries no information — every
    term is kindless — so the template drops the filter section and the
    'Uncategorized' heading and shows a flat list.
    """

    groups: list[KindGroup]
    counts: dict[str, int]
    undefined_count: int
    all_uncategorized: bool


# Heading label, filter key, and pill class for each kind, in display order.
_KIND_GROUPS: tuple[tuple[str, str, str], ...] = (
    ('Actors', 'actor', 'term-actor'),
    ('Work Objects', 'object', 'term-obj'),
    ('Verbs', 'verb', 'term-verb'),
    ('Uncategorized', 'kindless', 'term-kindless'),
)

# Only an entity has instances worth listing; a verb's surface forms are its
# own section.
_INSTANCE_KINDS = frozenset({'actor', 'object'})


def build_glossary_view(report: ReportData, views: GlossaryViews) -> GlossaryView:
    terms = report.glossary.terms if report.glossary is not None else []
    by_kind: dict[str, list[GlossaryTerm]] = {key: [] for _l, key, _c in _KIND_GROUPS}
    for term in terms:
        by_kind[term.kind or 'kindless'].append(term)
    counts = {key: len(group) for key, group in by_kind.items()}
    groups = [
        KindGroup(
            label=label,
            key=key,
            css_class=css_class,
            entries=[_term_entry(term, key, views) for term in by_kind[key]],
        )
        for label, key, css_class in _KIND_GROUPS
        if by_kind[key]
    ]
    return GlossaryView(
        groups=groups,
        counts=counts,
        undefined_count=sum(1 for term in terms if term.definition is None),
        all_uncategorized=bool(
            counts['kindless']
            and not (counts['actor'] or counts['object'] or counts['verb'])
        ),
    )


def _term_entry(term: GlossaryTerm, kind_key: str, views: GlossaryViews) -> TermEntry:
    aggregation = views.aggregations.get(term.id, GlossaryAggregation())
    scenario_ids = views.term_scenarios.get(term.id, [])
    show_instances = kind_key in _INSTANCE_KINDS and bool(aggregation.instances)
    return TermEntry(
        term=term,
        aggregation=aggregation,
        scenario_ids=scenario_ids,
        show_instances=show_instances,
        summary=' · '.join(
            part
            for part in (
                _plural(len(aggregation.instances), 'instance')
                if show_instances
                else '',
                _plural(len(aggregation.stories), 'story', 'stories'),
                _plural(len(scenario_ids), 'scenario'),
            )
            if part
        ),
    )


def _plural(n: int, singular: str, plural: str | None = None) -> str:
    """`'3 scenarios'`, or empty for a count of zero — the summary lists only
    what a term actually has."""
    if not n:
        return ''
    return f'{n} {singular}' if n == 1 else f'{n} {plural or singular + "s"}'


def build_coverage_maps(report: ReportData) -> CoverageMap:
    """Which activities each scenario covers, keyed by node id — empty for one
    bound to no story, or a report with no glossary to match term refs against.

    Each story is indexed once and reused across the scenarios bound to it.
    """
    glossary = report.glossary
    if glossary is None:
        return {scenario.id: set() for scenario in report.scenarios}
    stories = {story.id: story for story in report.stories}
    indexes: dict[StoryId, StoryIndex] = {}
    result: CoverageMap = {}
    for scenario in report.scenarios:
        story = stories.get(scenario.story_id) if scenario.story_id else None
        if story is None:
            result[scenario.id] = set()
            continue
        if story.id not in indexes:
            indexes[story.id] = build_story_index(glossary, story)
        result[scenario.id] = compute_coverage(glossary, scenario, indexes[story.id])
    return result


def build_story_rollups(
    report: ReportData, coverage_maps: CoverageMap
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
    coverage_maps: CoverageMap,
) -> dict[NodeId, list[ActivityId]]:
    """For each scenario, the sorted list of activity ids it covers."""
    return {scn_id: sorted(covered) for scn_id, covered in coverage_maps.items()}


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


@dataclass(frozen=True)
class GlossaryViews:
    """What the Glossary view reads: per-term aggregations, and which scenarios
    reference each term.

    Built from one walk, so the two cannot disagree about what counts as a
    reference — they did when one walked only the steps and the other the
    scenario's own narration too, and a term used solely in a `@scenario` title
    was listed as used by a scenario while contributing no instance.
    """

    aggregations: dict[TermId, GlossaryAggregation]
    term_scenarios: dict[TermId, list[NodeId]]


def build_glossary_views(report: ReportData) -> GlossaryViews:
    """Per-term aggregations and the term-to-scenarios index.

    Scenario narrations contribute entity instances; story activity prose
    contributes story refs, more instances, and verb surface forms. Scenario
    render order is preserved and each scenario appears at most once per term.
    """
    glossary = report.glossary
    if glossary is None:
        return GlossaryViews(aggregations={}, term_scenarios={})
    index = _GlossaryIndex(glossary)
    term_scenarios: dict[TermId, list[NodeId]] = {}
    for scenario in report.scenarios:
        seen: set[TermId] = set()
        for narration, fixture_name in _scenario_narrations(scenario):
            for part in narration.parts:
                if not isinstance(part, NarrationTermRef):
                    continue
                index.record_instance(
                    part.term_id, part.display, fixture_name=fixture_name
                )
                if part.term_id not in seen:
                    seen.add(part.term_id)
                    term_scenarios.setdefault(part.term_id, []).append(scenario.id)
    for story in report.stories:
        for ref in _story_term_refs(story):
            # Each `record_*` no-ops for a term of the wrong kind, so the walk
            # states what it saw rather than sorting it into a bucket.
            index.record_story_ref(ref.term_id, story.id)
            index.record_instance(ref.term_id, ref.display)
            index.record_form(ref.term_id, ref.display)
    return GlossaryViews(aggregations=index.result(), term_scenarios=term_scenarios)


def _scenario_narrations(scenario: Scenario) -> Iterator[tuple[Narration, str | None]]:
    """Every narration a scenario carries, with the fixture that recorded it —
    the scenario's own title first, then each step's."""
    yield scenario.narration, None
    for _path, step in walk_steps(scenario.steps):
        yield step.narration, step.fixture_name


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

    Every `record_*` is idempotent for a given identity and silently ignores a
    term whose kind the bucket does not take, so a caller can report an
    observation without first working out where it belongs.
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
