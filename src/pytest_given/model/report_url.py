"""The public URL a report is served from."""

from typing import NewType
from urllib.parse import urlsplit

from .errors import PytestGivenError

# A URL `resolve_report_url` accepted — the only way to get one, so a function
# taking it never has to validate it again.
ReportUrl = NewType('ReportUrl', str)


def resolve_report_url(value: str, setting: str) -> ReportUrl | None:
    """`value` as a report URL, or None when it is empty.

    A citation appends `#<fragment>` to it and writes it as a bare Markdown
    link destination, so only an absolute http(s) URL without a fragment of its
    own, and without a character that would end or escape within that
    destination, can be one.
    """
    if not value:
        return None
    parts = urlsplit(value)
    if (
        parts.scheme not in ('http', 'https')
        or not parts.netloc
        or '#' in value
        or any(_breaks_destination(char) for char in value)
    ):
        raise PytestGivenError(
            f'{setting} must be an absolute http(s) URL without a #fragment, '
            f'whitespace, control characters, <, >, (, ) or \\, but got {value!r}.'
        )
    return ReportUrl(value)


def _breaks_destination(char: str) -> bool:
    return char.isspace() or not char.isprintable() or char in '<>()\\'
