"""Story / Activity / Path constructors."""

from collections.abc import Iterable, Sequence

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
    # Stash the live Glossary objects the path references; the enclosing
    # activity and story merge them upwards, which is what enforces the v1 "one
    # glossary per story" invariant at construction time. Keyed by id(), which
    # dedups by identity (Glossary is unhashable) while keeping the object.
    glossaries: dict[int, Glossary] = {
        id(owner): owner
        for owner in (_glossary_of(part) for part in parts)
        if owner is not None
    }
    return ActivityPath(parts=schema_parts, _glossaries=glossaries)


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
    glossaries = merge_glossaries(p._glossaries for p in paths)
    if activity_id == 0:
        raise PytestGivenError(
            'activity(activity_id=0) is reserved as the unset sentinel; '
            'use activity_id=1.. or omit to take the auto-assigned sequence '
            'number.'
        )
    return Activity(
        id=ActivityId(activity_id if activity_id is not None else 0),
        paths=paths,
        _glossaries=glossaries,
    )


def merge_glossaries(
    stashes: Iterable[dict[int, Glossary]],
) -> dict[int, Glossary]:
    """Union the id→Glossary stashes of several paths/activities, deduping by
    object identity."""
    merged: dict[int, Glossary] = {}
    for stash in stashes:
        merged.update(stash)
    return merged


_STORY_REGISTRY: dict[StoryId, str] = {}


def clear_story_registry() -> None:
    _STORY_REGISTRY.clear()


def snapshot_story_registry() -> dict[StoryId, str]:
    """A copy of the registry, to hand back to `restore_story_registry`."""
    return dict(_STORY_REGISTRY)


def restore_story_registry(snapshot: dict[StoryId, str]) -> None:
    """Reinstate a snapshot taken with `snapshot_story_registry`."""
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
    source = capture_caller_source(skip=2)
    _register_story(sid, title, source)
    numbered = _assign_sequence_numbers(tuple(activities))
    _check_unique_ids(numbered)
    glossaries = merge_glossaries(a._glossaries for a in numbered)
    _check_single_glossary(title, glossaries)
    return Story(
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
        out.append(
            Activity(id=ActivityId(next_seq), paths=a.paths, _glossaries=a._glossaries)
        )
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


def _check_single_glossary(title: str, glossaries: dict[int, Glossary]) -> None:
    if len(glossaries) > 1:
        raise PytestGivenError(
            f'story {title!r} spans multiple glossaries ({len(glossaries)}); '
            f'v1 supports at most one glossary per story.'
        )


_KIND_LABEL = {'actor': 'an actor', 'object': 'a work object', 'verb': 'a verb'}

# The slot itself, phrased for the message ('must be …').
_ROLE_LABEL = {'actor': 'an actor', 'verb': 'a verb', 'noun': 'a noun'}


def _term_name(value: object) -> str:
    """The canonical term name behind a term ref, for error text."""
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
