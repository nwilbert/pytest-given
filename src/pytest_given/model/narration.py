"""The parts-to-text direction of `Narration`, shared by capture and grouping.

`Narration` carries both a rendered `text` and the `parts` that reconstruct it
(see `schema.Narration`); anything that builds parts has to derive the text the
same way, or the two disagree. `capture/` and `grouping/` both do, and neither
may import the other, so the rule lives here in the leaf — as `steps.py` does
for the tree walk and `ids.py` for id derivation.
"""

from .schema import (
    NarrationLiteral,
    NarrationPart,
    NarrationPlaceholder,
    NarrationTermRef,
    NarrationValue,
)


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
    return ''.join(out)
