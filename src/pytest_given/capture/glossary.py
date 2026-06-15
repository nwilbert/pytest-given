"""User-facing Glossary API: id derivation, value classes, registration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ..model import Glossary, GlossaryTerm, PytestGivenError, SourceLocation, TermId, id_derive
from .source import capture_caller_source


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
    source: SourceLocation | None = None,
) -> GlossaryTerm:
    """Idempotent registration. Returns the canonical term (existing or new).

    `source` is the call site of the user-facing wrapper (g.actor / g.work_object /
    g.verb) — captured by those wrappers and threaded through. First-registration
    wins: re-registration with matching (kind, canonical, definition) returns the
    existing term unchanged, preserving its original `source`.
    """
    new = GlossaryTerm(
        id=id_derive(name),
        kind=kind,
        canonical=name,
        definition=definition,
        source=source,
    )
    existing = self.get(new.id)
    if existing is not None:
        if (
            existing.kind == new.kind
            and existing.canonical == new.canonical
            and existing.definition == new.definition
        ):
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
    source = capture_caller_source(skip=2)
    term = _register_kind(self, 'actor', name, definition, source)
    return Actor(_term=term, _glossary=self)


def _glossary_work_object(
    self: Glossary, name: str, *, definition: str = ''
) -> WorkObject:
    source = capture_caller_source(skip=2)
    term = _register_kind(self, 'object', name, definition, source)
    return WorkObject(_term=term, _glossary=self)


def _glossary_verb(self: Glossary, name: str, *, definition: str = '') -> Verb:
    source = capture_caller_source(skip=2)
    term = _register_kind(self, 'verb', name, definition, source)
    return Verb(_term=term, _glossary=self)


Glossary.actor = _glossary_actor  # type: ignore[method-assign]
Glossary.work_object = _glossary_work_object  # type: ignore[method-assign]
Glossary.verb = _glossary_verb  # type: ignore[method-assign]
