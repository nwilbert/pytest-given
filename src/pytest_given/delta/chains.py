"""Applying the rename log: following a before identity along its entries to
the identity it has in the after report."""

from bisect import bisect_right
from collections.abc import Iterable, Mapping, Sequence
from collections.abc import Set as AbstractSet
from dataclasses import dataclass

from .renames import RenameEntry

type CaseMap = Mapping[str, str]


@dataclass(frozen=True)
class Rewrites:
    targets: dict[str, str]  # where each identity actually rewritten ends
    # Each identity's `cases` maps in order, up to its stop. One that stays put
    # still renames case IDs inside the scenario paired by the same identity.
    case_maps: dict[str, tuple[CaseMap, ...]]
    warnings: tuple[str, ...]


def rewrite_identities(
    before: Iterable[str],
    after: AbstractSet[str],
    entries: Sequence[RenameEntry],
    skipped_revs: AbstractSet[str],
) -> Rewrites:
    by_old: _ByOld = {}
    for position, entry in enumerate(
        entry for entry in entries if entry.rev not in skipped_revs
    ):
        by_old.setdefault(entry.old, []).append((position, entry))
    chains = {
        identity: _follow(identity, after, by_old) for identity in dict.fromkeys(before)
    }
    blocked, warnings = _merges(chains, after)
    targets: dict[str, str] = {}
    case_maps: dict[str, tuple[CaseMap, ...]] = {}
    for identity, chain in chains.items():
        maps = chain.unmoved_case_maps(identity)
        if identity not in blocked and chain.stop and chain.stop.identity != identity:
            targets[identity] = chain.stop.identity
            maps = tuple(chain.stop.case_maps)
        if maps:
            case_maps[identity] = maps
    return Rewrites(targets=targets, case_maps=case_maps, warnings=tuple(warnings))


def rewrite_case_id(
    case_id: str,
    case_maps: Sequence[CaseMap],
    after_case_ids: AbstractSet[str],
) -> str:
    result = case_id
    current = case_id
    for case_map in case_maps:
        current = case_map.get(current, current)
        if current in after_case_ids:
            result = current
    return result


def undo_case_merges(
    names: Sequence[str], starts: Sequence[str], ends: Sequence[str]
) -> tuple[list[str], list[str]]:
    """`ends`, the rewritten IDs of the cases `names`, with each merge the
    `cases` maps make undone, and a warning for each. Where distinct cases
    would end at one ID, each moved there stays at its start instead, which
    can make another merge, so to a fixpoint."""
    current = list(ends)
    warnings: list[str] = []
    while True:
        reached: dict[str, dict[str, None]] = {}
        for name, end in zip(names, current, strict=True):
            reached.setdefault(end, {})[name] = None
        merged = {end: list(group) for end, group in reached.items() if len(group) > 1}
        undone = [
            start if end in merged else end
            for start, end in zip(starts, current, strict=True)
        ]
        if undone == current:
            return current, warnings
        warnings += [_merge_message(group, end) for end, group in merged.items()]
        current = undone


@dataclass
class _Stop:
    identity: str
    entries: tuple[RenameEntry, ...]
    case_maps: list[CaseMap]


@dataclass
class _Chain:
    stop: _Stop | None
    stay_case_maps: tuple[CaseMap, ...]

    def unmoved_case_maps(self, start: str) -> tuple[CaseMap, ...]:
        """A chain back to its start still renamed cases on the way."""
        if self.stop is not None and self.stop.identity == start:
            return tuple(self.stop.case_maps)
        return self.stay_case_maps


def _merges(
    chains: dict[str, _Chain], after: AbstractSet[str]
) -> tuple[set[str], list[str]]:
    """The identities a merge blocks, to a fixpoint: a blocked identity present
    in after keeps it, which can make another rewrite onto it a merge too."""
    blocked: set[str] = set()
    warnings: list[str] = []
    while True:
        reached: dict[str, list[str]] = {}
        for identity, chain in chains.items():
            if identity not in blocked and chain.stop is not None:
                target: str | None = chain.stop.identity
            else:
                target = identity if identity in after else None
            if target is not None:
                reached.setdefault(target, []).append(identity)
        merged = {target: group for target, group in reached.items() if len(group) > 1}
        if not merged:
            return blocked, warnings
        for target, group in merged.items():
            blocked.update(group)
            warnings.append(_merge_warning(target, group, chains))


# The in-range entries by the identity they rename, each with its position
# in the log.
type _ByOld = dict[str, list[tuple[int, RenameEntry]]]


def _follow(start: str, after: AbstractSet[str], by_old: _ByOld) -> _Chain:
    """Along the log in its order, through each entry renaming the identity
    the chain has reached by then."""
    current = start
    recorded: list[RenameEntry] = []
    case_maps: list[CaseMap] = []
    stay_case_maps: list[CaseMap] = []
    moved = False
    stop: _Stop | None = None
    position = -1
    while True:
        renaming = by_old.get(current, [])
        found = bisect_right(renaming, position, key=lambda item: item[0])
        if found == len(renaming):
            break
        position, entry = renaming[found]
        recorded.append(entry)
        if entry.cases:
            case_maps.append(entry.cases)
        if entry.new is None:
            if not moved:
                stay_case_maps.append(entry.cases)
            if stop is not None and stop.identity == current:
                stop.case_maps.append(entry.cases)
            continue
        moved = True
        current = entry.new
        if current in after:
            stop = _Stop(current, tuple(recorded), list(case_maps))
    return _Chain(stop=stop, stay_case_maps=tuple(stay_case_maps))


def _merge_warning(
    target: str, identities: Sequence[str], chains: dict[str, _Chain]
) -> str:
    involved = {
        entry.label: None
        for identity in identities
        if (stop := chains[identity].stop) and stop.identity == target
        for entry in stop.entries
    }
    return _merge_message(identities, target, tuple(involved))


def _merge_message(
    identities: Sequence[str], target: str, entries: Sequence[str] = ()
) -> str:
    through = f' through {", ".join(entries)}' if entries else ''
    names = ', '.join(f'"{identity}"' for identity in identities)
    return (
        f'rename log: {names} would all end at "{target}"{through}, a merge it '
        f'does not model, so none is rewritten to it'
    )
