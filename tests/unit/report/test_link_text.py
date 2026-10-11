"""A citation's link text, written so it renders as the title it stands for,
and read back as the title it renders."""

import pytest

from pytest_given.model import (
    Narration,
    NarrationLiteral,
    NarrationPart,
    NarrationTermRef,
    NarrationValue,
    TermId,
    narration_of,
)
from pytest_given.report.link_text import fold_whitespace, link_text, plain_link_text


def test_a_tag_or_story_title_is_link_text_written_literally() -> None:
    assert link_text('spec/**x**') == 'spec/\\*\\*x\\*\\*'


def test_a_scenario_title_is_link_text_with_its_spans() -> None:
    assert link_text(Narration(text='Books a **suite**')) == 'Books a **suite**'


_TITLES = [
    'One xfailed case makes its parametrized scenario an expected failure',
    'a [b] *c* ~d~ <e> &f; |g| $h$ _i_ j_k \\ ` `code|x` ``',
    'Rendering {price} for a guest',
    'multi\nline\r\ntitle',
    '**`.l`** and __init__ and ***a***',
]

_NARRATIONS: list[tuple[NarrationPart, ...]] = [
    (
        NarrationLiteral(value='**'),
        NarrationTermRef(term_id=TermId('guest'), display='Guest'),
        NarrationLiteral(value=' books**'),
    ),
    (
        NarrationLiteral(value='Split *a* '),
        NarrationValue(rendered='[a*b`|c]', expression=''),
    ),
]


@pytest.mark.parametrize(
    'title',
    [
        *_TITLES,
        *(Narration(text=title) for title in _TITLES),
        *(narration_of(parts) for parts in _NARRATIONS),
    ],
)
@pytest.mark.parametrize('in_table_row', [False, True])
def test_written_text_reads_back_as_the_title(
    title: Narration | str, in_table_row: bool
) -> None:
    written = link_text(title, in_table_row=in_table_row)
    text = title if isinstance(title, str) else title.text
    assert plain_link_text(written, in_table_row=in_table_row) == fold_whitespace(text)


def test_a_hand_written_text_without_escapes_reads_as_the_title() -> None:
    assert plain_link_text('snake_case & friends') == 'snake_case & friends'


def test_an_unpaired_backtick_reads_literally() -> None:
    assert plain_link_text('one ` tick') == 'one ` tick'


def test_text_wrapped_across_lines_folds_to_one() -> None:
    assert plain_link_text('a long\n   title') == 'a long title'
