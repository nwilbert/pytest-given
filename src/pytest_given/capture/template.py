"""Step text: the authoring forms, what they parse to, and the two rules
that apply to a decorator-time t-string."""

from collections.abc import Mapping
from string import Formatter, templatelib
from typing import assert_never

from ..model import (
    Narration,
    NarrationLiteral,
    NarrationPart,
    NarrationPlaceholder,
    NarrationTermRef,
    NarrationValue,
    PytestGivenError,
    narration_text,
    placeholder_value,
    render_interpolation,
)
from .glossary import TermRef

_FORMATTER = Formatter()

# What an author may write as step or scenario text.
type StepText = str | templatelib.Template | Template
# What `@scenario` hands on once a decorator-time t-string has been rendered.
type ResolvedName = str | Template | Narration


def reject_baked_values(narration: Narration, form: str, when: str) -> None:
    """Refuse a decorator-time t-string that interpolates a non-glossary value.

    Such a t-string evaluates once, at *when*, so the value is frozen into
    every recorded step. Glossary handles render as term refs and are safe to
    bake in — they identify a concept, not a per-call datum.
    """
    for part in narration.parts:
        if not isinstance(part, NarrationValue):
            continue
        raise PytestGivenError(
            f'{form}(t"...") interpolates non-glossary value '
            f'{{{part.expression}}} (rendered as {part.rendered!r}); '
            f't-strings on a decorator evaluate once at {when}, so the value '
            f'is baked in. Use a glossary handle '
            f'(g.actor/g.work_object/g.verb) for a term reference; '
            f"pytest_given.Template('...{{{part.expression}}}...') for a "
            f'value bound per call; or move the text into the test body '
            f'(with given/when/then(t"...")) where the value is in scope.'
        )


def narration_from(value: StepText | Narration) -> Narration:
    """Build a Narration from a plain string, a Template, a t-string, or an
    already-rendered Narration (which passes through unchanged — used for eager
    glossary-t-string scenario names)."""
    if isinstance(value, Narration):
        return value
    if isinstance(value, templatelib.Template):
        text, parts = parse_tstring(value)
        return Narration(text=text, parts=parts)
    if isinstance(value, Template):
        # Text derived from the parts, never the raw template string: a
        # placeholder renders as its bare `{name}` token, so `'{amount:.2f}'`
        # would otherwise leave a `text` carrying a spec that nothing displays
        # — and `text` is what the report's search box and a `jq` query read.
        parts = list(value.parts)
        return Narration(text=narration_text(parts), parts=parts)
    return Narration(text=value)


class Template:
    """Deferred brace-style template. Same `{...}` syntax as f/t-strings.

    Supports bare identifiers only — `{name}`, `{name:spec}`, `{name!conv}`.
    Attribute access, indexing, and arbitrary expressions raise PytestGivenError
    at construction time.
    """

    def __init__(self, template: str) -> None:
        self.template = template
        parts: list[NarrationPart] = []
        for literal, name, spec, conversion in _FORMATTER.parse(template):
            if literal:
                parts.append(NarrationLiteral(value=literal))
            if name is not None:
                if not name.isidentifier():
                    raise PytestGivenError(
                        f'pytest_given.Template only supports bare identifiers '
                        f'as placeholders; got {name!r}. For attribute access '
                        f'or expressions, use a t-string in the test body '
                        f'(where the value is in scope).'
                    )
                parts.append(
                    NarrationPlaceholder(
                        name=name,
                        column_id=name,
                        format_spec=spec or '',
                        conversion=conversion,
                    )
                )
        self.parts: list[NarrationPart] = parts

    def get_identifiers(self) -> list[str]:
        return [p.name for p in self.parts if isinstance(p, NarrationPlaceholder)]


def parse_tstring(
    tstring: templatelib.Template,
) -> tuple[str, list[NarrationPart]]:
    """Convert a t-string Template into (rendered text, structured parts).

    An interpolation of a glossary handle (or one of its instances) records a
    `NarrationTermRef`; every other value records a `NarrationValue`.
    """
    parts: list[NarrationPart] = []
    rendered_chunks: list[str] = []
    for chunk in tstring:
        match chunk:
            case str() as literal:
                if literal:
                    parts.append(NarrationLiteral(value=literal))
                    rendered_chunks.append(literal)
            case templatelib.Interpolation(
                value=value,
                expression=expression,
                conversion=conversion,
                format_spec=format_spec,
            ):
                term_ref = try_term_ref(
                    value, expression, format_spec=format_spec, conversion=conversion
                )
                if term_ref is not None:
                    parts.append(term_ref)
                    rendered_chunks.append(term_ref.display)
                    continue
                rendered = render_interpolation(value, conversion, format_spec)
                parts.append(
                    NarrationValue(
                        rendered=rendered,
                        expression=expression,
                        format_spec=format_spec,
                        conversion=conversion,
                    )
                )
                rendered_chunks.append(rendered)
    return ''.join(rendered_chunks), parts


def try_term_ref(
    value: object,
    expression: str = '',
    *,
    format_spec: str = '',
    conversion: str | None = None,
) -> NarrationTermRef | None:
    """Return a NarrationTermRef if `value` is a glossary handle, instance, or
    inflection — else None (fall back to NarrationValue). Also used by
    grouping to unwrap a parametrized term instance to its display.

    Glossary handles render as kind-colored term refs carrying the term's
    canonical or instance display; format_spec and conversion have no
    meaningful target on a term ref, so a non-empty value is rejected at
    parse time rather than silently dropped.
    """
    if not isinstance(value, TermRef):
        return None
    display = value.display
    if format_spec or conversion:
        suffix = f':{format_spec}' if format_spec else ''
        conv = f'!{conversion}' if conversion else ''
        raise PytestGivenError(
            f'glossary term interpolation {{{expression}{conv}{suffix}}} '
            f'cannot carry a format spec or conversion — glossary handles '
            f'render as kind-colored term refs with a fixed display ({display!r}). '
            f'Drop the spec, or interpolate the underlying value separately.'
        )
    return NarrationTermRef(term_id=value.id, display=display, expression=expression)


def resolve_template_parts(
    parts: list[NarrationPart],
    mapping: Mapping[str, object],
) -> list[NarrationPart]:
    """Each `Template` part resolved against the value bound to its name."""
    out: list[NarrationPart] = []
    for part in parts:
        assert not isinstance(part, (NarrationValue, NarrationTermRef)), (
            'pytest_given.Template yields only literals and placeholders'
        )
        match part:
            case NarrationLiteral():
                out.append(part)
            case NarrationPlaceholder(name=name):
                out.append(resolved_placeholder_part(part, mapping[name]))
            case _:
                assert_never(part)
    return out


def resolved_placeholder_part(
    part: NarrationPlaceholder, value: object
) -> NarrationPart:
    """One `Template` slot resolved against the value bound to its name.

    A glossary term instance becomes a real term ref, the same thing a t-string
    interpolation of that handle records; `placeholder_value` alone would
    render the whole `Glossary` dataclass repr, since `model` is the leaf and
    cannot reach `try_term_ref`.

    Only an unformatted slot unwraps: a term ref can hold no spec, and the
    grouped path renders a spec'd slot through `render_interpolation` too, so
    gating here keeps the two paths agreeing.
    """
    if not part.conversion and not part.format_spec:
        term_ref = try_term_ref(value, part.name)
        if term_ref is not None:
            return term_ref
    return placeholder_value(part, value)
