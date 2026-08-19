"""The five authoring forms that would make a grouped tree lie about its cases.

Each raises `PytestGivenError` rather than reporting a finding the way lint
does: a grouped tree built on any of these is false, so the run fails and no
sink is written (see `plugin.pytest_sessionfinish`). Rules 1 and 3 are checked
up front, against the whole group; 2, 4 and 5 fire from the baseline walk,
which is where the offending part is in hand.
"""

from ..capture import render_interpolation
from ..model import (
    NarrationTermRef,
    NarrationValue,
    ParamSpec,
    Phase,
    PytestGivenError,
    RawParamValue,
    Scenario,
    Step,
    StepPath,
    TermId,
    case_suffix,
    location_suffix,
    node_base,
    walk_steps,
)
from .columns import GroupContext


def check_varying_str_narration(baseline: Scenario, ctx: GroupContext) -> None:
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
            raise grouping_error(
                ctx.anchor,
                f'step narration in {_test_name(ctx.anchor)!r} varies across '
                f'parametrize cases but records no parts — a plain str bakes '
                f"case 1's values (an f-string is the usual cause). Use a "
                f't-string: {step.phase}(t"…").',
            )


def check_promotable_expression(
    part: NarrationValue, phase: Phase, ctx: GroupContext
) -> None:
    """Rule 2: a varying interpolation whose expression is not a bare name.

    Checked where the promotion happens rather than up front: a compound
    expression that renders the same in every case has nothing to promote and
    stays inline untouched. Only a value about to become a column has to be one
    the author can point a reader at — a column headed `cup_size * 0.01` names
    no local the test body binds, and its `{name}` token would read as one.
    """
    if part.expression.isidentifier():
        return
    raise grouping_error(
        ctx.anchor,
        f'{part.expression!r} in {_test_name(ctx.anchor)!r} varies across '
        f'parametrize cases — bind it to a local and narrate that: '
        f'value = {part.expression}; {phase}(t"… {{value}} …").',
    )


def check_rebound_params(
    scenario: Scenario, spec: ParamSpec, ctx: GroupContext
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
            raise grouping_error(
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


def grouping_error(anchor: Scenario, body: str) -> PytestGivenError:
    """A rejected-form error, located the way a lint finding is.

    A step-level anchor is not available: `Step.source` is captured only when
    lint is enabled, and these rules must hold with lint off.
    """
    return PytestGivenError(f'{body}{location_suffix(anchor.source)}')


def _test_name(scenario: Scenario) -> str:
    """The bare test function name, for error messages: `test_brew`."""
    return node_base(scenario.id).rpartition('::')[2]


def check_attachment_labels(step: Step, path: StepPath, ctx: GroupContext) -> None:
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
        raise grouping_error(
            ctx.anchor,
            f'attachment label {missing[0]!r} in {_test_name(ctx.anchor)!r} is '
            f'attached in some parametrize cases but not others — a label names '
            f'the payload and must read the same in every case. Use a constant '
            f'label and let the content vary: attach("<constant>", …).',
        )


def check_constant_term_ref(
    part: NarrationTermRef,
    index: int,
    path: StepPath,
    phase: Phase,
    ctx: GroupContext,
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
        raise grouping_error(
            ctx.anchor,
            f'glossary term ref {{{part.expression}}} in '
            f'{_test_name(ctx.anchor)!r} varies across parametrize '
            f'cases — a term pill must name the same term and read the '
            f'same in every case. Split the pill from the value: '
            f'{phase}(t"{{pg[\'Term\']}} {{value}} …").',
        )


def _term_at(step: Step, index: int) -> tuple[TermId, str] | None:
    """That case's `(term_id, display)` at `index`, or None when the part list
    is shaped differently there."""
    if index >= len(step.narration.parts):
        return None
    part = step.narration.parts[index]
    if not isinstance(part, NarrationTermRef):
        return None
    return part.term_id, part.display
