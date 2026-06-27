"""User-facing Glossary API: id derivation, value classes, registration."""

from __future__ import annotations

import difflib
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


def _normalize_definition(definition: str | None) -> str | None:
    """Collapse an empty or whitespace-only definition to None so 'undefined'
    has exactly one representation."""
    if definition is None:
        return None
    stripped = definition.strip()
    return stripped or None


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


@dataclass(frozen=True)
class DeferredTermInstance:
    handle: DeferredTermHandle
    display: str


@dataclass(frozen=True)
class DeferredTermHandle(TermHandle):
    """Deferred-kind handle for a term whose kind is resolved post-collection
    (file-glossary terms and code-glossary g(...) / g[...] terms). One type for
    all kinds, unlike the eager Actor/WorkObject/Verb handles. Callable to
    override display."""

    def __call__(self, display: str) -> DeferredTermInstance:
        return DeferredTermInstance(handle=self, display=display)


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
    kind: Literal['actor', 'object', 'verb'] | None,
    name: str,
    definition: str | None,
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
        definition=_normalize_definition(definition),
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
    definition: str | None,
) -> TermHandle:
    # skip=3: this function → kind wrapper (actor/work_object/verb) → user call site
    source = capture_caller_source(skip=3)
    term = _register_kind(glossary, kind, name, definition, source)
    register_glossary(glossary)
    return _HANDLE_BY_KIND[kind](_term=term, _glossary=glossary)


def _glossary_actor(self: Glossary, name: str, definition: str | None = None) -> Actor:
    handle = _mint_handle(self, 'actor', name, definition)
    assert isinstance(handle, Actor)
    return handle


def _glossary_work_object(
    self: Glossary, name: str, definition: str | None = None
) -> WorkObject:
    handle = _mint_handle(self, 'object', name, definition)
    assert isinstance(handle, WorkObject)
    return handle


def _glossary_verb(self: Glossary, name: str, definition: str | None = None) -> Verb:
    handle = _mint_handle(self, 'verb', name, definition)
    assert isinstance(handle, Verb)
    return handle


def deferred_handle_or_raise(
    glossary: Glossary,
    name: str,
    handle_cache: dict[TermId, DeferredTermHandle] | None = None,
) -> DeferredTermHandle:
    """Name-based, case-insensitive get-only lookup returning a deferred handle.
    Raises PytestGivenError with a did-you-mean hint on an unknown name. Shared
    by the code glossary's g[...] / g(...) lookups and FileGlossary."""
    term_id = id_derive(name)
    if handle_cache is not None and term_id in handle_cache:
        return handle_cache[term_id]
    term = glossary.get(term_id)
    if term is None:
        close = difflib.get_close_matches(
            name, [candidate.canonical for candidate in glossary.terms], n=3
        )
        hint = f' Did you mean: {", ".join(close)}?' if close else ''
        raise PytestGivenError(f'no glossary term named {name!r}.{hint}')
    handle = DeferredTermHandle(_term=term, _glossary=glossary)
    if handle_cache is not None:
        handle_cache[term_id] = handle
    return handle


def _glossary_call(
    self: Glossary, name: str, definition: str | None = None
) -> DeferredTermHandle:
    # skip=2: this function → user call site
    source = capture_caller_source(skip=2)
    term = _register_kind(self, None, name, definition, source)
    register_glossary(self)
    return DeferredTermHandle(_term=term, _glossary=self)


def _glossary_getitem(self: Glossary, name: str) -> DeferredTermHandle:
    return deferred_handle_or_raise(self, name)


Glossary.actor = _glossary_actor  # type: ignore[method-assign]
Glossary.work_object = _glossary_work_object  # type: ignore[method-assign]
Glossary.verb = _glossary_verb  # type: ignore[method-assign]
Glossary.__call__ = _glossary_call  # type: ignore[method-assign]
Glossary.__getitem__ = _glossary_getitem  # type: ignore[method-assign]
