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
