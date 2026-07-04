import pytest

from pytest_given.report.inline_markdown import render_inline_markdown


@pytest.mark.parametrize(
    ('text', 'expected'),
    [
        ('plain', 'plain'),
        ('', ''),
        ('**bold**', '<strong>bold</strong>'),
        ('__bold__', '<strong>bold</strong>'),
        ('*italic*', '<em>italic</em>'),
        ('`code`', '<code>code</code>'),
        (
            'a **b** and *c* and `d`',
            'a <strong>b</strong> and <em>c</em> and <code>d</code>',
        ),
        # code span wins over emphasis inside it
        ('`a*b*c`', '<code>a*b*c</code>'),
        # unpaired / lone markers stay literal
        ('a * b', 'a * b'),
        ('lone ` tick', 'lone ` tick'),
        # HTML is escaped; only <br> is re-admitted
        ('1 < 2 & 3', '1 &lt; 2 &amp; 3'),
        ('<script>x</script>', '&lt;script&gt;x&lt;/script&gt;'),
        ('code with `<`', 'code with <code>&lt;</code>'),
        # hard breaks: literal <br> forms and real newlines
        ('a<br>b', 'a<br>b'),
        ('a<br/>b', 'a<br>b'),
        ('a<br />b', 'a<br>b'),
        ('a<BR>b', 'a<br>b'),
        ('a\nb', 'a<br>b'),
        ('a\r\nb', 'a<br>b'),
        ('**x**<br>`y`', '<strong>x</strong><br><code>y</code>'),
    ],
)
def test_render_inline_markdown(text: str, expected: str) -> None:
    assert render_inline_markdown(text) == expected
