import math
import re

from pytest_given.report.palette import param_column_colors

_HEX = re.compile(r'^#[0-9a-f]{6}$')


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


def test_param_column_colors_meet_wcag_aa_on_every_background_they_land_on() -> None:
    # A parameter value renders over the card, the page, the hovered row's
    # accent tint and the failed row's red tint. AA for body text is 4.5:1.
    backgrounds = ('#ffffff', '#f8fafc', '#dbeafe', '#fef2f2')
    for count in range(1, 25):
        for color in param_column_colors(count):
            for background in backgrounds:
                assert _contrast(color, background) >= 4.5, (
                    f'{color} on {background} at count={count}'
                )


def test_param_column_colors_share_one_lightness() -> None:
    # Every column sits at the same lightness, so hue does all the separating.
    # Darkening a column to separate it only drains its hue away, which is what
    # made an earlier two-band version hard to read.
    luminances = [_relative_luminance(c) for c in param_column_colors(8)]
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
