"""Text rules shared across packages that may not import each other.

`capture/markdown_glossary.py` *strips* this markup from a glossary term cell
while `report/inline_markdown.py` *renders* it in a definition cell: a term
written ``**Guest**`` has to canonicalize to the same word its definition
renders bold, so the two must recognize exactly the same spans. Neither package
may import the other, so the pattern lives here in the leaf.

Only the pattern is shared: what a match *becomes* differs by caller, so each
keeps its own substitution function. `plural` is here for the same reason:
`report/` and `lint/` both count things into a sentence, and neither may
import the other.
"""

import re

# Code span first, so nothing inside `code` is treated as markup — neither a
# `*` nor, on the render side, an escaped `<br>`. Callers get that only by
# routing every other substitution through this one pass; `render_inline_markdown`
# says what happens when they don't. The group order is part of the contract
# every substitution function reads: code span, **bold**, __bold__, *italic*.
# Only paired markers match, so a lone underscore inside an identifier
# (`work_object`) is left untouched — a paired dunder (`__init__`) is strong
# emphasis, which is what CommonMark makes it too.
EMPHASIS = re.compile(r'`(.+?)`|\*\*(.+?)\*\*|__(.+?)__|\*(.+?)\*')


def plural(count: int, singular: str, plural_form: str | None = None) -> str:
    """`'1 scenario'` / `'3 scenarios'` — the noun agreeing with its count."""
    if count == 1:
        return f'{count} {singular}'
    return f'{count} {plural_form or singular + "s"}'
