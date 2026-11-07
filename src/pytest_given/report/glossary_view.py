"""The Glossary view: each term's cross-references from `model`, grouped into
the kind and section headings the template renders.
"""

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Literal, NamedTuple

from ..model import (
    INSTANCE_KINDS,
    GlossaryAggregation,
    GlossaryTerm,
    NodeId,
    ReportData,
    TermCrossRefs,
    TermId,
    TermKind,
    build_term_crossrefs,
    plural,
)

OTHER_SECTION = 'Other'
"""The URL key of the Other group, whatever spelling its header shows."""


@dataclass(frozen=True)
class TermEntry:
    """One row of the Glossary view."""

    term: GlossaryTerm
    aggregation: GlossaryAggregation
    scenario_ids: list[NodeId]
    show_instances: bool
    show_forms: bool
    # The counts a term is summarized by, each its own phrase — the template
    # spaces them, so no separator glyph is baked into the text.
    summary: tuple[str, ...]


# A term's kind as the Glossary view keys on it: the model's three, plus the
# bucket a term whose kind was never settled falls into.
type KindKey = TermKind | Literal['kindless']


@dataclass(frozen=True)
class KindGroup[Entry]:
    """The Glossary view's terms under one kind heading."""

    label: str
    key: KindKey
    entries: list[Entry]


@dataclass(frozen=True)
class SectionGroup:
    """The Glossary view's terms under one section heading."""

    label: str
    key: str
    entries: list[TermEntry]


type Grouping = Literal['section', 'kind', 'flat']


@dataclass(frozen=True)
class KindGrouping[Entry]:
    """Terms under their kind headings, and the kinds the sidebar filters on.

    `all_uncategorized` says the kind grouping carries no information — every
    term is kindless — so the template drops the filter section and the
    'Uncategorized' heading and shows a flat list.
    """

    groups: list[KindGroup[Entry]]
    kinds: list[KindTally]
    all_uncategorized: bool


@dataclass(frozen=True)
class GlossaryView:
    """Everything the Glossary tab renders, computed here rather than in Jinja.

    `section_groups` is empty unless the glossary is sectioned.
    """

    grouping: KindGrouping[TermEntry]
    section_groups: list[SectionGroup]
    term_scenarios: dict[TermId, list[NodeId]]
    undefined_count: int
    default_grouping: Grouping
    show_grouping_switch: bool


class _KindRow(NamedTuple):
    """How one kind heading is presented, and the noun its count reads in."""

    label: str
    key: KindKey
    noun: str


@dataclass(frozen=True)
class KindTally:
    """One kind as the Glossary sidebar and header present it.

    Carries its own count and summary phrase, so the template loops over the
    catalog instead of restating it.
    """

    label: str
    key: KindKey
    count: int
    summary: str


# Each kind's heading, filter key, and count noun, in display order.
_KIND_GROUPS: tuple[_KindRow, ...] = (
    _KindRow('Actors', 'actor', 'actor'),
    _KindRow('Work Objects', 'object', 'work object'),
    _KindRow('Activities', 'activity', 'activity'),
    _KindRow('Uncategorized', 'kindless', 'uncategorized'),
)


def build_glossary_view(report: ReportData) -> GlossaryView:
    """The Glossary view's terms, grouped by kind, each with its cross-references."""
    crossrefs = build_term_crossrefs(report.scenarios, report.glossary, report.stories)
    terms = report.glossary.terms if report.glossary is not None else []
    # One entry per term, which both groupings list.
    entries = {term.id: _term_entry(term, crossrefs) for term in terms}
    grouping = group_by_kind(entries.values(), lambda entry: entry.term.kind)
    section_groups = _section_groups(terms, entries)
    sectioned = bool(section_groups)
    return GlossaryView(
        grouping=grouping,
        section_groups=section_groups,
        term_scenarios=crossrefs.term_scenarios,
        undefined_count=sum(1 for term in terms if term.definition is None),
        default_grouping=(
            'section' if sectioned else 'flat' if grouping.all_uncategorized else 'kind'
        ),
        show_grouping_switch=sectioned and not grouping.all_uncategorized,
    )


def group_by_kind[Entry](
    entries: Iterable[Entry], kind_of: Callable[[Entry], TermKind | None]
) -> KindGrouping[Entry]:
    by_kind: dict[KindKey, list[Entry]] = {row.key: [] for row in _KIND_GROUPS}
    for entry in entries:
        by_kind[kind_of(entry) or 'kindless'].append(entry)
    counts = {key: len(group) for key, group in by_kind.items()}
    return KindGrouping(
        groups=[
            KindGroup(label=row.label, key=row.key, entries=by_kind[row.key])
            for row in _KIND_GROUPS
            if by_kind[row.key]
        ],
        kinds=_kind_tallies(counts),
        all_uncategorized=bool(
            counts['kindless']
            and not (counts['actor'] or counts['object'] or counts['activity'])
        ),
    )


def section_keys(terms: list[GlossaryTerm]) -> dict[TermId, str | None]:
    """Each term's section group key, `None` throughout an unsectioned glossary.

    A term with no section of a sectioned glossary is in the Other group.
    """
    authored = {_section_key(term.section) for term in terms if term.section}
    if len(authored) < 2:
        return {term.id: None for term in terms}
    return {
        term.id: _section_key(term.section) if term.section else OTHER_SECTION
        for term in terms
    }


def _section_key(section: str) -> str:
    return OTHER_SECTION if section.casefold() == OTHER_SECTION.casefold() else section


def _section_groups(
    terms: list[GlossaryTerm], entries: dict[TermId, TermEntry]
) -> list[SectionGroup]:
    keys = section_keys(terms)
    labels: dict[str, str] = {}
    members: dict[str, list[GlossaryTerm]] = {}
    for term in terms:
        key = keys[term.id]
        if key is None:
            return []
        # The first authored spelling labels a group; sectionless terms add none.
        if term.section:
            labels.setdefault(key, term.section)
        members.setdefault(key, []).append(term)
    return [
        SectionGroup(
            label=labels.get(key, key),
            key=key,
            entries=[entries[term.id] for term in members[key]],
        )
        for key in sorted(members, key=lambda key: key == OTHER_SECTION)
    ]


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


def _term_entry(term: GlossaryTerm, crossrefs: TermCrossRefs) -> TermEntry:
    aggregation = crossrefs.aggregations.get(term.id, GlossaryAggregation())
    scenario_ids = crossrefs.term_scenarios.get(term.id, [])
    show_instances = term.kind in INSTANCE_KINDS and bool(aggregation.instances)
    show_forms = term.kind == 'activity' and bool(aggregation.forms)
    # An instance and an activity's inflection are both a term's other forms:
    # the card lists and counts them under one label.
    other_forms = (
        len(aggregation.instances)
        if show_instances
        else len(aggregation.forms)
        if show_forms
        else 0
    )
    return TermEntry(
        term=term,
        aggregation=aggregation,
        scenario_ids=scenario_ids,
        show_instances=show_instances,
        show_forms=show_forms,
        summary=tuple(
            part
            for part in (
                plural_if_any(other_forms, 'other form'),
                plural_if_any(len(aggregation.stories), 'story'),
                plural_if_any(len(scenario_ids), 'scenario'),
            )
            if part
        ),
    )


def plural_if_any(count: int, singular: str) -> str:
    """`'3 scenarios'`, or empty for a count of zero — a term's summary lists
    only what the term actually has."""
    return plural(count, singular) if count else ''
