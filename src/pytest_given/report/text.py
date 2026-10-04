"""Wording helpers the renderers and view builders share."""

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


def plural(count: int, singular: str, plural_form: str | None = None) -> str:
    """`'1 scenario'` / `'3 scenarios'` — the noun agreeing with its count."""
    if count == 1:
        return f'{count} {singular}'
    return f'{count} {plural_form or singular + "s"}'
