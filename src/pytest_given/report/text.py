"""Wording helpers the renderers and view builders share."""

from ..model import Status, s_form

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


def plural(count: int, singular: str) -> str:
    """`'1 scenario'` / `'3 stories'` — the noun agreeing with its count."""
    if count == 1:
        return f'{count} {singular}'
    return f'{count} {s_form(singular)}'
