"""The six authoring forms that would make a grouped tree lie about its cases.

Each raises `PytestGivenError` rather than reporting a finding the way lint
does: a grouped tree built on any of these is false, so the run fails and no
sink is written. Some are checked up front against the whole group; the rest
fire from the baseline walk, which is where the offending part is in hand.
"""

from collections.abc import Iterable, Iterator
from collections.abc import Set as AbstractSet

from ..model import (
    AttachmentLabel,
    NarrationTermRef,
    NarrationValue,
    NodeId,
    Phase,
    PytestGivenError,
    RawParamValue,
    Scenario,
    Step,
    case_suffix,
    location_suffix,
    node_base,
    render_interpolation,
)
from .context import Group, PartSite
from .step_shape import (
    _narration_difference,
    _part_key,
    _shape,
    _structure,
)


def check_same_template(group: Group) -> None:
    """Rules 6 and 1: every comparable case must narrate the baseline's
    template, and a part-less narration must render the same text in each.

    A column carries what varies *within* a sentence. A case that narrates a
    different sentence, or a different tree of them, has nothing a column can
    hold: the grouped view would show one case's words for all of them. Five
    shapes reach that state (a different step structure, a differently shaped
    narration under a matching one, different wording, a different interpolated
    expression, and a plain `str` that renders differently per case). The first
    four have the same answer and share a message; the fifth has a better one
    of its own, but the same walk finds it.

    Runs first, against the very tree `templatize_steps` goes on to walk: the
    other rules index a case by the baseline's path without a `.get` and read
    the part there as the baseline's kind, both of which hold only because this
    ran. A non-passed case is exempt — which is exactly `group.comparable`.
    """
    if not group.comparable:
        return
    baseline = group.baseline
    # `build_group` already walked and keyed every comparable case; the
    # baseline is `comparable[0]`, so its own walk is in there too. A
    # `walk_steps` mapping is keyed by DFS pre-order path, which makes the
    # path/shape list below equivalent to a recursive structure signature.
    baseline_steps = list(group.indexed[baseline.id].items())
    signature = _shape(baseline_steps)
    baseline_keys = [
        [_part_key(part) for part in step.narration.parts]
        for _path, step in baseline_steps
    ]
    for case in group.comparable:
        if case.id == baseline.id:
            continue
        case_steps = group.indexed[case.id]
        case_signature = _shape(case_steps.items())
        if _structure(case_signature) != _structure(signature):
            raise _divergence_error(case, 'a different step structure', group)
        if case_signature != signature:
            # Only the activities differ, which `a different step structure`
            # would misdescribe — and the fix is to pick one activity, not to
            # give up on grouping.
            raise _varying_activity_error(case, group)
        for (path, step), keys in zip(baseline_steps, baseline_keys, strict=True):
            # A comparable case has the baseline's exact structure, so every
            # baseline path exists in it — index, never `.get`.
            other = case_steps[path].narration
            if not keys and not other.parts:
                # Rule 1: nothing to compare as a template, so compare the text
                # and answer with the fix that names this step's own phase.
                if other.text != step.narration.text:
                    raise _varying_str_error(step, group)
                continue
            difference = _narration_difference(keys, other)
            if difference is not None:
                raise _divergence_error(
                    case, f'{difference} in its {step.phase} step', group
                )


def _varying_str_error(step: Step, group: Group) -> PytestGivenError:
    """Rule 1: a `str` narration whose rendered text varies across cases.

    A `str` records `parts == []` however it was built, so there is nothing to
    promote and the whole narration would be the baseline's. An f-string is the
    usual cause, but a helper call or a lookup looks identical from here.
    """
    return _grouping_error(
        group,
        f'step narration in {_test_name(group.anchor)!r} varies across '
        f'parametrize cases but records no parts — a plain str bakes case '
        f"{case_suffix(group.baseline.id)}'s values (an f-string is the usual "
        f'cause). Use a t-string: {step.phase}(t"…"), or '
        f'@scenario(..., group_parametrized=False) to emit one scenario per '
        f'case.',
    )


def _varying_activity_error(case: Scenario, group: Group) -> PytestGivenError:
    return _grouping_error(
        group,
        f'case {case_suffix(case.id)} of {_test_name(group.anchor)!r} claims '
        f'different step activities than case {case_suffix(group.baseline.id)} '
        f'— the grouped tree keeps one set, and story coverage is credited '
        f'from exactly that field. Give the step one activity, or use '
        f'@scenario(..., group_parametrized=False) to emit one scenario per '
        f'case.',
    )


def _divergence_error(
    case: Scenario, difference: str, group: Group
) -> PytestGivenError:
    return _grouping_error(
        group,
        f'case {case_suffix(case.id)} of {_test_name(group.anchor)!r} narrates '
        f'{difference} than case {case_suffix(group.baseline.id)} — a grouped '
        f'scenario renders one tree for every row, so the cases cannot be '
        f'merged honestly. Use @scenario(..., group_parametrized=False) to '
        f'emit one scenario per case.',
    )


def check_promotable_expression(
    part: NarrationValue, phase: Phase, group: Group
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
    raise _grouping_error(
        group,
        f'{part.expression!r} in {_test_name(group.anchor)!r} varies across '
        f'parametrize cases — bind it to a local and narrate that: '
        f'value = {part.expression}; {phase}(t"… {{value}} …").',
    )


def check_rebound_params(group: Group) -> None:
    """Rule 3: an expression that matches a parametrize name but not its value.

    A param match discards `rendered` and renders from the cell instead, so a
    step narrating anything else silently makes the report wrong for *every*
    case. Per case, re-apply the interpolation's own conversion and format spec
    to that case's **raw** parameter object and compare with what was recorded
    — exactly what the t-string did at capture time, so a faithful
    interpolation agrees for every type. Being per-case rather than a
    comparison, this fires where no other rule can: a single-value parametrize
    still catches it.

    A mismatch proves that the cell and the step disagree, not *why*: a local
    rebinding the name is one cause, a body mutating the value in place before
    narrating it the other. The message offers both remedies.
    """
    for scenario in group.comparable:
        _check_case_params(scenario, group)


def _check_case_params(scenario: Scenario, group: Group) -> None:
    params = group.case_params[scenario.id]
    for step in group.indexed[scenario.id].values():
        for part in step.narration.parts:
            if not isinstance(part, NarrationValue) or part.expression not in params:
                continue
            try:
                reformatted = _reformat(params[part.expression], part)
            except Exception:  # noqa: BLE001 — see _reformat's contract
                # A value whose own `__format__`/`__str__` raises something
                # other than the two errors `_reformat` handles is broken, not
                # evidence of a rebinding. Skipping is the only safe reading:
                # raising here would abort every sink in the session.
                continue
            if reformatted == part.rendered:
                continue
            raise _grouping_error(
                group,
                f'{part.expression!r} in {_test_name(group.anchor)!r} matches a '
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


def check_attachment_labels(
    baseline: AbstractSet[AttachmentLabel],
    others: Iterable[tuple[NodeId, AbstractSet[AttachmentLabel]]],
    group: Group,
) -> None:
    """Rule 5: a step whose set of attachment labels differs across cases.

    A label names its payload; the payload is what varies, and the row already
    says which case it belongs to. Content and content type are exempt by
    design — varying those is what the `attachment` column is for. The
    comparison is over the *distinct* labels, so a label attached a different
    number of times does not raise.

    Takes label *sets* rather than the maps the promotion walk grouped: those
    keys are all this reads, and asking for the whole map is what made this
    module know the shape of an attachment store it never opens. Each set
    arrives with its case id so the message can name the case, as every other
    refusal does.
    """
    for case_id, other in others:
        differing = sorted(baseline ^ other)
        if not differing:
            continue
        raise _grouping_error(
            group,
            f'attachment label {differing[0]!r} in {_test_name(group.anchor)!r} is '
            f'attached in case {case_suffix(case_id)} but not case '
            f'{case_suffix(group.baseline.id)} (or the other way round) — a label '
            f'names the payload and must read the same in every case. Use a '
            f'constant label and let the content vary: attach("<constant>", …).',
        )


def check_constant_term_ref(
    part: NarrationTermRef, site: PartSite, group: Group
) -> None:
    """Rule 4: a term ref must name the same term and read the same in every case.

    No exemption for one a parametrize column binds. Rejected rather than
    promoted, because promotion would strip the term ref out of the grouped
    tree, and story coverage matches on term-ref identities. The grouped tree
    keeps a single `term_id` and a single display either way, so a varying ref
    would file every case's value under the first case's.
    """
    identity = (part.term_id, part.display)
    for case_part in _case_term_refs(site, group):
        if (case_part.term_id, case_part.display) == identity:
            continue
        raise _grouping_error(
            group,
            f'glossary term ref {{{part.expression}}} in '
            f'{_test_name(group.anchor)!r} varies across parametrize '
            f'cases — a term ref must name the same term and read the '
            f'same in every case. Split the term ref from the value: '
            f'{site.phase}(t"{{pg[\'Term\']}} {{value}} …"), or use @scenario(..., '
            f'group_parametrized=False) to emit one scenario per case.',
        )


def _case_term_refs(site: PartSite, group: Group) -> Iterator[NarrationTermRef]:
    """The term ref at the baseline's position in each comparable case.

    Rule 6 pins every comparable case to the baseline's template, so a term ref
    here is a term ref there; what may still differ is which term it names and
    how it reads.
    """
    for _node_id, case_part in group.parts_at(site):
        assert isinstance(case_part, NarrationTermRef), (
            'rule 6 admits only cases shaped like the baseline'
        )
        yield case_part


def _grouping_error(group: Group, body: str) -> PytestGivenError:
    """A rejected-form error, located the way a lint finding is.

    A step-level anchor is not available: `Step.source` is captured only when
    lint is enabled, and these rules must hold with lint off.
    """
    return PytestGivenError(f'{body}{location_suffix(group.anchor.source)}')


def _test_name(scenario: Scenario) -> str:
    return node_base(scenario.id).rpartition('::')[2]
