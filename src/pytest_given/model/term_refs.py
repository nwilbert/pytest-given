"""Glossary term cross-references: where scenario narration and story prose name
each term, and as which instance or activity form. The Glossary view and the
delta both read this index.
"""

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import NewType

from .schema import (
    ClauseTermRef,
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
)
from .step_tree import iter_steps
from .text import name_key, name_keys

# Only an actor or work object has instances; an activity's surface forms are
# its own list.
INSTANCE_KINDS: frozenset[TermKind] = frozenset({'actor', 'object'})


@dataclass
class TermOccurrence:
    """One sighting of a term in the recorded steps, as the Glossary shows it.

    The report-side tally, not `capture`'s authored `TermInstance`.
    """

    display: str
    fixture_name: str | None = None


TermForm = NewType('TermForm', str)
"""One activity surface form collected from story clause parts.

The inflection as story prose spells it (`searches for` for `search`), never
a reading `is_own_name` accepts — `record_form` drops those. A distinct type, so it
cannot be confused with the canonical name or with a `TermId`.
"""


@dataclass
class GlossaryAggregation:
    """Aggregated cross-reference data for a single glossary term."""

    instances: list[TermOccurrence] = field(default_factory=list)
    forms: list[TermForm] = field(default_factory=list)
    stories: list[StoryId] = field(default_factory=list)


@dataclass(frozen=True)
class TermCrossRefs:
    """The cross-reference index the Glossary view and the delta are built from:
    per-term aggregations, and which scenarios reference each term.

    Built from one walk, so the two agree on what counts as a reference.
    """

    aggregations: dict[TermId, GlossaryAggregation]
    term_scenarios: dict[TermId, list[NodeId]]


def build_term_crossrefs(report: ReportData) -> TermCrossRefs:
    """Per-term aggregations and the term-to-scenarios index.

    Scenario narrations contribute actor and work-object instances; story sentence prose
    contributes story refs, more instances, and activity surface forms. Scenario
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
                    # A ref naming a term outside the selected glossary: the
                    # renderer draws it as plain text, so it is no reference.
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


def is_own_name(display: str, term: GlossaryTerm) -> bool:
    """Whether a reference reads as the term's canonical name or its S-form, in
    any case — `Guest`, `guest.l` and `guest.l.s` alike — and so names the
    concept itself rather than an instance or an inflection of it."""
    return name_key(display) in name_keys(term.canonical)


def _scenario_narrations(scenario: Scenario) -> Iterator[tuple[Narration, str | None]]:
    yield scenario.narration, None
    for step in iter_steps(scenario.steps):
        yield step.narration, step.fixture_name


def _story_term_refs(story: Story) -> Iterator[ClauseTermRef]:
    """Every glossary reference in a story's sentence prose."""
    return (
        part
        for sentence in story.sentences
        for clause in sentence.clauses
        for part in clause.parts
        if isinstance(part, ClauseTermRef)
    )


class _GlossaryIndex:
    """Accumulates the cross-references, deduping as it goes.

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
        """Note one occurrence of an actor or work-object term reading as `display`.

        A reading `is_own_name` accepts is the concept itself, not an
        instance; only specific displays (``Alice`` for ``Guest``) reach the
        Instances list. Activities and kindless terms have no instances and are
        ignored here.
        """
        term = self._glossary.get(term_id)
        if term is None or term.kind not in INSTANCE_KINDS:
            return
        if (term_id, display) in self._instances:
            return
        self._instances.add((term_id, display))
        if not is_own_name(display, term):
            self._agg(term_id).instances.append(
                TermOccurrence(display=display, fixture_name=fixture_name)
            )

    def record_form(self, term_id: TermId, display: str) -> None:
        """Note one surface form of an activity term.

        A reading `is_own_name` accepts is not a *form* of the term, so only
        other inflections are listed. Non-activities are ignored.
        """
        term = self._glossary.get(term_id)
        if term is None or term.kind != 'activity':
            return
        if (term_id, display) in self._forms:
            return
        self._forms.add((term_id, display))
        if not is_own_name(display, term):
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
