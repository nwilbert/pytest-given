"""The pure rules over `Narration` parts."""

from typing import Any, cast

import pytest

from pytest_given.model import (
    ColumnId,
    NarrationLiteral,
    NarrationPart,
    NarrationPlaceholder,
    NarrationTermRef,
    NarrationValue,
    TermId,
    narration_text,
    spanned_part,
)


def test_narration_text_rejects_unknown_variant() -> None:
    # The exhaustive match guards against a NarrationPart variant being added
    # without a text branch — which would drop it from `text` silently, and
    # `text` is what the report's search box and a `jq` query read.
    with pytest.raises(AssertionError):
        narration_text([cast(Any, object())])


def _value(expression: str) -> NarrationValue:
    return NarrationValue(rendered='v', expression=expression)


@pytest.mark.parametrize(
    ('parts', 'kind', 'index'),
    [
        (
            [
                NarrationLiteral(value='`run '),
                _value('cmd'),
                NarrationLiteral(value='`'),
            ],
            'a code span',
            1,
        ),
        (
            [
                NarrationLiteral(value='**'),
                NarrationTermRef(
                    term_id=TermId('guest'), display='Guest', expression='guest'
                ),
                NarrationLiteral(value='** books'),
            ],
            'bold',
            1,
        ),
        (
            [
                NarrationLiteral(value='a *'),
                NarrationPlaceholder(name='size', column_id=ColumnId('size')),
                NarrationLiteral(value=' cup*'),
            ],
            'italics',
            1,
        ),
        (
            [
                NarrationLiteral(value='*`code` '),
                _value('x'),
                NarrationLiteral(value='*'),
            ],
            'italics',
            1,
        ),
        (
            [
                NarrationLiteral(value='**a** `b` '),
                _value('x'),
                NarrationLiteral(value=' `c '),
                _value('y'),
                NarrationLiteral(value='`'),
            ],
            'a code span',
            3,
        ),
    ],
    ids=[
        'code-around-value',
        'bold-around-term-ref',
        'italic-around-placeholder',
        'italic-holding-code',
        'after-other-spans',
    ],
)
def test_spanned_part_names_the_span_and_the_part_it_holds(
    parts: list[NarrationPart], kind: str, index: int
) -> None:
    assert spanned_part(parts) == (kind, parts[index])


@pytest.mark.parametrize(
    'parts',
    [
        [NarrationLiteral(value='plain `code` and **bold**')],
        [NarrationLiteral(value='`run` '), _value('cmd')],
        [
            _value('a'),
            NarrationLiteral(value=' * '),
            _value('b'),
            NarrationLiteral(value=' *'),
        ],
        [
            NarrationLiteral(value='`x` '),
            NarrationValue(rendered='`', expression='tick'),
        ],
    ],
    ids=['literal-only', 'code-beside-value', 'spaced-asterisks', 'backtick-in-value'],
)
def test_spanned_part_finds_none_when_every_span_stays_in_its_text(
    parts: list[NarrationPart],
) -> None:
    assert spanned_part(parts) is None
