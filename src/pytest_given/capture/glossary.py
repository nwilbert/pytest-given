"""User-facing Glossary API: id derivation, value classes, registration."""

import difflib
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field

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


class LookupGlossary(BaseGlossary):
    """A glossary that reads a term back by name, as `g['Guest']`.

    Both user-facing glossaries do this, and both have to hand back the *same*
    handle for a repeated lookup — so the cache that guarantees it lives here
    rather than once per subclass, where it was also the reason the lookup had
    to take it as an argument.
    """

    def __post_init__(self) -> None:
        super().__post_init__()
        self._handles: dict[TermId, TermHandle] = {}

    def __getitem__(self, name: str) -> TermHandle:
        """Name-based, case-insensitive get-only lookup. Raises
        `PytestGivenError` with a did-you-mean hint on an unknown name."""
        term_id = TermId(id_derive(name))
        if term_id in self._handles:
            return self._handles[term_id]
        term = self.get(term_id)
        if term is None:
            close = difflib.get_close_matches(
                name, [candidate.canonical for candidate in self.terms], n=3
            )
            hint = f' Did you mean: {", ".join(close)}?' if close else ''
            raise PytestGivenError(f'no glossary term named {name!r}.{hint}')
        handle = TermHandle(_term=term, _glossary=self)
        self._handles[term_id] = handle
        return handle


class Glossary(LookupGlossary):
    """The user-facing glossary: the model's storage plus the registration API.

    Every registration below is idempotent for an *exactly* repeated one — kind,
    canonical and definition all equal — and raises on anything else, a
    definition supplied only the first time included. Re-reading a term declared
    elsewhere is `g[name]`, which never registers.
    """

    def _declare(
        self, kind: TermKind | None, name: str, definition: str | None
    ) -> TermHandle:
        """Register `name` under `kind` and hand back its handle."""
        term = _register_kind(self, kind, name, definition, capture_caller_source())
        return TermHandle(_term=term, _glossary=self)

    def actor(self, name: str, definition: str | None = None) -> TermHandle:
        """Register an actor — a participant in the domain."""
        return self._declare('actor', name, definition)

    def work_object(self, name: str, definition: str | None = None) -> TermHandle:
        """Register a work object — a thing acted on."""
        return self._declare('object', name, definition)

    def verb(self, name: str, definition: str | None = None) -> TermHandle:
        """Register a verb — an action."""
        return self._declare('verb', name, definition)

    def __call__(self, name: str, definition: str | None = None) -> TermHandle:
        """Declare-or-get a term whose kind inference will settle later."""
        return self._declare(None, name, definition)


def normalize_definition(definition: str | None) -> str | None:
    """Collapse an empty or whitespace-only definition to None so 'undefined'
    has exactly one representation."""
    if definition is None:
        return None
    stripped = definition.strip()
    return stripped or None


class TermRef(ABC):
    """Something that names a glossary term and knows how it should read.

    Two shapes implement it — a bare `TermHandle` reading as its canonical
    name, and a `TermInstance` wearing a surface form — and every consumer
    outside this module goes through `id` / `display` rather than branching on
    which it got.
    """

    @property
    @abstractmethod
    def term(self) -> GlossaryTerm: ...

    @property
    @abstractmethod
    def glossary(self) -> BaseGlossary: ...

    @property
    @abstractmethod
    def display(self) -> str: ...

    @property
    def id(self) -> TermId:
        return self.term.id

    @property
    def declared_kind(self) -> TermKind | None:
        """The kind the term claims, or None until `infer_glossary_kinds`
        settles it."""
        return self.term.kind


@dataclass(frozen=True)
class TermHandle(TermRef):
    """A `GlossaryTerm` plus a back-ref to its owning `Glossary`.

    One type for every kind and every accessor: the registration methods differ
    in what they register, not in what they hand back, and the kind is read off
    the term at use time.
    """

    _term: GlossaryTerm
    # Out of the identity: a handle *is* its term, so two handles for the same
    # term compare equal across the glossaries they came from.
    _glossary: BaseGlossary = field(compare=False)

    def __call__(self, display: str) -> TermInstance:
        """This term as one call site reads it (``guest('Alice')``).

        Whether that reads as a distinct entity or as a mere inflection is the
        *term's* business, decided from `declared_kind` where it matters — an
        actor's `Alice` is its own identity, a verb's `books` is the same verb
        in another form.
        """
        return TermInstance(handle=self, surface=display)

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
    def canonical(self) -> str:
        return self._term.canonical

    @property
    def display(self) -> str:
        """A bare handle reads as its canonical name."""
        return self._term.canonical


@dataclass(frozen=True)
class TermInstance(TermRef):
    """A term wearing one surface form: the handle it came from, plus display."""

    handle: TermHandle
    # Named apart from the `display` accessor it backs, so the field does not
    # shadow the base's property.
    surface: str

    @property
    def term(self) -> GlossaryTerm:
        return self.handle.term

    @property
    def glossary(self) -> BaseGlossary:
        return self.handle.glossary

    @property
    def display(self) -> str:
        return self.surface


def terms_match(existing: GlossaryTerm, candidate: GlossaryTerm) -> bool:
    """Whether two terms are the same registration: kind, canonical and
    definition agree. `source` is intentionally excluded."""
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
        id=TermId(id_derive(name)),
        kind=kind,
        canonical=name,
        definition=normalize_definition(definition),
        source=source,
    )
    return register_or_conflict(
        glossary,
        new,
        lambda existing: (
            f'term {name!r} (id {new.id!r}) conflicts with prior registration '
            f'(existing: kind={existing.kind!r}, canonical={existing.canonical!r}, '
            f'definition={existing.definition!r}; new: kind={new.kind!r}, '
            f'canonical={new.canonical!r}, definition={new.definition!r}).'
        ),
    )


def register_or_conflict(
    glossary: BaseGlossary,
    term: GlossaryTerm,
    conflict_message: Callable[[GlossaryTerm], str],
) -> GlossaryTerm:
    """Register `term`, or return the equal one already there.

    First-registration wins, and `terms_match` decides what "equal" means. The
    identity rule already lived in one place; this puts the flow around it
    there too, so the code glossary and the file-backed one cannot drift on
    what counts as a re-registration. Only the message differs, which is what
    the callback is for.
    """
    existing = glossary.get(term.id)
    if existing is not None:
        if terms_match(existing, term):
            return existing
        raise PytestGivenError(conflict_message(existing))
    glossary.register(term)
    return term
