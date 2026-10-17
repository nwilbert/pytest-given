"""Link text read back as the plain text it renders."""

import pytest

from pytest_given.markdown import plain_html_text, plain_link_text


def test_a_hand_written_text_without_escapes_reads_as_the_title() -> None:
    assert plain_link_text('snake_case & friends') == 'snake_case & friends'


def test_an_unpaired_backtick_reads_literally() -> None:
    assert plain_link_text('one ` tick') == 'one ` tick'


def test_text_wrapped_across_lines_folds_to_one() -> None:
    assert plain_link_text('a long\n   title') == 'a long title'


@pytest.mark.parametrize(
    ('written', 'plain'),
    [
        ('A <code>x</code> &amp; <em>y</em>', 'A x & y'),
        ('a\n  b', 'a b'),
        ('x &lt;y&gt;', 'x <y>'),
    ],
)
def test_plain_html_text(written: str, plain: str) -> None:
    assert plain_html_text(written) == plain
