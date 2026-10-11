import pytest

from pytest_given import attach, given, scenario, then, when
from pytest_given.model import (
    Narration,
    NarrationLiteral,
    NarrationTermRef,
    TermId,
    narration_of,
)
from pytest_given.report import CitationIndex, Target
from pytest_given.report.html_renderer import _make_narration_filter
from pytest_given.report.inline_markdown import render_definition
from pytest_given.report.md_renderer import render_md
from tests.ubiquitous_language import pg
from tests.unit.citation_reports import report_, scenario_


def _outputs(title: Narration) -> tuple[str, str, str]:
    """The title as the HTML, the Markdown report and a citation show it."""
    report = report_(scenario_('t.py::test_book'))
    report.scenarios[0].narration = title
    html = str(_make_narration_filter(param_color_map={}, glossary=None)(title))
    heading = render_md(report).splitlines()[2]
    citation = CitationIndex.of(report).citation(Target('scenario', 't.py::test_book'))
    return html, heading, citation.markdown_halves()[0]


@scenario(
    t"A {pg['Scenario title'].l}'s emphasis renders the same in every output",
    tags=['spec/inline-markdown'],
)
def test_a_title_s_emphasis_renders_the_same_in_every_output() -> None:
    with given(t'a {pg["Scenario title"].l} with a bold word and a code span'):
        title = Narration(text='Books a **suite** with `late_checkout`')
    with when(
        t'the HTML, the Markdown {pg["Report"].l} and a {pg["Citation"].l} show it'
    ):
        html, heading, citation = _outputs(title)
        attach('outputs', f'{html}\n{heading}\n{citation}')
    with then('the HTML renders the word bold and the code as code'):
        assert html == (
            'Books a <strong>suite</strong> with <code>late_checkout</code>'
        )
    with then('the Markdown keeps the same markers, so a viewer renders the same'):
        assert heading == '## ✓ Books a **suite** with `late_checkout`'
        assert citation == '✅ [Books a **suite** with `late_checkout`]('


@scenario(
    t'A span crossed by a {pg["Term ref"].l} stays literal in every output',
    tags=['spec/inline-markdown'],
)
def test_a_span_crossed_by_a_term_ref_stays_literal() -> None:
    with given(
        t'a {pg["Scenario title"].l} whose `**` markers enclose a {pg["Term ref"].l}'
    ):
        title = narration_of(
            [
                NarrationLiteral(value='**'),
                NarrationTermRef(term_id=TermId('guest'), display='Guest'),
                NarrationLiteral(value=' books**'),
            ]
        )
    with when(
        t'the HTML, the Markdown {pg["Report"].l} and a {pg["Citation"].l} show it'
    ):
        html, heading, citation = _outputs(title)
        attach('outputs', f'{html}\n{heading}\n{citation}')
    with then('the HTML shows both markers as written'):
        assert html == '**Guest books**'
    with then('the Markdown escapes them, so a viewer shows them as written'):
        assert heading == '## ✓ \\*\\*«Guest» books\\*\\*'
        assert citation == '✅ [\\*\\*Guest books\\*\\*]('


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
def test_a_title_s_spans_never_break(text: str, expected: str) -> None:
    render = _make_narration_filter(param_color_map={}, glossary=None)
    assert render(Narration(text=text)) == expected
