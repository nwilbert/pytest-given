"""Post-collection inference of file-glossary term kinds from story usage.

A term referenced by an activity path gets a kind from the slot positions it
appears in across all stories: 0 → actor, odd → verb, even ≥ 2 → noun
(actor or work object). Undeclared kinds are inferred; declared kinds are
verified against observed positions. Conflicts raise."""

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
    TermKind,
)

type _Slot = Literal['actor', 'verb', 'noun']


def infer_glossary_kinds(glossary: Glossary, stories: list[Story]) -> Glossary:
    """Return a new Glossary with each term's kind inferred/verified."""
    stories_by_slot: dict[TermId, dict[_Slot, set[str]]] = defaultdict(
        lambda: defaultdict(set)
    )
    for story in stories:
        for activity in story.activities:
            for activity_path in activity.paths:
                for position, part in enumerate(activity_path.parts):
                    if isinstance(part, ActivityTermRef):
                        slot = _slot_for(position)
                        stories_by_slot[part.term_id][slot].add(story.title)
    inferred_terms = [
        replace(term, kind=_infer_one(term, stories_by_slot.get(term.id, {})))
        for term in glossary.terms
    ]
    return Glossary(terms=inferred_terms)


def _slot_for(position: int) -> _Slot:
    if position == 0:
        return 'actor'
    if position % 2 == 1:
        return 'verb'
    return 'noun'


def _infer_one(
    term: GlossaryTerm,
    stories_by_slot: dict[_Slot, set[str]],
) -> TermKind | None:
    slots = set(stories_by_slot)
    if term.kind is not None:
        _verify_declared(term, stories_by_slot)
        return term.kind
    if 'verb' in slots and ('actor' in slots or 'noun' in slots):
        other: _Slot = 'actor' if 'actor' in slots else 'noun'
        where = _where(stories_by_slot, 'verb', other)
        raise PytestGivenError(
            f'term {term.canonical!r} is used in incompatible positions{where}: '
            f'a verb slot and an actor/noun slot. Add a kind column to disambiguate.'
        )
    if 'verb' in slots:
        return 'verb'
    if 'actor' in slots:
        return 'actor'
    if 'noun' in slots:
        return 'object'
    return None


def _verify_declared(
    term: GlossaryTerm, stories_by_slot: dict[_Slot, set[str]]
) -> None:
    declared = term.kind
    slots = set(stories_by_slot)
    if 'verb' in slots and declared != 'verb':
        _raise_declared(term, 'verb slot', _where(stories_by_slot, 'verb'))
    if 'actor' in slots and declared != 'actor':
        _raise_declared(term, 'actor slot', _where(stories_by_slot, 'actor'))
    if 'noun' in slots and declared == 'verb':
        _raise_declared(term, 'noun slot', _where(stories_by_slot, 'noun'))


def _raise_declared(term: GlossaryTerm, slot: str, where: str) -> None:
    raise PytestGivenError(
        f'term {term.canonical!r} is declared kind {term.kind!r} but appears in '
        f'a {slot}{where}, which is incompatible.'
    )


def _where(stories_by_slot: dict[_Slot, set[str]], *slots: _Slot) -> str:
    """Story titles for just the named slots, so a conflict names only the
    stories that actually contributed the offending positions."""
    titles = sorted({title for slot in slots for title in stories_by_slot[slot]})
    return f' (in {", ".join(titles)})' if titles else ''
