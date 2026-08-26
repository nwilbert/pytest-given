"""The six authoring forms that would make a grouped tree lie about its cases.

Each raises `PytestGivenError` rather than reporting a finding the way lint
does: a grouped tree built on any of these is false, so the run fails and no
sink is written (see `plugin.pytest_sessionfinish`). Rules 1, 3 and 6 are
checked up front, against the whole group; 2, 4 and 5 fire from the baseline
walk, which is where the offending part is in hand.
"""

from collections.abc import Iterator
from typing import NamedTuple, assert_never

from ..model import (
    Narration,
    NarrationLiteral,
    NarrationPart,
    NarrationPlaceholder,
    NarrationTermRef,
    NarrationValue,
    ParamSpec,
    Phase,
    PytestGivenError,
    RawParamValue,
    Scenario,
    Step,
    StepPath,
    case_suffix,
    location_suffix,
    node_base,
    render_interpolation,
    structure_signature,
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


def check_same_template(baseline: Scenario, ctx: GroupContext) -> None:
    """Rule 6: every comparable case must narrate the baseline's template.

    A column carries what varies *within* a sentence — a parameter, a derived
    value, an attachment payload. A case that narrates a different sentence, or
    a different tree of them, has nothing a column can hold: the grouped view
    would show one case's words for all of them. Four shapes reach that state
    (a different step structure, a differently shaped narration under a
    matching one, different wording, a different interpolated expression) and
    all four have the same answer, so they share a rule and a fix.

    Runs first, against the very tree `templatize_steps` goes on to walk: the
    other rules index `ctx.indexed[case.id][path]` without a `.get`, and the
    shape asserts in `_value_at` and `check_constant_term_ref` read the part
    there as the baseline's kind. Both hold because this ran and raised
    otherwise. A non-passed case is exempt — a skipped one records no steps and
    a failed one may abort mid-tree — which is exactly `ctx.comparable`.
    """
    signature = structure_signature(baseline.steps)
    # Walked and keyed once per group: every case is compared against the same
    # baseline, and rebuilding its keys per case is the bulk of this rule's work.
    baseline_steps = list(walk_steps(baseline.steps))
    baseline_keys = [
        [_part_key(part) for part in step.narration.parts]
        for _path, step in baseline_steps
    ]
    for case in ctx.comparable:
        if case.id == baseline.id:
            continue
        if structure_signature(case.steps) != signature:
            raise _divergence_error(baseline, case, 'a different step structure', ctx)
        for (path, step), keys in zip(baseline_steps, baseline_keys, strict=True):
            difference = _narration_difference(
                keys, ctx.indexed[case.id][path].narration
            )
            if difference is not None:
                raise _divergence_error(
                    baseline, case, f'{difference} in its {step.phase} step', ctx
                )


def _narration_difference(baseline: list[PartKey], case: Narration) -> str | None:
    """How the case's narration differs from the baseline's keys as a template,
    or None when they agree.

    A `str` narration contributes no parts on either side, so this stays silent
    on it and rule 1 keeps its own better diagnosis.
    """
    case_keys = [_part_key(part) for part in case.parts]
    if [key.kind for key in baseline] != [key.kind for key in case_keys]:
        return 'a differently shaped narration'
    for baseline_key, case_key in zip(baseline, case_keys, strict=True):
        if baseline_key == case_key:
            continue
        if baseline_key.kind == 'literal':
            return f'different wording ({baseline_key.label!r} vs {case_key.label!r})'
        return f'a different expression ({baseline_key.label!r} vs {case_key.label!r})'
    return None


class PartKey(NamedTuple):
    """What a part contributes to its narration's template: its kind, the text
    a divergence message names it by, and the rendering details that must match
    without being worth naming."""

    kind: str
    label: str
    detail: tuple[str, ...] = ()


def _part_key(part: NarrationPart) -> PartKey:
    """A part reduced to its template.

    Never `rendered`, which is exactly what grouping promotes into a column,
    and never a term ref's `display`, which rule 4 governs: no term ref may
    vary across cases, and rule 4 names that as the authoring error it is
    where a template divergence would only report that two cases disagree.
    """
    match part:
        case NarrationLiteral(value=value):
            return PartKey('literal', value)
        case NarrationValue(expression=e, conversion=c, format_spec=f):
            return PartKey('value', e, (c or '', f))
        case NarrationPlaceholder(name=n, conversion=c, format_spec=f):
            return PartKey('placeholder', n, (c or '', f))
        case NarrationTermRef(expression=expression):
            return PartKey('term', expression)
        case _:
            assert_never(part)


def _divergence_error(
    baseline: Scenario, case: Scenario, difference: str, ctx: GroupContext
) -> PytestGivenError:
    return grouping_error(
        ctx.anchor,
        f'case {case_suffix(case.id)} of {_test_name(ctx.anchor)!r} narrates '
        f'{difference} than case {case_suffix(baseline.id)} — a grouped '
        f'scenario renders one tree for every row, so the cases cannot be '
        f'merged honestly. Use @scenario(..., group_parametrized=False) to '
        f'emit one scenario per case.',
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
    params = spec.mapping()
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
    """Rule 4: a term ref must name the same term and read the same in every case.

    No exemption for one a parametrize column binds. Rejected rather than
    promoted, because promotion would strip the term ref out of the grouped tree
    and `compute_coverage` matches story activities on term-ref identities — and
    a grouped tree keeps a single `term_id` and a single display, so a varying
    ref would leave every case's value filed under the first case's, in the
    Glossary view and in story coverage alike.
    """
    identity = (part.term_id, part.display)
    for case_part in _case_term_refs(index, path, ctx):
        if (case_part.term_id, case_part.display) == identity:
            continue
        raise grouping_error(
            ctx.anchor,
            f'glossary term ref {{{part.expression}}} in '
            f'{_test_name(ctx.anchor)!r} varies across parametrize '
            f'cases — a term ref must name the same term and read the '
            f'same in every case. Split the term ref from the value: '
            f'{phase}(t"{{pg[\'Term\']}} {{value}} …"), or use @scenario(..., '
            f'group_parametrized=False) to emit one scenario per case.',
        )


def _case_term_refs(
    index: int, path: StepPath, ctx: GroupContext
) -> Iterator[NarrationTermRef]:
    """The part at the baseline's position in each comparable case.

    Rule 6 pins every comparable case to the baseline's template, so a term ref
    here is a term ref there; what may still differ is which term it names and
    how it reads, which is what rule 4 is about.
    """
    for case in ctx.comparable:
        case_part = ctx.indexed[case.id][path].narration.parts[index]
        assert isinstance(case_part, NarrationTermRef), (
            'rule 6 admits only cases shaped like the baseline'
        )
        yield case_part
