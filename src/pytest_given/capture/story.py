"""Story / Activity / Path constructors."""

from __future__ import annotations

import sys
from collections.abc import Sequence

from ..model import (
    Activity,
    ActivityId,
    ActivityPart,
    ActivityPath,
    ActivityTermRef,
    ActivityWord,
    Glossary,
    PytestGivenError,
    Story,
    StoryId,
    id_derive,
)
from .glossary import (
    Actor,
    ActorInstance,
    DeferredTermHandle,
    DeferredTermInstance,
    InflectedVerb,
    Verb,
    WorkObject,
    WorkObjectInstance,
)
from .source import capture_caller_source

# Capture the built-in id() before it can be shadowed by local parameters.
_obj_id = id

type _PathArg = (
    Actor
    | WorkObject
    | Verb
    | ActorInstance
    | WorkObjectInstance
    | InflectedVerb
    | DeferredTermHandle
    | DeferredTermInstance
    | str
)

# Even positions are graph nodes (entities); odd positions are edges (a verb
# arrow or a bare-string connective). A DeferredTermHandle/Instance has no eager
# kind, so it is structurally valid at either kind of position and resolved by
# kind inference + _slot_for later.
_ACTOR_TYPES = (Actor, ActorInstance, DeferredTermHandle, DeferredTermInstance)
_VERB_TYPES = (Verb, InflectedVerb, DeferredTermHandle, DeferredTermInstance)
_NODE_TYPES = (
    Actor,
    ActorInstance,
    WorkObject,
    WorkObjectInstance,
    DeferredTermHandle,
    DeferredTermInstance,
)


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
        if position == 0:
            _check_position(part, 0, 'actor', _ACTOR_TYPES, parts)
        elif position % 2 == 1:
            _check_position(part, position, 'verb', _VERB_TYPES, parts)
        else:
            _check_position(part, position, 'noun', _NODE_TYPES, parts)
    schema_parts = tuple(_to_part(part) for part in parts)
    # Stash the set of Glossary object-identities the path references — read
    # by activity() and _check_single_glossary to enforce the v1 "one glossary
    # per story" invariant at construction time. Not serialized.
    glossary_ids: frozenset[int] = frozenset(
        _obj_id(owner)
        for owner in (_glossary_of(part) for part in parts)
        if owner is not None
    )
    path_obj = ActivityPath(parts=schema_parts)
    object.__setattr__(path_obj, '_glossary_ids', glossary_ids)
    return path_obj


def _glossary_of(value: object) -> Glossary | None:
    match value:
        case Actor() | WorkObject() | Verb():
            return value.glossary
        case ActorInstance(actor=h):
            return h.glossary
        case WorkObjectInstance(work_object=h):
            return h.glossary
        case InflectedVerb(verb=h):
            return h.glossary
        case DeferredTermHandle():
            return value.glossary
        case DeferredTermInstance(handle=handle):
            return handle.glossary
    return None


def activity(
    *parts_or_paths: _PathArg | ActivityPath,
    id: int | None = None,
) -> Activity:
    """Build an Activity from either positional parts (single path) or
    positional ActivityPath instances (multi-path). Mixing raises.

    `id=` overrides the default sequence number (0). `story(...)` reassigns
    sequence numbers when activities are passed without explicit ids.
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
    glossary_ids: frozenset[int] = frozenset().union(
        *(getattr(p, '_glossary_ids', frozenset()) for p in paths)
    )
    if id == 0:
        raise PytestGivenError(
            'activity(id=0) is reserved as the unset sentinel; '
            'use id=1.. or omit to take the auto-assigned sequence number.'
        )
    a = Activity(id=ActivityId(id if id is not None else 0), paths=paths)
    object.__setattr__(a, '_glossary_ids', glossary_ids)
    return a


_STORY_REGISTRY: dict[StoryId, str] = {}


def clear_story_registry() -> None:
    _STORY_REGISTRY.clear()


def _register_story(sid: StoryId, title: str) -> None:
    frame = sys._getframe(2)
    site = f'{frame.f_code.co_filename}:{frame.f_lineno}'
    if sid in _STORY_REGISTRY:
        raise PytestGivenError(
            f'story {title!r} (id {sid!r}) already declared at '
            f'{_STORY_REGISTRY[sid]}; declaring it again at {site}.'
        )
    _STORY_REGISTRY[sid] = site


def story(title: str, activities: Sequence[Activity] = ()) -> Story:
    """Construct a Story. Reassigns auto-numbered ids, validates uniqueness,
    and enforces v1's single-glossary invariant."""
    sid = StoryId(id_derive(title))
    _register_story(sid, title)
    source = capture_caller_source(skip=2)
    numbered = _assign_sequence_numbers(tuple(activities))
    _check_unique_ids(numbered)
    _check_single_glossary(title, numbered)
    return Story(id=sid, title=title, activities=numbered, source=source)


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
        new = Activity(id=ActivityId(next_seq), paths=a.paths)
        object.__setattr__(
            new, '_glossary_ids', getattr(a, '_glossary_ids', frozenset())
        )
        out.append(new)
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


def _check_single_glossary(title: str, activities: tuple[Activity, ...]) -> None:
    glossary_ids: frozenset[int] = frozenset().union(
        *(getattr(a, '_glossary_ids', frozenset()) for a in activities)
    )
    if len(glossary_ids) > 1:
        raise PytestGivenError(
            f'story {title!r} spans multiple glossaries ({len(glossary_ids)}); '
            f'v1 supports at most one glossary per story.'
        )


def _check_position(
    value: object,
    pos: int,
    role: str,
    accepted: tuple[type, ...],
    full_parts: tuple[object, ...],
) -> None:
    if isinstance(value, accepted):
        return
    raise PytestGivenError(
        f'activity path position {pos} must be a glossary {role} handle or a '
        f'bare string; got {type(value).__name__}: {value!r}. '
        f'{_suggestion_for(role)} Full parts: {full_parts!r}'
    )


def _suggestion_for(role: str) -> str:
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
    match value:
        case Actor() | WorkObject() | Verb():
            return ActivityTermRef(term_id=value.id, display=value.canonical)
        case ActorInstance(actor=actor, display=display):
            return ActivityTermRef(term_id=actor.id, display=display)
        case WorkObjectInstance(work_object=wo, display=display):
            return ActivityTermRef(term_id=wo.id, display=display)
        case InflectedVerb(verb=verb, display=display):
            return ActivityTermRef(term_id=verb.id, display=display)
        case DeferredTermHandle():
            return ActivityTermRef(term_id=value.id, display=value.canonical)
        case DeferredTermInstance(handle=handle, display=display):
            return ActivityTermRef(term_id=handle.id, display=display)
        case str():
            return ActivityWord(text=value)
