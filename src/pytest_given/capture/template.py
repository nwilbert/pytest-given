from string import Formatter, templatelib

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
from .glossary import TermHandle, TermInstance

_FORMATTER = Formatter()


def narration_from(
    value: str | Template | templatelib.Template | Narration,
) -> Narration:
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
    match value:
        case TermHandle():
            display = value.canonical
            term_id = value.id
        case TermInstance(handle=handle, display=display):
            term_id = handle.id
        case _:
            return None
    if format_spec or conversion:
        suffix = f':{format_spec}' if format_spec else ''
        conv = f'!{conversion}' if conversion else ''
        raise PytestGivenError(
            f'glossary term interpolation {{{expression}{conv}{suffix}}} '
            f'cannot carry a format spec or conversion — glossary handles '
            f'render as kind-colored term refs with a fixed display ({display!r}). '
            f'Drop the spec, or interpolate the underlying value separately.'
        )
    return NarrationTermRef(term_id=term_id, display=display, expression=expression)


def resolved_placeholder_part(
    part: NarrationPlaceholder, value: object
) -> NarrationPart:
    """One `Template` slot resolved against the value bound to its name.

    A glossary term instance becomes a real term ref — the same thing a
    t-string interpolation of that handle records — so the declined-merge path
    and the helper-decorator path narrate a term the way the grouped path's
    cell does. `placeholder_value` alone would render the whole `Glossary`
    dataclass repr, since `model` is the leaf and cannot reach `try_term_ref`.

    Only an unformatted slot unwraps. A term ref carries a fixed display and
    can hold no spec, and the grouped path renders a spec'd slot through
    `render_interpolation` too — gating here keeps the two paths agreeing
    rather than making one of them raise where the other formats.
    """
    if not part.conversion and not part.format_spec:
        term_ref = try_term_ref(value, part.name)
        if term_ref is not None:
            return term_ref
    return placeholder_value(part, value)
