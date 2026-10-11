"""A citation's link text: written to render as its title, read back as the
title it renders."""

import pytest

from pytest_given.report.link_text import fold_whitespace, link_text, plain_link_text


@pytest.mark.parametrize(
    ('title', 'written'),
    [
        ('a [b] c', 'a \\[b\\] c'),
        ('2 * 3', '2 \\* 3'),
        ('~~gone~~', '\\~\\~gone\\~\\~'),
        ('<title> tag', '\\<title> tag'),
        ('&amp;', '\\&amp;'),
        ('a | b', 'a \\| b'),
        ('$x$', '\\$x\\$'),
        ('back\\slash', 'back\\\\slash'),
        ('_lead and trail_', '\\_lead and trail\\_'),
        ('snake_case and 2_3', 'snake_case and 2_3'),
        ('a `--given-md` flag', 'a `--given-md` flag'),
        ('one ` tick', 'one \\` tick'),
        ('two\nlines', 'two lines'),
    ],
)
def test_link_text_escapes_what_would_not_render_literally(
    title: str, written: str
) -> None:
    assert link_text(title) == written


@pytest.mark.parametrize(
    ('title', 'written'),
    [
        ('Books a **suite**', 'Books a **suite**'),
        ('a `x*y` and *z*', 'a `x*y` and *z*'),
        ('__init__ runs', '__init__ runs'),
        ('**a [b] | c**', '**a \\[b\\] \\| c**'),
    ],
)
def test_emphasis_the_report_renders_stays_emphasis(title: str, written: str) -> None:
    assert link_text(title) == written


def test_a_pipe_in_a_code_span_is_escaped_only_in_a_table_row() -> None:
    assert link_text('the `a|b` form') == 'the `a|b` form'
    assert link_text('the `a|b` form', in_table_row=True) == 'the `a\\|b` form'


@pytest.mark.parametrize(
    'title',
    [
        'One xfailed case makes its parametrized scenario an expected failure',
        'a [b] *c* ~d~ <e> &f; |g| $h$ _i_ j_k \\ ` `code|x` ``',
        'Rendering {price} for a guest',
        'multi\nline\r\ntitle',
    ],
)
@pytest.mark.parametrize('in_table_row', [False, True])
def test_written_text_reads_back_as_the_title(title: str, in_table_row: bool) -> None:
    written = link_text(title, in_table_row=in_table_row)
    assert plain_link_text(written, in_table_row=in_table_row) == fold_whitespace(title)


def test_a_hand_written_text_without_escapes_reads_as_the_title() -> None:
    assert plain_link_text('snake_case & friends') == 'snake_case & friends'


def test_an_unpaired_backtick_reads_literally() -> None:
    assert plain_link_text('one ` tick') == 'one ` tick'


def test_text_wrapped_across_lines_folds_to_one() -> None:
    assert plain_link_text('a long\n   title') == 'a long title'
