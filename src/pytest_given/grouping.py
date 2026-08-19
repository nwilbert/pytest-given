"""Grouping a parametrized test's cases into one scenario plus a case table.

The rule: the grouped step tree shows only what every case shares; anything that
varies becomes a column. See
docs/specs/2026-08-14-parametrized-case-columns-design.md.
"""

from dataclasses import dataclass, field, replace

from .capture import render_interpolation, try_term_ref
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
    location_suffix,
    node_base,
    placeholder_mismatch,
    structure_signature,
    walk_steps,
)


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
    ctx = _GroupContext(
        param_names=param_names,
        comparable=comparable,
        indexed=indexed,
        anchor=first,
    )
    _check_varying_str_narration(baseline, ctx)
    for scenario in group:
        if scenario.status == 'passed':
            _check_rebound_params(scenario, param_info[scenario.id], ctx)
    # Before the walk, not with the other cells below: a `param` cell is what
    # its placeholder substitutes, so the walk compares against it.
    formats = _param_cell_formats(baseline.steps, param_names)
    for scenario in group:
        spec = param_info[scenario.id]
        for name, value in zip(spec.names, spec.values, strict=True):
            ctx.set_cell(name, scenario.id, _param_cell(value, formats.get(name)))
    template_steps = _templatize_steps(baseline.steps, (), ctx)
    grouped_narration = _templatize_narration(first.narration, param_names)

    cases: list[ParameterCase] = []
    total_duration = 0
    comparable_ids = {s.id for s in comparable}
    for scenario in group:
        cases.append(
            ParameterCase(
                values=[ctx.cells[c.id].get(scenario.id) for c in ctx.columns],
                status=scenario.status,
                error=scenario.error,
                divergent=(
                    scenario.status == 'passed' and scenario.id not in comparable_ids
                ),
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
        parameters=ParameterTable(columns=ctx.columns, cases=cases),
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
        # The parametrize columns come first and keep their argname as id: a
        # step's placeholder points at them by name (`column_id=expression`),
        # and every generated column is emitted after them by the baseline
        # walk. Creating them here rather than in the caller keeps one column
        # list, one cell store, and one name registry — disambiguation spans
        # the whole table, not the generated columns alone.
        for name in self.param_names:
            self.new_column('param', name)

    def new_column(self, kind: ColumnKind, name: str) -> ParameterColumn:
        """Add a column and return it.

        A `param` column is identified by its argname; generated ids are
        `derived:0`, `attachment:0`, … numbered per kind in emission order. The
        colon makes collision with an argname impossible — those are
        `callspec.params` keys, hence always Python identifiers. The whole
        column comes back rather than its id alone because the caller also
        builds the step tree's pointer at it, which has to carry the
        disambiguated `name` (see `_unique_name`).
        """
        if kind == 'param':
            column_id = name
        else:
            index = self._counts.get(kind, 0)
            self._counts[kind] = index + 1
            column_id = f'{kind}:{index}'
        column = ParameterColumn(id=column_id, name=self._unique_name(name), kind=kind)
        self.columns.append(column)
        self.cells[column_id] = {}
        return column

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
    """The first passed case; failing that, the first case that recorded a
    tree; failing that, `group[0]`.

    A skipped case records no steps and a failed one may abort mid-tree, so
    neither can define the shared structure — with no passed case there is
    nothing to compare and the grouped tree is one case's rendering either way.
    Which one still matters: a skipped case has *no* steps, so preferring it
    over a failed one renders the scenario step-less and hides the failure a
    reader opened it for.
    """
    passed = next((s for s in group if s.status == 'passed'), None)
    if passed is not None:
        return passed
    return next((s for s in group if s.steps), group[0])


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


def _check_varying_str_narration(baseline: Scenario, ctx: _GroupContext) -> None:
    """Rule 1: a `str` narration whose rendered value varies across cases.

    A `str` records `parts == []` however it was built, so there is nothing to
    promote and nothing to compare — the whole narration is the baseline's. An
    f-string is the usual cause, but a helper call or a lookup looks identical
    from the recorder's side.
    """
    for path, step in walk_steps(baseline.steps):
        if step.narration.parts:
            continue
        for case in ctx.comparable:
            # A comparable case has the baseline's exact structure, so every
            # baseline path exists in it — index, never `.get`.
            if ctx.indexed[case.id][path].narration.text == step.narration.text:
                continue
            raise _grouping_error(
                ctx.anchor,
                f'step narration in {_test_name(ctx.anchor)!r} varies across '
                f'parametrize cases but records no parts — a plain str bakes '
                f"case 1's values (an f-string is the usual cause). Use a "
                f't-string: {step.phase}(t"…").',
            )


def _check_rebound_params(
    scenario: Scenario, spec: ParamSpec, ctx: _GroupContext
) -> None:
    """Rule 3: an expression that matches a parametrize name but not its value.

    A param match discards `rendered` and renders from the cell instead, so a
    step narrating anything else silently makes the report wrong for *every*
    case. Per case, re-apply the interpolation's own conversion and format spec
    to that case's **raw** parameter object and compare with what was recorded
    — exactly what the t-string did at capture time, so a faithful
    interpolation agrees for every type. Being a per-case check rather than a
    comparison, this fires where no other rule can: a single-value parametrize
    still catches it.

    What a mismatch proves is that the cell and the step disagree, not *why*.
    A local rebinding the name is one cause; a body mutating the value in place
    before narrating it is the other, since the cell holds the value as it
    stood at fixture setup (see `_capture_param_spec`). The message offers both
    remedies rather than asserting a cause it cannot tell apart.
    """
    params = dict(zip(spec.names, spec.values, strict=True))
    for _path, step in walk_steps(scenario.steps):
        for part in step.narration.parts:
            if not isinstance(part, NarrationValue) or part.expression not in params:
                continue
            try:
                reformatted = _reformat(params[part.expression], part)
            except Exception:  # noqa: BLE001 — see _reformat's contract
                # A value whose own `__format__`/`__str__` raises something
                # other than the two errors below is broken, not evidence of a
                # rebinding, and rule 3 cannot tell the difference. Skipping is
                # the only safe reading: raising would abort every sink in the
                # session, and letting it through would escape
                # `pytest_sessionfinish` as a bare traceback.
                continue
            if reformatted == part.rendered:
                continue
            raise _grouping_error(
                ctx.anchor,
                f'{part.expression!r} in {_test_name(ctx.anchor)!r} matches a '
                f'parametrize column but narrates a value that column does not '
                f'hold (case {case_suffix(scenario.id)} narrates '
                f'{part.rendered!r}) — the cell and the step would disagree, '
                f'and row hover substitutes the cell into the slot the step '
                f'rendered. Either a local rebinds the parametrize name, in '
                f'which case rename the local; or the body mutates the value '
                f'in place before narrating it, in which case bind the result '
                f'to its own name and narrate that.',
            )


def _reformat(value: RawParamValue, part: NarrationValue) -> str | None:
    """The interpolation re-applied to the raw parameter, or None when the raw
    value cannot produce that rendering at all (itself evidence of a
    rebinding). Any *other* exception belongs to the value itself and is left
    to the caller, which skips the check rather than reading it as evidence."""
    try:
        return render_interpolation(value, part.conversion, part.format_spec)
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


type _Format = tuple[str | None, str]


def _param_cell_formats(
    steps: list[Step], param_names: list[str]
) -> dict[str, _Format]:
    """The formatting each `param` column's cells are rendered with, for the
    columns whose placeholders agree on one.

    A cell is not decoration: row hover substitutes it into the slot the step
    rendered, so it has to *be* what that slot showed. `t"at {when:%H:%M}"`
    narrates `14:30` while `str(when)` is `2026-08-19 14:30:00`, and splicing
    the latter in builds a sentence no case ever narrated. Rule 3 has already
    established that the narration is the raw value rendered through the
    interpolation's own conversion and spec, so re-applying that spec to the
    cell reproduces the narrated text exactly.

    Only a formatting every placeholder for that column shares is used. Two
    steps formatting one parameter differently (`{when:%H:%M}` and
    `{when:%Y-%m-%d}`) leave no single text a shared cell could hold; the
    column keeps its plain value and the walk gives each disagreeing slot a
    column of its own (see `_templatize_param_value`). The trivial formatting
    counts as one of the two, so a column read plainly in one step and
    formatted in another goes the same way.
    """
    seen: dict[str, set[_Format]] = {}
    for _path, step in walk_steps(steps):
        for part in step.narration.parts:
            if isinstance(part, NarrationValue) and part.expression in param_names:
                seen.setdefault(part.expression, set()).add(
                    (part.conversion, part.format_spec)
                )
    return {
        name: next(iter(formats))
        for name, formats in seen.items()
        if len(formats) == 1 and formats != {(None, '')}
    }


def _param_cell(value: RawParamValue, fmt: _Format | None) -> ParamValue:
    """One `param` cell: the value rendered the way its placeholders render it,
    or `_param_value`'s plain coercion when they carry no formatting of their
    own or the value refuses this one.

    The unformatted path stays `_param_value` rather than `format(value, '')` —
    a glossary term instance has to unwrap to its display, and every cell that
    exists today keeps its current type and text.
    """
    if fmt is None:
        return _param_value(value)
    try:
        return render_interpolation(value, *fmt)
    except Exception:  # noqa: BLE001 — a value whose own rendering raises
        # The step cannot have narrated it either, so there is nothing to
        # agree with; the plain coercion is the honest fallback.
        return _param_value(value)


def _cell_text(cell: CellValue | None) -> str:
    """A cell as the renderers print it — what hover substitutes into a slot."""
    assert not isinstance(cell, Attachment), 'a param column holds no attachment'
    return str(cell)


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
    baseline = _by_label(step)
    others = {case.id: _by_label(ctx.indexed[case.id][path]) for case in ctx.comparable}

    out: list[StepAttachment] = []
    seen: dict[str, int] = {}
    for attachment in step.attachments:
        assert isinstance(attachment, Attachment), 'a recorded tree holds no refs'
        occurrence = seen.get(attachment.label, 0)
        seen[attachment.label] = occurrence + 1
        out.append(_promote_occurrence(attachment, occurrence, others, ctx))
        if occurrence == len(baseline[attachment.label]) - 1:
            _promote_extra_occurrences(attachment.label, baseline, others, ctx)
    return out


def _by_label(step: Step) -> dict[str, list[Attachment]]:
    """That step's attachments grouped by label, in the order it recorded them.

    The one shape everything below reads: a count is a `len`, an occurrence is
    an index, and a label the case never attached is a missing key. (A recorded
    tree holds no `AttachmentRef`s, so nothing here is content-less.)
    """
    out: dict[str, list[Attachment]] = {}
    for attachment in step.attachments:
        assert isinstance(attachment, Attachment), 'a recorded tree holds no refs'
        out.setdefault(attachment.label, []).append(attachment)
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
    attachment: Attachment,
    occurrence: int,
    others: dict[NodeId, dict[str, list[Attachment]]],
    ctx: _GroupContext,
) -> StepAttachment:
    """The baseline's `occurrence`-th attachment of `attachment.label`: stays
    inline when every comparable case's occurrence matches it byte for byte,
    otherwise promoted to a column with a content-less badge left in its place.
    """
    theirs = {
        node_id: _occurrence(by_label, attachment.label, occurrence)
        for node_id, by_label in others.items()
    }
    if all(
        other is not None
        and (other.content, other.content_type)
        == (attachment.content, attachment.content_type)
        for other in theirs.values()
    ):
        return attachment
    column = ctx.new_column('attachment', attachment.label)
    for node_id, other in theirs.items():
        ctx.set_cell(column.id, node_id, other)
    # The badge is labelled with the *column* name, not the attachment's own
    # label: a label attached twice gives two columns, and a badge repeating
    # the bare label points the reader at the wrong one.
    return AttachmentRef(
        label=column.name,
        content_type=attachment.content_type,
        column_id=column.id,
    )


def _promote_extra_occurrences(
    label: str,
    baseline: dict[str, list[Attachment]],
    others: dict[NodeId, dict[str, list[Attachment]]],
    ctx: _GroupContext,
) -> None:
    """Occurrences of `label` past the baseline's own count.

    Every case's occurrences of `label` past the baseline's last one get a
    column each, with every case's occurrence in its own cell and the
    baseline's left `None` — there is no baseline attachment for it, so nothing
    is appended to the grouped step's attachments.

    The count comes from `baseline`, never from `others[first case]`: the
    baseline is the first *passed* case, so a skipped first case would put the
    range at 0 and re-promote occurrences the baseline already carries a badge
    for. The baseline is itself one of `others` — it passed, and trivially
    matches its own structure signature — so `max` never falls below its own
    count. With no passed case at all `others` is empty and there is nothing
    past a baseline nobody can be compared to.
    """
    for occurrence in range(len(baseline.get(label, [])), _max_count(label, others)):
        column = ctx.new_column('attachment', label)
        for node_id, by_label in others.items():
            ctx.set_cell(column.id, node_id, _occurrence(by_label, label, occurrence))


def _max_count(label: str, others: dict[NodeId, dict[str, list[Attachment]]]) -> int:
    """The greatest number of times any comparable case attaches `label`."""
    return max(
        (len(by_label.get(label, [])) for by_label in others.values()), default=0
    )


def _occurrence(
    by_label: dict[str, list[Attachment]], label: str, index: int
) -> Attachment | None:
    """That case's `index`-th attachment carrying `label`, or None when the case
    attached that label fewer times than `index` requires."""
    matching = by_label.get(label, [])
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
    independent = _case_independent_part(part, ctx.param_names)
    if independent is not None:
        if isinstance(part, NarrationValue) and isinstance(
            independent, NarrationPlaceholder
        ):
            return _templatize_param_value(part, independent, index, path, ctx)
        return independent
    if isinstance(part, NarrationValue):
        return _templatize_value(part, index, path, phase, ctx)
    assert isinstance(part, NarrationTermRef), (
        'a literal or placeholder is case-independent by definition'
    )
    _check_constant_term_ref(part, index, path, phase, ctx)
    return part


def _templatize_param_value(
    part: NarrationValue,
    placeholder: NarrationPlaceholder,
    index: int,
    path: StepPath,
    ctx: _GroupContext,
) -> NarrationPart:
    """A slot bound to a `param` column: it keeps pointing there when the cell
    reads the way this slot rendered, and gets a column of its own when it does
    not.

    `_param_cell_formats` already gave the column the one formatting its
    placeholders agree on, so this is a no-op for every slot in the ordinary
    case. It earns its keep where they disagree — two steps formatting one
    parameter differently — which no shared cell can serve: the odd slot is
    promoted like any other varying value, and the ` #2` suffix keeps its token
    pointing at the column that actually holds its text.
    """
    rendered = {
        case.id: _value_at(ctx.indexed[case.id][path], index) for case in ctx.comparable
    }
    if all(
        text == _cell_text(ctx.cells[part.expression][case_id])
        for case_id, text in rendered.items()
    ):
        return placeholder
    column = ctx.new_column('derived', part.expression)
    for case_id, text in rendered.items():
        ctx.set_cell(column.id, case_id, text)
    return NarrationPlaceholder(
        name=column.name,
        column_id=column.id,
        format_spec=part.format_spec,
        conversion=part.conversion,
    )


def _templatize_value(
    part: NarrationValue, index: int, path: StepPath, phase: Phase, ctx: _GroupContext
) -> NarrationPart:
    """An interpolation no parametrize column binds: kept as it is when every
    case renders it the same, promoted to a `derived` column when they do not."""
    if all(
        _value_at(ctx.indexed[case.id][path], index) == part.rendered
        for case in ctx.comparable
    ):
        # Checked before the cells are collected: nothing varies in the
        # overwhelming majority of parts, and only a promotion needs every
        # case's rendering kept.
        return part
    if not part.expression.isidentifier():
        raise _grouping_error(
            ctx.anchor,
            f'{part.expression!r} in {_test_name(ctx.anchor)!r} varies across '
            f'parametrize cases — bind it to a local and narrate that: '
            f'value = {part.expression}; {phase}(t"… {{value}} …").',
        )
    column = ctx.new_column('derived', part.expression)
    for case in ctx.comparable:
        ctx.set_cell(column.id, case.id, _value_at(ctx.indexed[case.id][path], index))
    # The token names the *column*, not the expression: one expression promoted
    # in two steps gives two columns, and `{price}` in both tokens points the
    # reader at the first one twice.
    return NarrationPlaceholder(
        name=column.name,
        column_id=column.id,
        format_spec=part.format_spec,
        conversion=part.conversion,
    )


def _check_constant_term_ref(
    part: NarrationTermRef,
    index: int,
    path: StepPath,
    phase: Phase,
    ctx: _GroupContext,
) -> None:
    """Rule 4: a pill no parametrize column binds must read the same in every
    case.

    Rejected rather than promoted: promotion would strip the pill out of the
    grouped tree, and `compute_coverage` matches story activities on term-ref
    identities.
    """
    identity = (part.term_id, part.display)
    for case in ctx.comparable:
        if _term_at(ctx.indexed[case.id][path], index) == identity:
            continue
        raise _grouping_error(
            ctx.anchor,
            f'glossary term ref {{{part.expression}}} in '
            f'{_test_name(ctx.anchor)!r} varies across parametrize '
            f'cases — a term pill must name the same term and read the '
            f'same in every case. Split the pill from the value: '
            f'{phase}(t"{{pg[\'Term\']}} {{value}} …").',
        )


def _case_independent_part(
    part: NarrationPart, param_names: list[str]
) -> NarrationPart | None:
    """The part as it stands when no other case has a say in it, or None when
    it has to be compared against them first.

    A literal is one by definition, and so is anything a parametrize column
    binds — the column already holds every case's value. That makes this the
    whole of templatizing a *scenario* name, which is evaluated once at
    decoration time and cannot vary; a step's narration reaches its own
    comparison work only past it. One definition, so the placeholder contract
    (`name` and `column_id` both the parametrize name) and the term-ref
    exemption cannot drift between the two callers.
    """
    match part:
        case NarrationLiteral():
            return part
        case NarrationValue(expression=expression, format_spec=fs, conversion=conv):
            if expression not in param_names:
                return None
            return NarrationPlaceholder(
                name=expression,
                column_id=expression,
                format_spec=fs,
                conversion=conv,
            )
        case NarrationPlaceholder(name=name):
            if name not in param_names:
                raise placeholder_mismatch(name, param_names)
            return part
        case NarrationTermRef(expression=expression) if expression in param_names:
            # Exempt: its display varies by construction and the `param` column
            # already holds every case's value. This is what keeps
            # `param_column` alive.
            return replace(part, param_column=expression)
    return None


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
    compare against other cases the way a step's narration is. That makes it
    exactly `_param_bound_part` and nothing else: a part no parametrize column
    binds stays verbatim, since its rendering is shared across cases.
    """
    if not narration.parts:
        return narration
    out = [
        _case_independent_part(part, param_names) or part for part in narration.parts
    ]
    return replace(narration, parts=out)
