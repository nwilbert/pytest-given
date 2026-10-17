"""What a citation of each kind says, computed from a report."""

from urllib.parse import parse_qs

import pytest

from pytest_given.model import (
    NarrationLiteral,
    NarrationPlaceholder,
    NarrationTermRef,
    NarrationValue,
    Scenario,
    Status,
    Story,
    TermId,
    narration_of,
    param_id,
)
from pytest_given.report.citation_index import (
    Citation,
    CitationIndex,
    Target,
    report_fragment,
)
from tests.unit.citation_reports import URL, report_, scenario_, story_


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
    before, _ = citation.markdown_halves()
    assert before == '✅ [Split *it* \\[a\\*b\\*c\\]]('


def test_a_tag_and_a_story_title_are_written_literally() -> None:
    story = story_('s', 'Book a *suite*')
    index = _index(
        scenario_('t.py::test_a', tags=('a*b*',), stories=('s',)), stories=(story,)
    )
    tag_before, _ = index.citation(Target('tag', 'a*b*')).markdown_halves()
    story_before, _ = index.citation(Target('story', 's')).markdown_halves()
    assert tag_before == '✅ [a\\*b\\*]('
    assert story_before == '✅ [Book a \\*suite\\*]('


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
    before, after = citation.markdown_halves()
    assert before + URL + after == f'🔵 [spec/x]({URL}#tag=spec/x) (1 🔵)'


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
