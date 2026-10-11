"""What a citation of each kind says, computed from a report."""

from pathlib import Path
from urllib.parse import parse_qs

import pytest

from pytest_given.model import (
    Metadata,
    Narration,
    NarrationLiteral,
    NarrationPlaceholder,
    NarrationTermRef,
    NodeId,
    ParameterCase,
    ParameterColumn,
    ParameterTable,
    ReportData,
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
from pytest_given.report import citation_index
from pytest_given.report.citation_index import (
    Citation,
    CitationIndex,
    Target,
    parse_fragment,
    report_fragment,
)

URL = 'https://example.org/report.html'


def _scenario(
    node_id: str,
    title: str = 'A title',
    *,
    status: Status = 'passed',
    tags: tuple[str, ...] = (),
    grouped: bool = False,
    stories: tuple[str, ...] = (),
) -> Scenario:
    table = (
        ParameterTable(
            columns=[ParameterColumn(id=param_id('x'), name='x', kind='param')],
            cases=[ParameterCase(values=[1], status=status)],
        )
        if grouped
        else None
    )
    return Scenario(
        id=NodeId(node_id),
        narration=Narration(text=title),
        module='m',
        status=status,
        tags=list(tags),
        parameters=table,
        story_ids=tuple(StoryId(story) for story in stories),
    )


def _index(*scenarios: Scenario, stories: tuple[Story, ...] = ()) -> CitationIndex:
    return CitationIndex(
        ReportData(
            metadata=Metadata(
                project='p', timestamp='t', pytest_version='9', plugin_version='0'
            ),
            scenarios=list(scenarios),
            stories=list(stories),
        )
    )


@pytest.mark.parametrize(
    ('status', 'glyph'),
    [('passed', '✅'), ('failed', '❌'), ('skipped', '🟠'), ('xfailed', '🔵')],
)
def test_a_scenario_citation_carries_its_status_glyph_and_no_summary(
    status: Status, glyph: str
) -> None:
    index = _index(_scenario('t.py::test_a', 'Pay', status=status))
    citation = index.citation(Target('scenario', 't.py::test_a'))
    assert (citation.glyph, citation.title, citation.summary) == (glyph, 'Pay', None)
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
            _scenario(f't.py::test_{number}', status=status, tags=('spec/x',))
            for number, status in enumerate(statuses)
        )
    )
    citation = index.citation(Target('tag', 'spec/x'))
    assert (citation.glyph, citation.title, citation.summary) == (
        glyph,
        'spec/x',
        summary,
    )


def test_a_tag_covers_the_tags_below_it_and_no_sibling_prefix() -> None:
    index = _index(
        _scenario('t.py::test_a', tags=('spec/citations',)),
        _scenario('t.py::test_b', tags=('specimen',)),
    )
    assert index.citation(Target('tag', 'spec')).summary == '(1 ✅)'
    assert index.resolve(Target('tag', 'spe')) is None
    assert index.tags == ['spec', 'spec/citations', 'specimen']


def test_a_story_sums_up_its_scenarios_and_reads_no_scenarios_when_empty() -> None:
    sentence = Sentence(id=SentenceId(1), clauses=())
    told = Story(id=StoryId('cancel'), title='Cancel a Booking', sentences=(sentence,))
    empty = Story(id=StoryId('later'), title='Later', sentences=(sentence,))
    index = _index(
        _scenario('t.py::test_a', stories=('cancel',)),
        _scenario('t.py::test_b', status='xfailed', stories=('cancel',)),
        stories=(told, empty),
    )
    citation = index.citation(Target('story', 'cancel'))
    assert (citation.glyph, citation.title, citation.summary) == (
        '🔵',
        'Cancel a Booking',
        '(1 ✅ · 1 🔵)',
    )
    assert citation.fragment == 'view=stories&story=cancel'
    later = index.citation(Target('story', 'later'))
    assert (later.glyph, later.summary) == ('🟠', '(no scenarios)')
    assert index.story_ids == ['cancel', 'later']


def test_a_grouped_scenario_is_cited_by_its_base_node_id_and_templated_title() -> None:
    grouped = _scenario('t.py::test_pour[water]', grouped=True)
    grouped.narration = narration_of(
        [
            NarrationLiteral(value='Pour '),
            NarrationPlaceholder(name='liquid', column_id=param_id('liquid')),
        ]
    )
    per_case = _scenario('t.py::test_case[a]', 'Case a')
    index = _index(grouped, per_case)
    assert set(index.scenarios) == {'t.py::test_pour', 't.py::test_case[a]'}
    assert (
        index.citation(Target('scenario', 't.py::test_pour')).title == 'Pour {liquid}'
    )


def test_a_term_ref_title_reads_as_its_display_text() -> None:
    scenario = _scenario('t.py::test_a')
    scenario.narration = narration_of(
        [
            NarrationLiteral(value='A '),
            NarrationTermRef(term_id=TermId('guest'), display='guest'),
            NarrationLiteral(value=' books'),
        ]
    )
    citation = _index(scenario).citation(Target('scenario', 't.py::test_a'))
    assert citation.title == 'A guest books'


def test_a_slug_or_a_case_suffix_resolves_to_the_cited_node_id() -> None:
    index = _index(
        _scenario('pkg/test_pour.py::test_pour[water]', grouped=True),
        _scenario('pkg/test_shop.py::test_buy'),
    )
    assert index.resolve(Target('scenario', 'shop/buy')) == Target(
        'scenario', 'pkg/test_shop.py::test_buy'
    )
    assert index.resolve(
        Target('scenario', 'pkg/test_pour.py::test_pour[fire]')
    ) == Target('scenario', 'pkg/test_pour.py::test_pour')
    assert index.resolve(Target('scenario', 'pkg/test_shop.py::test_gone')) is None


def test_two_groups_of_one_function_are_each_cited_by_their_own_node_id() -> None:
    index = _index(
        _scenario('t.py::test_pour[a]', 'Pour a', grouped=True),
        _scenario('t.py::test_pour[b]', 'Pour b', grouped=True),
    )
    assert set(index.scenarios) == {'t.py::test_pour[a]', 't.py::test_pour[b]'}
    assert index.resolve(Target('scenario', 't.py::test_pour[c]')) is None
    assert index.resolve(Target('scenario', 't.py::test_pour')) is None


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
    assert parse_fragment(fragment) == Target('scenario', node_id)


def test_the_readable_characters_stay_unencoded() -> None:
    assert report_fragment(Target('tag', 'spec/a-b.c_d~e:f')) == 'tag=spec/a-b.c_d~e:f'


@pytest.mark.parametrize(
    ('fragment', 'target'),
    [
        ('story=cancel&view=stories', Target('story', 'cancel')),
        ('view=stories&story=cancel', Target('story', 'cancel')),
        ('tag=a&tag=b', None),
        ('q=foo', None),
        ('view=glossary&story=cancel', None),
        ('scenario=a&q=b', None),
        ('', None),
    ],
)
def test_only_the_three_shapes_are_report_link_fragments(
    fragment: str, target: Target | None
) -> None:
    assert parse_fragment(fragment) == target


def test_a_citation_renders_as_one_markdown_line() -> None:
    citation = Citation(
        state='xfailed', title='spec/x', fragment='tag=spec/x', summary='(1 🔵)'
    )
    assert citation.markdown(URL) == f'🔵 [spec/x]({URL}#tag=spec/x) (1 🔵)'


def under_prefix(key: str, prefix: str) -> bool:
    """A port of `app.js`'s `underPrefix`: a `#tag=` link opens the scenarios
    carrying the tag or one below it, so its citation counts them."""
    return key == prefix or key.startswith(prefix + '/')


def test_a_tag_citation_counts_what_under_prefix_matches() -> None:
    tag_sets = [('a/b', 'a/c'), ('a',), ('ab/c',), ('a//b', '/x'), ('a/',), ()]
    scenarios = [
        _scenario(f't.py::test_{number}', tags=tags)
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


def test_under_prefix_ports_the_report_script_rule() -> None:
    """A `#tag=` link opens what `app.js`'s `underPrefix` matches, and a tag
    citation counts what `under_prefix` matches; this holds the original to
    the port's one-line rule."""
    app_js = Path(citation_index.__file__).parent / 'templates' / 'app.js'
    assert 'return key === filter || key.startsWith(filter + sep);' in app_js.read_text(
        encoding='utf-8'
    )


def test_suggestions_rank_by_node_id_and_by_title() -> None:
    index = _index(
        _scenario('t.py::test_pay_by_card', 'Pay by card'),
        _scenario('t.py::test_refund', 'Refund a payment'),
    )
    suggestions = index.suggestions(
        Target('scenario', 't.py::test_pay_card'), 'Pay with a card'
    )
    assert suggestions[0].startswith('closest by node id: t.py::test_pay_by_card')
    assert any(
        line.startswith('closest by scenario title:') and 'test_pay_by_card' in line
        for line in suggestions
    )


def test_suggestions_for_a_tag_and_a_story() -> None:
    sentence = Sentence(id=SentenceId(1), clauses=())
    story = Story(
        id=StoryId('cancel-a-booking'), title='Cancel a Booking', sentences=(sentence,)
    )
    index = _index(_scenario('t.py::test_a', tags=('checkout',)), stories=(story,))
    assert index.suggestions(Target('tag', 'checkouts'), 'checkouts') == [
        'closest tags: checkout'
    ]
    assert index.suggestions(Target('story', 'cancel-booking'), 'Cancel a booking') == [
        'closest by story id: cancel-a-booking',
        'closest by story title: cancel-a-booking ("Cancel a Booking")',
    ]
    assert index.suggestions(Target('tag', 'zzz'), 'zzz') == []


def test_scenarios_titled_matches_exactly_after_folding() -> None:
    index = _index(
        _scenario('t.py::test_a', 'Pay  by\ncard'),
        _scenario('t.py::test_b', 'Pay by card'),
        _scenario('t.py::test_c', 'Pay by cards'),
    )
    assert sorted(index.scenarios_titled('Pay by card')) == [
        't.py::test_a',
        't.py::test_b',
    ]


def test_a_tag_fragment_and_the_current_keys_resolve_as_they_are() -> None:
    sentence = Sentence(id=SentenceId(1), clauses=())
    story = Story(id=StoryId('cancel'), title='Cancel', sentences=(sentence,))
    index = _index(_scenario('t.py::test_a', tags=('spec',)), stories=(story,))
    assert parse_fragment('tag=spec') == Target('tag', 'spec')
    for target in (
        Target('scenario', 't.py::test_a'),
        Target('tag', 'spec'),
        Target('story', 'cancel'),
    ):
        assert index.resolve(target) == target
    assert index.resolve(Target('story', 'gone')) is None
