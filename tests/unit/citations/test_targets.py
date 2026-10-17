"""A report link read back: the target its fragment names, and what the report
holds under that name."""

from urllib.parse import parse_qs

import pytest

from pytest_given.citations.targets import TargetResolver, parse_fragment
from pytest_given.model import Scenario, Story
from pytest_given.report import Target, report_fragment
from tests.unit.citation_reports import report_, scenario_, story_


def _resolver(*scenarios: Scenario, stories: tuple[Story, ...] = ()) -> TargetResolver:
    return TargetResolver(report_(*scenarios, stories=stories))


@pytest.mark.parametrize(
    'node_id',
    [
        'tests/test_x.py::test_y[a b+c&d#e%f=g]',
        'tests/test_ü.py::test_ß[ünïcode]',
        'tests/test_x.py::test_y[1.5-x_y~z]',
    ],
)
def test_a_fragment_round_trips_through_parse_fragment(node_id: str) -> None:
    fragment = report_fragment(Target('scenario', node_id))
    assert parse_qs(fragment)['scenario'] == [node_id]
    assert parse_fragment(fragment) == Target('scenario', node_id)


@pytest.mark.parametrize(
    ('fragment', 'target'),
    [
        ('tag=spec', Target('tag', 'spec')),
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


def test_the_current_keys_resolve_as_they_are() -> None:
    story = story_('cancel', 'Cancel')
    resolver = _resolver(scenario_('t.py::test_a', tags=('spec/x',)), stories=(story,))
    for target in (
        Target('scenario', 't.py::test_a'),
        Target('tag', 'spec'),
        Target('tag', 'spec/x'),
        Target('story', 'cancel'),
    ):
        assert resolver.resolve(target) == target
    assert resolver.resolve(Target('tag', 'spe')) is None
    assert resolver.resolve(Target('story', 'gone')) is None


def test_a_slug_or_a_case_suffix_resolves_to_the_cited_node_id() -> None:
    resolver = _resolver(
        scenario_('pkg/test_pour.py::test_pour[water]', grouped=True),
        scenario_('pkg/test_shop.py::test_buy'),
    )
    assert resolver.resolve(Target('scenario', 'shop/buy')) == Target(
        'scenario', 'pkg/test_shop.py::test_buy'
    )
    assert resolver.resolve(
        Target('scenario', 'pkg/test_pour.py::test_pour[fire]')
    ) == Target('scenario', 'pkg/test_pour.py::test_pour')
    assert resolver.resolve(Target('scenario', 'pkg/test_shop.py::test_gone')) is None


def test_scenarios_titled_matches_exactly_after_folding() -> None:
    resolver = _resolver(
        scenario_('t.py::test_a', 'Pay  by\ncard'),
        scenario_('t.py::test_b', 'Pay by card'),
        scenario_('t.py::test_c', 'Pay by cards'),
    )
    assert sorted(resolver.scenarios_titled('Pay by card', 'markdown')) == [
        't.py::test_a',
        't.py::test_b',
    ]


def test_suggestions_rank_by_node_id_and_by_title() -> None:
    resolver = _resolver(
        scenario_('t.py::test_pay_by_card', 'Pay by card'),
        scenario_('t.py::test_refund', 'Refund a payment'),
    )
    suggestions = resolver.suggestions(
        Target('scenario', 't.py::test_pay_card'), 'Pay with a card'
    )
    assert suggestions[0].startswith('closest by node ID: t.py::test_pay_by_card')
    assert any(
        line.startswith('closest by scenario title:') and 'test_pay_by_card' in line
        for line in suggestions
    )


def test_an_html_link_text_matches_the_title_as_html_shows_it() -> None:
    resolver = _resolver(scenario_('t.py::test_pay', 'Pay `by` card'))
    assert resolver.scenarios_titled('Pay by card', 'html') == ['t.py::test_pay']
    assert resolver.scenarios_titled('Pay by card', 'markdown') == []
    suggestions = resolver.suggestions(
        Target('scenario', 't.py::test_gone'), 'Pay by card', 'html'
    )
    assert 'closest by scenario title: t.py::test_pay ("Pay by card")' in suggestions


def test_suggestions_for_a_tag_and_a_story() -> None:
    story = story_('cancel-a-booking', 'Cancel a Booking')
    resolver = _resolver(
        scenario_('t.py::test_a', tags=('checkout',)), stories=(story,)
    )
    assert resolver.suggestions(Target('tag', 'checkouts'), 'checkouts') == [
        'closest tags: checkout'
    ]
    assert resolver.suggestions(
        Target('story', 'cancel-booking'), 'Cancel a booking'
    ) == [
        'closest by story id: cancel-a-booking',
        'closest by story title: cancel-a-booking ("Cancel a Booking")',
    ]
    assert resolver.suggestions(Target('tag', 'zzz'), 'zzz') == []
