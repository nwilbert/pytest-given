import colorsys
import math
import re

import pytest

from pytest_given.report.html_renderer import _TEMPLATES_DIR
from pytest_given.report.palette import Surface, param_column_colors

_HEX = re.compile(r'^#[0-9a-f]{6}$')
_STYLES = (_TEMPLATES_DIR / 'styles.css').read_text(encoding='utf-8')


def _srgb(hex_color: str) -> tuple[float, float, float]:
    return tuple(  # type: ignore[return-value]
        int(hex_color[i : i + 2], 16) / 255 for i in (1, 3, 5)
    )


def _relative_luminance(hex_color: str) -> float:
    channels = [
        c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
        for c in _srgb(hex_color)
    ]
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def _chromaticity(hex_color: str) -> tuple[float, float, float]:
    """Linear RGB normalized to sum 1 — the color with its brightness divided
    out, so distance here is separation in hue and saturation alone."""
    channels = [
        c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
        for c in _srgb(hex_color)
    ]
    total = sum(channels)
    return tuple(c / total for c in channels)  # type: ignore[return-value]


def _hue_degrees(hex_color: str) -> float:
    """sRGB hue angle, enough to check two colours are the same hue."""
    return colorsys.rgb_to_hsv(*_srgb(hex_color))[0] * 360


def _theme_tokens(surface: Surface) -> dict[str, str]:
    """The colour tokens the stylesheet sets for one theme, read from its own
    block so the guarantee follows a retuned token rather than a stale copy."""
    selector = ':root' if surface == 'light' else '[data-theme="dark"]'
    block = re.search(re.escape(selector) + r' \{(.*?)\n\}', _STYLES, re.DOTALL)
    assert block is not None, selector
    return dict(re.findall(r'(--[\w-]+): (#[0-9a-f]{6});', block.group(1)))


def _contrast(hex_color: str, background: str) -> float:
    lo, hi = sorted((_relative_luminance(hex_color), _relative_luminance(background)))
    return (hi + 0.05) / (lo + 0.05)


def test_param_column_colors_returns_one_color_per_column() -> None:
    assert len(param_column_colors(4)) == 4


def test_param_column_colors_of_zero_columns_is_empty() -> None:
    # A report with no parametrized scenarios asks for none, and the template
    # loops over the result — it must not have to guard the empty case.
    assert param_column_colors(0) == []


def test_param_column_colors_are_lowercase_six_digit_hex() -> None:
    assert all(_HEX.match(color) for color in param_column_colors(8))


def test_param_column_colors_are_distinct() -> None:
    # The colors exist only to be told apart; two equal ones would silently
    # merge two columns. The old fixed list wrapped at six.
    for count in range(1, 25):
        colors = param_column_colors(count)
        assert len(set(colors)) == count


def test_param_column_colors_are_deterministic() -> None:
    assert param_column_colors(5) == param_column_colors(5)


def test_param_column_colors_of_a_count_extend_the_shorter_ones() -> None:
    # An index resolves to the same color whatever the count, so a longer list
    # is the shorter list plus more. Without this, adding a parametrized
    # scenario anywhere in the suite would recolor every column in the report.
    for count in range(1, 24):
        assert param_column_colors(count + 1)[:count] == param_column_colors(count)


@pytest.mark.parametrize('surface', ['light', 'dark'])
def test_param_column_colors_meet_wcag_aa_on_every_background_they_land_on(
    surface: Surface,
) -> None:
    # A parameter value renders over the surface, the page, the hovered row's
    # accent tint and the failed row's tint — on the dark theme the last is the
    # lightest and so the tightest. AA for body text is 4.5:1.
    tokens = _theme_tokens(surface)
    backgrounds = [
        tokens[name]
        for name in (
            '--bg-surface',
            '--bg-page',
            '--color-accent-tint',
            '--color-failed-tint',
        )
    ]
    for count in range(1, 25):
        for color in param_column_colors(count, surface):
            for background in backgrounds:
                assert _contrast(color, background) >= 4.5, (
                    f'{color} on {background} at count={count}'
                )


@pytest.mark.parametrize('surface', ['light', 'dark'])
def test_param_column_colors_share_one_lightness(surface: Surface) -> None:
    # Every column sits at the same lightness, so hue does all the separating.
    # Darkening a column to separate it only drains its hue away, which is what
    # made an earlier two-band version hard to read.
    luminances = [_relative_luminance(c) for c in param_column_colors(8, surface)]
    assert max(luminances) - min(luminances) < 0.01


def test_param_column_colors_hold_neighbouring_indices_far_apart() -> None:
    # The guard on the whole scheme. A scenario's columns are numbered in the
    # order they are first seen, so the columns that appear side by side in one
    # table carry *consecutive* indices — those are the pairs that have to be
    # tellable apart, and the ring is stepped by the golden ratio to keep them
    # so at any count. Every column shares a lightness, so the separation lives
    # entirely in chromaticity. The floor is the measured value less a wide
    # margin; stepping the ring by equal angles measured 0.15 here at eight.
    for count in (2, 3, 4, 6, 8, 12, 24):
        colors = param_column_colors(count)
        points = [_chromaticity(color) for color in colors]
        closest = min(math.dist(points[i], points[i + 1]) for i in range(count - 1))
        assert closest >= 0.45, f'{closest:.3f} at count={count}: {colors}'


def test_dark_param_column_colors_keep_the_light_hues_index_for_index() -> None:
    # Column N is the same hue in both themes, only lighter — a reader who
    # flips the theme mid-read must not see the columns swap colours. The
    # tolerance is loose because an sRGB hue angle drifts with chroma even at
    # one LCh hue (blues most, ~23°); a swapped index would be off by the
    # ring's step, ~100°.
    light = param_column_colors(8)
    dark = param_column_colors(8, 'dark')
    assert len(dark) == 8
    for light_color, dark_color in zip(light, dark, strict=True):
        apart = abs(_hue_degrees(light_color) - _hue_degrees(dark_color))
        assert min(apart, 360 - apart) < 30, (light_color, dark_color)
        assert _relative_luminance(dark_color) > _relative_luminance(light_color)
