"""User-facing Glossary API: id derivation, value classes, registration."""

import difflib
from dataclasses import dataclass

from ..model import (
    Glossary as BaseGlossary,
)
from ..model import (
    GlossaryTerm,
    PytestGivenError,
    SourceLocation,
    TermId,
    TermKind,
    id_derive,
)
from .source import capture_caller_source


def normalize_definition(definition: str | None) -> str | None:
    """Collapse an empty or whitespace-only definition to None so 'undefined'
    has exactly one representation."""
    if definition is None:
        return None
    stripped = definition.strip()
    return stripped or None


@dataclass(frozen=True)
class TermHandle:
    """A `GlossaryTerm` plus a back-ref to its owning `Glossary`.

    The whole behavior of a handle lives here: calling one names a surface form
    for the term, and `declared_kind` reads whatever kind the registration
    settled on. One type for all three kinds — `g.actor(...)`, `g.work_object(...)`
    and `g.verb(...)` differ in what they register, not in what they hand back,
    and the kind is read off the term at use time.
    """

    _term: GlossaryTerm
    _glossary: BaseGlossary

    def __call__(self, display: str) -> TermInstance:
        """This term as one call site reads it (``guest('Alice')``).

        Whether that reads as a distinct entity or as a mere inflection is the
        *term's* business, decided from `declared_kind` where it matters (see
        `report.coverage.identity_of_part`) — an actor's `Alice` is its own
        identity, a verb's `books` is the same verb in another form.
        """
        return TermInstance(handle=self, display=display)

    @property
    def low(self) -> TermInstance:
        """The canonical term lowercased — the common mid-sentence form
        (``guest.low`` instead of ``guest('guest')``)."""
        return self(self.canonical.lower())

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

    @property
    def declared_kind(self) -> TermKind | None:
        """The kind the term claims, or None while it is still deferred.

        One reading for every flavor: an eager handle's kind was written into
        the term by `_register_kind`, and a deferred one carries whatever the
        glossary declared — `None` until `infer_glossary_kinds` settles it.
        """
        return self._term.kind


@dataclass(frozen=True)
class TermInstance:
    """A term wearing one surface form: the handle it came from, plus display.

    One type for every kind. The three it replaces (`ActorInstance`,
    `WorkObjectInstance`, `InflectedVerb`) differed only in the name of this
    field, which bought nothing — every consumer had to enumerate all three,
    and the identity rule they were supposed to encode is read off the term's
    kind at use time regardless.
    """

    handle: TermHandle
    display: str

    @property
    def term(self) -> GlossaryTerm:
        return self.handle.term

    @property
    def glossary(self) -> BaseGlossary:
        return self.handle.glossary

    @property
    def declared_kind(self) -> TermKind | None:
        return self.handle.declared_kind


@dataclass(frozen=True)
class DeferredTermHandle(TermHandle):
    """A term whose kind is settled post-collection — a file-glossary row with
    no kind column, or a code-glossary `g(...)` / `g[...]` lookup."""


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


def _register_kind(
    glossary: BaseGlossary,
    kind: TermKind | None,
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
        definition=normalize_definition(definition),
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

    def actor(self, name: str, definition: str | None = None) -> TermHandle:
        """Register (or fetch) an actor — a participant in the domain."""
        term = _register_kind(
            self, 'actor', name, definition, capture_caller_source(skip=2)
        )
        return TermHandle(_term=term, _glossary=self)

    def work_object(self, name: str, definition: str | None = None) -> TermHandle:
        """Register (or fetch) a work object — a thing acted on."""
        term = _register_kind(
            self, 'object', name, definition, capture_caller_source(skip=2)
        )
        return TermHandle(_term=term, _glossary=self)

    def verb(self, name: str, definition: str | None = None) -> TermHandle:
        """Register (or fetch) a verb — an action."""
        term = _register_kind(
            self, 'verb', name, definition, capture_caller_source(skip=2)
        )
        return TermHandle(_term=term, _glossary=self)

    def __call__(self, name: str, definition: str | None = None) -> DeferredTermHandle:
        """Declare-or-get a term whose kind inference will settle later."""
        term = _register_kind(
            self, None, name, definition, capture_caller_source(skip=2)
        )
        return DeferredTermHandle(_term=term, _glossary=self)

    def __getitem__(self, name: str) -> DeferredTermHandle:
        """Get-only lookup; an unknown name raises with a did-you-mean hint."""
        return deferred_handle_or_raise(self, name)
