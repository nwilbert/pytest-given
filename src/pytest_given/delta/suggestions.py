"""Suggested matches: a removed and an added item that look like one renamed
item. Recorded for an agent or a person to confirm into the rename log, never
applied."""

import math
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from itertools import groupby

from ..model import (
    ColumnId,
    DiffSegment,
    GlossaryDelta,
    GlossaryTerm,
    IdentityPair,
    Narration,
    NarrationPart,
    NarrationTermRef,
    NodeId,
    ParameterTable,
    Scenario,
    ScenarioDelta,
    Suggestion,
    TermId,
    TermKind,
    case_id,
    iter_steps,
    scenario_identity,
    walk_step_deltas,
)
from .narration import Reading, Token, WordKey, reading_words, word_counts
from .table import CellKey, cells_of

SUGGESTION_SIMILARITY = 0.8  # the least Dice share of words two items must have
MAX_SUGGESTION_CANDIDATES = 25  # candidates scored per removed item, rarest words first

LIMITED_WARNING = (
    'suggested matches were limited: too many removed and added scenarios or '
    'terms share words to compare every pair'
)

type _Swaps = list[tuple[TermId, TermId]]


@dataclass(frozen=True)
class Suggestions:
    suggestions: tuple[Suggestion, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class _Found[Item]:
    items: list[Item]
    limited: bool  # some candidates went unscored


def suggest(
    scenarios: Sequence[ScenarioDelta],
    glossary: GlossaryDelta,
    before_reading: Reading,
    after_reading: Reading,
) -> Suggestions:
    swaps = _unambiguous(_swapped_terms(scenarios, glossary))
    swapped_before = {before for before, _ in swaps}
    swapped_after = {after for _, after in swaps}
    by_steps = _scenario_suggestions(scenarios, before_reading, after_reading)
    by_definition = _definition_suggestions(
        glossary, before_reading, after_reading, swapped_before, swapped_after
    )
    return Suggestions(
        suggestions=(
            *by_steps.items,
            *_case_suggestions(scenarios),
            *(
                Suggestion(of='term', before=before, after=after)
                for before, after in swaps
            ),
            *by_definition.items,
        ),
        warnings=(LIMITED_WARNING,)
        if by_steps.limited or by_definition.limited
        else (),
    )


def _scenario_suggestions(
    scenarios: Sequence[ScenarioDelta], before_reading: Reading, after_reading: Reading
) -> _Found[Suggestion]:
    removed = [
        item.before
        for item in scenarios
        if item.before is not None and item.after is None
    ]
    added = [
        item.after
        for item in scenarios
        if item.after is not None and item.before is None
    ]
    matches = _mutual_best(
        [_step_words(scenario, before_reading) for scenario in removed],
        [_step_words(scenario, after_reading) for scenario in added],
    )
    return _Found(
        [
            Suggestion(
                of='scenario',
                before=scenario_identity(removed[index_before]),
                after=scenario_identity(added[index_after]),
            )
            for index_before, index_after in matches.items
        ],
        matches.limited,
    )


def _step_words(scenario: Scenario, reading: Reading) -> list[Token]:
    return [
        word
        for step in iter_steps(scenario.steps)
        for word in reading_words(step.narration, reading)
    ]


def _case_suggestions(scenarios: Sequence[ScenarioDelta]) -> list[Suggestion]:
    suggestions: list[Suggestion] = []
    for item in scenarios:
        if item.parameters is None:
            continue
        before, after = item.paired()
        assert before.parameters is not None
        assert after.parameters is not None
        param_ids = {
            column.id for column in before.parameters.columns if column.kind == 'param'
        }
        shared = [
            (column.before, column.after)
            for column in item.parameters.columns
            if column.before in param_ids and column.after is not None
        ]
        removed = [
            case.before
            for case in item.parameters.cases
            if case.before is not None and case.after is None
        ]
        added = [
            case.after
            for case in item.parameters.cases
            if case.after is not None and case.before is None
        ]
        if not shared:
            continue
        before_cells = _shared_cells(
            before.parameters, removed, [one for one, _ in shared]
        )
        after_cells = _shared_cells(
            after.parameters, added, [other for _, other in shared]
        )
        near = _near_cases(before_cells, after_cells, len(shared))
        suggestions.extend(
            Suggestion(
                of='case',
                before=case_id(removed[index_before]),
                after=case_id(added[index_after]),
                scenario=IdentityPair(
                    before=scenario_identity(before), after=scenario_identity(after)
                ),
            )
            for index_before, index_after in _unambiguous(near)
        )
    return suggestions


def _near_cases(
    before_cells: list[list[CellKey]], after_cells: list[list[CellKey]], width: int
) -> list[tuple[int, int]]:
    """The (removed, added) index pairs differing in exactly one shared column,
    found by matching on all the other columns, not by comparing every pair."""
    near: list[tuple[int, int]] = []
    for column in range(width):
        added_without: dict[tuple[CellKey, ...], list[int]] = {}
        for index_after, cells in enumerate(after_cells):
            added_without.setdefault(_without(cells, column), []).append(index_after)
        for index_before, cells in enumerate(before_cells):
            near.extend(
                (index_before, index_after)
                for index_after in added_without.get(_without(cells, column), [])
                if cells[column] != after_cells[index_after][column]
            )
    return near


def _without(cells: list[CellKey], column: int) -> tuple[CellKey, ...]:
    return (*cells[:column], *cells[column + 1 :])


def _shared_cells(
    table: ParameterTable, case_ids: list[NodeId], column_ids: list[ColumnId]
) -> list[list[CellKey]]:
    by_id = {case.id: case for case in table.cases}
    cells = [cells_of(table, by_id[node_id]) for node_id in case_ids]
    return [[case_cells[column_id] for column_id in column_ids] for case_cells in cells]


def _swapped_terms(
    scenarios: Sequence[ScenarioDelta], glossary: GlossaryDelta
) -> _Swaps:
    removed = {
        delta.before.id for delta in glossary.terms if delta.before and not delta.after
    }
    added = {
        delta.after.id for delta in glossary.terms if delta.after and not delta.before
    }
    swaps: _Swaps = []
    if not (removed and added):
        return swaps
    for item in scenarios:
        for step in walk_step_deltas(item.steps):
            if step.change == 'modified':
                swaps.extend(_replaced_refs(step.words, removed, added))
    return swaps


def _replaced_refs(
    words: Sequence[DiffSegment], removed: set[TermId], added: set[TermId]
) -> _Swaps:
    """The ref pairs of the stretches a step's word diff changed, each holding
    exactly one removed term's ref before and one added term's after."""
    swaps: _Swaps = []
    for equal, stretch in groupby(words, key=lambda segment: segment.mark == 'equal'):
        if equal:
            continue
        segments = list(stretch)
        gone = _refs_to([part for one in segments for part in one.before], removed)
        came = _refs_to([part for one in segments for part in one.after], added)
        if len(gone) == 1 and len(came) == 1:
            swaps.append((gone[0], came[0]))
    return swaps


def _refs_to(parts: list[NarrationPart], term_ids: set[TermId]) -> list[TermId]:
    return [
        part.term_id
        for part in parts
        if isinstance(part, NarrationTermRef) and part.term_id in term_ids
    ]


def _unambiguous[Before, After](
    pairs: Iterable[tuple[Before, After]],
) -> list[tuple[Before, After]]:
    """Each pair once, and only where neither side has another partner."""
    distinct = list(dict.fromkeys(pairs))
    befores = Counter(before for before, _ in distinct)
    afters = Counter(after for _, after in distinct)
    return [
        (before, after)
        for before, after in distinct
        if befores[before] == 1 and afters[after] == 1
    ]


def _definition_suggestions(
    glossary: GlossaryDelta,
    before_reading: Reading,
    after_reading: Reading,
    swapped_before: set[TermId],
    swapped_after: set[TermId],
) -> _Found[Suggestion]:
    removed: dict[TermKind | None, list[GlossaryTerm]] = {}
    added: dict[TermKind | None, list[GlossaryTerm]] = {}
    for delta in glossary.terms:
        if delta.before and not delta.after and delta.before.id not in swapped_before:
            removed.setdefault(delta.before.kind, []).append(delta.before)
        elif delta.after and not delta.before and delta.after.id not in swapped_after:
            added.setdefault(delta.after.kind, []).append(delta.after)
    suggestions: list[Suggestion] = []
    limited = False
    for kind, removed_terms in removed.items():
        before_terms = [term for term in removed_terms if term.definition]
        after_terms = [term for term in added.get(kind, []) if term.definition]
        matches = _mutual_best(
            [_definition_words(term, before_reading) for term in before_terms],
            [_definition_words(term, after_reading) for term in after_terms],
        )
        limited = limited or matches.limited
        suggestions.extend(
            Suggestion(
                of='term',
                before=before_terms[index_before].id,
                after=after_terms[index_after].id,
            )
            for index_before, index_after in matches.items
        )
    return _Found(suggestions, limited)


def _definition_words(term: GlossaryTerm, reading: Reading) -> list[Token]:
    return reading_words(Narration(text=term.definition or ''), reading)


def _mutual_best(
    before_words: list[list[Token]], after_words: list[list[Token]]
) -> _Found[tuple[int, int]]:
    """The index pairs each the other's single best match, at the suggestion
    similarity. A tie for best matches nothing.

    Similarity is the Dice share of words, order ignored. A removed item is
    scored only against the added items sharing its rarest words, at most
    `MAX_SUGGESTION_CANDIDATES` of them, so many look-alikes cost bounded work."""
    after_counts = [word_counts(words) for words in after_words]
    postings: dict[WordKey, list[int]] = {}
    for index_after, counts in enumerate(after_counts):
        for key in counts:
            postings.setdefault(key, []).append(index_after)
    scores: dict[tuple[int, int], float] = {}
    limited = False
    for index_before, words in enumerate(before_words):
        counts_before = word_counts(words)
        candidates, cut = _candidates(counts_before, postings)
        limited = limited or cut
        for index_after in candidates:
            counts_after = after_counts[index_after]
            score = (
                2
                * (counts_before & counts_after).total()
                / (counts_before.total() + counts_after.total())
            )
            if score >= SUGGESTION_SIMILARITY:
                scores[index_before, index_after] = score
    best_after = _best(scores, by_before=True)
    best_before = _best(scores, by_before=False)
    return _Found(
        [
            (index_before, index_after)
            for index_before, index_after in best_after.items()
            if best_before.get(index_after) == index_before
        ],
        limited,
    )


def _candidates(
    counts: Counter[WordKey], postings: dict[WordKey, list[int]]
) -> tuple[list[int], bool]:
    """The added items that could reach the suggestion similarity, from the
    rarest word up, and whether more than the limit could.

    Reaching it takes an overlap of `needed` words, so an item sharing none of
    the rarest `total - needed + 1` words falls short (a prefix filter)."""
    total = counts.total()
    needed = math.ceil(
        SUGGESTION_SIMILARITY * total / (2 - SUGGESTION_SIMILARITY) - 1e-9
    )
    ranked = sorted(counts, key=lambda key: (len(postings.get(key, ())), key))
    found: dict[int, None] = {}
    prefix = 0
    for key in ranked:
        if prefix > total - needed:
            break
        prefix += counts[key]
        for index in postings.get(key, ()):
            if index not in found:
                if len(found) == MAX_SUGGESTION_CANDIDATES:
                    return list(found), True
                found[index] = None
    return list(found), False


def _best(scores: dict[tuple[int, int], float], *, by_before: bool) -> dict[int, int]:
    """For each index of one side, its partner on the other side, where a single
    one scores highest."""
    candidates: dict[int, list[tuple[float, int]]] = {}
    for (index_before, index_after), score in scores.items():
        own, other = (
            (index_before, index_after) if by_before else (index_after, index_before)
        )
        candidates.setdefault(own, []).append((score, other))
    best: dict[int, int] = {}
    for own, options in candidates.items():
        top = max(score for score, _ in options)
        leaders = [other for score, other in options if score == top]
        if len(leaders) == 1:
            best[own] = leaders[0]
    return best
