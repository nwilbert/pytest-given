"""The per-case path: a scenario that declines the merge.

`@scenario(group_parametrized=False)` says the cases have nothing honest to
share, so each one leaves here as a scenario of its own — no parameter table,
no shared tree. What the grouped path renders as a `{name}` token pointing at a
column, this path renders as the case's own value.
"""

from dataclasses import replace

from ..model import (
    Narration,
    NarrationLiteral,
    NarrationPart,
    NarrationPlaceholder,
    ParamInfo,
    ParamSpec,
    RawParamValue,
    Scenario,
    Step,
    case_suffix,
    narration_text,
    placeholder_mismatch,
    placeholder_value,
)


def per_case_scenarios(group: list[Scenario], param_info: ParamInfo) -> list[Scenario]:
    """Each case of an opted-out group as its own scenario, titled by its
    parametrize id.

    Every case takes the id, including one whose `Template` name already
    renders its values — the redundancy buys a title that says the same thing
    whichever cases a run collected. Deciding per group instead (suffix only
    when two titles would collide) makes the title depend on the selection: `-k`
    down to one case of a colliding group would drop a suffix the full run
    carries.
    """
    return [
        replace(case, narration=_suffixed(case.narration, case_suffix(case.id)))
        for case in (_substituted(s, param_info[s.id]) for s in group)
    ]


def _substituted(scenario: Scenario, spec: ParamSpec) -> Scenario:
    """The case with every placeholder — in its name and in its steps — filled
    from its own parameters."""
    params = spec.mapping()
    return replace(
        scenario,
        narration=_substituted_narration(scenario.narration, params, spec.names),
        steps=_substituted_steps(scenario.steps, params, spec.names),
    )


def _substituted_steps(
    steps: list[Step], params: dict[str, RawParamValue], names: list[str]
) -> list[Step]:
    return [
        replace(
            step,
            narration=_substituted_narration(step.narration, params, names),
            children=_substituted_steps(step.children, params, names),
        )
        for step in steps
    ]


def _substituted_narration(
    narration: Narration, params: dict[str, RawParamValue], names: list[str]
) -> Narration:
    """Every placeholder replaced by what this case's parameters render.

    Left alone when there is none to fill: a `str` narration carries its text
    with no parts to rebuild it from.
    """
    if not _has_placeholder(narration):
        return narration
    parts = [_substituted_part(part, params, names) for part in narration.parts]
    return Narration(text=narration_text(parts), parts=parts)


def _has_placeholder(narration: Narration) -> bool:
    return any(isinstance(part, NarrationPlaceholder) for part in narration.parts)


def _substituted_part(
    part: NarrationPart, params: dict[str, RawParamValue], names: list[str]
) -> NarrationPart:
    if not isinstance(part, NarrationPlaceholder):
        return part
    if part.name not in params:
        raise placeholder_mismatch(part.name, names)
    return placeholder_value(part, params[part.name])


def _suffixed(narration: Narration, suffix: str) -> Narration:
    """The parametrize id appended as text and, when the narration is built
    from parts, as one more literal — so a term ref survives the suffixing and
    the text still reads as what the parts render."""
    parts = list(narration.parts)
    if parts:
        parts.append(NarrationLiteral(value=f' {suffix}'))
    return Narration(text=f'{narration.text} {suffix}', parts=parts)
