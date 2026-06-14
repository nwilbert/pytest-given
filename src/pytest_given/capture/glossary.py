"""User-facing Glossary API: id derivation, value classes, registration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ..model import Glossary, GlossaryTerm, PytestGivenError, TermId, id_derive

__all__ = [
    'Actor',
    'ActorInstance',
    'InflectedVerb',
    'Verb',
    'WorkObject',
    'WorkObjectInstance',
    'id_derive',
]


@dataclass(frozen=True)
class _TermHandle:
    """Common base: a GlossaryTerm + back-ref to its owning Glossary."""

    _term: GlossaryTerm
    _glossary: Glossary

    @property
    def term(self) -> GlossaryTerm:
        return self._term

    @property
    def glossary(self) -> Glossary:
        return self._glossary

    @property
    def id(self) -> TermId:
        return self._term.id

    @property
    def canonical(self) -> str:
        return self._term.canonical


@dataclass(frozen=True)
class Actor(_TermHandle):
    def __call__(self, display: str) -> ActorInstance:
        return ActorInstance(actor=self, display=display)


@dataclass(frozen=True)
class WorkObject(_TermHandle):
    def __call__(self, display: str) -> WorkObjectInstance:
        return WorkObjectInstance(work_object=self, display=display)


@dataclass(frozen=True)
class Verb(_TermHandle):
    def __call__(self, display: str) -> InflectedVerb:
        return InflectedVerb(verb=self, display=display)


@dataclass(frozen=True)
class ActorInstance:
    actor: Actor
    display: str


@dataclass(frozen=True)
class WorkObjectInstance:
    work_object: WorkObject
    display: str


@dataclass(frozen=True)
class InflectedVerb:
    verb: Verb
    display: str


def _register_kind(
    self: Glossary,
    kind: Literal['actor', 'object', 'verb'],
    name: str,
    definition: str,
) -> GlossaryTerm:
    """Idempotent registration. Returns the canonical term (existing or new)."""
    new = GlossaryTerm(
        id=id_derive(name),
        kind=kind,
        canonical=name,
        definition=definition,
    )
    existing = self.get(new.id)
    if existing is not None:
        if existing == new:
            return existing
        raise PytestGivenError(
            f'term {name!r} (id {new.id!r}) conflicts with prior registration '
            f'(existing: kind={existing.kind!r}, canonical={existing.canonical!r}, '
            f'definition={existing.definition!r}; new: kind={new.kind!r}, '
            f'canonical={new.canonical!r}, definition={new.definition!r}).'
        )
    self._register(new)
    return new


def _glossary_actor(self: Glossary, name: str, *, definition: str = '') -> Actor:
    term = _register_kind(self, 'actor', name, definition)
    return Actor(_term=term, _glossary=self)


def _glossary_work_object(
    self: Glossary, name: str, *, definition: str = ''
) -> WorkObject:
    term = _register_kind(self, 'object', name, definition)
    return WorkObject(_term=term, _glossary=self)


def _glossary_verb(self: Glossary, name: str, *, definition: str = '') -> Verb:
    term = _register_kind(self, 'verb', name, definition)
    return Verb(_term=term, _glossary=self)


Glossary.actor = _glossary_actor  # type: ignore[method-assign]
Glossary.work_object = _glossary_work_object  # type: ignore[method-assign]
Glossary.verb = _glossary_verb  # type: ignore[method-assign]
