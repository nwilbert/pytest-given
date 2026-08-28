"""Render a small set of inline Markdown (bold, italic, inline code, hard line
breaks) from glossary term descriptions to safe HTML. Rendering is a report
concern, so this lives in `report/` and never imports from `capture/`."""

import re

from markupsafe import escape

# Re-admit an author's escaped <br> / <br/> / <br /> (any case) as a real break.
_BR = re.compile(r'&lt;br\s*/?\s*&gt;', re.IGNORECASE)
_NEWLINE = re.compile(r'\r\n|[\r\n]')
# Code span first so a `*` inside `code` is not treated as emphasis.
# Deliberately the same alternation as `capture/markdown_glossary._EMPHASIS`,
# which *strips* this markup from a term cell while this renders it in a
# definition cell: a term written `**Guest**` must canonicalize to the same
# word its definition renders bold. The two cannot share one constant —
# `capture/` and `report/` may not import from each other, and neither
# pattern belongs in `model/` — so changing one means changing both.
_INLINE = re.compile(r'`(.+?)`|\*\*(.+?)\*\*|__(.+?)__|\*(.+?)\*')


def _emphasis(match: re.Match[str]) -> str:
    code, bold_star, bold_underscore, italic = match.groups()
    if code is not None:
        return f'<code>{code}</code>'
    if bold_star is not None:
        return f'<strong>{bold_star}</strong>'
    if bold_underscore is not None:
        return f'<strong>{bold_underscore}</strong>'
    assert italic is not None
    return f'<em>{italic}</em>'


def render_inline_markdown(text: str) -> str:
    """HTML-escape `text`, then render **bold**/__bold__, *italic*, `code`, and
    hard breaks (<br> or a newline) as safe inline HTML."""
    escaped = str(escape(text))
    with_breaks = _NEWLINE.sub('<br>', _BR.sub('<br>', escaped))
    return _INLINE.sub(_emphasis, with_breaks)
