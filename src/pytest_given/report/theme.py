"""The theme the HTML report opens in, as configured.

The report ships both themes and a toggle; this only decides the default a
viewer who has never chosen sees. The head script in `report.html.j2` reads it
from `<html data-theme-default>`, so the value has to be one of the three
spellings it understands — a typo would silently render light.
"""

from typing import Literal, cast

from ..model import PytestGivenError

type Theme = Literal['light', 'dark', 'auto']

THEMES: tuple[Theme, ...] = ('light', 'dark', 'auto')
DEFAULT_THEME: Theme = 'auto'
THEME_HELP = (
    'Colour theme the HTML report opens in: light, dark, or auto (follow the '
    "viewer's system). A viewer's own choice, once made, overrides it."
)


def resolve_theme(value: str, setting: str) -> Theme:
    """`setting` is how the user spelled the option, so the error quotes the
    flag or ini they actually wrote."""
    if value not in THEMES:
        raise PytestGivenError(
            f'Unknown {setting} value {value!r}: expected light, dark or auto.'
        )
    return cast('Theme', value)
