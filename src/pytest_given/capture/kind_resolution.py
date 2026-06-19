"""Post-collection inference of file-glossary term kinds from story usage.

A term referenced by an activity path gets a kind from the slot positions it
appears in across all stories: position 0 → actor slot, 1 → verb slot, ≥2 →
noun slot (actor or work object). Undeclared kinds are inferred; declared
kinds are verified against observed positions. Conflicts raise."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import replace
from typing import Literal

from ..model import (
    ActivityTermRef,
    Glossary,
    GlossaryTerm,
    PytestGivenError,
    Story,
    TermId,
)

type _Kind = Literal['actor', 'object', 'verb']
type _Slot = Literal['actor', 'verb', 'noun']


def resolve_glossary_kinds(glossary: Glossary, stories: list[Story]) -> Glossary:
    """Return a new Glossary with each term's kind inferred/verified."""
    slots_by_term: dict[TermId, set[_Slot]] = defaultdict(set)
    stories_by_term: dict[TermId, set[str]] = defaultdict(set)
    for story in stories:
        for activity in story.activities:
            for activity_path in activity.paths:
                for position, part in enumerate(activity_path.parts):
                    if isinstance(part, ActivityTermRef):
                        slots_by_term[part.term_id].add(_slot_for(position))
                        stories_by_term[part.term_id].add(story.title)
    resolved_terms = [
        replace(
            term,
            kind=_resolve_one(
                term,
                slots_by_term.get(term.id, set()),
                sorted(stories_by_term.get(term.id, set())),
            ),
        )
        for term in glossary.terms
    ]
    return Glossary(terms=resolved_terms)


def _slot_for(position: int) -> _Slot:
    if position == 0:
        return 'actor'
    if position == 1:
        return 'verb'
    return 'noun'


def _resolve_one(
    term: GlossaryTerm,
    slots: set[_Slot],
    story_titles: list[str],
) -> _Kind | None:
    where = f' (in {", ".join(story_titles)})' if story_titles else ''
    if term.kind is not None:
        _verify_declared(term, slots, where)
        return term.kind
    if 'verb' in slots and ('actor' in slots or 'noun' in slots):
        raise PytestGivenError(
            f'term {term.id!r} is used in incompatible positions{where}: '
            f'a verb slot and an actor/noun slot. Add a kind column to disambiguate.'
        )
    if 'verb' in slots:
        return 'verb'
    if 'actor' in slots:
        return 'actor'
    if 'noun' in slots:
        return 'object'
    return None


def _verify_declared(term: GlossaryTerm, slots: set[_Slot], where: str) -> None:
    declared = term.kind
    if 'verb' in slots and declared != 'verb':
        _raise_declared(term, 'verb slot', where)
    if 'actor' in slots and declared != 'actor':
        _raise_declared(term, 'actor slot', where)
    if 'noun' in slots and declared == 'verb':
        _raise_declared(term, 'noun slot', where)


def _raise_declared(term: GlossaryTerm, slot: str, where: str) -> None:
    raise PytestGivenError(
        f'term {term.id!r} is declared kind {term.kind!r} but appears in '
        f'a {slot}{where}, which is incompatible.'
    )
