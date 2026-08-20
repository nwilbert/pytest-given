"""User-facing Glossary API: id derivation, value classes, registration."""

import difflib
from dataclasses import dataclass
from typing import Literal

from ..model import (
    Glossary as BaseGlossary,
)
from ..model import (
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
    _glossary: BaseGlossary

    @property
    def term(self) -> GlossaryTerm:
        return self._term

    @property
    def glossary(self) -> BaseGlossary:
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

    @property
    def low(self) -> ActorInstance:
        """Instance whose surface is the canonical term lowercased -- the common
        mid-sentence form (``guest.low`` instead of ``guest('guest')``)."""
        return self(self.canonical.lower())


@dataclass(frozen=True)
class WorkObject(TermHandle):
    def __call__(self, display: str) -> WorkObjectInstance:
        return WorkObjectInstance(work_object=self, display=display)

    @property
    def low(self) -> WorkObjectInstance:
        """Instance whose surface is the canonical term lowercased -- the common
        mid-sentence form (``room.low`` instead of ``room('room')``)."""
        return self(self.canonical.lower())


@dataclass(frozen=True)
class Verb(TermHandle):
    def __call__(self, display: str) -> InflectedVerb:
        return InflectedVerb(verb=self, display=display)

    @property
    def low(self) -> InflectedVerb:
        """Inflection whose surface is the canonical term lowercased -- the common
        mid-sentence form (``book.low`` instead of ``book('book')``)."""
        return self(self.canonical.lower())


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

    @property
    def low(self) -> DeferredTermInstance:
        """Instance whose surface is the canonical term lowercased -- the common
        mid-sentence form (``pg['Attachment'].low`` instead of
        ``pg['Attachment']('attachment')``)."""
        return self(self.canonical.lower())


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
    glossary: BaseGlossary,
    kind: Literal['actor', 'object', 'verb'] | None,
    name: str,
    definition: str | None,
    source: SourceLocation | None = None,
) -> GlossaryTerm:
    """Idempotent registration. Returns the canonical term (existing or new).

    `source` is the call site of the user-facing method (`g.actor` /
    `g.work_object` / `g.verb`), captured there and threaded through.
    First-registration wins: re-registration with matching (kind, canonical,
    definition) returns the existing term unchanged, preserving its original
    `source`.
    """
    new = GlossaryTerm(
        id=id_derive(name),
        kind=kind,
        canonical=name,
        definition=_normalize_definition(definition),
        source=source,
    )
    existing = glossary.get(new.id)
    if existing is not None:
        if terms_match(existing, new):
            return existing
        raise PytestGivenError(
            f'term {name!r} (id {new.id!r}) conflicts with prior registration '
            f'(existing: kind={existing.kind!r}, canonical={existing.canonical!r}, '
            f'definition={existing.definition!r}; new: kind={new.kind!r}, '
            f'canonical={new.canonical!r}, definition={new.definition!r}).'
        )
    glossary._register(new)
    return new


def deferred_handle_or_raise(
    glossary: BaseGlossary,
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


class Glossary(BaseGlossary):
    """The user-facing glossary: storage plus the registration API.

    Subclasses the report model's storage rather than being grafted onto it.
    Every method here needs the *caller's* source location, which only
    `capture` knows how to resolve — and `model`, being the leaf, may not
    import from it. Everything internal (serde, grouping, the renderers) keeps
    annotating the base, which a `Glossary` satisfies; only what a user
    constructs is this class.

    `skip=2` throughout: this method, then the user's call site.
    """

    def actor(self, name: str, definition: str | None = None) -> Actor:
        """Register (or fetch) an actor — a participant in the domain."""
        term = _register_kind(
            self, 'actor', name, definition, capture_caller_source(skip=2)
        )
        return Actor(_term=term, _glossary=self)

    def work_object(self, name: str, definition: str | None = None) -> WorkObject:
        """Register (or fetch) a work object — a thing acted on."""
        term = _register_kind(
            self, 'object', name, definition, capture_caller_source(skip=2)
        )
        return WorkObject(_term=term, _glossary=self)

    def verb(self, name: str, definition: str | None = None) -> Verb:
        """Register (or fetch) a verb — an action."""
        term = _register_kind(
            self, 'verb', name, definition, capture_caller_source(skip=2)
        )
        return Verb(_term=term, _glossary=self)

    def __call__(self, name: str, definition: str | None = None) -> DeferredTermHandle:
        """Declare-or-get a term whose kind inference will settle later."""
        term = _register_kind(
            self, None, name, definition, capture_caller_source(skip=2)
        )
        return DeferredTermHandle(_term=term, _glossary=self)

    def __getitem__(self, name: str) -> DeferredTermHandle:
        """Get-only lookup; an unknown name raises with a did-you-mean hint."""
        return deferred_handle_or_raise(self, name)
