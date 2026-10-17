"""The pure rules over `Narration` parts, shared by capture, grouping and report.

`capture/` records narration parts and `grouping/` rewrites them; both have to
derive the text the same way and resolve a placeholder the same way, or they
disagree about what one narration says. So a rule lives once here in the leaf
rather than twice in the layers above.

Only rules that need nothing but the parts. `try_term_ref` stays in
`capture/template.py`, where the glossary handle types it matches on live.
"""

from collections.abc import Callable, Iterable, Sequence
from string import Formatter
from typing import Literal, assert_never

from .schema import (
    Narration,
    NarrationLiteral,
    NarrationPart,
    NarrationPlaceholder,
    NarrationTermRef,
    NarrationValue,
)
from .steps import PartIndex
from .text import (
    CodeSpan,
    EmphasisSpan,
    InlineSpan,
    PlainSpan,
    located_spans,
    read_spans,
)

type InterpolatedPart = NarrationValue | NarrationPlaceholder | NarrationTermRef
type NarrationPiece = InlineSpan | InterpolatedPart

_FORMATTER = Formatter()


def placeholder_token(part: NarrationPlaceholder) -> str:
    """A grouped-template slot as its bare `{name}` token.

    The grouped view is schematic: it marks *which* column varies, not how any
    one value prints, so the conversion and format spec are dropped — they are
    already applied in the concrete per-case rows. Both renderers print the
    slot this way, and `narration_text` derives `text` from it.
    """
    return '{' + part.name + '}'


def narration_text(parts: Sequence[NarrationPart]) -> str:
    """The text those parts render.

    A placeholder stands for a value not yet known, so it renders as its own
    `{name}` token — which is what makes this both the grouped template's text
    (placeholders left standing, pointing at columns) and a substituted case's
    (no placeholders left to stand).

    The `case _` guard is load-bearing: the match appends in a loop, so a new
    part kind would otherwise vanish silently.
    """
    out: list[str] = []
    for part in parts:
        match part:
            case NarrationLiteral(value=value):
                out.append(value)
            case NarrationValue(rendered=rendered):
                out.append(rendered)
            case NarrationPlaceholder():
                out.append(placeholder_token(part))
            case NarrationTermRef(display=display):
                out.append(display)
            case _:
                assert_never(part)
    return ''.join(out)


def read_narration(narration: Narration) -> list[NarrationPiece]:
    """A title or step as every output shows it: each literal read for spans on
    its own, so a span never crosses a term ref or a value."""
    parts = narration.parts or (NarrationLiteral(value=narration.text),)
    texts = [narration_text((part,)) for part in parts]
    whole = ''.join(texts)
    pieces: list[NarrationPiece] = []
    end = 0
    for part, text in zip(parts, texts, strict=True):
        start, end = end, end + len(text)
        if isinstance(part, NarrationLiteral):
            before, after = whole[max(start - 1, 0) : start], whole[end : end + 1]
            pieces.extend(read_spans(part.value, before=before, after=after))
        else:
            pieces.append(part)
    return pieces


type SpanKind = Literal['a code span', 'bold', 'italics']

# What every value, placeholder and term ref reads as, so whether a span holds
# one never depends on a value only a run knows.
_STAND_IN = 'x'


def spanned_part(
    parts: Sequence[NarrationPart],
) -> tuple[SpanKind, InterpolatedPart] | None:
    """The first span that reading the text whole would open around a value, a
    placeholder or a term ref, and the part it holds — the span `read_narration`
    leaves as written, its markers having no partner within one literal."""
    whole = ''
    held: dict[int, InterpolatedPart] = {}
    for part in parts:
        if isinstance(part, NarrationLiteral):
            whole += part.value
        else:
            held[len(whole)] = part
            whole += _STAND_IN
    for span, chars in located_spans(whole):
        if isinstance(span, PlainSpan):
            continue
        inside = next((part for at, part in held.items() if at in chars), None)
        if inside is not None:
            return _span_kind(span), inside
    return None


def _span_kind(span: CodeSpan | EmphasisSpan) -> SpanKind:
    if isinstance(span, CodeSpan):
        return 'a code span'
    return 'bold' if span.strong else 'italics'


def narration_of(parts: Iterable[NarrationPart]) -> Narration:
    """A narration carrying those parts, with `text` derived from them.

    `text` must equal `narration_text(parts)` — grouping partitions cases on
    it and the report's search box reads it — and the dataclass does not
    enforce that.
    """
    parts = tuple(parts)
    return Narration(text=narration_text(parts), parts=parts)


def rebuilt(
    narration: Narration, part_of: Callable[[PartIndex, NarrationPart], NarrationPart]
) -> Narration:
    """The narration with every part mapped, and its text re-derived from them.

    Lives here with `narration_text`, which is the rule it has to reapply. A
    part-less narration passes through: its text is all it has, and there is
    nothing to rebuild it from.

    `part_of` takes the part's `PartIndex` as well as the part: a grouping slot
    is identified by its position, and a mapper that does not care ignores it.
    """
    if not narration.parts:
        return narration
    return narration_of(
        part_of(PartIndex(index), part) for index, part in enumerate(narration.parts)
    )


def render_interpolation(
    value: object, conversion: str | None, format_spec: str
) -> str:
    """One interpolation rendered the way an f-string renders it: `!conv`
    first, then `:spec`.

    The single definition of that rule; grouping re-applies it to a raw
    parametrize value to decide whether a narration that names a column really
    narrates it (rule 3).
    """
    return format(_FORMATTER.convert_field(value, conversion), format_spec)


def placeholder_value(part: NarrationPlaceholder, value: object) -> NarrationValue:
    """One `Template` placeholder resolved against the value bound to its name.

    Each caller keeps its own lookup, since what a missing name means differs —
    a helper's signature has already been bound, while a per-case placeholder
    naming no column is an author's typo.
    """
    return NarrationValue(
        rendered=render_interpolation(value, part.conversion, part.format_spec),
        expression=part.name,
        format_spec=part.format_spec,
        conversion=part.conversion,
    )
