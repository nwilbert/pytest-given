import pytest

from pytest_given.report.inline_markdown import render_definition, render_spans


@pytest.mark.parametrize(
    ('text', 'expected'),
    [
        ('plain', 'plain'),
        ('', ''),
        ('**bold**', '<strong>bold</strong>'),
        ('*italic*', '<em>italic</em>'),
        ('`code`', '<code>code</code>'),
        (
            'a **b** and *c* and `d`',
            'a <strong>b</strong> and <em>c</em> and <code>d</code>',
        ),
        ('**`.l`**', '<strong><code>.l</code></strong>'),
        # code span wins over emphasis inside it
        ('`a*b*c`', '<code>a*b*c</code>'),
        # unpaired, spaced or underscore markers stay literal
        ('a * b', 'a * b'),
        ('2 * 3 * 4', '2 * 3 * 4'),
        ('__bold__', '__bold__'),
        ('lone ` tick', 'lone ` tick'),
        # HTML is escaped; only <br> is re-admitted
        ('1 < 2 & 3', '1 &lt; 2 &amp; 3'),
        ('<script>x</script>', '&lt;script&gt;x&lt;/script&gt;'),
        ('code with `<`', 'code with <code>&lt;</code>'),
        ('`<br>` shows', '<code>&lt;br&gt;</code> shows'),
        # hard breaks: literal <br> forms and real newlines
        ('a<br>b', 'a<br>b'),
        ('a<br/>b', 'a<br>b'),
        ('a<br />b', 'a<br>b'),
        ('a<BR>b', 'a<br>b'),
        ('a\nb', 'a<br>b'),
        ('a\r\nb', 'a<br>b'),
        ('**x**<br>`y`', '<strong>x</strong><br><code>y</code>'),
        ('**a<br>b**', '<strong>a<br>b</strong>'),
    ],
)
def test_render_definition(text: str, expected: str) -> None:
    assert render_definition(text) == expected


@pytest.mark.parametrize(
    ('text', 'expected'),
    [
        ('Books a **suite**', 'Books a <strong>suite</strong>'),
        ('*a* `b`', '<em>a</em> <code>b</code>'),
        ('1 < 2 & 3', '1 &lt; 2 &amp; 3'),
        # A title or step never breaks a line.
        ('a<br>b', 'a&lt;br&gt;b'),
        ('a\nb', 'a\nb'),
    ],
)
def test_render_spans_never_breaks(text: str, expected: str) -> None:
    assert render_spans(text) == expected
