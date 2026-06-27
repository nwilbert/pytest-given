"""User-facing Glossary API: id derivation, value classes, registration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ..model import (
    Glossary,
    GlossaryTerm,
    PytestGivenError,
    SourceLocation,
    TermId,
    id_derive,
)
from .source import capture_caller_source


@dataclass(frozen=True)
class TermHandle:
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
class Actor(TermHandle):
    def __call__(self, display: str) -> ActorInstance:
        return ActorInstance(actor=self, display=display)


@dataclass(frozen=True)
class WorkObject(TermHandle):
    def __call__(self, display: str) -> WorkObjectInstance:
        return WorkObjectInstance(work_object=self, display=display)


@dataclass(frozen=True)
class Verb(TermHandle):
    def __call__(self, display: str) -> InflectedVerb:
        return InflectedVerb(verb=self, display=display)


def terms_match(existing: GlossaryTerm, candidate: GlossaryTerm) -> bool:
    """Whether two terms are the same registration: kind, canonical, and
    definition agree (`source` is intentionally excluded). Shared by the
    code-defined (`_register_kind`) and file-backed (`FileGlossary._add_row`)
    idempotency-and-conflict checks so the identity rule lives in one place."""
    return (
        existing.kind == candidate.kind
        and existing.canonical == candidate.canonical
        and existing.definition == candidate.definition
    )


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
        if terms_match(existing, new):
            return existing
        raise PytestGivenError(
            f'term {name!r} (id {new.id!r}) conflicts with prior registration '
            f'(existing: kind={existing.kind!r}, canonical={existing.canonical!r}, '
            f'definition={existing.definition!r}; new: kind={new.kind!r}, '
            f'canonical={new.canonical!r}, definition={new.definition!r}).'
        )
    self._register(new)
    return new


_HANDLE_BY_KIND: dict[Literal['actor', 'object', 'verb'], type[TermHandle]] = {
    'actor': Actor,
    'object': WorkObject,
    'verb': Verb,
}


# Insertion-ordered registry of Glossary instances ever used during the
# session. Populated lazily by `_mint_handle` (i.e. the first time the
# user mints any handle from a Glossary) so unused Glossaries don't show
# up. plugin._resolve_glossary reads this to find "the" glossary without
# needing a side-channel attribute on stories, which doesn't survive
# JSON round-trip.
_REGISTERED_GLOSSARIES: dict[int, Glossary] = {}


def register_glossary(glossary: Glossary) -> None:
    _REGISTERED_GLOSSARIES.setdefault(id(glossary), glossary)


def get_registered_glossaries() -> list[Glossary]:
    """Return Glossary instances that minted at least one handle this session."""
    return list(_REGISTERED_GLOSSARIES.values())


def clear_glossary_registry() -> None:
    """Reset the session-scoped Glossary registry. Called at pytest_sessionstart."""
    _REGISTERED_GLOSSARIES.clear()


def _mint_handle(
    glossary: Glossary,
    kind: Literal['actor', 'object', 'verb'],
    name: str,
    definition: str,
) -> TermHandle:
    # skip=3: this function → kind wrapper (actor/work_object/verb) → user call site
    source = capture_caller_source(skip=3)
    term = _register_kind(glossary, kind, name, definition, source)
    register_glossary(glossary)
    return _HANDLE_BY_KIND[kind](_term=term, _glossary=glossary)


def _glossary_actor(self: Glossary, name: str, definition: str = '') -> Actor:
    handle = _mint_handle(self, 'actor', name, definition)
    assert isinstance(handle, Actor)
    return handle


def _glossary_work_object(
    self: Glossary, name: str, definition: str = ''
) -> WorkObject:
    handle = _mint_handle(self, 'object', name, definition)
    assert isinstance(handle, WorkObject)
    return handle


def _glossary_verb(self: Glossary, name: str, definition: str = '') -> Verb:
    handle = _mint_handle(self, 'verb', name, definition)
    assert isinstance(handle, Verb)
    return handle


Glossary.actor = _glossary_actor  # type: ignore[method-assign]
Glossary.work_object = _glossary_work_object  # type: ignore[method-assign]
Glossary.verb = _glossary_verb  # type: ignore[method-assign]
