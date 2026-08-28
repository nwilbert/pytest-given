"""Generated text colors for the HTML report's parametrize columns.

A report needs one color per parametrize column, for a count it only learns at
render time. The fixed six-color list this replaces capped that count — a
seventh column wrapped back onto the first color — and it had to be *ordered*
by hand so that every prefix stayed well spread, since a two-column table only
ever sees the first two entries.

Colors come off a ring: one lightness at full chroma, stepped by colorfulness
rather than by angle. An index picks its place on that ring by the golden
ratio, which is what makes every prefix spread by itself.

Columns are the report's one *arbitrary* color vocabulary — the index means
nothing, the colors only have to be told apart — which is why they can take
the whole ring. The colors that carry meaning are spent elsewhere: the term
kinds mark the word with a wash behind it rather than with ink, so a column
sharing a hue with a kind still cannot be mistaken for one, and the statuses
sit in their own slot beside a glyph.
"""

import bisect
import functools
import math

# Where column 0 sits on the ring, as a fraction of the ring's circumference.
# Swept against everything a column color has to stay clear of — the term-kind
# inks, the three statuses and the accent. Nothing in the first four columns
# comes within dE00 11 of a reserved color, which matters most for the hue
# that reads as "failed": a red column value inside a failed row's red tint is
# the one confusion worth designing out.
_HUE_OFFSET = 0.395

# Successive columns step this far around the ring. The golden ratio's defining
# property is that its multiples never fall into a repeating pattern, so every
# prefix of the sequence is spread near-evenly and no two indices coincide.
#
# The alternative — dividing the ring into exactly `count` equal steps — is
# better on paper, since it maximizes the closest pair for that one count. It
# is worse in the report, for two reasons. Columns are numbered in the order
# they are first seen, so the columns of any one scenario get *consecutive*
# indices, and consecutive indices are precisely the neighbours an even
# division places closest together: at eight columns their separation collapses
# to a quarter of what it holds here, and the pairs that collapse are exactly
# the pairs that appear side by side in a table. And an even division makes
# every color depend on the report's total count, so adding a parametrized
# scenario anywhere in the suite recolors every column in it.
_GOLDEN_RATIO_CONJUGATE = 0.6180339887498949

# CIELAB lightness, shared by every column. It is as light as WCAG AA allows —
# a parameter value renders over the card, the page, the hovered row's blue
# tint and the failed row's red tint, and the worst case anywhere on the ring
# is 4.72:1 — and light is what the ring wants, because chroma collapses as a
# color darkens. An earlier version alternated a second, darker band to buy
# separation; it bought near-black instead, and the columns became hard to tell
# apart. Lightness is the wrong axis for this: at 13px you identify a word's
# color by its hue, and darkening only drains the hue away.
_LIGHTNESS = 43.0

# How finely the ring is sampled when measuring its circumference. One degree
# resolves the placement to well under a just-noticeable difference.
_HUE_SAMPLES = 360

_D65 = (0.95047, 1.0, 1.08883)

# CIEXYZ (D65) to linear sRGB.
_XYZ_TO_RGB = (
    (3.2404542, -1.5371385, -0.4985314),
    (-0.9692660, 1.8760108, 0.0415560),
    (0.0556434, -0.2040259, 1.0572252),
)

# The CIE standard's epsilon/kappa pair, as exact ratios.
_EPSILON = 216 / 24389
_KAPPA = 24389 / 27


def param_column_colors(count: int) -> list[str]:
    """`count` hex colors for the parametrize columns, column 0 first.

    An index always resolves to the same color, whatever the count — the count
    only says how many of them this report needs."""
    return [_column_color(index) for index in range(count)]


def _column_color(index: int) -> str:
    hue = _hue_at(_HUE_OFFSET + index * _GOLDEN_RATIO_CONJUGATE)
    return _lch_to_hex(_LIGHTNESS, _max_chroma(_LIGHTNESS, hue), hue)


def _hue_at(fraction: float) -> float:
    """The hue this far around the ring, measured in colorfulness rather than
    in degrees.

    Splitting the circle into equal *angles* looks right and reads wrong,
    because sRGB does not hold the same chroma everywhere: the blue-green arc
    from roughly 140 to 260 degrees is a quarter of the circle but can only
    reach a third of the chroma the reds and violets can. An even angular split
    spends a quarter of its columns in there, and they come out as three
    near-identical dark blue-greens. Walking the circle in equal steps of
    available chroma instead puts fewer columns where the gamut is thin and
    more where it is wide, which is where they can actually be told apart.
    Together with the golden-ratio placement above, this holds neighbouring
    columns a constant distance apart at every count, and beats the
    hand-picked list this replaces at every count past two — in ordinary
    vision and under simulated deuteranopia, protanopia and tritanopia."""
    arc = _chroma_arc()
    target = (fraction % 1.0) * arc[-1]
    return float(bisect.bisect_left(arc, target) % _HUE_SAMPLES) * (
        360.0 / _HUE_SAMPLES
    )


@functools.cache
def _chroma_arc() -> tuple[float, ...]:
    """Cumulative chroma around the ring, one entry per sample plus a closing
    total — the ruler `_hue_at` measures against."""
    total = 0.0
    arc = [0.0]
    for sample in range(_HUE_SAMPLES):
        total += _max_chroma(_LIGHTNESS, sample * 360.0 / _HUE_SAMPLES)
        arc.append(total)
    return tuple(arc)


def _max_chroma(lightness: float, hue: float) -> float:
    """The most chroma this lightness and hue can hold inside sRGB, by bisection
    — the gamut boundary has no closed form in CIELAB."""
    low, high = 0.0, 200.0
    for _ in range(32):
        mid = (low + high) / 2
        if _in_gamut(_lch_to_rgb(lightness, mid, hue)):
            low = mid
        else:
            high = mid
    return low


def _lch_to_hex(lightness: float, chroma: float, hue: float) -> str:
    red, green, blue = _lch_to_rgb(lightness, chroma, hue)
    return '#' + ''.join(
        f'{round(min(1.0, max(0.0, channel)) * 255):02x}'
        for channel in (red, green, blue)
    )


def _lch_to_rgb(
    lightness: float, chroma: float, hue: float
) -> tuple[float, float, float]:
    """CIELCh(ab) to sRGB, unclamped — a component outside 0..1 means the color
    is outside the gamut, which is what `_max_chroma` bisects on."""
    radians = math.radians(hue)
    return _lab_to_rgb(
        lightness, chroma * math.cos(radians), chroma * math.sin(radians)
    )


def _lab_to_rgb(
    lightness: float, a_star: float, b_star: float
) -> tuple[float, float, float]:
    f_y = (lightness + 16) / 116
    f_x, f_z = f_y + a_star / 500, f_y - b_star / 200
    xyz = (
        _inverse_f(f_x) * _D65[0],
        (
            ((lightness + 16) / 116) ** 3
            if lightness > _KAPPA * _EPSILON
            else lightness / _KAPPA
        )
        * _D65[1],
        _inverse_f(f_z) * _D65[2],
    )
    linear = tuple(sum(row[i] * xyz[i] for i in range(3)) for row in _XYZ_TO_RGB)
    red, green, blue = (_gamma_encode(channel) for channel in linear)
    return red, green, blue


def _inverse_f(value: float) -> float:
    cubed = value**3
    return cubed if cubed > _EPSILON else (116 * value - 16) / _KAPPA


def _gamma_encode(channel: float) -> float:
    # The linear branch also absorbs the negative channels an out-of-gamut
    # color produces: it keeps them negative, which is what `_in_gamut` reads.
    if channel <= 0.0031308:
        return 12.92 * channel
    return 1.055 * math.pow(channel, 1 / 2.4) - 0.055


def _in_gamut(rgb: tuple[float, float, float]) -> bool:
    return all(-1e-6 <= channel <= 1 + 1e-6 for channel in rgb)
