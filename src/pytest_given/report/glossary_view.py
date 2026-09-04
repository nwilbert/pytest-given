"""The Glossary view's rollups: per-term instances, surface forms and story
refs, grouped into the kind headings the template renders.

Its own module rather than a shared `aggregations`, for the reason `slugs.py`
gives for itself: this shares no input, no output and no vocabulary with the
story rollups next door.
"""

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Literal, NamedTuple, NewType

from ..model import (
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
    TermKind,
    iter_steps,
    plural,
)


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


@dataclass(frozen=True)
class TermEntry:
    """One row of the Glossary view."""

    term: GlossaryTerm
    aggregation: GlossaryAggregation
    scenario_ids: list[NodeId]
    show_instances: bool
    show_forms: bool
    summary: str


# A term's kind as the Glossary view keys on it: the model's three, plus the
# bucket a term whose kind was never settled falls into.
type KindKey = TermKind | Literal['kindless']


@dataclass(frozen=True)
class KindGroup:
    """The Glossary view's terms under one kind heading."""

    label: str
    key: KindKey
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
    kinds: list[KindTally]
    counts: dict[KindKey, int]
    term_scenarios: dict[TermId, list[NodeId]]
    undefined_count: int
    all_uncategorized: bool


class _KindRow(NamedTuple):
    """How one kind heading is presented: the same three fields `KindGroup`
    carries, minus the entries the view fills in."""

    label: str
    key: KindKey
    css_class: str
    noun: str


@dataclass(frozen=True)
class KindTally:
    """One kind as the Glossary sidebar and header present it.

    Carries its own count and its own summary phrase, so the template loops
    over the catalog instead of restating it — four hand-written filter rows
    and four hand-pluralized counts that had to be edited in step with
    `_KIND_GROUPS` to stay true.
    """

    label: str
    key: KindKey
    count: int
    summary: str


# Each kind's heading, filter key, and pill class, in display order.
_KIND_GROUPS: tuple[_KindRow, ...] = (
    _KindRow('Actors', 'actor', 'term-actor', 'actor'),
    _KindRow('Work Objects', 'object', 'term-obj', 'work object'),
    _KindRow('Verbs', 'verb', 'term-verb', 'verb'),
    _KindRow('Uncategorized', 'kindless', 'term-kindless', 'uncategorized'),
)

# Only an entity has instances worth listing; a verb's surface forms are its
# own section.
_INSTANCE_KINDS: frozenset[KindKey] = frozenset({'actor', 'object'})


def build_glossary_view(report: ReportData) -> GlossaryView:
    """The Glossary view, and the cross-reference index it was built from."""
    crossrefs = build_term_crossrefs(report)
    terms = report.glossary.terms if report.glossary is not None else []
    by_kind: dict[KindKey, list[GlossaryTerm]] = {row.key: [] for row in _KIND_GROUPS}
    for term in terms:
        by_kind[term.kind or 'kindless'].append(term)
    counts = {key: len(group) for key, group in by_kind.items()}
    groups = [
        KindGroup(
            label=row.label,
            key=row.key,
            css_class=row.css_class,
            entries=[
                _term_entry(term, row.key, crossrefs) for term in by_kind[row.key]
            ],
        )
        for row in _KIND_GROUPS
        if by_kind[row.key]
    ]
    return GlossaryView(
        groups=groups,
        kinds=_kind_tallies(counts),
        counts=counts,
        term_scenarios=crossrefs.term_scenarios,
        undefined_count=sum(1 for term in terms if term.definition is None),
        all_uncategorized=bool(
            counts['kindless']
            and not (counts['actor'] or counts['object'] or counts['verb'])
        ),
    )


def _kind_tallies(counts: dict[KindKey, int]) -> list[KindTally]:
    """The kinds the sidebar filters on and the header counts.

    `kindless` appears only when something is in it — an empty bucket is not a
    filter worth offering — while the three real kinds always do, so their
    checkboxes do not appear and disappear as terms are categorized.
    """
    return [
        KindTally(
            label=row.label,
            key=row.key,
            count=counts[row.key],
            summary=(
                f'{counts[row.key]} {row.noun}'
                if row.key == 'kindless'
                else plural(counts[row.key], row.noun)
            ),
        )
        for row in _KIND_GROUPS
        if row.key != 'kindless' or counts[row.key]
    ]


def _term_entry(
    term: GlossaryTerm, kind_key: KindKey, crossrefs: TermCrossRefs
) -> TermEntry:
    aggregation = crossrefs.aggregations.get(term.id, GlossaryAggregation())
    scenario_ids = crossrefs.term_scenarios.get(term.id, [])
    show_instances = kind_key in _INSTANCE_KINDS and bool(aggregation.instances)
    return TermEntry(
        term=term,
        aggregation=aggregation,
        scenario_ids=scenario_ids,
        show_instances=show_instances,
        show_forms=kind_key == 'verb' and bool(aggregation.forms),
        summary=' · '.join(
            part
            for part in (
                _some(len(aggregation.instances), 'instance') if show_instances else '',
                _some(len(aggregation.stories), 'story', 'stories'),
                _some(len(scenario_ids), 'scenario'),
            )
            if part
        ),
    )


def _some(n: int, singular: str, plural_form: str | None = None) -> str:
    """`'3 scenarios'`, or empty for a count of zero — the summary lists only
    what a term actually has."""
    return plural(n, singular, plural_form) if n else ''


@dataclass(frozen=True)
class TermCrossRefs:
    """The cross-reference index the Glossary view is built from: per-term
    aggregations, and which scenarios reference each term.

    Built from one walk, so the two cannot disagree about what counts as a
    reference — they did when one walked only the steps and the other the
    scenario's own narration too, and a term used solely in a `@scenario` title
    was listed as used by a scenario while contributing no instance.
    """

    aggregations: dict[TermId, GlossaryAggregation]
    term_scenarios: dict[TermId, list[NodeId]]


def build_term_crossrefs(report: ReportData) -> TermCrossRefs:
    """Per-term aggregations and the term-to-scenarios index.

    Scenario narrations contribute entity instances; story activity prose
    contributes story refs, more instances, and verb surface forms. Scenario
    render order is preserved and each scenario appears at most once per term.
    """
    glossary = report.glossary
    if glossary is None:
        return TermCrossRefs(aggregations={}, term_scenarios={})
    index = _GlossaryIndex(glossary)
    term_scenarios: dict[TermId, list[NodeId]] = {}
    for scenario in report.scenarios:
        seen: set[TermId] = set()
        for narration, fixture_name in _scenario_narrations(scenario):
            for part in narration.parts:
                if not isinstance(part, NarrationTermRef):
                    continue
                if glossary.get(part.term_id) is None:
                    # A ref naming a term outside the selected glossary. The
                    # renderer already draws it as plain text, and
                    # `record_instance` skips it — so counting it here made
                    # the two halves of this one walk disagree, and shipped a
                    # phantom id into the Terms browse axis.
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
    return TermCrossRefs(aggregations=index.result(), term_scenarios=term_scenarios)


def _scenario_narrations(scenario: Scenario) -> Iterator[tuple[Narration, str | None]]:
    yield scenario.narration, None
    for step in iter_steps(scenario.steps):
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
        if (term_id, display) in self._instances:
            return
        self._instances.add((term_id, display))
        if display != term.canonical:
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
