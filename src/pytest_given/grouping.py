"""Grouping a parametrized test's cases into one scenario plus a case table.

The rule: the grouped step tree shows only what every case shares; anything that
varies becomes a column. See
docs/specs/proposed/2026-08-14-parametrized-case-columns-design.md.
"""

from dataclasses import dataclass, field, replace
from string import Formatter

from .capture import try_term_ref
from .lint import location_suffix
from .model import (
    Attachment,
    AttachmentRef,
    CellValue,
    ColumnKind,
    Narration,
    NarrationLiteral,
    NarrationPart,
    NarrationPlaceholder,
    NarrationTermRef,
    NarrationValue,
    NodeId,
    ParameterCase,
    ParameterColumn,
    ParameterTable,
    ParamInfo,
    ParamSpec,
    ParamValue,
    Phase,
    PytestGivenError,
    RawParamValue,
    Scenario,
    Step,
    StepAttachment,
    StepPath,
    TermId,
    case_suffix,
    node_base,
    structure_signature,
    walk_steps,
)

_FORMATTER = Formatter()


def group_parametrized(
    scenarios: list[Scenario], param_info: ParamInfo
) -> list[Scenario]:
    """Group parametrized scenarios into single scenarios with parameter tables."""
    result: list[Scenario] = []
    groups: dict[tuple[str, str], list[Scenario]] = {}
    group_order: list[tuple[str, str]] = []

    for scenario in scenarios:
        if scenario.id in param_info:
            key = (node_base(scenario.id), scenario.narration.text)
            if key not in groups:
                groups[key] = []
                group_order.append(key)
            groups[key].append(scenario)
        else:
            result.append(scenario)

    result.extend(_grouped_scenario(groups[key], param_info) for key in group_order)

    return result


def _grouped_scenario(group: list[Scenario], param_info: ParamInfo) -> Scenario:
    first = group[0]
    param_names = list(param_info[first.id].names)
    baseline = _baseline(group)
    comparable = _comparable(group, baseline)
    indexed = _indexed(comparable)
    _check_varying_str_narration(baseline, comparable, indexed, first)
    for scenario in group:
        if scenario.status == 'passed':
            _check_rebound_params(scenario, param_info[scenario.id], first)
    ctx = _GroupContext(
        param_names=param_names,
        comparable=comparable,
        indexed=indexed,
        anchor=first,
    )
    template_steps = _templatize_steps(baseline.steps, (), ctx)
    grouped_narration = _templatize_narration(first.narration, param_names)

    cases: list[ParameterCase] = []
    total_duration = 0
    for scenario in group:
        param_cells: list[CellValue | None] = [
            _param_value(v) for v in param_info[scenario.id].values
        ]
        generated = [ctx.cells[c.id].get(scenario.id) for c in ctx.columns]
        cases.append(
            ParameterCase(
                values=[*param_cells, *generated],
                status=scenario.status,
                error=scenario.error,
            )
        )
        total_duration += scenario.duration_ms

    return Scenario(
        id=first.id,
        narration=grouped_narration,
        module=first.module,
        tags=first.tags,
        status=_grouped_status(cases),
        duration_ms=total_duration,
        steps=template_steps,
        parameters=ParameterTable(
            columns=[
                *(
                    ParameterColumn(id=name, name=name, kind='param')
                    for name in param_names
                ),
                *ctx.columns,
            ],
            cases=cases,
        ),
        source=first.source,
        story_id=first.story_id,
        activity_ids=first.activity_ids,
    )


@dataclass
class _GroupContext:
    """Everything the baseline walk needs, plus the columns it accumulates."""

    param_names: list[str]
    comparable: list[Scenario]
    indexed: dict[NodeId, dict[StepPath, Step]]
    anchor: Scenario
    columns: list[ParameterColumn] = field(default_factory=list)
    cells: dict[str, dict[NodeId, CellValue | None]] = field(default_factory=dict)
    _counts: dict[ColumnKind, int] = field(default_factory=dict)
    _taken_names: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        # The parametrize columns are built inline in `_grouped_scenario`
        # rather than through `new_column`, so their names are seeded here:
        # disambiguation spans the whole table, not the generated columns
        # alone.
        self._taken_names.update(self.param_names)

    def new_column(self, kind: ColumnKind, name: str) -> str:
        """Add a column and return its id.

        Generated ids are `derived:0`, `attachment:0`, … numbered per kind in
        emission order. The colon makes collision with a parametrize name
        impossible — those are `callspec.params` keys, hence always Python
        identifiers.
        """
        index = self._counts.get(kind, 0)
        self._counts[kind] = index + 1
        column_id = f'{kind}:{index}'
        self.columns.append(
            ParameterColumn(id=column_id, name=self._unique_name(name), kind=kind)
        )
        self.cells[column_id] = {}
        return column_id

    def set_cell(
        self, column_id: str, node_id: NodeId, value: CellValue | None
    ) -> None:
        self.cells[column_id][node_id] = value

    def _unique_name(self, name: str) -> str:
        """`name`, or `name #2`, `name #3`, … once it is already taken.

        An id disambiguates two columns in the JSON, but a rendered table shows
        only the name and a Markdown badge carries no id at all — so two
        occurrences of one attachment label, or one expression promoted in two
        steps, need distinct names as well. The first stays bare: a single
        column is the overwhelmingly common case, and suffixing it would churn
        every existing report.

        The candidate is checked against the names already taken rather than
        counted per name, because a label is arbitrary text and can itself read
        like a suffix — `log`, `log #2`, `log` must still come out distinct.
        """
        candidate = name
        suffix = 1
        while candidate in self._taken_names:
            suffix += 1
            candidate = f'{name} #{suffix}'
        self._taken_names.add(candidate)
        return candidate


def _baseline(group: list[Scenario]) -> Scenario:
    """The first passed case, else `group[0]`.

    A skipped case records no steps and a failed one may abort mid-tree, so
    neither can define the shared structure. With no passed case there is
    nothing to compare, and today's `group[0]` rendering stands.
    """
    return next((s for s in group if s.status == 'passed'), group[0])


def _comparable(group: list[Scenario], baseline: Scenario) -> list[Scenario]:
    """The passed cases whose step structure matches the baseline's.

    A case that branched differently is positionally incomparable — lining a
    `when` up against a `given` would raise a rejected-form error about two
    unrelated steps. Divergence stays `divergent-case-structure`'s business;
    such a case drops out of validation exactly as it drops out of cell-filling.
    """
    signature = structure_signature(baseline.steps)
    return [
        s
        for s in group
        if s.status == 'passed' and structure_signature(s.steps) == signature
    ]


def _indexed(scenarios: list[Scenario]) -> dict[NodeId, dict[StepPath, Step]]:
    """Each case's tree keyed by position, so "the same position in every other
    case" is a lookup rather than a parallel descent through several trees."""
    return {s.id: dict(walk_steps(s.steps)) for s in scenarios}


def _check_varying_str_narration(
    baseline: Scenario,
    comparable: list[Scenario],
    indexed: dict[NodeId, dict[StepPath, Step]],
    anchor: Scenario,
) -> None:
    """Rule 1: a `str` narration whose rendered value varies across cases.

    A `str` records `parts == []` however it was built, so there is nothing to
    promote and nothing to compare — the whole narration is the baseline's. An
    f-string is the usual cause, but a helper call or a lookup looks identical
    from the recorder's side.
    """
    for path, step in walk_steps(baseline.steps):
        if step.narration.parts:
            continue
        for case in comparable:
            # A comparable case has the baseline's exact structure, so every
            # baseline path exists in it — index, never `.get`.
            if indexed[case.id][path].narration.text == step.narration.text:
                continue
            raise _grouping_error(
                anchor,
                f'step narration in {_test_name(anchor)!r} varies across '
                f'parametrize cases but records no parts — a plain str bakes '
                f"case 1's values (an f-string is the usual cause). Use a "
                f't-string: {step.phase}(t"…").',
            )


def _check_rebound_params(
    scenario: Scenario, spec: ParamSpec, anchor: Scenario
) -> None:
    """Rule 3: an expression that matches a parametrize name but not its value.

    A param match discards `rendered` and renders from the cell instead, so
    rebinding the name silently makes the report wrong for *every* case. Per
    case, re-apply the interpolation's own conversion and format spec to that
    case's **raw** parameter object and compare with what was recorded —
    exactly what the t-string did at capture time, so a faithful interpolation
    agrees for every type. Being a per-case check rather than a comparison, this
    fires where no other rule can: a single-value parametrize still catches it.
    """
    params = dict(zip(spec.names, spec.values, strict=True))
    for _path, step in walk_steps(scenario.steps):
        for part in step.narration.parts:
            if not isinstance(part, NarrationValue) or part.expression not in params:
                continue
            if _reformat(params[part.expression], part) == part.rendered:
                continue
            raise _grouping_error(
                anchor,
                f'{part.expression!r} in {_test_name(anchor)!r} matches a '
                f'parametrize column but narrates a different value '
                f'(case {case_suffix(scenario.id)} narrates {part.rendered!r}) '
                f'— rebinding a parameter name makes the narration ambiguous. '
                f'Rename the local.',
            )


def _reformat(value: RawParamValue, part: NarrationValue) -> str | None:
    """The interpolation re-applied to the raw parameter, or None when the raw
    value cannot produce that rendering at all (itself evidence of a rebinding)."""
    try:
        return format(
            _FORMATTER.convert_field(value, part.conversion), part.format_spec
        )
    except ValueError, TypeError:
        return None


def _grouping_error(anchor: Scenario, body: str) -> PytestGivenError:
    """A rejected-form error, located the way a lint finding is.

    A step-level anchor is not available: `Step.source` is captured only when
    lint is enabled, and these rules must hold with lint off.
    """
    return PytestGivenError(f'{body}{location_suffix(anchor.source)}')


def _grouped_status(cases: list[ParameterCase]) -> str:
    if any(c.status == 'failed' for c in cases):
        return 'failed'
    if all(c.status == 'skipped' for c in cases):
        return 'skipped'
    return 'passed'


def _test_name(scenario: Scenario) -> str:
    """The bare test function name, for error messages: `test_brew`."""
    return node_base(scenario.id).rpartition('::')[2]


def _param_value(value: RawParamValue) -> ParamValue:
    """Coerce a raw parametrize argument into a table cell.

    A glossary term instance unwraps to its display — the `param` column is the
    only place a case's display exists once the pill in the grouped tree reads
    the baseline's, and `str()` on the instance would store a dataclass repr of
    the whole `Glossary`. JSON primitives pass through; everything else is its
    `str()`, since a cell only ever feeds display and the JSON sink.
    """
    term_ref = try_term_ref(value)
    if term_ref is not None:
        return term_ref.display
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _templatize_steps(
    steps: list[Step], prefix: StepPath, ctx: _GroupContext
) -> list[Step]:
    """Walk the baseline tree, promoting anything that varies into a column."""
    out: list[Step] = []
    for index, step in enumerate(steps):
        path = (*prefix, index)
        out.append(
            replace(
                step,
                narration=_templatize_step_narration(step, path, ctx),
                attachments=_templatize_attachments(step, path, ctx),
                children=_templatize_steps(step.children, path, ctx),
            )
        )
    return out


def _templatize_attachments(
    step: Step, path: StepPath, ctx: _GroupContext
) -> list[StepAttachment]:
    """Baseline attachments, with any whose payload varies promoted to a column.

    Paired **by label** — rule 5 guarantees the label set is shared, making the
    key total, and position does not survive a case attaching the same labels in
    a different order. Same-label attachments pair by occurrence order.

    A non-baseline case may attach a label *more* times than the baseline does
    — rule 5 only checks the label *set*, so a differing count does not raise.
    Once the baseline's own occurrences of a label are exhausted, any further
    occurrence in another case gets a column-only promotion (baseline cell
    blank, no badge — the baseline tree has no slot for an occurrence it never
    recorded), appended right after that label's baseline occurrences so
    column ids keep following the walk.
    """
    _check_attachment_labels(step, path, ctx)
    baseline_counts: dict[str, int] = {}
    for a in step.attachments:
        baseline_counts[a.label] = baseline_counts.get(a.label, 0) + 1

    out: list[StepAttachment] = []
    seen: dict[str, int] = {}
    for attachment in step.attachments:
        assert isinstance(attachment, Attachment), 'a recorded tree holds no refs'
        occurrence = seen.get(attachment.label, 0)
        seen[attachment.label] = occurrence + 1
        out.append(_promote_occurrence(attachment, occurrence, path, ctx))
        if occurrence + 1 == baseline_counts[attachment.label]:
            _promote_extra_occurrences(
                attachment.label, baseline_counts[attachment.label], path, ctx
            )
    return out


def _check_attachment_labels(step: Step, path: StepPath, ctx: _GroupContext) -> None:
    """Rule 5: a step whose set of attachment labels differs across cases.

    A label names its payload; the payload is what varies, and the row already
    says which case it belongs to. Content and content type are exempt by
    design — varying those is what the `attachment` column is for. The
    comparison is over the *distinct* labels, so a label attached a different
    number of times does not raise.
    """
    labels = {a.label for a in step.attachments}
    for case in ctx.comparable:
        other_labels = {a.label for a in ctx.indexed[case.id][path].attachments}
        missing = sorted(labels ^ other_labels)
        if not missing:
            continue
        raise _grouping_error(
            ctx.anchor,
            f'attachment label {missing[0]!r} in {_test_name(ctx.anchor)!r} is '
            f'attached in some parametrize cases but not others — a label names '
            f'the payload and must read the same in every case. Use a constant '
            f'label and let the content vary: attach("<constant>", …).',
        )


def _promote_occurrence(
    attachment: Attachment, occurrence: int, path: StepPath, ctx: _GroupContext
) -> StepAttachment:
    """The baseline's `occurrence`-th attachment of `attachment.label`: stays
    inline when every comparable case's occurrence matches it byte for byte,
    otherwise promoted to a column with a content-less badge left in its place.
    """
    others = {
        case.id: _occurrence(ctx.indexed[case.id][path], attachment.label, occurrence)
        for case in ctx.comparable
    }
    if all(
        other is not None
        and (other.content, other.content_type)
        == (attachment.content, attachment.content_type)
        for other in others.values()
    ):
        return attachment
    column_id = ctx.new_column('attachment', attachment.label)
    for node_id, other in others.items():
        ctx.set_cell(column_id, node_id, other)
    return AttachmentRef(
        label=attachment.label,
        content_type=attachment.content_type,
        column_id=column_id,
    )


def _promote_extra_occurrences(
    label: str, baseline_count: int, path: StepPath, ctx: _GroupContext
) -> None:
    """Occurrences of `label` past the baseline's own count.

    `max_count` is the greatest number of times any comparable case (including
    the baseline) attaches `label`; each occurrence from `baseline_count` up to
    it gets a column, with every case's occurrence in its own cell and the
    baseline's left `None` — there is no baseline attachment for it, so nothing
    is appended to the grouped step's attachments.

    `max_count >= baseline_count` whenever `comparable` is non-empty, because
    the baseline is itself a member of it — it passed, and trivially matches
    its own structure signature. Without that the range could silently be
    empty and the baseline's own occurrences would go missing.

    `default=baseline_count` covers `comparable` being empty, which happens
    exactly when no case passed: such a group still has a baseline with a
    recorded tree, so this runs and a bare `max()` would raise `ValueError`.
    The default's *value* is an equivalent mutant — `baseline_count >= 1`
    always, so any default at or below it yields no columns — chosen to read
    as "nothing beyond the baseline".
    """
    max_count = max(
        (_label_count(ctx.indexed[case.id][path], label) for case in ctx.comparable),
        default=baseline_count,
    )
    for occurrence in range(baseline_count, max_count):
        column_id = ctx.new_column('attachment', label)
        for case in ctx.comparable:
            ctx.set_cell(
                column_id,
                case.id,
                _occurrence(ctx.indexed[case.id][path], label, occurrence),
            )


def _label_count(step: Step, label: str) -> int:
    """How many times `step` attaches `label`.

    Every attachment of the label counts, ref or not: an `AttachmentRef` is
    content-less but still an attachment of that label, so there is nothing to
    filter out. (These are recorded trees, which hold no refs anyway.)
    """
    return sum(1 for a in step.attachments if a.label == label)


def _occurrence(step: Step, label: str, index: int) -> Attachment | None:
    """That case's `index`-th attachment carrying `label`, or None when the case
    attached that label fewer times than `index` requires."""
    matching = [
        a for a in step.attachments if isinstance(a, Attachment) and a.label == label
    ]
    return matching[index] if index < len(matching) else None


def _templatize_step_narration(
    step: Step, path: StepPath, ctx: _GroupContext
) -> Narration:
    """The baseline step's narration with varying values promoted.

    A step with no parts is a `str` narration: rule 1 has already rejected it if
    it varies, so it passes through. Otherwise each part is compared against the
    same position in every comparable case.
    """
    narration = step.narration
    if not narration.parts:
        return narration
    out = [
        _templatize_part(part, index, path, step.phase, ctx)
        for index, part in enumerate(narration.parts)
    ]
    return Narration(text=_text_from_parts(out), parts=out)


def _text_from_parts(parts: list[NarrationPart]) -> str:
    """A grouped step's display text: the template, not the baseline's rendering."""
    out: list[str] = []
    for part in parts:
        match part:
            case NarrationLiteral(value=value):
                out.append(value)
            case NarrationValue(rendered=rendered):
                out.append(rendered)
            case NarrationPlaceholder(name=name):
                out.append('{' + name + '}')
            case NarrationTermRef(display=display):
                out.append(display)
    return ''.join(out)


def _templatize_part(
    part: NarrationPart, index: int, path: StepPath, phase: Phase, ctx: _GroupContext
) -> NarrationPart:
    match part:
        case NarrationLiteral():
            return part
        case NarrationValue(expression=expression, format_spec=fs, conversion=conv):
            if expression in ctx.param_names:
                return NarrationPlaceholder(
                    name=expression,
                    column_id=expression,
                    format_spec=fs,
                    conversion=conv,
                )
            rendered = {
                case.id: _value_at(ctx.indexed[case.id][path], index)
                for case in ctx.comparable
            }
            if all(value == part.rendered for value in rendered.values()):
                return part
            if not expression.isidentifier():
                raise _grouping_error(
                    ctx.anchor,
                    f'{expression!r} in {_test_name(ctx.anchor)!r} varies across '
                    f'parametrize cases — bind it to a local and narrate that: '
                    f'value = {expression}; {phase}(t"… {{value}} …").',
                )
            column_id = ctx.new_column('derived', expression)
            for node_id, value in rendered.items():
                ctx.set_cell(column_id, node_id, value)
            return NarrationPlaceholder(
                name=expression, column_id=column_id, format_spec=fs, conversion=conv
            )
        case NarrationPlaceholder(name=name):
            if name not in ctx.param_names:
                raise PytestGivenError(
                    f"pytest_given.Template placeholder '{{{name}}}' does not "
                    f'match any parametrize column (have: '
                    f'{sorted(ctx.param_names)}).'
                )
            return part
        case NarrationTermRef(expression=expression):
            if expression in ctx.param_names:
                # Exempt: its display varies by construction and the `param`
                # column already holds every case's value. This is what keeps
                # `param_column` alive.
                return replace(part, param_column=expression)
            identity = (part.term_id, part.display)
            for case in ctx.comparable:
                if _term_at(ctx.indexed[case.id][path], index) == identity:
                    continue
                # Rejected rather than promoted: promotion would strip the pill
                # out of the grouped tree, and `compute_coverage` matches story
                # activities on term-ref identities.
                raise _grouping_error(
                    ctx.anchor,
                    f'glossary term ref {{{expression}}} in '
                    f'{_test_name(ctx.anchor)!r} varies across parametrize '
                    f'cases — a term pill must name the same term and read the '
                    f'same in every case. Split the pill from the value: '
                    f'{phase}(t"{{pg[\'Term\']}} {{value}} …").',
                )
            return part


def _value_at(step: Step, index: int) -> str | None:
    """That case's rendering of the interpolation at `index`, or None.

    None covers a case whose part list is shaped differently under a matching
    structure — a known limitation, deferred with divergent structure itself;
    it reads as "differs", so the value is promoted. The step itself is always
    present: only comparable cases are indexed, and they share the baseline's
    structure.
    """
    if index >= len(step.narration.parts):
        return None
    part = step.narration.parts[index]
    return part.rendered if isinstance(part, NarrationValue) else None


def _term_at(step: Step, index: int) -> tuple[TermId, str] | None:
    """That case's `(term_id, display)` at `index`, or None when the part list
    is shaped differently there."""
    if index >= len(step.narration.parts):
        return None
    part = step.narration.parts[index]
    if not isinstance(part, NarrationTermRef):
        return None
    return part.term_id, part.display


def _templatize_narration(
    narration: Narration,
    param_names: list[str],
) -> Narration:
    """Convert matching NarrationValue entries to NarrationPlaceholder.

    For the **scenario** narration only — a scenario name is evaluated once at
    decoration time, so it cannot vary across cases and there is nothing to
    compare against other cases the way a step's narration is. NarrationLiteral
    parts pass through unchanged. A NarrationValue whose `expression` matches a
    parametrize column becomes a NarrationPlaceholder; otherwise it stays
    verbatim (the rendered value is shared across cases). A NarrationPlaceholder
    must reference a known parametrize column.
    """
    if not narration.parts:
        return narration
    out: list[NarrationPart] = []
    for part in narration.parts:
        match part:
            case NarrationLiteral():
                out.append(part)
            case NarrationValue(expression=expression, format_spec=fs, conversion=conv):
                if expression in param_names:
                    out.append(
                        NarrationPlaceholder(
                            name=expression,
                            column_id=expression,
                            format_spec=fs,
                            conversion=conv,
                        )
                    )
                else:
                    out.append(part)
            case NarrationPlaceholder(name=name):
                if name not in param_names:
                    raise PytestGivenError(
                        f"pytest_given.Template placeholder '{{{name}}}' does "
                        f'not match any parametrize column (have: '
                        f'{sorted(param_names)}).'
                    )
                out.append(part)
            case NarrationTermRef(expression=expression):
                if expression in param_names:
                    out.append(replace(part, param_column=expression))
                else:
                    out.append(part)
    return replace(narration, parts=out)
