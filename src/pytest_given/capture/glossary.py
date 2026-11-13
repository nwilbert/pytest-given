"""User-facing Glossary API: lookup by name, term handles, registration."""

import difflib
import re
from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from functools import cache

from ..model import (
    Definition,
    GlossaryTerm,
    PytestGivenError,
    PytestGivenLookupError,
    SourceLocation,
    TermId,
    TermKind,
    avoided_word,
    id_derive,
    name_key,
    name_keys,
    s_form,
)
from ..model import (
    Glossary as BaseGlossary,
)
from .source import capture_caller_source


class LookupGlossary(BaseGlossary):
    """A glossary that reads a term back by name, as `g['Guest']`.

    Both user-facing glossaries do this, and a repeated lookup hands back the
    *same* handle.
    """

    def __post_init__(self) -> None:
        super().__post_init__()
        self._handles: dict[TermId, TermHandle] = {}

    def __getitem__(self, name: str) -> TermHandle:
        """Name-based, case-insensitive get-only lookup. Raises
        `PytestGivenLookupError` with a did-you-mean hint on an unknown name."""
        term_id = TermId(id_derive(name))
        if term_id in self._handles:
            return self._handles[term_id]
        term = self.get(term_id)
        if term is None:
            close = difflib.get_close_matches(
                name, [candidate.canonical for candidate in self.terms], n=3
            )
            hint = f' Did you mean: {", ".join(close)}?' if close else ''
            raise PytestGivenLookupError(f'no glossary term named {name!r}.{hint}')
        handle = TermHandle(_term=term, _glossary=self)
        self._handles[term_id] = handle
        return handle


class _TermDeclarations(ABC):
    """The four ways to declare a term, shared by a glossary and its sections."""

    def actor(
        self, name: str, definition: str | None = None, *, avoid: Sequence[str] = ()
    ) -> TermHandle:
        """Register an actor — a participant in the domain."""
        return self._declare('actor', name, definition, avoid)

    def work_object(
        self, name: str, definition: str | None = None, *, avoid: Sequence[str] = ()
    ) -> TermHandle:
        """Register a work object — a thing acted on."""
        return self._declare('object', name, definition, avoid)

    def activity(
        self, name: str, definition: str | None = None, *, avoid: Sequence[str] = ()
    ) -> TermHandle:
        """Register an activity — what an actor does."""
        return self._declare('activity', name, definition, avoid)

    def __call__(
        self, name: str, definition: str | None = None, *, avoid: Sequence[str] = ()
    ) -> TermHandle:
        """Register a term whose kind inference will settle later."""
        return self._declare(None, name, definition, avoid)

    @abstractmethod
    def _declare(
        self,
        kind: TermKind | None,
        name: str,
        definition: str | None,
        avoid: Sequence[str],
    ) -> TermHandle: ...


class Glossary(LookupGlossary, _TermDeclarations):
    """The user-facing glossary: the model's storage plus the registration API.

    Every registration is idempotent for an *exactly* repeated one — kind,
    canonical, definition, section and avoid entries all equal — and raises on
    anything else, a definition supplied only the first time included.
    Re-reading a term declared elsewhere is `g[name]`, which never registers.
    """

    def section(self, name: str) -> GlossarySection:
        """A group of terms declared into this glossary under the heading
        `name`. Two sections of one name declare into the same group."""
        stripped = name.strip()
        if not stripped:
            raise PytestGivenError('a glossary section needs a name.')
        return GlossarySection(_glossary=self, name=stripped)

    def _declare(
        self,
        kind: TermKind | None,
        name: str,
        definition: str | None,
        avoid: Sequence[str],
        section: str | None = None,
    ) -> TermHandle:
        term = _register_kind(
            self, kind, name, definition, section, avoid, capture_caller_source()
        )
        return TermHandle(_term=term, _glossary=self)


@dataclass(frozen=True)
class GlossarySection(_TermDeclarations):
    """Declares terms into its glossary under one section name. It has no
    lookup: `g[name]` reads a term back whatever its section."""

    _glossary: Glossary
    name: str

    def _declare(
        self,
        kind: TermKind | None,
        name: str,
        definition: str | None,
        avoid: Sequence[str],
    ) -> TermHandle:
        return self._glossary._declare(kind, name, definition, avoid, self.name)


def normalize_definition(definition: str | None) -> Definition | None:
    """A definition as declared, its refs left for `resolve_definition_refs`.
    An empty or whitespace-only one is None, so 'undefined' has exactly one
    representation."""
    if definition is None:
        return None
    stripped = definition.strip()
    return Definition.literal(stripped) if stripped else None


class TermHandleBase(ABC):
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

    # Named for brevity inside a t-string (`{guest.l.s}`), at the cost of E743's
    # l-versus-1 ambiguity.
    @property
    def l(self) -> TermInstance:  # noqa: E743
        """This reading lowercased — the common mid-sentence form
        (``guest.l`` instead of ``guest('guest')``)."""
        return self._reading(_lowercase_words(self.display))

    @property
    def s(self) -> TermInstance:
        """This reading's S-form — a plural, or a verb's third person singular
        (``room.s``, ``room.l.s``)."""
        return self._reading(s_form(self.display))

    @abstractmethod
    def _reading(self, surface: str) -> TermInstance:
        """The same term, read as `surface`."""


@dataclass(frozen=True)
class TermHandle(TermHandleBase):
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

        Whether that reads as a distinct instance or as a mere inflection is the
        *term's* business, decided from `declared_kind` where it matters — an
        actor's `Alice` is its own identity, an activity's `books` is the same term
        in another form.
        """
        return TermInstance(handle=self, surface=display)

    def _reading(self, surface: str) -> TermInstance:
        return self(surface)

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
class TermInstance(TermHandleBase):
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

    def _reading(self, surface: str) -> TermInstance:
        return self.handle(surface)


_WORD = re.compile(r'[^\W\d_]+')


def _lowercase_words(text: str) -> str:
    """Lowercase each capitalized word, leaving acronyms (``LLM``), standalone
    letters (``Plan B``) and mixed case (``iPhone``) as written. A letter before
    a hyphen starts a word (``E-Mail``), so it is lowercased."""

    def lowered(match: re.Match[str]) -> str:
        word = match[0]
        starts_hyphenated = len(word) == 1 and text[match.end() :].startswith('-')
        if word[0].isupper() and (word[1:].islower() or starts_hyphenated):
            return word.lower()
        return word

    return _WORD.sub(lowered, text)


def terms_match(existing: GlossaryTerm, candidate: GlossaryTerm) -> bool:
    """Whether two terms are the same registration: kind, canonical,
    definition, section and avoid entries agree. `source` is intentionally
    excluded."""
    return (
        existing.kind == candidate.kind
        and existing.canonical == candidate.canonical
        and existing.definition == candidate.definition
        and existing.section == candidate.section
        and existing.avoid == candidate.avoid
    )


def unique_avoid(entries: Iterable[str]) -> tuple[str, ...]:
    """The entries in order, dropping one whose avoided word repeats an
    earlier one's as names compare."""
    kept: dict[str, str] = {}
    for entry in entries:
        word = avoided_word(entry)
        if not word:
            raise PytestGivenError(f'avoid entry {entry!r} has no avoided word.')
        kept.setdefault(name_key(word), entry)
    return tuple(kept.values())


def check_avoided_words(glossary: BaseGlossary, term: GlossaryTerm) -> None:
    """Raise when an avoided word of `term` names a term of the glossary,
    `term` included, or an avoided word of a registered term names `term`.
    Two registered terms were checked against each other on registering."""
    registered = [other for other in glossary.terms if other.id != term.id]
    for entry in term.avoid:
        for named in [term, *registered]:
            if _avoided_word_keys(entry) & _name_keys(named.canonical):
                raise _avoided_word_error(entry, term, named)
    for avoiding in registered:
        for entry in avoiding.avoid:
            if _avoided_word_keys(entry) & _name_keys(term.canonical):
                raise _avoided_word_error(entry, avoiding, term)


def _avoided_word_error(
    entry: str, avoiding: GlossaryTerm, named: GlossaryTerm
) -> PytestGivenError:
    return PytestGivenError(
        f'avoided word {avoided_word(entry)!r} of term {avoiding.canonical!r} '
        f'names term {named.canonical!r}.'
    )


# Cached because every registration checks its term against all registered
# ones, so a glossary of n terms would re-derive each word's keys n times.
@cache
def _avoided_word_keys(entry: str) -> frozenset[str]:
    return _name_keys(avoided_word(entry))


@cache
def _name_keys(name: str) -> frozenset[str]:
    return frozenset(name_keys(name))


def _register_kind(
    glossary: BaseGlossary,
    kind: TermKind | None,
    name: str,
    definition: str | None,
    section: str | None,
    avoid: Sequence[str],
    source: SourceLocation | None = None,
) -> GlossaryTerm:
    """Idempotent registration. Returns the canonical term (existing or new).

    `source` is the call site of the user-facing method, captured there and
    threaded through. First-registration wins: re-registration with matching
    `terms_match` fields returns the existing term unchanged, preserving its
    original `source`.
    """
    if isinstance(avoid, str):
        raise PytestGivenError(
            f'term {name!r} takes its avoided words as a list, as avoid=[{avoid!r}].'
        )
    entries = [entry.strip() for entry in avoid]
    if not all(entries):
        raise PytestGivenError(f'term {name!r} has an empty avoid entry.')
    new = GlossaryTerm(
        id=TermId(id_derive(name)),
        kind=kind,
        canonical=name,
        definition=normalize_definition(definition),
        source=source,
        section=section,
        avoid=unique_avoid(entries),
    )
    return register_or_conflict(
        glossary,
        new,
        lambda existing: (
            f'term {name!r} (id {new.id!r}) conflicts with prior registration '
            f'(existing: kind={existing.kind!r}, canonical={existing.canonical!r}, '
            f'definition={existing.definition_text!r}, '
            f'section={existing.section!r}, avoid={existing.avoid!r}; '
            f'new: kind={new.kind!r}, canonical={new.canonical!r}, '
            f'definition={new.definition_text!r}, '
            f'section={new.section!r}, avoid={new.avoid!r}).'
        ),
    )


def register_or_conflict(
    glossary: BaseGlossary,
    term: GlossaryTerm,
    conflict_message: Callable[[GlossaryTerm], str],
) -> GlossaryTerm:
    """Register `term`, or return the equal one already there.

    First-registration wins, and `terms_match` decides what "equal" means.
    Shared by both glossaries so they agree on what counts as a
    re-registration and on which avoided words are refused; only the conflict
    message differs.
    """
    existing = glossary.get(term.id)
    if existing is not None:
        if terms_match(existing, term):
            return existing
        raise PytestGivenError(conflict_message(existing))
    check_avoided_words(glossary, term)
    glossary.register(term)
    return term
