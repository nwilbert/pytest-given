"""Applying the rename log: following a before identity along its entries to
the identity it has in the after report."""

from collections.abc import Iterable, Sequence
from collections.abc import Set as AbstractSet
from dataclasses import dataclass

from .renames import RenameEntry

type CaseMap = tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class Rewrite:
    identity: str  # where the before identity ends
    entries: tuple[RenameEntry, ...]  # the chain followed, up to the stop
    case_maps: tuple[CaseMap, ...]  # the `cases` maps up to the stop, in order


@dataclass(frozen=True)
class Rewrites:
    by_identity: dict[str, Rewrite]  # only identities actually rewritten
    warnings: tuple[str, ...]
    # The `cases` maps of identities that stay put: they still rename case IDs
    # inside the scenario paired by the same identity.
    unmoved_case_maps: dict[str, tuple[CaseMap, ...]]

    def case_maps_of(self, identity: str) -> tuple[CaseMap, ...]:
        rewrite = self.by_identity.get(identity)
        if rewrite is not None:
            return rewrite.case_maps
        return self.unmoved_case_maps.get(identity, ())


def rewrite_identities(
    before: Iterable[str],
    after: AbstractSet[str],
    entries: Sequence[RenameEntry],
    skipped_revs: AbstractSet[str],
) -> Rewrites:
    in_range = [entry for entry in entries if entry.rev not in skipped_revs]
    chains = {
        identity: _follow(identity, after, in_range)
        for identity in dict.fromkeys(before)
    }
    blocked, warnings = _merges(chains, after)
    by_identity = {
        identity: Rewrite(
            identity=chain.stop.identity,
            entries=chain.stop.entries,
            case_maps=tuple(chain.stop.case_maps),
        )
        for identity, chain in chains.items()
        if identity not in blocked and chain.stop and chain.stop.identity != identity
    }
    unmoved_case_maps = {
        identity: maps
        for identity, chain in chains.items()
        if identity not in by_identity and (maps := chain.unmoved_case_maps(identity))
    }
    return Rewrites(
        by_identity=by_identity,
        warnings=tuple(warnings),
        unmoved_case_maps=unmoved_case_maps,
    )


def rewrite_case_id(
    case_id: str,
    case_maps: Sequence[Sequence[tuple[str, str]]],
    after_case_ids: AbstractSet[str],
) -> str:
    result = case_id
    current = case_id
    for case_map in case_maps:
        current = dict(case_map).get(current, current)
        if current in after_case_ids:
            result = current
    return result


@dataclass
class _Stop:
    identity: str
    entries: tuple[RenameEntry, ...]
    case_maps: list[CaseMap]


@dataclass
class _Chain:
    stop: _Stop | None
    stay_case_maps: tuple[CaseMap, ...]

    def target(self, start: str, after: AbstractSet[str]) -> str | None:
        if self.stop is not None:
            return self.stop.identity
        return start if start in after else None

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
            if identity in blocked:
                target = identity if identity in after else None
            else:
                target = chain.target(identity, after)
            if target is not None:
                reached.setdefault(target, []).append(identity)
        merged = {target: group for target, group in reached.items() if len(group) > 1}
        if not merged:
            return blocked, warnings
        for target, group in merged.items():
            blocked.update(group)
            warnings.append(_merge_warning(target, group, chains))


def _follow(
    start: str, after: AbstractSet[str], entries: Sequence[RenameEntry]
) -> _Chain:
    current = start
    recorded: list[RenameEntry] = []
    case_maps: list[CaseMap] = []
    stay_case_maps: list[CaseMap] = []
    moved = False
    stop: _Stop | None = None
    for entry in entries:
        if entry.old != current:
            continue
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
    entries = f' through {", ".join(involved)}' if involved else ''
    names = ', '.join(f'"{identity}"' for identity in identities)
    return (
        f'rename log: {names} would all end at "{target}"{entries}, a merge it '
        f'does not model, so none is rewritten to it'
    )
