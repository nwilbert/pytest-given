"""Story / Activity / Path constructors."""

from __future__ import annotations

import sys
from collections.abc import Sequence

from ..model import (
    Activity,
    ActivityId,
    ActivityPart,
    ActivityPath,
    ActivityPlaceholder,
    ActivityTermRef,
    ActivityWord,
    Glossary,
    PytestGivenError,
    Story,
    StoryId,
    id_derive,
)
from .draft import DraftActor, DraftVerb, DraftWorkObject
from .file_glossary import FileTermHandle, FileTermInstance
from .glossary import (
    Actor,
    ActorInstance,
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
    | DraftActor
    | DraftWorkObject
    | DraftVerb
    | FileTermHandle
    | FileTermInstance
    | str
)

_ACTOR_TYPES = (Actor, ActorInstance, DraftActor, FileTermHandle, FileTermInstance)
_VERB_TYPES = (Verb, InflectedVerb, DraftVerb, FileTermHandle, FileTermInstance)
_NOUN_TYPES = (
    Actor,
    ActorInstance,
    WorkObject,
    WorkObjectInstance,
    DraftActor,
    DraftWorkObject,
    FileTermHandle,
    FileTermInstance,
)


def path(*parts: _PathArg) -> ActivityPath:
    """Build an ActivityPath. Enforces the DS sentence grammar on the leading
    triple: actor → verb → noun. Beyond position 2, free-form."""
    if len(parts) < 3:
        raise PytestGivenError(
            f'activity path is incomplete: needs at least actor → verb → noun, '
            f'got {len(parts)} part(s): {parts!r}.'
        )
    _check_position(parts[0], 0, 'actor', _ACTOR_TYPES, parts)
    _check_position(parts[1], 1, 'verb', _VERB_TYPES, parts)
    _check_position(parts[2], 2, 'noun', _NOUN_TYPES, parts)
    schema_parts = tuple(_to_part(p) for p in parts)
    # Stash the set of Glossary object-identities the path references — read
    # by activity() and _check_single_glossary to enforce the v1 "one glossary
    # per story" invariant at construction time. Not serialized.
    glossary_ids: frozenset[int] = frozenset(
        _obj_id(g) for g in (_glossary_of(p) for p in parts) if g is not None
    )
    p_obj = ActivityPath(parts=schema_parts)
    object.__setattr__(p_obj, '_glossary_ids', glossary_ids)
    return p_obj


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
        case FileTermHandle():
            return value.glossary
        case FileTermInstance(handle=handle):
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
    suggestion = _suggestion_for(pos, value)
    raise PytestGivenError(
        f'activity path position {pos} must be an anchored {role}; '
        f'got {type(value).__name__}: {value!r}. {suggestion} '
        f'Full parts: {full_parts!r}'
    )


def _suggestion_for(pos: int, value: object) -> str:
    if pos == 0:
        return 'Rephrase in active voice — start with the actor doing the action.'
    if pos == 1:
        return (
            'Position 1 must be the verb; give the activity an action '
            '(e.g., g.verb("submits") or draft.verb("submits")).'
        )
    if isinstance(value, str):
        return (
            'Wrap the noun: use g.work_object("...") for committed '
            'vocabulary, or draft.work_object("...") for an unsettled draft.'
        )
    return 'Position 2 must be a noun (actor or work object), not a verb.'


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
        case FileTermHandle():
            return ActivityTermRef(term_id=value.id, display=value.canonical)
        case FileTermInstance(handle=handle, display=display):
            return ActivityTermRef(term_id=handle.id, display=display)
        case DraftActor() | DraftWorkObject() | DraftVerb():
            return ActivityPlaceholder(kind=value.kind, text=value.text)
        case str():
            return ActivityWord(text=value)
