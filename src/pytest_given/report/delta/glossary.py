"""The delta page's Glossary tab: a card per listed term, the listed scenarios
that refer to it, and the terms a ref's tooltip reads."""

from dataclasses import dataclass
from typing import Literal

from ...model import (
    SIDE_MARK,
    Change,
    DeltaData,
    Glossary,
    GlossaryTerm,
    Side,
    TermDelta,
    TermFacts,
    TermId,
    build_term_crossrefs,
    change_counts,
    on_side,
    other_side,
    plural,
)
from ..glossary_view import KindGrouping, group_by_kind, plural_if_any
from .scenarios import REMOVED, ListedScenario
from .steps import MarkedRun, side_runs

type FormChange = Literal['added', 'removed']


@dataclass(frozen=True)
class OtherForm:
    text: str
    change: FormChange | None = None


@dataclass(frozen=True)
class ListedTerm:
    """A term's card, shown from its after side, or its before side when it
    was removed."""

    delta: TermDelta
    # The listed scenarios that refer to it, on either side. Its unchanged
    # ones it only counts: they aren't on the page.
    scenarios: list[ListedScenario]

    @property
    def change(self) -> Change:
        return self.delta.change

    @property
    def side(self) -> Side:
        return self.delta.shown_side

    @property
    def shown(self) -> GlossaryTerm:
        return self.delta.shown

    @property
    def key(self) -> str:
        """Its card's ID, prefixed as a removed scenario's slug is (`REMOVED`):
        a term whose kind changed has a card under each kind."""
        prefix = REMOVED if self.delta.after is None else ''
        return prefix + self.shown.id

    @property
    def renamed_from(self) -> str | None:
        """A changed term's before name, where its after one differs."""
        before, after = self.delta.before, self.delta.after
        if before is None or after is None or before.canonical == after.canonical:
            return None
        return before.canonical

    @property
    def sides(self) -> tuple[Side, ...]:
        """A changed term's two, or the one it is shown from."""
        return ('before', 'after') if self.change == 'changed' else (self.side,)

    def term(self, side: Side) -> GlossaryTerm:
        term = self.delta.on(side)
        assert term is not None
        return term

    def definition(self, side: Side) -> tuple[MarkedRun, ...]:
        """A changed definition on one side, the words only it has marked;
        empty where the definition reads unmarked."""
        return side_runs(self.delta.definition, side)

    def other_forms(self, side: Side) -> list[OtherForm]:
        """A changed term's forms only this side has are marked."""
        forms = self._facts(side).other_forms
        if self.change != 'changed':
            return [OtherForm(form) for form in forms]
        other = self._facts(other_side(side)).other_forms
        return [
            OtherForm(form, None if form in other else SIDE_MARK[side])
            for form in forms
        ]

    def scenario_count(self, side: Side) -> str:
        """A changed term's on both sides, a none included, so they compare."""
        count = self._facts(side).scenario_count
        if self.change == 'changed':
            return plural(count, 'scenario')
        return plural_if_any(count, 'scenario')

    @property
    def search_text(self) -> str:
        sides = (self.delta.before, self.delta.after)
        names = [side.canonical for side in sides if side is not None]
        return ' '.join(dict.fromkeys(names)).lower()

    def _facts(self, side: Side) -> TermFacts:
        facts = on_side(side, self.delta.before_facts, self.delta.after_facts)
        return facts or TermFacts()


@dataclass(frozen=True)
class DeltaGlossaryView:
    listed: list[ListedTerm]
    grouping: KindGrouping[ListedTerm]
    change_counts: dict[Change, int]
    unchanged_count: int
    undefined_count: int


# The listed scenarios that refer to a term, by the side they were read on.
type TermReach = dict[Side, dict[TermId, list[ListedScenario]]]


def term_reach(delta: DeltaData, listed: list[ListedScenario]) -> TermReach:
    sides: tuple[tuple[Side, Glossary | None], ...] = (
        ('before', delta.glossary.before),
        ('after', delta.glossary.after),
    )
    reach: TermReach = {}
    for side, glossary in sides:
        read = {
            scenario.id: (scenario, item)
            for item in listed
            if (scenario := item.delta.on(side)) is not None
        }
        crossrefs = build_term_crossrefs(
            [scenario for scenario, _ in read.values()], glossary
        )
        reach[side] = {
            term_id: [read[node_id][1] for node_id in node_ids]
            for term_id, node_ids in crossrefs.term_scenarios.items()
        }
    return reach


def delta_glossary_view(
    delta: DeltaData, listed: list[ListedScenario], reach: TermReach
) -> DeltaGlossaryView:
    position = {item.slug: index for index, item in enumerate(listed)}
    cards = [
        ListedTerm(term_delta, _referring(term_delta, position, reach))
        for term_delta in delta.glossary.terms
    ]
    return DeltaGlossaryView(
        listed=cards,
        grouping=group_by_kind(cards, lambda card: card.shown.kind),
        change_counts=change_counts(card.change for card in cards),
        unchanged_count=len(delta.glossary.unchanged),
        undefined_count=sum(card.shown.definition is None for card in cards),
    )


def shown_term_scenarios(reach: TermReach) -> dict[TermId, list[str]]:
    """The Terms axis: each listed scenario under the terms of the side it is
    shown from."""
    shown: dict[TermId, list[str]] = {}
    for side, by_term in reach.items():
        for term_id, items in by_term.items():
            slugs = [item.slug for item in items if item.side == side]
            if slugs:
                shown.setdefault(term_id, []).extend(slugs)
    return shown


def tip_terms(delta: DeltaData) -> list[GlossaryTerm]:
    """The after glossary's terms, then the before glossary's it lacks, which
    no after-side ref can name."""
    after = _terms(delta.glossary.after)
    after_ids = {term.id for term in after}
    return after + [
        term for term in _terms(delta.glossary.before) if term.id not in after_ids
    ]


def before_tip_terms(delta: DeltaData) -> list[GlossaryTerm]:
    """The before glossary's terms whose tooltip reads otherwise than the after
    glossary's term of that ID: a term ref read from the before side looks here
    first."""
    after = {term.id: term for term in _terms(delta.glossary.after)}
    return [
        term
        for term in _terms(delta.glossary.before)
        if (shared := after.get(term.id)) is not None
        and (shared.canonical, shared.definition_text)
        != (term.canonical, term.definition_text)
    ]


def _referring(
    term_delta: TermDelta, position: dict[str, int], reach: TermReach
) -> list[ListedScenario]:
    """In the list's order, `position` by slug, each scenario once."""
    sides: tuple[Side, ...] = ('before', 'after')
    found = {
        item.slug: item
        for side in sides
        if (term := term_delta.on(side)) is not None
        for item in reach[side].get(term.id, [])
    }
    return sorted(found.values(), key=lambda item: position[item.slug])


def _terms(glossary: Glossary | None) -> list[GlossaryTerm]:
    return glossary.terms if glossary is not None else []
