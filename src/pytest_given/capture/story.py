"""Story / Activity / Path constructors, and the glossary pin they carry."""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace

from ..model import (
    Activity,
    ActivityId,
    ActivityPart,
    ActivityPath,
    ActivityTermRef,
    ActivityWord,
    Glossary,
    PytestGivenError,
    SourceLocation,
    Story,
    StoryId,
    id_derive,
)
from .glossary import TermRef
from .kind_inference import ROLE_ACCEPTS, Slot, slot_for
from .source import capture_caller_source

# What every slot accepts structurally: a glossary reference of some sort, or a
# bare connective. Which *kind* fits a given position is `_check_position`'s.
type _PathArg = TermRef | str


@dataclass(frozen=True, kw_only=True)
class _Pinned:
    """The live `Glossary` objects a story-tree node's subtree references.

    `story()` pins them at construction so `discovery.resolve_glossary` can
    pick the suite's glossary off the story tree it was handed, rather than off
    a session-global that a nested run could clear.

    A capture-side subclass rather than a field on the schema: the report model
    neither carries this nor serializes it, and `model/` is the leaf — it may
    not reach into `capture` for the `Glossary` these actually are. Underscored
    all the same, so the reflective serializer drops it if one of these ever
    does reach serde.
    """

    _glossaries: frozenset[Glossary] = frozenset()


@dataclass(frozen=True, kw_only=True)
class _PinnedPath(ActivityPath, _Pinned):
    pass


@dataclass(frozen=True, kw_only=True)
class _PinnedActivity(Activity, _Pinned):
    pass


@dataclass(frozen=True, kw_only=True)
class _PinnedStory(Story, _Pinned):
    pass


def pinned_glossaries(node: object) -> frozenset[Glossary]:
    """The glossaries pinned on a story-tree node.

    Empty for a node that did not come from `path()` / `activity()` /
    `story()` — a deserialized report's, most of all, which carries its
    glossary as a serialized field instead.
    """
    return node._glossaries if isinstance(node, _Pinned) else frozenset()


def path(*parts: _PathArg) -> ActivityPath:
    """Build an ActivityPath as a node/edge alternation, so it maps directly
    onto a Domain Storytelling graph. Even positions (0, 2, ...) are entity
    nodes (actor / work object); odd positions (1, 3, ...) are edges — a verb
    handle or a bare-string connective. Position 0 is an actor, position 1 a
    verb — but any position also accepts a bare string (an ActivityWord that
    carries no role). The path has odd length >= 3 and ends on a node."""
    if len(parts) < 3 or len(parts) % 2 == 0:
        raise PytestGivenError(
            f'activity path must alternate node / edge / node … with an odd '
            f'length >= 3 (it must start and end on an entity node); got '
            f'{len(parts)} part(s): {parts!r}. A trailing arrow with no target '
            f'is not allowed — split multi-arrow activities into separate '
            f'path(...) calls.'
        )
    for position, part in enumerate(parts):
        if isinstance(part, str):
            continue  # a bare word carries no role; valid at any position
        _check_position(part, position, slot_for(position), parts)
    schema_parts = tuple(_to_part(part) for part in parts)
    # Pin the live Glossary objects the path references; the enclosing activity
    # and story union them upwards, which is what enforces the v1 "one glossary
    # per story" invariant at construction time.
    glossaries = frozenset(
        owner for part in parts if (owner := _glossary_of(part)) is not None
    )
    return _PinnedPath(parts=schema_parts, _glossaries=glossaries)


def _glossary_of(value: object) -> Glossary | None:
    return value.glossary if isinstance(value, TermRef) else None


def activity(
    *parts_or_paths: _PathArg | ActivityPath,
    activity_id: int | None = None,
) -> Activity:
    """Build an Activity from either positional parts (single path) or
    positional ActivityPath instances (multi-path). Mixing raises.

    `activity_id=` overrides the default sequence number (0). `story(...)`
    reassigns sequence numbers when activities are passed without explicit ids.
    """
    has_paths = any(isinstance(p, ActivityPath) for p in parts_or_paths)
    has_parts = any(not isinstance(p, ActivityPath) for p in parts_or_paths)
    if has_paths and has_parts:
        raise PytestGivenError(
            'activity(...) cannot mix ActivityPath instances with bare parts; '
            'either pass parts (for a single path) or paths (for multi-path), '
            'not both.'
        )
    if has_paths:
        paths = tuple(p for p in parts_or_paths if isinstance(p, ActivityPath))
    else:
        paths = (path(*parts_or_paths),)  # type: ignore[arg-type]
    glossaries = union_glossaries(pinned_glossaries(p) for p in paths)
    if activity_id == 0:
        raise PytestGivenError(
            'activity(activity_id=0) is reserved as the unset sentinel; '
            'use activity_id=1.. or omit to take the auto-assigned sequence '
            'number.'
        )
    return _PinnedActivity(
        id=ActivityId(activity_id if activity_id is not None else 0),
        paths=paths,
        _glossaries=glossaries,
    )


def union_glossaries(pins: Iterable[frozenset[Glossary]]) -> frozenset[Glossary]:
    """The distinct glossaries a group of pins reaches."""
    return frozenset[Glossary]().union(*pins)


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


def story(title: str, activities: Sequence[Activity] = ()) -> Story:
    """Construct a Story. Reassigns auto-numbered ids, validates uniqueness,
    and enforces v1's single-glossary invariant."""
    sid = StoryId(id_derive(title))
    source = capture_caller_source()
    _register_story(sid, title, source)
    numbered = _assign_sequence_numbers(tuple(activities))
    _check_unique_ids(numbered)
    glossaries = union_glossaries(pinned_glossaries(a) for a in numbered)
    _check_single_glossary(title, glossaries)
    return _PinnedStory(
        id=sid,
        title=title,
        activities=numbered,
        source=source,
        _glossaries=glossaries,
    )


def _assign_sequence_numbers(
    activities: tuple[Activity, ...],
) -> tuple[Activity, ...]:
    """Activities passed with id=0 (the unset sentinel) get sequential ids
    skipping any explicit ids already taken; activities with an explicit id
    keep theirs."""
    taken: set[ActivityId] = {a.id for a in activities if a.id != 0}
    out: list[Activity] = []
    next_seq = 1
    for a in activities:
        if a.id != 0:
            out.append(a)
            continue
        while ActivityId(next_seq) in taken:
            next_seq += 1
        out.append(replace(a, id=ActivityId(next_seq)))
        next_seq += 1
    return tuple(out)


def _check_unique_ids(activities: tuple[Activity, ...]) -> None:
    seen: set[ActivityId] = set()
    for a in activities:
        if a.id in seen:
            raise PytestGivenError(
                f'duplicate activity id {a.id} in story; activity ids must be unique.'
            )
        seen.add(a.id)


def _check_single_glossary(title: str, glossaries: frozenset[Glossary]) -> None:
    if len(glossaries) > 1:
        raise PytestGivenError(
            f'story {title!r} spans multiple glossaries ({len(glossaries)}); '
            f'v1 supports at most one glossary per story.'
        )


_KIND_LABEL = {'actor': 'an actor', 'object': 'a work object', 'verb': 'a verb'}

# The slot itself, phrased for the message ('must be …').
_ROLE_LABEL = {'actor': 'an actor', 'verb': 'a verb', 'noun': 'a noun'}


def _term_name(value: object) -> str:
    return value.term.canonical if isinstance(value, TermRef) else type(value).__name__


def _render_path(parts: tuple[object, ...]) -> str:
    """The offending path as names, so the message keeps its context without
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
        f'activity path position {pos} must be {_ROLE_LABEL[role]}: {problem}. '
        f'{_suggestion_for(role)} Path: {_render_path(full_parts)}.'
    )


def _suggestion_for(role: Slot) -> str:
    if role == 'actor':
        return (
            'Position 0 is the actor node — pass an actor handle '
            '(g.actor("…") / g("…")) or a bare string, not a work object or verb.'
        )
    if role == 'verb':
        return (
            'An edge takes a verb handle (g.verb("…") / g("…")) or a bare '
            'connective string, not an actor or work object.'
        )
    return (
        'A node takes an actor or work-object handle (g.work_object("…") / '
        'g("…")) or a bare string, not a verb.'
    )


def _to_part(value: _PathArg) -> ActivityPart:
    if isinstance(value, TermRef):
        return ActivityTermRef(term_id=value.id, display=value.display)
    return ActivityWord(text=value)
