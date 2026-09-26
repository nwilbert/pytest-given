"""Story / Sentence / Clause constructors, the glossaries they carry, and the
sentence handles a story hands out."""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

from ..model import (
    Clause,
    ClausePart,
    ClauseTermRef,
    ClauseWord,
    Glossary,
    Pin,
    PytestGivenError,
    Sentence,
    SentenceId,
    SentenceName,
    SourceLocation,
    StoryId,
    id_derive,
)
from ..model import Story as BaseStory
from .glossary import TermRef
from .kind_inference import ROLE_ACCEPTS, Slot, slot_for
from .source import capture_caller_source

# What every slot accepts structurally: a glossary reference of some sort, or a
# bare connective. Which *kind* fits a given position is `_check_position`'s.
type _ClauseArg = TermRef | str


@dataclass(frozen=True, kw_only=True)
class _GlossaryCarrier:
    """The live `Glossary` objects a story-tree node's subtree references.

    `clause()` / `sentence()` / `story()` carry them at construction so
    `discovery.resolve_glossary` can pick the suite's glossary off the story
    tree it was handed, rather than off a session-global that a nested run
    could clear.

    A capture-side mixin rather than a field on the schema: the report model
    neither carries this nor serializes it, and `model/` is the leaf — it may
    not reach into `capture` for the `Glossary` these actually are. Underscored
    all the same, so the reflective serializer drops it if one of these ever
    does reach serde.
    """

    _glossaries: frozenset[Glossary] = frozenset()


@dataclass(frozen=True, kw_only=True)
class _CarrierClause(Clause, _GlossaryCarrier):
    pass


@dataclass(frozen=True, kw_only=True)
class UnnumberedSentence(_GlossaryCarrier):
    """What `sentence()` builds: a sentence before `story()` gives it its
    number. Not a model `Sentence` — it has no id until `story()` assigns
    one by position."""

    clauses: tuple[Clause, ...]
    name: SentenceName | None = None


@dataclass(frozen=True, kw_only=True)
class Story(BaseStory, _GlossaryCarrier):
    """The story `story()` returns: the model's storage plus sentence lookup,
    as the capture `Glossary` adds term lookup to the model's."""

    def __getitem__(self, key: int | str) -> SentenceHandle:
        """`story['name']` or `story[3]`; a number is the 1-based sentence
        number, never a list index, so 0, negatives and bools miss."""
        found = _find_sentence(self.sentences, key)
        if found is None:
            if self.sentences:
                listing = ', '.join(
                    f'{one.id} {one.name!r}' if one.name is not None else str(one.id)
                    for one in self.sentences
                )
                detail = f'its sentences are {listing}.'
            else:
                detail = 'it has no sentences.'
            raise PytestGivenError(
                f'story {self.title!r} has no sentence {key!r}; {detail}'
            )
        return SentenceHandle(
            pin=Pin(story_id=self.id, sentence_id=found.id), story=self
        )


def _find_sentence(sentences: tuple[Sentence, ...], key: int | str) -> Sentence | None:
    if isinstance(key, str):
        return next((one for one in sentences if one.name == key), None)
    if (
        isinstance(key, int)
        and not isinstance(key, bool)
        and 1 <= key <= len(sentences)
    ):
        return sentences[key - 1]
    return None


@dataclass(frozen=True)
class SentenceHandle:
    """A sentence as its story hands it out. Carries the live story so
    `@scenario` can register a story it reaches only through a pin."""

    pin: Pin
    story: Story = field(repr=False, compare=False)


# What `pins=` accepts, on a step and on `@scenario` alike.
type Pins = SentenceHandle | Sequence[SentenceHandle]


def sentence_handles(pins: Pins | None) -> tuple[SentenceHandle, ...]:
    """`pins=` as the handles it names. A bare number or name is refused: it
    would need a story to resolve against, which a pin carries itself."""
    if pins is None:
        return ()
    items = (pins,) if isinstance(pins, SentenceHandle) else pins
    if (
        isinstance(items, Sequence)
        and not isinstance(items, str)
        and all(isinstance(item, SentenceHandle) for item in items)
    ):
        return tuple(items)
    raise PytestGivenError(
        f'pins= takes sentence handles, got {pins!r}. Look the sentence up on '
        f"its story: pins=the_story['name'] or pins=the_story[3]."
    )


def carried_glossaries(node: object) -> frozenset[Glossary]:
    """The glossaries carried on a story-tree node.

    Empty for a node that did not come from `clause()` / `sentence()` /
    `story()` — a deserialized report's, most of all, which carries its
    glossary as a serialized field instead.
    """
    return node._glossaries if isinstance(node, _GlossaryCarrier) else frozenset()


def clause(*parts: _ClauseArg) -> Clause:
    """Build a Clause as a node/edge alternation, so it maps directly
    onto a Domain Storytelling graph. Even positions (0, 2, ...) are entity
    nodes (actor / work object); odd positions (1, 3, ...) are edges — an
    activity handle or a bare-string connective. Position 0 is an actor,
    position 1 an activity — but any position also accepts a bare string (a
    ClauseWord that carries no role). The clause has odd length >= 3 and ends
    on a node."""
    if len(parts) < 3 or len(parts) % 2 == 0:
        raise PytestGivenError(
            f'clause must alternate node / edge / node … with an odd '
            f'length >= 3 (it must start and end on an entity node); got '
            f'{len(parts)} part(s): {parts!r}. A trailing arrow with no target '
            f'is not allowed — split multi-arrow sentences into separate '
            f'clause(...) calls.'
        )
    for position, part in enumerate(parts):
        if isinstance(part, str):
            continue  # a bare word carries no role; valid at any position
        _check_position(part, position, slot_for(position), parts)
    schema_parts = tuple(_to_part(part) for part in parts)
    # Carry the live Glossary objects the clause references; the enclosing
    # sentence and story union them upwards, which is what enforces the v1
    # "one glossary per story" invariant at construction time.
    glossaries = frozenset(
        owner for part in parts if (owner := _glossary_of(part)) is not None
    )
    return _CarrierClause(parts=schema_parts, _glossaries=glossaries)


def _glossary_of(value: object) -> Glossary | None:
    return value.glossary if isinstance(value, TermRef) else None


def sentence(
    *parts_or_clauses: _ClauseArg | Clause,
    name: str | None = None,
) -> UnnumberedSentence:
    """Build an UnnumberedSentence from either positional parts (single
    clause) or positional Clause instances (multi-clause). Mixing raises.

    Its number is its position, which `story()` assigns.
    """
    has_clauses = any(isinstance(p, Clause) for p in parts_or_clauses)
    has_parts = any(not isinstance(p, Clause) for p in parts_or_clauses)
    if has_clauses and has_parts:
        raise PytestGivenError(
            'sentence(...) cannot mix Clause instances with bare parts; '
            'either pass parts (for a single clause) or clauses (for multi-clause), '
            'not both.'
        )
    if has_clauses:
        clauses = tuple(p for p in parts_or_clauses if isinstance(p, Clause))
    else:
        clauses = (clause(*parts_or_clauses),)  # type: ignore[arg-type]
    glossaries = union_glossaries(carried_glossaries(one) for one in clauses)
    if name is not None and (
        not isinstance(name, str) or not name or name != name.strip()
    ):
        raise PytestGivenError(
            f'a sentence name must be a non-empty str, with no leading or '
            f'trailing whitespace; got {name!r}.'
        )
    return UnnumberedSentence(
        clauses=clauses,
        name=SentenceName(name) if name is not None else None,
        _glossaries=glossaries,
    )


def union_glossaries(carried: Iterable[frozenset[Glossary]]) -> frozenset[Glossary]:
    """The distinct glossaries a group of carriers reaches."""
    return frozenset[Glossary]().union(*carried)


# Which story ids this process has seen declared, and where. Process-global,
# so `process_state` — its only sanctioned caller — swaps it around a nested
# in-process run.
_STORY_REGISTRY: dict[StoryId, str] = {}


def snapshot_story_registry() -> dict[StoryId, str]:
    return dict(_STORY_REGISTRY)


def restore_story_registry(snapshot: dict[StoryId, str]) -> None:
    """Reinstate a snapshot; `{}` clears the registry for a fresh session."""
    _STORY_REGISTRY.clear()
    _STORY_REGISTRY.update(snapshot)


def _register_story(sid: StoryId, title: str, source: SourceLocation | None) -> None:
    """Claim `sid`, or refuse a second claim on it.

    Takes the source `story()` already captured rather than walking the same
    frame again: a raw `co_filename` would put an absolute, unfolded path in
    the message.
    """
    site = _site_text(source)
    if sid in _STORY_REGISTRY:
        raise PytestGivenError(
            f'story {title!r} (id {sid!r}) already declared at '
            f'{_STORY_REGISTRY[sid]}; declaring it again at {site}.'
        )
    _STORY_REGISTRY[sid] = site


def _site_text(source: SourceLocation | None) -> str:
    """The declaration site a collision message names; None outside rootdir."""
    if source is None:
        return 'an unknown location'
    return f'{source.relpath}:{source.line}'


def story(title: str, sentences: Sequence[UnnumberedSentence] = ()) -> Story:
    """Construct a Story: numbers its sentences by position, and enforces
    unique sentence names and v1's single-glossary invariant."""
    sid = StoryId(id_derive(title))
    source = capture_caller_source()
    _register_story(sid, title, source)
    numbered = tuple(
        Sentence(id=SentenceId(position), clauses=one.clauses, name=one.name)
        for position, one in enumerate(sentences, start=1)
    )
    _check_unique_names(title, numbered)
    glossaries = union_glossaries(one._glossaries for one in sentences)
    _check_single_glossary(title, glossaries)
    return Story(
        id=sid, title=title, sentences=numbered, source=source, _glossaries=glossaries
    )


def _check_unique_names(title: str, sentences: tuple[Sentence, ...]) -> None:
    first_with: dict[SentenceName, SentenceId] = {}
    for one in sentences:
        if one.name is None:
            continue
        if one.name in first_with:
            raise PytestGivenError(
                f'story {title!r} names two sentences {one.name!r} (sentences '
                f'{first_with[one.name]} and {one.id}); a sentence name must be '
                f'unique within its story.'
            )
        first_with[one.name] = one.id


def _check_single_glossary(title: str, glossaries: frozenset[Glossary]) -> None:
    if len(glossaries) > 1:
        raise PytestGivenError(
            f'story {title!r} spans multiple glossaries ({len(glossaries)}); '
            f'v1 supports at most one glossary per story.'
        )


_KIND_LABEL = {
    'actor': 'an actor',
    'object': 'a work object',
    'activity': 'an activity',
}

# The slot itself, phrased for the message ('must be …').
_ROLE_LABEL = {'actor': 'an actor', 'verb': 'a verb', 'noun': 'a noun'}


def _term_name(value: object) -> str:
    return value.term.canonical if isinstance(value, TermRef) else type(value).__name__


def _render_clause(parts: tuple[object, ...]) -> str:
    """The offending clause as names, so the message keeps its context without
    dumping handle reprs (each of which embeds the whole Glossary)."""
    return ' → '.join(
        part if isinstance(part, str) else _term_name(part) for part in parts
    )


def _check_position(
    value: object,
    pos: int,
    role: Slot,
    full_parts: tuple[object, ...],
) -> None:
    """Reject a part whose kind cannot fill this slot.

    A declared kind — eager handle or `kind_column` row — is verified here, at
    construction; only a genuinely undeclared one is deferred to
    `infer_glossary_kinds`.
    """
    declared = value.declared_kind if isinstance(value, TermRef) else None
    if declared is not None:
        if declared in ROLE_ACCEPTS[role]:
            return
        problem = f'{_term_name(value)!r} is declared {_KIND_LABEL[declared]}'
    elif isinstance(value, TermRef):
        return
    else:
        problem = f'got {type(value).__name__}'
    raise PytestGivenError(
        f'clause position {pos} must be {_ROLE_LABEL[role]}: {problem}. '
        f'{_suggestion_for(role)} Clause: {_render_clause(full_parts)}.'
    )


def _suggestion_for(role: Slot) -> str:
    if role == 'actor':
        return (
            'Position 0 is the actor node — pass an actor handle '
            '(g.actor("…") / g("…")) or a bare string, not a work object or activity.'
        )
    if role == 'verb':
        return (
            'An edge takes an activity handle (g.activity("…") / g("…")) or a bare '
            'connective string, not an actor or work object.'
        )
    return (
        'A node takes an actor or work-object handle (g.work_object("…") / '
        'g("…")) or a bare string, not an activity.'
    )


def _to_part(value: _ClauseArg) -> ClausePart:
    if isinstance(value, TermRef):
        return ClauseTermRef(term_id=value.id, display=value.display)
    return ClauseWord(text=value)
