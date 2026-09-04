"""Render a small set of inline Markdown (bold, italic, inline code, hard line
breaks) from glossary term descriptions to safe HTML. Rendering is a report
concern, so this lives in `report/` and never imports from `capture/`."""

import re

from markupsafe import escape

from ..model import EMPHASIS

# Re-admit an author's escaped <br> / <br/> / <br /> (any case) as a real break.
_BR = re.compile(r'&lt;br\s*/?\s*&gt;', re.IGNORECASE)
_NEWLINE = re.compile(r'\r\n|[\r\n]')


def render_inline_markdown(text: str) -> str:
    """HTML-escape `text`, then render **bold**/__bold__, *italic*, `code`, and
    hard breaks (<br> or a newline) as safe inline HTML.

    One pass over the emphasis spans, so the code span protects its contents
    from break substitution as well as from emphasis. Substituting breaks up
    front instead let `` `<br>` `` through as a real break — the one thing a
    definition documenting that escape hatch needs to render as text.
    """
    escaped = str(escape(text))
    out: list[str] = []
    end = 0
    for match in EMPHASIS.finditer(escaped):
        out.append(_breaks(escaped[end : match.start()]))
        out.append(_emphasis(match))
        end = match.end()
    out.append(_breaks(escaped[end:]))
    return ''.join(out)


def _emphasis(match: re.Match[str]) -> str:
    code, bold_star, bold_underscore, italic = match.groups()
    if code is not None:
        # Verbatim: a code span is the way to *show* `<br>` rather than break.
        return f'<code>{code}</code>'
    if bold_star is not None:
        return f'<strong>{_breaks(bold_star)}</strong>'
    if bold_underscore is not None:
        return f'<strong>{_breaks(bold_underscore)}</strong>'
    assert italic is not None
    return f'<em>{_breaks(italic)}</em>'


def _breaks(text: str) -> str:
    """An author's `<br>` (escaped on the way in) and any newline as a real
    break."""
    return _NEWLINE.sub('<br>', _BR.sub('<br>', text))
