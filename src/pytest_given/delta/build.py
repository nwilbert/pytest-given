"""Two reports built into a delta: scenarios paired, then compared."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from ..model import (
    ColumnId,
    DeltaData,
    DeltaMetadata,
    DeltaSide,
    IdentityPair,
    Narration,
    NarrationLiteral,
    NarrationPlaceholder,
    NarrationValue,
    ReportData,
    Scenario,
    ScenarioDelta,
    ScenarioPairing,
    case_id,
    case_suffix,
    narration_of,
    node_base,
)
from .chains import Rewrites, rewrite_case_id, rewrite_identities
from .identity import scenario_identity
from .narration import (
    Reading,
    Token,
    TokenBucket,
    narrations_equal,
    placeholder_name,
    same_term_id,
    token_bucket,
    token_lists_equal,
    tokens,
)
from .order import interleaved
from .renames import RenameLog
from .steps import align_steps, steps_changed
from .suggestions import suggest
from .table import align_table
from .terms import TermAlignment, align_terms


def is_per_case(scenario: Scenario) -> bool:
    return bool(case_suffix(scenario.id)) and scenario.parameters is None


def comparable_title(scenario: Scenario) -> Narration:
    """A per-case scenario's title without the case ID grouping appends to it,
    for comparing two paired scenarios, whose identities already tell it.
    Pairing by title keeps it."""
    parts = scenario.narration.parts
    if is_per_case(scenario):
        match parts[-3:]:
            case (
                NarrationLiteral(value=' ['),
                NarrationValue(rendered=rendered, expression=''),
                NarrationLiteral(value=']'),
            ) if rendered == case_id(scenario.id):
                return narration_of(parts[:-3])
    return scenario.narration


@dataclass(frozen=True, kw_only=True)
class DeltaInputs:
    before: ReportData
    after: ReportData
    renames: RenameLog = field(default_factory=RenameLog)
    skipped_revs: frozenset[str] = frozenset()
    before_label: str | None = None
    after_label: str | None = None
    plugin_version: str
    timestamp: str


@dataclass(frozen=True)
class DeltaResult:
    delta: DeltaData
    warnings: tuple[str, ...]


def build_delta(inputs: DeltaInputs) -> DeltaResult:
    before, after = inputs.before, inputs.after
    terms = align_terms(before, after, inputs.renames, inputs.skipped_revs)
    identities = _Identities(before.scenarios, after.scenarios, inputs)
    before_reading = Reading(before.glossary, terms.term_id, placeholder_name)
    after_reading = Reading(after.glossary, same_term_id, placeholder_name)
    pairing = _pair(before, after, before_reading, after_reading, identities)

    listed: list[ScenarioDelta] = []
    unchanged: list[IdentityPair] = []
    for before_index, after_index in interleaved(
        list(range(len(after.scenarios))),
        list(range(len(before.scenarios))),
        {index: partner for index, (partner, _) in pairing.items()},
    ):
        if after_index is None:
            assert before_index is not None
            listed.append(
                ScenarioDelta(change='removed', before=before.scenarios[before_index])
            )
        elif before_index is None:
            listed.append(
                ScenarioDelta(change='added', after=after.scenarios[after_index])
            )
        else:
            compared = _compare(
                before.scenarios[before_index],
                after.scenarios[after_index],
                pairing[before_index][1],
                identities,
                terms,
                inputs,
            )
            if compared is None:
                unchanged.append(
                    IdentityPair(
                        before=scenario_identity(before.scenarios[before_index]),
                        after=scenario_identity(after.scenarios[after_index]),
                    )
                )
            else:
                listed.append(compared)

    suggested = suggest(listed, terms.delta, before_reading, after_reading)
    delta = DeltaData(
        metadata=DeltaMetadata(
            before=_side(before, inputs.before_label),
            after=_side(after, inputs.after_label),
            plugin_version=inputs.plugin_version,
            timestamp=inputs.timestamp,
        ),
        scenarios=tuple(listed),
        unchanged=tuple(unchanged),
        suggestions=suggested.suggestions,
        glossary=terms.delta,
    )
    return DeltaResult(
        delta=delta,
        warnings=(
            *terms.warnings,
            *identities.rewrites.warnings,
            *suggested.warnings,
        ),
    )


def _side(report: ReportData, label: str | None) -> DeltaSide:
    return DeltaSide(
        metadata=report.metadata,
        label=label,
        modules=tuple(dict.fromkeys(scenario.module for scenario in report.scenarios)),
    )


class _Identities:
    """Each before scenario's identity once the rename log has rewritten it.

    The log names a `node_base`: a per-case scenario's tail is rewritten
    through the `cases` maps against the after cases sharing its new base."""

    def __init__(
        self, before: Sequence[Scenario], after: Sequence[Scenario], inputs: DeltaInputs
    ) -> None:
        self.rewrites: Rewrites = rewrite_identities(
            [node_base(scenario.id) for scenario in before],
            {node_base(scenario.id) for scenario in after},
            inputs.renames.of('scenario'),
            inputs.skipped_revs,
        )
        per_case_ids: dict[str, set[str]] = {}
        for scenario in after:
            if is_per_case(scenario):
                per_case_ids.setdefault(node_base(scenario.id), set()).add(
                    case_id(scenario.id)
                )
        self.rewritten = [
            self._rewritten(scenario, per_case_ids) for scenario in before
        ]

    def _rewritten(self, scenario: Scenario, per_case_ids: dict[str, set[str]]) -> str:
        base = node_base(scenario.id)
        rewrite = self.rewrites.by_identity.get(base)
        new_base = rewrite.identity if rewrite else base
        if not is_per_case(scenario):
            return new_base
        tail = rewrite_case_id(
            case_id(scenario.id),
            self.rewrites.case_maps_of(base),
            per_case_ids.get(new_base, set()),
        )
        return f'{new_base}[{tail}]'

    def case_rewrite(self, scenario: Scenario, after: Scenario) -> Callable[[str], str]:
        assert after.parameters is not None
        case_maps = self.rewrites.case_maps_of(node_base(scenario.id))
        after_ids = {case_id(case.id) for case in after.parameters.cases}
        return lambda before_id: rewrite_case_id(before_id, case_maps, after_ids)


type _Pairing = dict[int, tuple[int, ScenarioPairing]]  # before index → after index


def _pair(
    before: ReportData,
    after: ReportData,
    before_reading: Reading,
    after_reading: Reading,
    identities: _Identities,
) -> _Pairing:
    """By rewritten identity, then by a title unique on each side among the
    unpaired. One-to-one even when a malformed report repeats an identity."""
    pairing: _Pairing = {}
    unpaired_after: dict[str, list[int]] = {}
    for index, scenario in enumerate(after.scenarios):
        unpaired_after.setdefault(scenario_identity(scenario), []).append(index)
    for index, scenario in enumerate(before.scenarios):
        identity = identities.rewritten[index]
        candidates = unpaired_after.get(identity)
        if candidates:
            rewritten = identity != scenario_identity(scenario)
            pairing[index] = (
                candidates.pop(0),
                'rename-log' if rewritten else 'node-id',
            )

    # Columns pair only once their scenarios have, so a placeholder reads by name.
    # A per-case title keeps its case ID: an argname added, or grouping turned
    # on, reads as removed and added unless the rename log maps it.
    paired_after = {partner for partner, _ in pairing.values()}
    for before_index, after_index in _unique_titles(
        {
            index: tokens(scenario.narration, before_reading)
            for index, scenario in enumerate(before.scenarios)
            if index not in pairing
        },
        {
            index: tokens(scenario.narration, after_reading)
            for index, scenario in enumerate(after.scenarios)
            if index not in paired_after
        },
    ):
        pairing[before_index] = (after_index, 'title')
    return pairing


def _unique_titles(
    before: dict[int, list[Token]], after: dict[int, list[Token]]
) -> list[tuple[int, int]]:
    """The pairs whose title no other unpaired scenario on either side reads as."""
    before_buckets = _buckets(before)
    after_buckets = _buckets(after)
    pairs: list[tuple[int, int]] = []
    for before_index, read in before.items():
        bucket = token_bucket(read)
        matches = [
            index
            for index in after_buckets.get(bucket, [])
            if token_lists_equal(read, after[index])
        ]
        if len(matches) != 1:
            continue
        rivals = [
            index
            for index in before_buckets[bucket]
            if token_lists_equal(before[index], after[matches[0]])
        ]
        if rivals == [before_index]:
            pairs.append((before_index, matches[0]))
    return pairs


def _buckets(read: dict[int, list[Token]]) -> dict[TokenBucket, list[int]]:
    buckets: dict[TokenBucket, list[int]] = {}
    for index, title in read.items():
        buckets.setdefault(token_bucket(title), []).append(index)
    return buckets


def _compare(
    before: Scenario,
    after: Scenario,
    paired_by: ScenarioPairing,
    identities: _Identities,
    terms: TermAlignment,
    inputs: DeltaInputs,
) -> ScenarioDelta | None:
    """The changed scenario's delta, or `None` when nothing that counts differs."""
    parameters = None
    column_of: dict[ColumnId, ColumnId] = {}
    table_changed = (before.parameters is None) != (after.parameters is None)
    if before.parameters is not None and after.parameters is not None:
        table = align_table(
            before.parameters,
            after.parameters,
            identities.case_rewrite(before, after),
        )
        parameters, column_of = table.delta, table.column_of
        table_changed = parameters.changed

    def before_column(placeholder: NarrationPlaceholder) -> str:
        # An unpaired column's key matches no after column ID, all of which are
        # identifiers or `kind:N`.
        paired = column_of.get(placeholder.column_id)
        return paired if paired is not None else f'unpaired {placeholder.column_id}'

    before_reading = Reading(inputs.before.glossary, terms.term_id, before_column)
    after_reading = Reading(inputs.after.glossary, same_term_id, _column_id)
    title_changed = not narrations_equal(
        comparable_title(before), before_reading, comparable_title(after), after_reading
    )
    steps = align_steps(before.steps, before_reading, after.steps, after_reading)
    delta = ScenarioDelta(
        change='changed',
        before=before,
        after=after,
        paired_by=paired_by,
        title_changed=title_changed,
        steps=steps,
        parameters=parameters,
    )
    if (
        title_changed
        or steps_changed(steps)
        or delta.tags_added
        or delta.tags_removed
        or delta.status_changed
        or delta.reason_changed
        or table_changed
    ):
        return delta
    return None


def _column_id(placeholder: NarrationPlaceholder) -> str:
    return placeholder.column_id
