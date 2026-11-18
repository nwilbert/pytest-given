"""The delta page's Glossary tab: a card per listed term, the listed scenarios
that refer to it, and the terms a ref's tooltip reads."""

from dataclasses import dataclass
from typing import Literal

from ...delta import (
    SIDE_MARK,
    Change,
    DeltaData,
    Side,
    TermDelta,
    TermFacts,
    change_counts,
    on_side,
    other_side,
    terms_read_the_same,
)
from ...model import Glossary, GlossaryTerm, TermId, build_term_crossrefs, plural
from ..glossary_view import KindGrouping, group_by_kind, plural_if_any
from ..html_renderer import TermRefTarget
from .scenarios import REMOVED, ListedScenario
from .steps import MarkedRun, side_runs

type FormChange = Literal['added', 'removed']

# Prefixes the tooltip key of a before term reading otherwise than the after
# term of its ID. A term ID never holds a `:`.
_BEFORE_TIP = 'before:'


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
        return card_key(self.delta)

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


def card_key(term_delta: TermDelta) -> str:
    """A term card's ID, prefixed as a removed scenario's slug is (`REMOVED`):
    a term whose kind changed has a card under each kind."""
    prefix = REMOVED if term_delta.after is None else ''
    return prefix + term_delta.shown.id


def tip_terms(delta: DeltaData) -> dict[str, GlossaryTerm]:
    """Every term a ref's tooltip shows, by its tooltip key: the after
    glossary's terms, the before glossary's it lacks, which no after-side ref
    can name, then the before ones reading otherwise than the after term of
    their ID."""
    tips: dict[str, GlossaryTerm] = {
        term.id: term for term in _terms(delta.glossary.after)
    }
    for term in _terms(delta.glossary.before):
        tips.setdefault(term.id, term)
    for term in _read_otherwise(delta):
        tips[_BEFORE_TIP + term.id] = term
    return tips


def term_ref_targets(delta: DeltaData) -> dict[Side, _SideTargets]:
    """Where a term ref read on each side points: its side's reading of the
    term, and the card listing the term's change, if one does."""
    entries: dict[Side, dict[TermId, str]] = {'before': {}, 'after': {}}
    for term_delta in delta.glossary.terms:
        for side, by_id in entries.items():
            if (term := term_delta.on(side)) is not None:
                by_id[term.id] = card_key(term_delta)
    return {
        'before': _SideTargets(
            entries['before'], frozenset(term.id for term in _read_otherwise(delta))
        ),
        'after': _SideTargets(entries['after'], frozenset()),
    }


@dataclass(frozen=True)
class _SideTargets:
    entries: dict[TermId, str]
    # The terms whose tooltip is keyed `_BEFORE_TIP`.
    read_otherwise: frozenset[TermId]

    def __call__(self, term_id: TermId) -> TermRefTarget:
        tip = _BEFORE_TIP + term_id if term_id in self.read_otherwise else term_id
        return TermRefTarget(tip=tip, entry=self.entries.get(term_id))


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


def _read_otherwise(delta: DeltaData) -> list[GlossaryTerm]:
    """The before glossary's terms whose tooltip reads otherwise than the after
    glossary's term of that ID."""
    after = {term.id: term for term in _terms(delta.glossary.after)}
    return [
        term
        for term in _terms(delta.glossary.before)
        if (shared := after.get(term.id)) is not None
        and not terms_read_the_same(term, shared)
    ]


def _terms(glossary: Glossary | None) -> list[GlossaryTerm]:
    return glossary.terms if glossary is not None else []
