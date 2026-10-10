"""Wording helpers the renderers and view builders share."""

from typing import Literal

from ..model import Status

# How a status is marked, wherever it is shown.
STATUS_GLYPH: dict[Status, str] = {
    'passed': '✓',
    'failed': '✗',
    'skipped': '○',
    'xfailed': '⊗',
}
STATUS_LABEL: dict[Status, str] = {
    'passed': 'passed',
    'failed': 'failed',
    'skipped': 'skipped',
    'xfailed': 'expected failure',
}

# A citation's state: its target's status, or `missing` for a target the
# report lacks.
type CitationState = Status | Literal['missing']

# How a citation marks its state. Emoji, because Markdown has no portable way
# to colour text; they follow the report's status colours.
CITATION_GLYPH: dict[CitationState, str] = {
    'passed': '✅',
    'failed': '❌',
    'skipped': '🟠',
    'xfailed': '🔵',
    'missing': '❓',
}

# Also read as a citation's glyph, and rewritten as emoji by `citations
# update`: the Markdown sink's glyphs and a typed `?`, so a hand-typed
# placeholder works either way.
CITATION_GLYPH_PLACEHOLDERS: tuple[str, ...] = (*STATUS_GLYPH.values(), '?')
