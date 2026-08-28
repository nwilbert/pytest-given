"""The pure rules over `Narration` parts, shared by capture and grouping.

`Narration` carries both a rendered `text` and the `parts` that reconstruct
it (see `schema.Narration`); anything that builds parts has to derive the text
the same way, and resolve a placeholder the same way, or two callers disagree
about what the same narration says. `capture/` records them and `grouping/`
rewrites them, so a rule either lives once here in the leaf or twice in the
layers above.

Only rules that need nothing but the parts. `try_term_ref` stays in
`capture/template.py`, where the glossary handle types it matches on live.
"""

from string import Formatter
from typing import Any, assert_never

from .schema import (
    NarrationLiteral,
    NarrationPart,
    NarrationPlaceholder,
    NarrationTermRef,
    NarrationValue,
)

_FORMATTER = Formatter()


def narration_text(parts: list[NarrationPart]) -> str:
    """The text those parts render.

    A placeholder stands for a value not yet known, so it renders as its own
    `{name}` token — which is what makes this both the grouped template's text
    (placeholders left standing, pointing at columns) and a substituted case's
    (no placeholders left to stand).
    """
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
            case _:
                assert_never(part)
    return ''.join(out)


def render_interpolation(value: Any, conversion: str | None, format_spec: str) -> str:
    """One interpolation rendered the way an f-string renders it: `!conv`
    first, then `:spec`.

    The single definition of that rule. Grouping re-applies it to a raw
    parametrize value to decide whether a narration that names a column really
    narrates it (rule 3), and a second copy of the rule there would accuse a
    faithful narration the moment the two drifted apart.
    """
    return format(_FORMATTER.convert_field(value, conversion), format_spec)


def placeholder_value(part: NarrationPlaceholder, value: Any) -> NarrationValue:
    """One `Template` placeholder resolved against the value bound to its name.

    The single definition of that conversion, for the same reason
    `render_interpolation` is the single definition of the rendering it wraps.
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
