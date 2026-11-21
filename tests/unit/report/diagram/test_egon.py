"""The egon.io file of a laid-out story: the JSON egon.io reads."""

import json

import pytest

from pytest_given.model import Glossary, Story, StoryId
from pytest_given.report.diagram import (
    DiagramLayout,
    build_graph,
    layout_graph,
    render_egn,
)
from pytest_given.report.diagram.egon import DOCUMENT_SVG, PERSON_SVG

type EgnElement = dict[str, object]


@pytest.fixture
def trip_layout(trip_story: Story, trip_glossary: Glossary) -> DiagramLayout:
    return layout_graph(build_graph(trip_story, trip_glossary))


def _elements(layout: DiagramLayout) -> list[EgnElement]:
    elements: list[EgnElement] = json.loads(render_egn(layout))['dst']
    return elements


def _of_type(elements: list[EgnElement], *types: str) -> list[EgnElement]:
    return [element for element in elements if element.get('type') in types]


def test_the_file_carries_egons_icons_and_ends_in_its_version(
    trip_layout: DiagramLayout,
) -> None:
    document = json.loads(render_egn(trip_layout))
    assert document['domain'] == {
        'name': 'default',
        'actors': {'Person': PERSON_SVG},
        'workObjects': {'Document': DOCUMENT_SVG},
    }
    assert document['dst'][-2:] == [{'info': ''}, {'version': '2.0.1'}]


def test_each_node_is_a_shape_whose_icon_box_centres_on_it(
    trip_layout: DiagramLayout,
) -> None:
    shapes = _of_type(
        _elements(trip_layout),
        'domainStory:actorPerson',
        'domainStory:workObjectDocument',
    )
    assert len(shapes) == len(trip_layout.nodes)
    for shape, placed in zip(shapes, trip_layout.nodes, strict=True):
        is_actor = placed.node.glyph == 'actor'
        assert shape == {
            'type': (
                'domainStory:actorPerson'
                if is_actor
                else 'domainStory:workObjectDocument'
            ),
            'name': placed.node.label,
            'id': shape['id'],
            'pickedColor': 'black',
            'x': round(placed.x) - 38,
            'y': round(placed.y) - 38,
            '$type': 'Element',
            'di': {},
            '$descriptor': {},
        }


def test_each_edge_is_an_activity_between_the_shapes_of_its_nodes(
    trip_layout: DiagramLayout,
) -> None:
    elements = _elements(trip_layout)
    shapes = _of_type(
        elements, 'domainStory:actorPerson', 'domainStory:workObjectDocument'
    )
    # A work object is a node per sentence, so labels repeat but node ids don't.
    shape_ids = {
        placed.node.id: shape['id']
        for placed, shape in zip(trip_layout.nodes, shapes, strict=True)
    }
    activities = _of_type(elements, 'domainStory:activity')
    assert len(activities) == len(trip_layout.edges)
    for activity, placed in zip(activities, trip_layout.edges, strict=True):
        assert activity['name'] == placed.edge.label
        assert activity['number'] == placed.edge.number
        assert activity['source'] == shape_ids[placed.edge.source]
        assert activity['target'] == shape_ids[placed.edge.target]
        start = {'x': round(placed.x1), 'y': round(placed.y1)}
        assert activity['waypoints'] == [
            {'original': start, **start},
            {
                'original': {'x': round(placed.x2), 'y': round(placed.y2)},
                'x': round(placed.x2),
                'y': round(placed.y2),
            },
        ]


def test_only_a_numbered_activity_says_whether_its_number_repeats(
    trip_layout: DiagramLayout,
) -> None:
    activities = _of_type(_elements(trip_layout), 'domainStory:activity')
    by_number = {
        number: [activity for activity in activities if activity['number'] == number]
        for number in {activity['number'] for activity in activities}
    }
    # Sentence 1 has two clauses, so two arrows carry its number.
    assert [act['multipleNumberAllowed'] for act in by_number[1]] == [True, True]
    assert [act['multipleNumberAllowed'] for act in by_number[2]] == [False]
    assert all('multipleNumberAllowed' not in act for act in by_number[None])


def test_an_empty_story_is_a_file_with_no_shapes() -> None:
    layout = layout_graph(
        build_graph(Story(id=StoryId('empty'), title='Empty', sentences=()), None)
    )
    assert _elements(layout) == [{'info': ''}, {'version': '2.0.1'}]
