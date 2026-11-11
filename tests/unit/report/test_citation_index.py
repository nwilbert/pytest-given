"""What a citation of each kind says, computed from a report."""

from urllib.parse import parse_qs

import pytest

from pytest_given.model import (
    Clause,
    ClauseTermRef,
    GlossaryTerm,
    NarrationLiteral,
    NarrationPlaceholder,
    NarrationTermRef,
    NarrationValue,
    Scenario,
    Sentence,
    SentenceId,
    Status,
    Story,
    StoryId,
    TermId,
    narration_of,
    param_id,
)
from pytest_given.report.citation_index import (
    Citation,
    CitationIndex,
    Target,
    citation_templates,
    report_fragment,
)
from pytest_given.report.md_renderer import citation_body_md, narration_body_md
from tests.unit.citation_reports import (
    URL,
    filled,
    report_,
    scenario_,
    story_,
    term_,
    using_,
)


def _index(*scenarios: Scenario, stories: tuple[Story, ...] = ()) -> CitationIndex:
    return CitationIndex.of(report_(*scenarios, stories=stories))


@pytest.mark.parametrize(
    ('status', 'glyph'),
    [('passed', '✅'), ('failed', '❌'), ('skipped', '🟠'), ('xfailed', '🔵')],
)
def test_a_scenario_citation_carries_its_status_glyph_and_no_summary(
    status: Status, glyph: str
) -> None:
    index = _index(scenario_('t.py::test_a', 'Pay', status=status))
    citation = index.citation(Target('scenario', 't.py::test_a'))
    assert (citation.glyph, citation.title_text, citation.summary) == (
        glyph,
        'Pay',
        None,
    )
    assert citation.fragment == 'scenario=t.py::test_a'


@pytest.mark.parametrize(
    ('statuses', 'glyph', 'summary'),
    [
        (('passed', 'xfailed', 'failed'), '❌', '(1 ✅ · 1 ❌ · 1 🔵)'),
        (('passed', 'passed', 'xfailed', 'skipped'), '🔵', '(2 ✅ · 1 🟠 · 1 🔵)'),
        (('skipped', 'passed'), '✅', '(1 ✅ · 1 🟠)'),
        (('skipped', 'skipped'), '🟠', '(2 🟠)'),
    ],
)
def test_a_tag_sums_up_its_scenarios(
    statuses: tuple[Status, ...], glyph: str, summary: str
) -> None:
    index = _index(
        *(
            scenario_(f't.py::test_{number}', status=status, tags=('spec/x',))
            for number, status in enumerate(statuses)
        )
    )
    citation = index.citation(Target('tag', 'spec/x'))
    assert (citation.glyph, citation.title_text, citation.summary) == (
        glyph,
        'spec/x',
        summary,
    )


def test_a_tag_covers_the_tags_below_it_and_no_sibling_prefix() -> None:
    index = _index(
        scenario_('t.py::test_a', tags=('spec/citations',)),
        scenario_('t.py::test_b', tags=('specimen',)),
    )
    assert index.citation(Target('tag', 'spec')).summary == '(1 ✅)'
    assert list(index.tags) == ['spec', 'spec/citations', 'specimen']


def test_a_story_sums_up_its_scenarios_and_reads_no_scenarios_when_empty() -> None:
    told = story_('cancel', 'Cancel a Booking')
    empty = story_('later', 'Later')
    index = _index(
        scenario_('t.py::test_a', stories=('cancel',)),
        scenario_('t.py::test_b', status='xfailed', stories=('cancel',)),
        stories=(told, empty),
    )
    citation = index.citation(Target('story', 'cancel'))
    assert (citation.glyph, citation.title_text, citation.summary) == (
        '🔵',
        'Cancel a Booking',
        '(1 ✅ · 1 🔵)',
    )
    assert citation.fragment == 'view=stories&story=cancel'
    later = index.citation(Target('story', 'later'))
    assert (later.glyph, later.summary) == ('🟠', '(no scenarios)')
    assert list(index.stories) == ['cancel', 'later']


def test_a_grouped_scenario_is_cited_by_its_base_node_id_and_templated_title() -> None:
    grouped = scenario_('t.py::test_pour[water]', grouped=True)
    grouped.narration = narration_of(
        [
            NarrationLiteral(value='Pour '),
            NarrationPlaceholder(name='liquid', column_id=param_id('liquid')),
        ]
    )
    per_case = scenario_('t.py::test_case[a]', 'Case a')
    index = _index(grouped, per_case)
    assert set(index.scenarios) == {'t.py::test_pour', 't.py::test_case[a]'}
    assert (
        index.citation(Target('scenario', 't.py::test_pour')).title_text
        == 'Pour {liquid}'
    )


def test_a_term_ref_title_reads_as_its_display_text() -> None:
    scenario = scenario_('t.py::test_a')
    scenario.narration = narration_of(
        [
            NarrationLiteral(value='A '),
            NarrationTermRef(term_id=TermId('guest'), display='guest'),
            NarrationLiteral(value=' books'),
        ]
    )
    citation = _index(scenario).citation(Target('scenario', 't.py::test_a'))
    assert citation.title_text == 'A guest books'


def test_a_per_case_title_writes_its_case_id_literally() -> None:
    scenario = scenario_('t.py::test_split[a*b*c]')
    scenario.narration = narration_of(
        [
            NarrationLiteral(value='Split *it*'),
            NarrationLiteral(value=' ['),
            NarrationValue(rendered='a*b*c', expression=''),
            NarrationLiteral(value=']'),
        ]
    )
    citation = _index(scenario).citation(Target('scenario', 't.py::test_split[a*b*c]'))
    assert citation.template_row()[2] == 'Split *it* \\[a\\*b\\*c\\]'


def test_a_tag_and_a_story_title_are_written_literally() -> None:
    story = story_('s', 'Book a *suite*')
    index = _index(
        scenario_('t.py::test_a', tags=('a*b*',), stories=('s',)), stories=(story,)
    )
    assert index.citation(Target('tag', 'a*b*')).template_row()[2] == 'a\\*b\\*'
    assert index.citation(Target('story', 's')).template_row()[2] == (
        'Book a \\*suite\\*'
    )


@pytest.mark.parametrize(
    'node_id',
    [
        'tests/test_x.py::test_y[a b+c&d#e%f=g]',
        'tests/test_ü.py::test_ß[ünïcode]',
        'tests/test_x.py::test_y[1.5-x_y~z]',
    ],
)
def test_a_fragment_round_trips_through_parse_qs(node_id: str) -> None:
    fragment = report_fragment(Target('scenario', node_id))
    assert parse_qs(fragment)['scenario'] == [node_id]
    assert ' ' not in fragment
    assert fragment.startswith('scenario=tests/test_')


def test_the_readable_characters_stay_unencoded() -> None:
    assert report_fragment(Target('tag', 'spec/a-b.c_d~e:f')) == 'tag=spec/a-b.c_d~e:f'


def test_a_citation_renders_as_one_markdown_line_around_the_report_url() -> None:
    citation = Citation(
        state='xfailed', title='spec/x', fragment='tag=spec/x', summary='(1 🔵)'
    )
    assert filled(citation_templates(URL)['citation'], citation.template_row()) == (
        f'🔵 [spec/x]({URL}#tag=spec/x) (1 🔵)'
    )


def under_prefix(key: str, prefix: str) -> bool:
    """The Tags sidebar's filter rule: a `#tag=` link opens the scenarios
    carrying the tag or one below it, so its citation counts them."""
    return key == prefix or key.startswith(prefix + '/')


def test_a_tag_citation_counts_what_under_prefix_matches() -> None:
    tag_sets = [('a/b', 'a/c'), ('a',), ('ab/c',), ('a//b', '/x'), ('a/',), ()]
    scenarios = [
        scenario_(f't.py::test_{number}', tags=tags)
        for number, tags in enumerate(tag_sets)
    ]
    index = _index(*scenarios)
    for tag in index.tags:
        matched = [
            scenario
            for scenario in scenarios
            if any(under_prefix(key, tag) for key in scenario.tags)
        ]
        assert index.citation(Target('tag', tag)).summary == f'({len(matched)} ✅)'


def test_a_target_counts_the_scenario_or_those_its_summary_counts() -> None:
    pay = scenario_('t.py::test_pay', tags=('checkout/card',), stories=('s',))
    refund = scenario_('t.py::test_refund', tags=('checkout/refund',))
    index = _index(pay, refund, stories=(story_('s'),))
    assert index.counted(Target('scenario', 't.py::test_pay')) == [pay]
    assert index.counted(Target('tag', 'checkout')) == [pay, refund]
    assert index.counted(Target('story', 's')) == [pay]


def test_a_scenario_row_fills_each_template_to_its_copied_form() -> None:
    scenario = scenario_('t.py::test_pay', 'Pay `by` card & cash')
    citation = _index(scenario).citation(Target('scenario', 't.py::test_pay'))
    templates = citation_templates(URL)
    row = citation.template_row()
    assert filled(templates['citation'], row) == (
        f'✅ [Pay `by` card \\& cash]({URL}#scenario=t.py::test_pay)'
    )
    assert filled(templates['narrated'], row) == (
        '<details markdown="1">\n'
        f'<summary>✅ <a href="{URL}#scenario=t.py::test_pay">'
        'Pay <code>by</code> card &amp; cash</a></summary>'
        '\n\n</details>'
    )


def test_a_scenario_row_leaves_out_an_html_title_its_markdown_title_matches() -> None:
    citation = _index(scenario_('t.py::test_pay', 'Pay by card')).citation(
        Target('scenario', 't.py::test_pay')
    )
    assert citation.template_row() == ['✅', 'scenario=t.py::test_pay', 'Pay by card']


@pytest.mark.parametrize('form', ['narrated', 'defining'])
def test_a_details_template_escapes_the_url_as_an_attribute(form: str) -> None:
    citation = _index(scenario_('t.py::test_pay', 'Pay')).citation(
        Target('scenario', 't.py::test_pay')
    )
    url = 'https://example.org/r.html?a=1&b="2"'
    copied = filled(citation_templates(url)[form], citation.template_row())
    assert (
        'href="https://example.org/r.html?a=1&amp;b=&quot;2&quot;#scenario=' in copied
    )


def test_a_scenarios_body_is_its_markdown_narration_framed_by_blank_lines() -> None:
    grouped = scenario_('t.py::test_pour[water]', grouped=True)
    index = _index(grouped)
    assert citation_body_md(index.cited(Target('scenario', 't.py::test_pour'))) == (
        f'\n{narration_body_md(grouped)}\n'
    )


def test_a_scenario_without_steps_has_an_empty_body() -> None:
    index = _index(scenario_('t.py::test_pay'))
    assert citation_body_md(index.cited(Target('scenario', 't.py::test_pay'))) == ''


# --- Term citations ---


GUEST = term_('Guest', 'Someone staying at the hotel.')


def test_a_term_citation_rolls_up_the_scenarios_that_reference_it() -> None:
    index = CitationIndex.of(
        report_(
            using_('guest', scenario_('t.py::test_a')),
            using_('guest', scenario_('t.py::test_b', status='xfailed')),
            scenario_('t.py::test_c', status='failed'),
            terms=(GUEST,),
        )
    )
    target = Target('term', 'guest')
    citation = index.citation(target)
    assert (citation.glyph, citation.title_text, citation.summary) == (
        '🔵',
        'Guest',
        '(1 ✅ · 1 🔵)',
    )
    assert citation.fragment == 'view=glossary&term=guest'
    assert [scenario.id for scenario in index.counted(target)] == [
        't.py::test_a',
        't.py::test_b',
    ]


def test_a_term_ref_in_a_scenario_title_counts_as_a_reference() -> None:
    titled = scenario_('t.py::test_a')
    titled.narration = narration_of(
        [NarrationTermRef(term_id=TermId('guest'), display='guest')]
    )
    index = CitationIndex.of(report_(titled, terms=(GUEST,)))
    assert index.citation(Target('term', 'guest')).summary == '(1 ✅)'


def test_a_grouped_scenario_counts_once_under_a_term() -> None:
    grouped = scenario_(
        't.py::test_a[1]', grouped=True, other_cases=('t.py::test_a[2]',)
    )
    index = CitationIndex.of(report_(using_('guest', grouped), terms=(GUEST,)))
    assert index.citation(Target('term', 'guest')).summary == '(1 ✅)'


def test_a_term_no_scenario_references_reads_as_having_no_scenarios() -> None:
    index = CitationIndex.of(report_(scenario_('t.py::test_a'), terms=(GUEST,)))
    citation = index.citation(Target('term', 'guest'))
    assert (citation.glyph, citation.summary) == ('🟠', '(no scenarios)')


def test_a_reference_from_a_story_sentence_alone_does_not_count() -> None:
    told = Story(
        id=StoryId('stay'),
        title='Stay',
        sentences=(
            Sentence(
                id=SentenceId(1),
                clauses=(
                    Clause(
                        parts=(ClauseTermRef(term_id=TermId('guest'), display='guest'),)
                    ),
                ),
            ),
        ),
    )
    index = CitationIndex.of(report_(stories=(told,), terms=(GUEST,)))
    assert index.citation(Target('term', 'guest')).summary == '(no scenarios)'


def test_a_report_without_a_glossary_holds_no_terms() -> None:
    assert CitationIndex.of(report_(scenario_('t.py::test_a'))).terms == {}


@pytest.mark.parametrize(
    ('canonical', 'markdown', 'html_text'),
    [
        ('Guest', 'Guest', 'Guest'),
        ('A<B & *c*', 'A\\<B \\& \\*c\\*', 'A&lt;B &amp; *c*'),
    ],
)
def test_a_term_title_is_literal_in_both_forms(
    canonical: str, markdown: str, html_text: str
) -> None:
    term = GlossaryTerm(id=TermId('t'), kind=None, canonical=canonical)
    citation = CitationIndex.of(report_(terms=(term,))).citation(Target('term', 't'))
    assert filled(citation_templates(URL)['citation'], citation.template_row()) == (
        f'🟠 [{markdown}]({URL}#view=glossary&term=t) (no scenarios)'
    )
    assert citation.html_link_text == html_text


def test_a_defining_citation_is_the_block_with_its_summary_and_an_empty_body() -> None:
    index = CitationIndex.of(
        report_(using_('guest', scenario_('t.py::test_a')), terms=(GUEST,))
    )
    row = index.citation(Target('term', 'guest')).template_row()
    assert filled(citation_templates(URL)['defining'], row) == (
        '<details markdown="1">\n'
        f'<summary>✅ <a href="{URL}#view=glossary&term=guest">Guest</a> (1 ✅)'
        '</summary>\n'
        '\n'
        '</details>'
    )


def test_a_terms_body_is_its_definition_framed_by_blank_lines() -> None:
    index = CitationIndex.of(report_(terms=(GUEST, term_('Host'))))
    assert (
        citation_body_md(index.cited(Target('term', 'guest')))
        == '\nSomeone staying at the hotel.\n'
    )
    assert citation_body_md(index.cited(Target('term', 'host'))) == ''
