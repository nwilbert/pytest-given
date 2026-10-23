"""Step text: the authoring forms, what they parse to, and the two rules
that apply to a decorator-time t-string."""

from collections.abc import Mapping, Sequence
from string import Formatter, templatelib

from ..model import (
    InterpolatedPart,
    Narration,
    NarrationLiteral,
    NarrationPart,
    NarrationPlaceholder,
    NarrationTermRef,
    NarrationValue,
    PytestGivenError,
    narration_of,
    param_id,
    placeholder_value,
    render_interpolation,
    spanned_part,
)
from .glossary import TermHandleBase

_FORMATTER = Formatter()

# What an author may write as step or scenario text.
type StepText = str | templatelib.Template | Template
# What `@scenario` hands on once a decorator-time t-string has been rendered.
type ResolvedTitle = str | Template | Narration


def reject_baked_values(
    narration: Narration, form: str, when: str, remedy: str
) -> None:
    """Refuse a decorator-time t-string that interpolates a non-glossary value.

    Such a t-string evaluates once, at *when*, so the value is frozen into
    every recorded step. Glossary handles render as term refs and are safe to
    bake in — they identify a concept, not a per-call datum.

    Detection and the two remedies both forms share are stated here; *remedy*
    is the caller's own third, because what a step's text can fall back to and
    what a scenario *title* can are not the same thing.
    """
    for part in narration.parts:
        if not isinstance(part, NarrationValue):
            continue
        raise PytestGivenError(
            f'{form}(t"...") interpolates non-glossary value '
            f'{{{part.expression}}} (rendered as {part.rendered!r}); '
            f't-strings on a decorator evaluate once at {when}, so the value '
            f'is baked in. Use a glossary handle '
            f'(g.actor/g.work_object/g.activity) for a term reference; '
            f"pytest_given.Template('...{{{part.expression}}}...') for a "
            f'value bound per call; or {remedy}.'
        )


def reject_spanned_parts(parts: Sequence[NarrationPart]) -> None:
    """Refuse a span whose markers sit on either side of a value, placeholder
    or term ref: Markdown is read within each literal alone, so the span would
    silently not render."""
    spanned = spanned_part(parts)
    if spanned is None:
        return
    kind, part = spanned
    raise PytestGivenError(
        f'narration puts {_as_written(part)} in {kind}, but Markdown is read '
        f'only in the text around a value, placeholder or term ref, so that span '
        f'would not render. Keep the span within the text beside it, or drop its '
        f'markers.'
    )


def _as_written(part: InterpolatedPart) -> str:
    if isinstance(part, NarrationTermRef):
        return '{' + part.expression + '}'
    name = part.name if isinstance(part, NarrationPlaceholder) else part.expression
    conversion = f'!{part.conversion}' if part.conversion else ''
    spec = f':{part.format_spec}' if part.format_spec else ''
    return '{' + name + conversion + spec + '}'


def narration_from(value: StepText | Narration) -> Narration:
    """Build a Narration from a plain string, a Template, a t-string, or an
    already-rendered Narration (which passes through unchanged — used for eager
    glossary-t-string scenario titles)."""
    if isinstance(value, Narration):
        return value
    if isinstance(value, templatelib.Template):
        # Through `narration_of` like the `Template` branch below, rather than
        # pairing text and parts by hand: one constructor, one place the
        # text-renders-its-parts invariant is established.
        parts = parse_tstring(value)
        reject_spanned_parts(parts)
        return narration_of(parts)
    if isinstance(value, Template):
        # Text derived from the parts, never the raw template string: a
        # placeholder renders as its bare `{name}` token, so `'{amount:.2f}'`
        # would otherwise leave a `text` carrying a spec that nothing displays
        # — and `text` is what the report's search box and a `jq` query read.
        return narration_of(value.parts)
    return Narration(text=value)


class Template:
    """Deferred brace-style template. Same `{...}` syntax as f/t-strings.

    Supports bare identifiers only — `{name}`, `{name:spec}`, `{name!conv}`.
    Attribute access, indexing, arbitrary expressions, and a brace left open
    raise PytestGivenError at construction time.
    """

    def __init__(self, template: str) -> None:
        self.template = template
        parts: list[NarrationPart] = []
        # An escaped brace ends a literal of its own, so the text up to each
        # placeholder is joined back: each literal is read for spans alone.
        text = ''
        try:
            parsed = list(_FORMATTER.parse(template))
        except ValueError as error:
            raise PytestGivenError(
                f'pytest_given.Template cannot read {template!r}: {error}. '
                'Escape a literal brace as {{ or }}, and close every '
                "placeholder's brace."
            ) from error
        for literal, name, spec, conversion in parsed:
            text += literal
            if name is None:
                continue
            if not name.isidentifier():
                raise PytestGivenError(
                    f'pytest_given.Template only supports bare identifiers '
                    f'as placeholders; got {name!r}. For attribute access '
                    f'or expressions, use a t-string in the test body '
                    f'(where the value is in scope).'
                )
            if text:
                parts.append(NarrationLiteral(value=text))
                text = ''
            parts.append(
                NarrationPlaceholder(
                    name=name,
                    column_id=param_id(name),
                    format_spec=spec or '',
                    conversion=conversion,
                )
            )
        if text:
            parts.append(NarrationLiteral(value=text))
        self.parts: tuple[NarrationPart, ...] = tuple(parts)
        reject_spanned_parts(self.parts)

    def get_identifiers(self) -> list[str]:
        return [p.name for p in self.parts if isinstance(p, NarrationPlaceholder)]


def parse_tstring(
    tstring: templatelib.Template,
) -> tuple[NarrationPart, ...]:
    """Convert a t-string Template into its structured parts.

    An interpolation of a glossary handle (or one of its instances) records a
    `NarrationTermRef`; every other value records a `NarrationValue`.
    """
    parts: list[NarrationPart] = []
    for chunk in tstring:
        match chunk:
            case str() as literal:
                if literal:
                    parts.append(NarrationLiteral(value=literal))
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
    return tuple(parts)


def try_term_ref(
    value: object,
    expression: str = '',
    *,
    format_spec: str = '',
    conversion: str | None = None,
) -> NarrationTermRef | None:
    """Return a NarrationTermRef if `value` is a glossary handle, instance, or
    inflection — else None (fall back to NarrationValue).

    Glossary handles render as kind-colored term refs carrying the term's
    canonical or instance display; format_spec and conversion have no
    meaningful target on a term ref, so a non-empty value is rejected at
    parse time rather than silently dropped.
    """
    if not isinstance(value, TermHandleBase):
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
    parts: Sequence[NarrationPart],
    mapping: Mapping[str, object],
) -> tuple[NarrationPart, ...]:
    """Each `Template` part resolved against the value bound to its name."""
    out: list[NarrationPart] = []
    for part in parts:
        match part:
            case NarrationLiteral():
                out.append(part)
            case NarrationPlaceholder(name=name):
                out.append(resolved_placeholder_part(part, mapping[name]))
            case _:
                raise AssertionError(
                    f'pytest_given.Template yields only literals and '
                    f'placeholders, not {part!r}'
                )
    return tuple(out)


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
